#!/usr/bin/env python3
"""Calibrate a tell: does Jev's answer separate AI text from human text, and is it right when it says yes?

A run directory holds sample.jsonl, ans.jsonl, registration.json, label files and decision.json.

  calibrate.py gen-prompts  RUN --corpus DIR [--genres acad,news] [--per-genre 150] [--shards 6]
      HAP-E-2 chunk_1 prompts to continue with a model; writes prompts/ shards
  calibrate.py sample       RUN --corpus DIR (--ai-parquet NAME | --ai-jsonl FILE) [--per-genre 150]
      human chunk_2 and AI sentences, one per text, paired by opening
  calibrate.py run          RUN --tells a,b [--defs tells.json] [--cap-usd 0.5] [--tag T] [--ids FILE]
      one Jev request per sample sentence (resumable)
  calibrate.py rank         RUN                       ratios at p >= 0.5
  calibrate.py register     RUN --tells a,b [--defs F] [--min-ratio 2 --min-precision 0.8]
      freeze definitions, sample and rule BEFORE any label exists
  calibrate.py label-sheet  RUN                       40 sentences per tell, blind sheet, dev/held-out split
  calibrate.py decide       RUN                       bands, held-out precision, ratio, keep/not keep
  calibrate.py replay-ids   RUN                       ids within 0.1 of a cutoff, to run again with --tag replay1
  calibrate.py promote      RUN --into tells.json --id ID --ai-source NAME [--defs F --questions-revision q2]
"""
import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev
import textsplit

SEED = 194
PER_TELL = 40
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TELLS = os.path.join(HERE, "..", "tells.json")


# ---------- statistics ----------
def ratio_ci(a_yes, a_n, h_yes, h_n):
    """AI-to-human ratio of yes rates with a 0.5 correction, 95% interval by the log method."""
    a, h = a_yes + 0.5, h_yes + 0.5
    r = (a / (a_n + 0.5)) / (h / (h_n + 0.5))
    se = math.sqrt(1 / a - 1 / (a_n + 0.5) + 1 / h - 1 / (h_n + 0.5))
    return r, r * math.exp(-1.96 * se), r * math.exp(1.96 * se)


def wilson(k, n):
    if n == 0:
        return (float("nan"), float("nan"))
    p, z = k / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - w, c + w)


# ---------- run files ----------
def jl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def write_jl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_sample(run):
    return {r["id"]: r for r in jl(f"{run}/sample.jsonl")}


def load_answers(run, orig_only=False):
    """Mean probability per id and tell over the original answers and any replays."""
    acc = defaultdict(lambda: defaultdict(list))
    path = f"{run}/ans.jsonl"
    if not os.path.exists(path):
        return {}
    for o in jl(path):
        if "answers" not in o or (orig_only and o.get("tag")):
            continue
        for k, v in o["answers"].items():
            if v is not None:
                acc[o["id"]][k].append(v)
    return {i: {k: sum(v) / len(v) for k, v in d.items()} for i, d in acc.items()}


def pilot_table(run, tells, thr=0.5, orig_only=False):
    rows, ans = load_sample(run), load_answers(run, orig_only)
    out = []
    for t in tells:
        th = thr.get(t, 0.5) if isinstance(thr, dict) else thr
        side = {"human": [], "ai": []}
        for i, r in rows.items():
            if i in ans and t in ans[i]:
                side[r["source"]].append(ans[i][t])
        hy, ay = sum(p >= th for p in side["human"]), sum(p >= th for p in side["ai"])
        hn, an = len(side["human"]), len(side["ai"])
        r, lo, hi = ratio_ci(ay, an, hy, hn)
        mh, ma = sum(side["human"]) / max(hn, 1), sum(side["ai"]) / max(an, 1)
        out.append({"tell": t, "threshold": th, "human_yes": hy, "human_n": hn, "ai_yes": ay, "ai_n": an,
                    "ratio": round(r, 2), "ci_lo": round(lo, 2), "ci_hi": round(hi, 2),
                    "mean_p_ratio": round(ma / mh, 2) if mh else None, "too_rare": hy + ay < 5})
    return out


# ---------- sampling from HAP-E-2 ----------
def eligible(s):
    w = s.split()
    return (6 <= len(w) <= 60 and re.search(r"[.!?][\"'”’)]?$", s) and "\n" not in s
            and sum(ch.isalpha() for ch in s) >= 0.6 * len(s.replace(" ", "")) and s[0].isupper())


