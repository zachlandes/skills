"""Public snapshot corpus builder; no downloads, API calls or feature computation."""
import hashlib
import json
import random
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict

import profile_features as pf
import textsplit

SOURCES = {
    "peps": {"repo": "python/peps", "revision": "580f8e3c7015a56d9935d595798ffa2eaf387939", "genre": "G2", "licence": "public domain"},
    "kubernetes": {"repo": "kubernetes/website", "revision": "354061c1", "genre": "G3", "licence": "CC BY 4.0"},
    "mdn": {"repo": "mdn/content", "revision": "5d6dd7b9", "genre": "G3", "licence": "CC BY-SA 2.5"},
    "go": {"repo": "golang/website", "revision": "05f06604", "genre": "G3", "licence": "CC BY"}}
SITES = {"ux", "softwareengineering", "academia", "pm"}
TARGETS = {"G1": 240, "G2": 160, "G3": 200}
CUTOFF = "2022-11-30"


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args])


def rst_to_markdown(text):
    """Prose-only PEP rendering, retaining the registered three section names."""
    lines = text.splitlines()
    out, include, code_indent = [], False, None
    for i, line in enumerate(lines):
        if i + 1 < len(lines) and re.fullmatch(r"[=~^-]{3,}\s*", lines[i + 1]):
            title = line.strip()
            include = title.casefold() in {"abstract", "motivation", "rationale"}
            if include:
                out.append("\n## " + title + "\n")
            continue
        if re.fullmatch(r"[=~^-]{3,}\s*", line):
            continue
        if not include:
            continue
        if re.match(r"\s*\.\.\s+(?:code|code-block|literalinclude)::", line):
            code_indent = len(line) - len(line.lstrip()); continue
        if code_indent is not None:
            if not line.strip() or len(line) - len(line.lstrip()) > code_indent:
                continue
            code_indent = None
        line = re.sub(r":\w+:`([^`]+)`", r"\1", line)
        line = re.sub(r"`([^`<>]+)\s*<[^>]+>`_", r"\1", line)
        line = re.sub(r"\[\d+\]_", "", line)
        out.append(line)
    return "\n".join(out)


def clean_markdown(text):
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.S)
    text = re.sub(r"{{[%<].*?[%>]}}|{{.*?}}", "", text, flags=re.S)
    return text


def normalize(text, fmt):
    units = textsplit.extract(text, fmt, positional=True)[1]
    return pf.render(units)


def count_words(rendered):
    return sum(len(u["text"].split()) for u in textsplit.extract(rendered, "html")[1] if u["kind"] == "sentence")


def repo_pages(source, path):
    spec = SOURCES[source]
    full = git(path, "rev-parse", spec["revision"] + "^{commit}").decode().strip()
    if not full.startswith(spec["revision"]) or not re.fullmatch(r"[0-9a-f]{40}", full):
        raise ValueError("snapshot is not the pinned public revision")
    paths = git(path, "ls-tree", "-r", "--name-only", full).decode().splitlines()
    for name in paths:
        low = name.lower()
        if source == "peps":
            use = bool(re.fullmatch(r"(?:peps/)?pep-\d+\.rst", name))
        elif source == "kubernetes":
            use = name.startswith("content/en/docs/concepts/") and name.endswith(".md")
        elif source == "mdn":
            use = (name.startswith("files/en-us/web/") and "/guide" in name) or name.startswith("files/en-us/learn/")
            use = use and name.endswith("index.md")
        else:
            use = name.startswith("_content/blog/") and low.endswith((".md", ".article", ".html"))
        if not use:
            continue
        raw = git(path, "show", f"{full}:{name}")
        text = raw.decode("utf-8")
        if source == "peps":
            text = rst_to_markdown(text)
        elif source == "go" and low.endswith(".article"):
            text = re.sub(r"(?m)^\*\s+", "## ", text)
            text = re.sub(r"(?m)^\.(?:code|play|image|iframe|video|link).*\n?", "", text)
        else:
            text = clean_markdown(text)
        rendered = normalize(text, "html" if low.endswith(".html") else "markdown")
        units = textsplit.extract(rendered, "html")[1]
        words = count_words(rendered)
        if not 250 <= words <= 1200 or (spec["genre"] == "G3" and sum(u["kind"] == "heading" for u in units) < 2):
            continue
        yield {"id": f"{source}:{name}", "origin": source, "genre": spec["genre"], "text": rendered,
               "words": words, "revision": full, "path": name, "licence": spec["licence"],
               "url": f"https://github.com/{spec['repo']}/blob/{full}/{name}",
               "raw_sha256": hashlib.sha256(raw).hexdigest(), "rendered_sha256": pf.digest(rendered)}


