"""Jev requests: one per sentence, pinned to jev-1.14.0, spend cap enforced in code.

The key goes only into the Authorization header. It is read from the environment (TYPESAFE_API_KEY),
from a named .env file (only that one variable) or from a private key file, and is never printed,
logged or written. Spend is tracked in a ledger file; each request reserves an over-estimate before it
is sent and settles on the input tokens the response reports.
"""
import json
import os
import stat
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MODEL = "jev-1.14.0"
USD_PER_MTOK = 0.042
PROVIDERS = {
    "typesafe": ("https://api.typesafe.ai/v1/systemone", MODEL, "~/.config/decision-gate/typesafe.key"),
    "vercel": ("https://ai-gateway.vercel.sh/typesafe/v1/systemone", "typesafe-ai/" + MODEL,
               "~/.config/decision-gate/vercel-ai-gateway-key"),
}


class JevError(Exception):
    pass


def endpoint_for(provider="typesafe"):
    """Real endpoint, or a loopback stand-in when AITELLS_TEST_ENDPOINT is set. Never any other host."""
    test = os.environ.get("AITELLS_TEST_ENDPOINT", "")
    if test:
        if not test.startswith("http://127.0.0.1:"):
            raise JevError("AITELLS_TEST_ENDPOINT must be http://127.0.0.1:<port>")
        return test
    return PROVIDERS[provider][0]


def read_key(provider="typesafe", env_file=None, key_file=None):
    if env_file and provider == "typesafe":
        try:
            lines = open(os.path.expanduser(env_file)).read().splitlines()
        except OSError:
            raise JevError("cannot read the named env file; nothing was sent")
        for line in lines:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            if line.startswith("TYPESAFE_API_KEY="):
                v = line.split("=", 1)[1].strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                    v = v[1:-1]
                return _one_token(v)
        raise JevError("the named env file has no TYPESAFE_API_KEY; nothing was sent")
    if provider == "typesafe" and os.environ.get("TYPESAFE_API_KEY", "").strip():
        return _one_token(os.environ["TYPESAFE_API_KEY"].strip())
    path = os.path.expanduser(key_file or os.environ.get("JEV_KEY_FILE") or PROVIDERS[provider][2])
    try:
        st = os.stat(path)
    except FileNotFoundError:
        raise JevError("no key found (set TYPESAFE_API_KEY, or use a private key file); nothing was sent")
    if not stat.S_ISREG(st.st_mode) or (st.st_mode & 0o777) != 0o600:
        raise JevError("key file must be a private regular file (chmod 600); nothing was sent")
    return _one_token(open(path).read().strip())


def _one_token(v):
    if not v or any(c.isspace() for c in v):
        raise JevError("the key must be one token; nothing was sent")
    return v


def build_body(state, questions, provider="typesafe"):
    return {"model": PROVIDERS[provider][1], "state": state, "questions": questions}


def estimate_tokens(body):
    return int(len(json.dumps(body)) / 4 * 1.5) + 200


def usd(tokens):
    return tokens / 1e6 * USD_PER_MTOK


class Ledger:
    """Reserve before sending, settle on reported usage. Persisted so a cap spans resumed runs."""

    def __init__(self, path, cap_usd):
        self.path, self.cap, self.reserved, self.lock = path, cap_usd, 0, threading.Lock()
        self.data = json.load(open(path)) if path and os.path.exists(path) else {"tokens": 0, "requests": 0}

    def reserve(self, est):
        with self.lock:
            if usd(self.data["tokens"] + self.reserved + est) > self.cap:
                raise JevError("spend cap reached; request not sent")
            self.reserved += est

    def settle(self, est, actual):
        with self.lock:
            self.reserved -= est
            self.data["tokens"] += actual if actual is not None else est
            self.data["requests"] += 1
            if self.path:
                json.dump(self.data, open(self.path, "w"))

    @property
    def spent(self):
        return usd(self.data["tokens"])


def ask(body, key, ledger, endpoint, provider="typesafe", retries=5):
    """Send one request. Returns {"answers": {name: probability}, "model", "input_tokens"} or {"error": str}."""
    data = json.dumps(body).encode()
    est = estimate_tokens(body)
    pinned = (MODEL, PROVIDERS[provider][1])
    for attempt in range(retries):
        try:
            ledger.reserve(est)
        except JevError as e:
            return {"error": str(e)}
        req = urllib.request.Request(endpoint, data=data, method="POST", headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                j = json.loads(resp.read())
            tokens = j.get("usage", {}).get("input_tokens")
            ledger.settle(est, tokens)
            if j.get("model") not in pinned:
                return {"error": f"unexpected model {j.get('model')}"}
            return {"answers": {k: v.get("noul") for k, v in j["answers"].items()}, "model": j["model"],
                    "input_tokens": tokens}
        except urllib.error.HTTPError as e:
            # A refused request (4xx other than 429) is not billed; a 5xx might be, so settle at the estimate
            ledger.settle(est, 0 if 400 <= e.code < 500 and e.code != 429 else None)
            if e.code in (429, 500, 502, 503, 504, 529):
                time.sleep(min(30, 2 ** attempt + float(e.headers.get("retry-after") or 0)))
                continue
            return {"error": f"HTTP {e.code}"}
        except (urllib.error.URLError, TimeoutError):
            ledger.settle(est, None)
            time.sleep(2 ** attempt)
    return {"error": "gave up after retries"}


def run_rows(rows, questions, key, ledger, endpoint, provider="typesafe", workers=4, state_of=None, on_result=None):
    """rows: dicts with id and sentence. Returns results in order; stops sending once the cap is hit."""
    state_of = state_of or (lambda r: {"sentence": r["sentence"]})
    out = []

    def one(r):
        res = ask(build_body(state_of(r), questions, provider), key, ledger, endpoint, provider)
        res["id"] = r["id"]
        return res

    with ThreadPoolExecutor(workers) as ex:
        for res in ex.map(one, rows):
            out.append(res)
            if on_result:
                on_result(res)
    return out