def pick_sentence(text, rng):
    ss = [u["text"] for u in textsplit.from_plain(re.sub(r"\s+", " ", text)) if u["kind"] == "sentence"]
    idx = [i for i, s in enumerate(ss) if eligible(s)]
    if not idx:
        return None
    i = rng.choice(idx)
    return ss[i], ss[i - 1] if i else ""


def paired_bases(corpus, genres, per_genre):
    """Document openings that have human chunk_1 and chunk_2, in seeded order per genre."""
    import pandas as pd
    h2 = pd.read_parquet(f"{corpus}/hape2-text_chunk_2.parquet")
    h1 = pd.read_parquet(f"{corpus}/hape2-text_chunk_1.parquet")
    for d in (h1, h2):
        d["base"] = d.doc_id.str.split("@").str[0]
    both = sorted(set(h1.base) & set(h2.base))
    rng = random.Random(SEED)
    out = {}
    for g in genres:
        pool = [b for b in both if b.startswith(g + "_")]
        rng.shuffle(pool)
        out[g] = pool
    return h1.drop_duplicates("base").set_index("base").text, h2.drop_duplicates("base").set_index("base").text, out


def cmd_gen_prompts(a):
    c1, _, pools = paired_bases(a.corpus, a.genres.split(","), a.per_genre)
    os.makedirs(f"{a.run}/prompts", exist_ok=True)
    items = []
    for g, pool in pools.items():
        for b in pool[:a.per_genre]:
            items.append({"base": b, "genre": g, "prompt": c1[b]})
    for k in range(a.shards):
        write_jl(f"{a.run}/prompts/shard_{k}.jsonl", items[k::a.shards])
    print(f"{len(items)} prompts in {a.shards} shards")


def cmd_sample(a):
    import pandas as pd
    genres = a.genres.split(",")
    _, c2, pools = paired_bases(a.corpus, genres, a.per_genre)
    if a.ai_parquet:
        ai = pd.read_parquet(f"{a.corpus}/hape2-text_{a.ai_parquet}.parquet")
        ai["base"] = ai.doc_id.str.split("@").str[0]
        ai_text = ai.drop_duplicates("base").set_index("base").text
    else:
        ai_text = {r["base"]: r["text"] for r in jl(a.ai_jsonl)}
    rng = random.Random(SEED)
    rows = []
    for g in genres:
        taken = 0
        for b in pools[g]:
            if taken == a.per_genre:
                break
            if b not in ai_text or not isinstance(ai_text[b], str) or not ai_text[b].strip():
                continue
            picks = {s: pick_sentence(t, rng) for s, t in (("human", c2[b]), ("ai", ai_text[b]))}
            if not all(picks.values()):
                continue
            taken += 1
            for side, (s, prev) in picks.items():
                rows.append({"id": f"{b}:{side}", "pair": b, "genre": g, "source": side, "sentence": s,
                             "previous_sentence": prev, "words": len(s.split())})
    os.makedirs(a.run, exist_ok=True)
    write_jl(f"{a.run}/sample.jsonl", rows)
    man = {"seed": SEED, "rows": len(rows), "sha256": sha(f"{a.run}/sample.jsonl"), "ai_source": a.ai_parquet or a.ai_jsonl}
    json.dump(man, open(f"{a.run}/manifest.json", "w"), indent=1)
    print(json.dumps(man))


# ---------- sending ----------
def candidate_questions(defs_path, names):
    reg = json.load(open(defs_path or DEFAULT_TELLS))
    missing = [n for n in names if n not in reg["tells"]]
    if missing:
        raise SystemExit(f"no definition for: {', '.join(missing)}")
    return {n: reg["tells"][n]["question"] for n in names}


