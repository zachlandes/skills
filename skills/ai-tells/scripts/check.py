#!/usr/bin/env python3
"""Check a page or text for validated AI tells with Jev (jev-1.14.0).

usage: check.py INPUT|- [--format html|markdown|plain] [--leads] [--tells a,b]
                [--cap-usd 0.25] [--provider typesafe|vercel] [--env-file F] [--key-file F]
                [--tells-file tells.json] [--json OUT.json] [--dry-run]

Sends one request per sentence, asking only the kept tells (and, with --leads, the leads).
Leads are not validated tells: they are listed apart and never counted as tells.
The key is read from TYPESAFE_API_KEY, a named .env file or a private key file and goes only
into the request header.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev
import textsplit

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TELLS = os.path.join(HERE, "..", "tells.json")


def load_registry(path=None):
    return json.load(open(path or DEFAULT_TELLS))


def select_tells(reg, names=None, leads=False):
    """Kept tells, plus leads when asked. Rejected tells are never asked. Returns {name: tell}."""
    out = {}
    for name, t in reg["tells"].items():
        if names and name not in names:
            continue
        if t["status"] == "kept" or (leads and t["status"] == "lead"):
            out[name] = t
    if names:
        missing = [n for n in names if n not in out]
        if missing:
            raise SystemExit(f"not available to ask (unknown, rejected, or a lead without --leads): {', '.join(missing)}")
    return out


def band(p, t):
    if p >= t["t_hi"]:
        return "yes"
    if p >= t["t_lo"]:
        return "unsure"
    return "no"


def rate_row(count, n_sent, n_words):
    return {"count": count, "per100": round(100 * count / n_sent, 1) if n_sent else 0.0,
            "per1k": round(1000 * count / n_words, 2) if n_words else 0.0}


def build_report(sentences, answers, chosen):
    """sentences: list of {id, text}. answers: {id: {tell: p}}. chosen: {name: tell dict}."""
    sentences = [s for s in sentences if s["id"] in answers]  # rates cover answered sentences only
    n_sent = len(sentences)
    n_words = sum(len(s["text"].split()) for s in sentences)
    tells, leads = {}, {}
    for name, t in chosen.items():
        flagged, unsure = [], []
        for s in sentences:
            p = answers.get(s["id"], {}).get(name)
            if p is None:
                continue
            b = band(p, t)
            if b == "yes":
                flagged.append({"id": s["id"], "p": round(p, 3), "sentence": s["text"]})
            elif b == "unsure":
                unsure.append({"id": s["id"], "p": round(p, 3), "sentence": s["text"]})
        row = {"status": t["status"], "t_hi": t["t_hi"], "t_lo": t["t_lo"], "flagged": flagged, "unsure": unsure,
               "rate": rate_row(len(flagged), n_sent, n_words)}
        bases = t.get("baselines")
        if bases and t["status"] == "kept":
            row["baselines"] = bases
            h = bases[-1]["human"]["per1k"]  # the latest calibration's human text
            row["vs_human"] = round(row["rate"]["per1k"] / h, 2) if h else None
        (tells if t["status"] == "kept" else leads)[name] = row
    return {"model": jev.MODEL, "sentences": n_sent, "words": n_words, "tells": tells, "leads": leads}


def format_text(rep, headings=0, spent=None):
    L = [f"{rep['sentences']} sentences, {rep['words']} words ({headings} headings set apart). Model {rep['model']}."]
    if spent is not None:
        L.append(f"Spend ${spent:.4f}.")
    for title, group in (("TELLS (validated)", rep["tells"]), ("LEADS (not validated; do not count as tells)", rep["leads"])):
        if not group:
            continue
        L.append("")
        L.append(title)
        for name, r in group.items():
            line = (f"  {name}: {r['rate']['count']} flagged, {r['rate']['per100']} per 100 sentences, "
                    f"{r['rate']['per1k']} per 1,000 words (cutoffs yes >= {r['t_hi']}, unsure >= {r['t_lo']})")
            L.append(line)
            for b in r.get("baselines", []):
                L.append(f"    baseline {b['calibration']}: human text {b['human']['per100']} per 100 / {b['human']['per1k']} per 1k; "
                         f"AI text ({b['ai_source']}) {b['ai']['per100']} / {b['ai']['per1k']}")
            if r.get("vs_human") is not None:
                L.append(f"    this text runs at {r['vs_human']}x the latest human rate per 1,000 words")
            for f in r["flagged"]:
                L.append(f"    YES    {f['p']:.2f}  {f['id']}  {f['sentence']}")
            for f in r["unsure"]:
                L.append(f"    unsure {f['p']:.2f}  {f['id']}  {f['sentence']}")
    L.append("")
    L.append("Rates compare per 1,000 words first: calibration sentences average about 24 words, so per-100-sentence rates run high for short-sentence text.")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--format", choices=["html", "markdown", "plain"])
    ap.add_argument("--leads", action="store_true")
    ap.add_argument("--tells")
    ap.add_argument("--cap-usd", type=float, default=0.25)
    ap.add_argument("--provider", default="typesafe", choices=list(jev.PROVIDERS))
    ap.add_argument("--env-file"); ap.add_argument("--key-file")
    ap.add_argument("--tells-file")
    ap.add_argument("--json")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    text = sys.stdin.read() if a.input == "-" else open(a.input, encoding="utf-8").read()
    fmt, units = textsplit.extract(text, a.format, None if a.input == "-" else a.input)
    sentences = [{"id": f"s{n:04d}", "text": u["text"]} for n, u in enumerate((u for u in units if u["kind"] == "sentence"), 1)]
    headings = sum(1 for u in units if u["kind"] == "heading")
    reg = load_registry(a.tells_file)
    chosen = select_tells(reg, a.tells.split(",") if a.tells else None, a.leads)
    if not chosen:
        raise SystemExit("no tells to ask")
    questions = {n: t["question"] for n, t in chosen.items()}
    est = sum(jev.estimate_tokens(jev.build_body({"sentence": s["text"]}, questions, a.provider)) for s in sentences)
    # The estimate is an over-estimate by design (1.5x), so it is a safe upper bound for the cap check
    print(f"{fmt}: {len(sentences)} sentences, {len(chosen)} tells, up to ${jev.usd(est):.4f} (cap ${a.cap_usd:.2f})", file=sys.stderr)
    if a.dry_run:
        return 0
    if jev.usd(est) > a.cap_usd:
        raise SystemExit(f"estimated spend ${jev.usd(est):.4f} exceeds the cap ${a.cap_usd:.2f}; nothing was sent (raise --cap-usd to proceed)")
    try:
        key = jev.read_key(a.provider, a.env_file, a.key_file)
        endpoint = jev.endpoint_for(a.provider)
    except jev.JevError as e:
        raise SystemExit(str(e))
    ledger = jev.Ledger(None, a.cap_usd)
    rows = [{"id": s["id"], "sentence": s["text"]} for s in sentences]
    results = jev.run_rows(rows, questions, key, ledger, endpoint, a.provider, a.workers)
    answers = {r["id"]: r["answers"] for r in results if "answers" in r}
    errors = [r for r in results if "error" in r]
    rep = build_report(sentences, answers, chosen)
    rep["errors"] = len(errors)
    rep["spent_usd"] = round(ledger.spent, 4)
    print(format_text(rep, headings, ledger.spent))
    if errors:
        print(f"\n{len(errors)} sentences got no answer ({errors[0]['error']}); rates cover only answered sentences.", file=sys.stderr)
    if a.json:
        json.dump(rep, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