def stackexchange_pages(site, path, expected_hash):
    if site not in SITES:
        raise ValueError("only the registered public Stack Exchange sites are allowed")
    if pf.file_hash(path) != expected_hash:
        raise ValueError("public Posts.xml hash mismatch")
    questions, answers = {}, defaultdict(list)
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "row":
            continue
        r = dict(elem.attrib); elem.clear()
        if r.get("CreationDate", "9999") >= CUTOFF or r.get("LastEditDate", "") >= CUTOFF:
            continue
        if r.get("PostTypeId") == "1":
            questions[r["Id"]] = r
        elif r.get("PostTypeId") == "2" and int(r.get("Score", "0")) >= 4:
            body = r.get("Body", "")
            if re.search(r"<(?:code|pre)\b", body, re.I):
                continue
            rendered = normalize(body, "html")
            words = count_words(rendered)
            if 150 <= words <= 700:
                answers[r["ParentId"]].append((int(r["Score"]), int(r["Id"]), r, rendered))
    for qid in sorted(set(questions) & set(answers)):
        _, _, r, rendered = max(answers[qid], key=lambda x: (x[0], -x[1]))
        q = questions[qid]
        yield {"id": f"{site}:{r['Id']}", "origin": site, "genre": "G1", "text": rendered,
               "question": {"title": q["Title"], "body": q["Body"]}, "words": count_words(rendered),
               "licence": "CC BY-SA 4.0", "url": f"https://{site}.stackexchange.com/a/{r['Id']}",
               "author": r.get("OwnerUserId", r.get("OwnerDisplayName", "deleted user")),
               "question_id": qid, "revision": expected_hash,
               "raw_sha256": pf.digest(r), "rendered_sha256": pf.digest(rendered)}


def sample_humans(pages, targets=None, spares=.2):
    targets = TARGETS if targets is None else targets
    rng = random.Random(194)
    by_genre = defaultdict(list)
    for p in sorted(pages, key=lambda p: p["id"]):
        by_genre[p["genre"]].append(p)
    out = []
    for genre, n in targets.items():
        pool = by_genre[genre]
        rng.shuffle(pool)
        need = math_ceil(n * (1 + spares))
        if len(pool) < need:
            raise ValueError(f"insufficient public supply for {genre}: need {need}, found {len(pool)}")
        out += pool[:need]
    return out


def math_ceil(value):
    import math
    return math.ceil(value)


def word_runs(text, length):
    words = re.findall(r"\b[\w’']+\b", " ".join(u["text"] for u in textsplit.extract(text, "html")[1]).casefold())
    return {tuple(words[i:i + length]) for i in range(len(words) - length + 1)}


def check_brief(human, brief):
    text = " ".join([brief["title"], brief["problem"], brief["proposal"], *brief["facts"]])
    if len(brief["facts"]) > 12 or word_runs(human["text"], 5) & word_runs(text, 5):
        raise ValueError("brief has too many facts or copies a five-word source run")


def pair_pages(humans, ai_rows, targets=None):
    """Filter only overlaps, source cues and length, never profile measurements."""
    targets = TARGETS if targets is None else targets
    ai = {}
    for r in ai_rows:
        if r["id"] in ai:
            raise ValueError("duplicate generation id")
        ai[r["id"]] = r
    valid = defaultdict(list)
    for h in humans:
        if h["id"] not in ai:
            continue
        a = ai[h["id"]]
        if a["model"] != "claude-opus-5-5" or a["effort"] != "high" or a["thinking"] != "adaptive":
            raise ValueError("generation must record the registered model, effort and thinking")
        if not a.get("prompt") or not a.get("system"):
            raise ValueError("generation needs its exact prompt and system text")
        if h["genre"] != "G1":
            check_brief(h, a["brief"])
        rendered = normalize(a["text"], a.get("format", "markdown"))
        if re.search(r"@\w+|\bthe OP\b|\bEdit:|\bAs an AI\b|\b(?:meta comment|word count|here is (?:the|your) (?:answer|page))\b", rendered, re.I):
            continue
        if word_runs(h["text"], 8) & word_runs(rendered, 8):
            continue
        n = count_words(rendered)
        if not max(h["words"], n) <= 1.25 * min(h["words"], n) or not 150 <= n <= 1200:
            continue
        pair = h["id"]
        common = {"pair": pair, "genre": h["genre"], "origin": h["origin"]}
        valid[h["genre"]].append([
            {**h, **common, "id": pair + ":human", "source": "human"},
            {**a, **common, "id": pair + ":ai", "source": "ai", "text": rendered,
             "words": n, "rendered_sha256": pf.digest(rendered)}])
    rng = random.Random(194)
    selected = []
    for genre, n in targets.items():
        pairs = sorted(valid[genre], key=lambda p: p[0]["pair"])
        rng.shuffle(pairs)
        if len(pairs) < n:
            raise ValueError(f"insufficient valid pairs for {genre}: need {n}, found {len(pairs)}")
        selected += pairs[:n]
    strata = defaultdict(list)
    for pair in selected:
        strata[(pair[0]["genre"], pair[0]["origin"])].append(pair)
    dev_counts = {key: len(pairs) // 2 for key, pairs in strata.items()}
    for genre, target in targets.items():
        odd = sorted(key for key, pairs in strata.items() if key[0] == genre and len(pairs) % 2)
        rng.shuffle(odd)
        remaining = target // 2 - sum(n for key, n in dev_counts.items() if key[0] == genre)
        for key in odd[:remaining]:
            dev_counts[key] += 1
    rows = []
    for key, pairs in sorted(strata.items()):
        rng.shuffle(pairs)
        for i, pair in enumerate(pairs):
            for r in pair:
                rows.append(dict(r, split="dev" if i < dev_counts[key] else "heldout"))
    return rows


def manifest(rows):
    fields = ("id", "pair", "source", "genre", "origin", "split", "revision", "raw_sha256", "rendered_sha256",
              "url", "licence", "author", "model", "effort", "thinking")
    return {"seed": 194, "sources": SOURCES, "rows": [{k: r[k] for k in fields if k in r} for r in rows],
            "pages_sha256": pf.digest(rows)}