def cmd_run(a):
    names = a.tells.split(",")
    questions = candidate_questions(a.defs, names)
    rows = list(load_sample(a.run).values())
    if a.ids:
        want = set(open(a.ids).read().split())
        rows = [r for r in rows if r["id"] in want]
    done = set()
    if os.path.exists(f"{a.run}/ans.jsonl"):
        done = {o["id"] for o in jl(f"{a.run}/ans.jsonl") if "answers" in o and o.get("tag", "") == a.tag
                and set(names) <= set(o["answers"])}
    todo = [r for r in rows if r["id"] not in done]
    ledger = jev.Ledger(f"{a.run}/spend_ledger.json", a.cap_usd)
    est = sum(jev.estimate_tokens(jev.build_body({"sentence": r["sentence"]}, questions, a.provider)) for r in todo)
    print(f"{len(todo)} requests to send ({len(done)} done), up to ${jev.usd(est):.4f}; spent so far ${ledger.spent:.4f}; cap ${a.cap_usd:.2f}", file=sys.stderr)
    if a.dry_run:
        return
    if jev.usd(ledger.data["tokens"] + est) > a.cap_usd:
        raise SystemExit("the estimate would pass the cap; nothing was sent (raise --cap-usd to proceed)")
    try:
        key = jev.read_key(a.provider, a.env_file, a.key_file)
        endpoint = jev.endpoint_for(a.provider)
    except jev.JevError as e:
        raise SystemExit(str(e))
    outf = open(f"{a.run}/ans.jsonl", "a", encoding="utf-8")
    errs = []

    def save(res):
        if "answers" in res:
            outf.write(json.dumps({"id": res["id"], "tag": a.tag, "model": res["model"], "answers": res["answers"],
                                   "input_tokens": res["input_tokens"]}) + "\n")
            outf.flush()
        else:
            errs.append(res)
    jev.run_rows(todo, questions, key, ledger, endpoint, a.provider, a.workers, on_result=save)
    print(json.dumps({"sent": len(todo) - len(errs), "errors": len(errs), "spent_usd": round(ledger.spent, 4), "cap_usd": a.cap_usd}))
    if errs:
        print("first error:", errs[0]["error"], file=sys.stderr)
        sys.exit(1)


def cmd_rank(a):
    tells = sorted({k for v in load_answers(a.run).values() for k in v})
    for r in sorted(pilot_table(a.run, tells), key=lambda r: -r["ratio"]):
        print(f"{r['tell']:26s} human {r['human_yes']:3d}/{r['human_n']}  ai {r['ai_yes']:3d}/{r['ai_n']}  ratio {r['ratio']:5.2f} "
              f"[{r['ci_lo']:.2f}, {r['ci_hi']:.2f}]{'  TOO RARE' if r['too_rare'] else ''}")


# ---------- registration, labels, decision ----------
def cmd_register(a):
    if os.path.exists(f"{a.run}/labels.jsonl"):
        raise SystemExit("labels already exist; the rule must be registered before labelling")
    names = a.tells.split(",")
    qs = candidate_questions(a.defs, names)
    reg = {"tells": names, "min_ratio": a.min_ratio, "min_heldout_precision": a.min_precision, "per_tell_labels": PER_TELL,
           "seed": SEED, "questions_sha256": hashlib.sha256(json.dumps(qs, sort_keys=True).encode()).hexdigest(),
           "sample_sha256": sha(f"{a.run}/sample.jsonl"),
           "bands": "t_hi: smallest of 0.5..0.9 with dev precision >= 0.8 (0.9 if none); t_lo: largest of 0.5..0.1 under which >= 90% of dev labels are no (0.1 if none)",
           "rule": "keep when ratio at t_hi >= min_ratio and held-out precision at t_hi >= min_heldout_precision; fewer than 5 yes answers is too rare"}
    json.dump(reg, open(f"{a.run}/registration.json", "w"), indent=1)
    print(f"registered {len(names)} tells; rule frozen before labelling")


def load_registration(run):
    p = f"{run}/registration.json"
    if not os.path.exists(p):
        raise SystemExit("no registration.json: run `register` before labelling")
    reg = json.load(open(p))
    if reg["sample_sha256"] != sha(f"{run}/sample.jsonl"):
        raise SystemExit("sample.jsonl changed after registration")
    return reg


def cmd_label_sheet(a):
    reg = load_registration(a.run)
    rows, ans = load_sample(a.run), load_answers(a.run, orig_only=True)
    rng = random.Random(reg["seed"])
    key, items = {}, []
    for t in reg["tells"]:
        ids = sorted(i for i in rows if i in ans and t in ans[i])
        hi = [i for i in ids if ans[i][t] >= .5]
        mid = [i for i in ids if .1 <= ans[i][t] < .5]
        low = [i for i in ids if ans[i][t] < .1]
        for g in (hi, mid, low):
            rng.shuffle(g)
        take_hi = hi[:PER_TELL // 2]
        rest = PER_TELL - len(take_hi)
        take_mid = mid[:math.ceil(rest / 2)]
        take_low = low[:rest - len(take_mid)]
        if len(take_low) < rest - len(take_mid):
            take_mid = mid[:rest - len(take_low)]
        strata = [(i, "hi") for i in take_hi] + [(i, "mid") for i in take_mid] + [(i, "low") for i in take_low]
        split = {}
        for s in ("hi", "mid", "low"):
            xs = [i for i, st in strata if st == s]
            rng.shuffle(xs)
            for j, i in enumerate(xs):
                split[i] = "dev" if j % 2 == 0 else "heldout"
        key[t] = [{"id": i, "stratum": st, "split": split[i]} for i, st in strata]
        items += [(t, i) for i, _ in strata]
    rng.shuffle(items)
    json.dump(key, open(f"{a.run}/label_key.json", "w"), indent=1)
    # The blind sheet carries the tell and the sentence only: no probability, no source
    write_jl(f"{a.run}/label_sheet.jsonl", [{"item": n, "tell": t, "sentence": rows[i]["sentence"]} for n, (t, i) in enumerate(items)])
    json.dump({str(n): [t, i] for n, (t, i) in enumerate(items)}, open(f"{a.run}/label_items.json", "w"))
    print({t: len(v) for t, v in key.items()}, "items", len(items))


def load_labels(run):
    """labels.jsonl rows are {"item": n, "label": bool} or {"tell", "id", "label"}."""
    items = json.load(open(f"{run}/label_items.json")) if os.path.exists(f"{run}/label_items.json") else {}
    out = {}
    for o in jl(f"{run}/labels.jsonl"):
        t, i = (o["tell"], o["id"]) if "id" in o else items[str(o["item"])]
        out[(t, i)] = bool(o["label"])
    return out


def bands(dev):
    t_hi = 0.9
    for c in (0.5, 0.6, 0.7, 0.8, 0.9):
        ys = [l for p, l in dev if p >= c]
        if ys and sum(ys) / len(ys) >= 0.8:
            t_hi = c
            break
    t_lo = 0.1
    for c in (0.5, 0.4, 0.3, 0.2, 0.1):
        ns = [l for p, l in dev if p < c]
        if ns and sum(1 - l for l in ns) / len(ns) >= 0.9:
            t_lo = min(c, t_hi)
            break
    return t_hi, t_lo


def decide(run, key=None, labels=None, rule=None):
    """Bands come from the original answers; ratios and held-out precision use the mean over any replays."""
    rule = rule or load_registration(run)
    key = key or json.load(open(f"{run}/label_key.json"))
    labels = labels if labels is not None else load_labels(run)
    orig, final = load_answers(run, True), load_answers(run)
    res = {}
    for t, lst in key.items():
        dev = [(orig[x["id"]][t], labels[(t, x["id"])]) for x in lst if x["split"] == "dev"]
        t_hi, t_lo = bands(dev)
        ho = [(final[x["id"]][t], labels[(t, x["id"])]) for x in lst if x["split"] == "heldout"]
        hy = [l for p, l in ho if p >= t_hi]
        dy = [l for p, l in dev if p >= t_hi]
        res[t] = {"t_hi": t_hi, "t_lo": t_lo, "dev_yes": len(dy), "dev_precision": round(sum(dy) / len(dy), 2) if dy else None,
                  "heldout_yes": len(hy), "heldout_precision": round(sum(hy) / len(hy), 2) if hy else None,
                  "heldout_ci": [round(x, 2) for x in wilson(sum(hy), len(hy))] if hy else None,
                  "thin": len(hy) < 5, "labelled": len(lst), "labelled_true": sum(labels[(t, x["id"])] for x in lst)}
    thr = {t: res[t]["t_hi"] for t in res}
    out = []
    for r in pilot_table(run, list(res), thr):
        r.update(res[r["tell"]])
        r["kept"] = (not r["too_rare"]) and r["ratio"] >= rule["min_ratio"] and (r["heldout_precision"] or 0) >= rule["min_heldout_precision"]
        out.append(r)
    return out


def cmd_decide(a):
    out = decide(a.run)
    json.dump(out, open(f"{a.run}/decision.json", "w"), indent=1)
    for r in out:
        print(f"{r['tell']:26s} t_hi {r['t_hi']} t_lo {r['t_lo']} ratio {r['ratio']:.2f} [{r['ci_lo']:.2f},{r['ci_hi']:.2f}] "
              f"held-out precision {r['heldout_precision']} on {r['heldout_yes']}  {'KEPT' if r['kept'] else 'not kept'}{'  too rare' if r['too_rare'] else ''}")


def cmd_replay_ids(a):
    dec = {r["tell"]: r for r in json.load(open(f"{a.run}/decision.json"))}
    orig = load_answers(a.run, True)
    ids = sorted(i for i, an in orig.items() if any(t in an and abs(an[t] - d["t_hi"]) <= 0.1 for t, d in dec.items()))
    open(f"{a.run}/replay_ids.txt", "w").write("\n".join(ids))
    print(len(ids), "ids to run again with --tag replay1 --ids", f"{a.run}/replay_ids.txt")


def baseline_for(run, tell, t_hi, ai_source, cal_id):
    rows, ans = load_sample(run), load_answers(run)
    out = {"calibration": cal_id, "ai_source": ai_source}
    for side in ("human", "ai"):
        ids = [i for i, r in rows.items() if r["source"] == side and i in ans and tell in ans[i]]
        yes = sum(ans[i][tell] >= t_hi for i in ids)
        words = sum(rows[i]["words"] for i in ids)
        out[side] = {"per100": round(100 * yes / len(ids), 1), "per1k": round(1000 * yes / words, 2)}
    return out


def cmd_promote(a):
    reg = json.load(open(a.into))
    dec = json.load(open(f"{a.run}/decision.json"))
    defs = json.load(open(a.defs)) if a.defs else None
    for r in dec:
        t = reg["tells"][r["tell"]]
        # A tell that passed before and fails now is demoted to a lead, not dropped: the earlier pass still stands in its record
        was = t["status"]
        t["status"] = "kept" if r["kept"] else ("lead" if was == "kept" or (was == "lead" and r["ratio"] >= 2.0 and not r["too_rare"]) else "rejected")
        t["t_hi"], t["t_lo"] = r["t_hi"], r["t_lo"]
        t["calibration"] = {"id": a.id, "ai_source": a.ai_source, "ratio": r["ratio"], "ratio_ci": [r["ci_lo"], r["ci_hi"]],
                            "human_yes": r["human_yes"], "ai_yes": r["ai_yes"], "n_per_side": r["human_n"],
                            "heldout_precision": r["heldout_precision"], "heldout_yes": r["heldout_yes"], "kept_by_rule": r["kept"]}
        if defs:
            t["question"] = defs["tells"][r["tell"]]["question"]
        t["baselines"] = [b for b in t.get("baselines", []) if b["calibration"] != a.id] + [baseline_for(a.run, r["tell"], r["t_hi"], a.ai_source, a.id)]
    reg["questions_revision"] = a.questions_revision or reg.get("questions_revision")
    reg["calibrations"].append({"id": a.id, "date": a.date, "note": a.note or ""})
    json.dump(reg, open(a.into, "w"), indent=1, ensure_ascii=False)
    print("updated", a.into)


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *opts):
        p = sub.add_parser(name)
        p.add_argument("run")
        p.set_defaults(fn=fn)
        for o in opts:
            o(p)
    corpus = lambda p: p.add_argument("--corpus", required=True)
    genres = lambda p: (p.add_argument("--genres", default="acad,news"), p.add_argument("--per-genre", type=int, default=150))
    add("gen-prompts", cmd_gen_prompts, corpus, genres, lambda p: p.add_argument("--shards", type=int, default=6))

    def sample_opts(p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--ai-parquet"); g.add_argument("--ai-jsonl")
    add("sample", cmd_sample, corpus, genres, sample_opts)

    def run_opts(p):
        p.add_argument("--tells", required=True); p.add_argument("--defs")
        p.add_argument("--cap-usd", type=float, default=0.5); p.add_argument("--tag", default="")
        p.add_argument("--ids"); p.add_argument("--provider", default="typesafe", choices=list(jev.PROVIDERS))
        p.add_argument("--env-file"); p.add_argument("--key-file"); p.add_argument("--workers", type=int, default=4)
        p.add_argument("--dry-run", action="store_true")
    add("run", cmd_run, run_opts)
    add("rank", cmd_rank)
    add("register", cmd_register, lambda p: (p.add_argument("--tells", required=True), p.add_argument("--defs"),
                                             p.add_argument("--min-ratio", type=float, default=2.0),
                                             p.add_argument("--min-precision", type=float, default=0.8)))
    add("label-sheet", cmd_label_sheet)
    add("decide", cmd_decide)
    add("replay-ids", cmd_replay_ids)
    add("promote", cmd_promote, lambda p: (p.add_argument("--into", default=DEFAULT_TELLS), p.add_argument("--id", required=True),
                                           p.add_argument("--ai-source", required=True), p.add_argument("--date", default=""),
                                           p.add_argument("--note"), p.add_argument("--defs"),
                                           p.add_argument("--questions-revision")))
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
