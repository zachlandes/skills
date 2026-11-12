"""Profile calibration workflow, exposed through calibrate.py profile.

No corpus data or model is bundled. Register before measurements; evaluate once.
"""
import argparse
import json
import math
import os
import random
import re
from collections import defaultdict
from pathlib import Path

import jev
import profile_corpus as corpus
import profile_features as pf
import textsplit


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def save(path, value, exclusive=True):
    with open(path, "x" if exclusive else "w", encoding="utf-8") as f:
        json.dump(value, f, indent=1, ensure_ascii=False, allow_nan=False)
        f.write("\n")


def save_rows(path, rows):
    with open(path, "x", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def run_dir(path):
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    return p


def code_hashes():
    here = Path(__file__).parent
    return {name: pf.file_hash(here / name) for name in
            ("profile_workflow.py", "profile_features.py", "profile_model.py", "profile_corpus.py", "profile_labels.py", "calibrate.py", "textsplit.py", "jev.py")}


def pages(run):
    rows = read_rows(Path(run) / "pages.jsonl")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate page id")
    pairs = defaultdict(list)
    for r in rows:
        if r["rendered_sha256"] != pf.digest(r["text"]):
            raise ValueError("rendered page hash mismatch")
        pairs[r["pair"]].append(r)
    for pair in pairs.values():
        if len(pair) != 2 or {r["source"] for r in pair} != {"ai", "human"} or len({r["split"] for r in pair}) != 1:
            raise ValueError("split must keep a complete pair together")
        if pair[0]["split"] not in {"dev", "heldout"}:
            raise ValueError("unknown split")
        if len({(r["genre"], r["origin"]) for r in pair}) != 1:
            raise ValueError("pair genre/source mismatch")
    return rows


def registration(run):
    run = Path(run)
    reg = read_json(run / "profile-registration.json")
    if pf.digest({k: v for k, v in reg.items() if k != "sha256"}) != reg["sha256"]:
        raise ValueError("registration hash mismatch")
    if reg["code_sha256"] != code_hashes():
        raise ValueError("measurement code changed after registration; use a fresh run")
    if pf.file_hash(run / "pages.jsonl") != reg["pages_sha256"] or pf.file_hash(run / "manifest.json") != reg["manifest_sha256"]:
        raise ValueError("corpus changed after registration")
    return reg


def cmd_corpus(a):
    run = run_dir(a.run)
    config = read_json(a.sources)
    pool = []
    for source, snapshot in config.items():
        if source in corpus.SOURCES:
            pool.extend(corpus.repo_pages(source, snapshot["path"]))
        elif source in corpus.SITES:
            pool.extend(corpus.stackexchange_pages(source, snapshot["path"], snapshot["sha256"]))
        else:
            raise ValueError("unregistered public source")
    selected = corpus.sample_humans(pool)
    save_rows(run / "humans.jsonl", selected)
    save(run / "human-manifest.json", {"sources": config, "items": [{k: v for k, v in p.items() if k not in {"text", "question"}}
                                                                for p in selected]})


def cmd_pair(a):
    run = Path(a.run)
    rows = corpus.pair_pages(read_rows(run / "humans.jsonl"), read_rows(a.ai))
    save_rows(run / "pages.jsonl", rows)
    save(run / "manifest.json", corpus.manifest(rows))


def cmd_register(a):
    run = Path(a.run)
    if any((run / name).exists() for name in ("profile-answers.jsonl", "features.jsonl", "profile-fit.json", "profile-evaluation.json")):
        raise ValueError("register before any feature or Jev answer exists")
    rows = pages(run)
    manifest = read_json(run / "manifest.json")
    if manifest != corpus.manifest(rows):
        raise ValueError("manifest does not describe corpus")
    for genre, target in corpus.TARGETS.items():
        if sum(r["genre"] == genre and r["source"] == "human" for r in rows) != target:
            raise ValueError("corpus size differs from the registered genre mix")
    qs = pf.questions(read_json(a.defs))
    pf.load_banlist(a.banlist)
    reg = {"version": "profile-p1", "seed": 194, "pages_sha256": pf.file_hash(run / "pages.jsonl"),
           "manifest_sha256": pf.file_hash(run / "manifest.json"), "questions": qs, "questions_sha256": pf.digest(qs),
           "features": pf.definitions(), "features_sha256": pf.digest(pf.definitions()),
           "banlist_sha256": pf.file_hash(a.banlist), "code_sha256": code_hashes(), "model": jev.MODEL,
           "screen_t": 3.2, "minimum_nonzero_dev_pages": 10, "penalties": [.3, 1, 3, 10, 30, 100],
           "folds": 5, "flag_quantile": .9, "pair_bootstraps": 2000, "weight_refits": 1000, "permutations": 50,
           "H1": "95% pair-bootstrap AUC(profile)-AUC(dev best single) lower bound > 0; empty fails",
           "H2": "only after H1; weak ratio strictly (0.5,2); weak AUC lower > .5 and gain lower > 0",
           "ship": "H1 and profile AUC lower bound >= .70; otherwise best single page line",
           "baselines": ["B1 best single", "B2 tricolon", "B3 code only F16:F25", "B4 unweighted Jev sentence load",
                         "B5 Jev F1:F15 and F26", "unconstrained ridge"],
           "explanation": "additive contributions relative to dev human transformed means, medians, fired ids, name precision caveat, recall; no authorship probability",
           "recall": {"seed": 194, "uniform_sentences_per_side": 300, "positional_units": 60,
                      "enriched_max_per_question": 40, "rare_below": 15, "weighting": "inverse inclusion probability"},
           "marking": {"seed": 194, "pages": 40, "repeats": 4, "practice": 3, "ai_share": [.4, .6],
                       "heldout_only": True, "one_side_per_pair": True, "rating": [1, 2, 3, 4, 5],
                       "recognised": "drop", "new_tells": "fresh pairs in later round"}}
    reg["sha256"] = pf.digest(reg)
    save(run / "profile-registration.json", reg)


def jobs_for(rows, qs):
    jobs = []
    for page in rows:
        units = textsplit.extract(page["text"], "html", positional=True)[1]
        for req in pf.requests(units, qs):
            jobs.append(dict(req, id=page["id"] + "::" + req["id"], page=page["id"], unit=req["id"]))
    return jobs


def estimate(jobs, provider):
    return sum(jev.estimate_tokens(jev.build_body(j["state"], j["questions"], provider)) for j in jobs)


def send(jobs, key, ledger, endpoint, provider, workers=4, on_result=None):
    grouped = defaultdict(list)
    for j in jobs:
        grouped[pf.digest(j["questions"])].append(j)
    results = []
    for group in grouped.values():
        results += jev.run_rows(group, group[0]["questions"], key, ledger, endpoint, provider, workers,
                                state_of=lambda r: r["state"], on_result=on_result)
    return results


def validate_answer(answer, job):
    return (answer.get("model") == jev.MODEL and set(answer.get("answers", {})) == set(job["questions"])
            and all(isinstance(p, (float, int)) and math.isfinite(p) and 0 <= p <= 1 for p in answer["answers"].values())
            and answer.get("shape_sha256") == pf.digest({"state": job["state"], "questions": job["questions"]}))


def cmd_run(a):
    run = Path(a.run); reg = registration(run)
    jobs = jobs_for(pages(run), reg["questions"])
    existing = read_rows(run / "profile-answers.jsonl") if (run / "profile-answers.jsonl").exists() else []
    done = {}
    byid = {j["id"]: j for j in jobs}
    for answer in existing:
        if answer["id"] in done or answer["id"] not in byid or not validate_answer(answer, byid[answer["id"]]):
            raise ValueError("duplicate, foreign or changed original profile answer")
        done[answer["id"]] = answer
    todo = [j for j in jobs if j["id"] not in done]
    ledger = jev.Ledger(str(run / "profile-spend.json"), a.cap_usd)
    est = estimate(todo, a.provider)
    print(f"{len(todo)} requests; estimate ${jev.usd(est):.4f}; cap ${a.cap_usd:.2f}")
    if a.dry_run:
        return
    if jev.usd(ledger.data["tokens"] + est) > a.cap_usd:
        raise ValueError("estimate exceeds cap; nothing sent")
    endpoint = jev.endpoint_for(a.provider)
    key = jev.read_key(a.provider, a.env_file, a.key_file)
    with open(run / "profile-answers.jsonl", "a", encoding="utf-8") as f:
        def persist(result):
            if "answers" in result:
                j = byid[result["id"]]
                result["shape_sha256"] = pf.digest({"state": j["state"], "questions": j["questions"]})
                if not validate_answer(result, j):
                    raise ValueError("invalid profile response")
                f.write(json.dumps(result) + "\n"); f.flush()
        results = send(todo, key, ledger, endpoint, a.provider, a.workers, persist)
    if any("error" in r for r in results):
        raise ValueError("profile answers incomplete; resume before measuring")


def original_answers(run, rows, reg):
    answers = read_rows(Path(run) / "profile-answers.jsonl")
    jobs = {j["id"]: j for j in jobs_for(rows, reg["questions"])}
    if len(answers) != len(jobs) or len({a["id"] for a in answers}) != len(jobs):
        raise ValueError("profile requires exactly one original answer per registered request")
    out = defaultdict(dict)
    for a in answers:
        if a["id"] not in jobs or not validate_answer(a, jobs[a["id"]]):
            raise ValueError("profile answer shape/model differs from registration")
        j = jobs[a["id"]]
        out[j["page"]][j["unit"]] = a["answers"]
    return out


def cmd_features(a):
    run = Path(a.run); reg = registration(run)
    rows = pages(run); answers = original_answers(run, rows, reg)
    banlist = pf.load_banlist(a.banlist, reg["banlist_sha256"])
    output = []
    for r in rows:
        units = textsplit.extract(r["text"], "html", positional=True)[1]
        meta = {k: r[k] for k in ("id", "pair", "split", "source", "genre", "origin")}
        output.append({**meta, "features": pf.measure(units, answers[r["id"]], banlist),
                       "soft": pf.measure(units, answers[r["id"]], banlist, soft=True)})
    save_rows(run / "features.jsonl", output)
    save(run / "feature-record.json", {"registration_sha256": reg["sha256"],
         "features_sha256": pf.file_hash(run / "features.jsonl"), "answers_sha256": pf.file_hash(run / "profile-answers.jsonl")})


def measured(run):
    run = Path(run); reg = registration(run)
    record = read_json(run / "feature-record.json")
    if record != {"registration_sha256": reg["sha256"], "features_sha256": pf.file_hash(run / "features.jsonl"),
                  "answers_sha256": pf.file_hash(run / "profile-answers.jsonl")}:
        raise ValueError("feature/answer record changed")
    rows = read_rows(run / "features.jsonl")
    expected = {r["id"]: {k: r[k] for k in ("id", "pair", "split", "source", "genre", "origin")} for r in pages(run)}
    if len(rows) != len(expected) or {r["id"]: {k: r[k] for k in expected[r["id"]]} for r in rows} != expected:
        raise ValueError("feature rows differ from registered page identities/split")
    return reg, rows


def cmd_fit(a):
    import profile_model as pm
    run = Path(a.run); reg, rows = measured(run)
    dev = [r for r in rows if r["split"] == "dev"]
    fitted = pm.fit_all(dev)
    soft = [dict(r, features=r["soft"]) for r in dev]
    fitted.update(soft_model=pm.fit(soft), registration_sha256=reg["sha256"],
                  features_sha256=pf.file_hash(run / "features.jsonl"))
    save(run / "profile-fit.json", fitted)


def cmd_evaluate(a):
    import profile_model as pm
    run = Path(a.run); reg, rows = measured(run)
    fitted = read_json(run / "profile-fit.json")
    if fitted["registration_sha256"] != reg["sha256"] or fitted["features_sha256"] != pf.file_hash(run / "features.jsonl"):
        raise ValueError("fit not bound to registered features")
    # Reserve the held-out set before reading any scores, even if evaluation is interrupted
    seal = {"registration_sha256": reg["sha256"], "fit_sha256": pf.file_hash(run / "profile-fit.json"), "state": "spent"}
    save(run / "profile-evaluation-seal.json", seal)
    dev = [r for r in rows if r["split"] == "dev"]
    heldout = [r for r in rows if r["split"] == "heldout"]
    result = pm.evaluate(heldout, fitted, reg["pair_bootstraps"])
    result["diagnostics"] = pm.diagnostics(dev, heldout, fitted, reg["weight_refits"], reg["permutations"])
    soft = [dict(r, features=r["soft"]) for r in heldout]
    s = pm.scores(soft, fitted["soft_model"])
    import numpy as np
    result["soft"] = {"auc": pm.auc(s, np.array([int(r["source"] == "ai") for r in soft])), "ci": pm.pair_bootstrap(soft, s)}
    result.update(seal, state="complete")
    result["sha256"] = pf.digest(result)
    save(run / "profile-evaluation.json", result)


def explain(features, instrument):
    model = instrument["model"]
    base = model["intercept"] + sum(w * (h - m) / s for w, h, m, s in
                                     zip(model["weights"], model["human_mean"], model["mean"], model["sd"]))
    contributions = []
    for i, fid in enumerate(pf.IDS):
        row = features[fid]; w = model["weights"][i]
        val = model["human_mean"][i] if row["value"] is None else row["value"]
        precision = instrument.get("precision", {}).get(fid)
        name = pf.NAMES[i]
        caveat = None
        if i < 15 and (precision is None or precision < .8):
            name = instrument["questions"][name]["instructions"]["question"]
            caveat = "Jev question; what it detects is not confirmed" if precision is None else f"Jev question; held-out precision {precision:.2f}; name approximate"
        recall = instrument.get("recall", {}).get(fid)
        contributions.append({"feature": fid, "name": name, "weight": w,
                              "contribution": w * (val - model["human_mean"][i]) / model["sd"][i],
                              "rate": row["rate"], "k": row["k"], "n": row["n"], "unit": pf.definitions()[fid]["unit"],
                              "medians": instrument["medians"][fid], "fired": row["fired"], "caveat": caveat,
                              "not_applicable": row["value"] is None, "recall": recall})
    score = base + sum(c["contribution"] for c in contributions)
    tails = {side: sum(s >= score for s in values) / len(values) for side, values in instrument["reference_scores"].items()}
    return {"id": instrument["id"], "kind": instrument["kind"], "context": instrument["context"], "score": score,
            "human_reference_score": base, "flag_line": model["flag_line"], "flagged": score >= model["flag_line"],
            "heldout_tail_rates": tails, "contributions": contributions}


def format_explanation(report):
    lines = [f"PROFILE {report['id']} ({report['context']})",
             f"  score {report['score']:+.4f}; flag line {report['flag_line']:+.4f}; instrument: {report['kind']}",
             "  On held-out pages, " + ", ".join(f"{v:.1%} of {side} pages scored this high" for side, v in report["heldout_tail_rates"].items()),
             f"  average human score {report['human_reference_score']:+.4f}"]
    for c in sorted(report["contributions"], key=lambda c: -c["contribution"]):
        if not c["weight"]:
            continue
        if c["not_applicable"]:
            lines.append(f"  {c['feature']} {c['name']}: not applicable on this page (contributes zero)")
            continue
        lines.append(f"  {c['contribution']:+.4f} {c['feature']} {c['name']}: page {c['rate']:.4g}; "
                     f"human / AI medians {c['medians']['human']} / {c['medians']['ai']}; {c['unit']}; " + " ".join(c["fired"]))
        if c["caveat"]:
            lines.append("    " + c["caveat"])
        if c["recall"]:
            recall = c["recall"]
            lines.append("    recall " + json.dumps(recall, sort_keys=True))
            rates = [r["recall"] for r in recall.values() if r.get("recall") is not None]
            if rates and min(rates) < .5:
                lines.append("    Low count is weak evidence that the construction is absent")
            if rates and min(rates) > 0 and max(rates) / min(rates) > 1.5:
                lines.append("    Warning: the tell is missed more on one side")
        elif c["feature"] in pf.IDS[:15]:
            lines.append("    recall unknown")
    lines.append("  not in this profile: " + ", ".join(pf.NAMES[i] for i, c in enumerate(report["contributions"]) if not c["weight"]))
    return "\n".join(lines)


def verified_result(run):
    run = Path(run); reg = registration(run)
    seal = read_json(run / "profile-evaluation-seal.json")
    result = read_json(run / "profile-evaluation.json")
    if (result["state"] != "complete" or result["registration_sha256"] != reg["sha256"] or
        seal["fit_sha256"] != pf.file_hash(run / "profile-fit.json") or
        result["sha256"] != pf.digest({k: v for k, v in result.items() if k != "sha256"})):
        raise ValueError("evaluation seal mismatch")
    return reg, result


def cmd_promote(a):
    run = Path(a.run); reg, result = verified_result(run)
    fitted = read_json(run / "profile-fit.json")
    name = "profile" if result["qualifies"] else "B1"
    heldout = [r for r in read_rows(run / "features.jsonl") if r["split"] == "heldout"]
    values = result["instruments"][name]["scores"]
    instrument = {"id": a.id, "kind": "profile" if name == "profile" else "best single feature",
                  "model": fitted["models"][name], "medians": fitted["medians"], "questions": reg["questions"],
                  "features": reg["features"], "features_sha256": reg["features_sha256"],
                  "banlist_sha256": reg["banlist_sha256"], "questions_sha256": reg["questions_sha256"],
                  "registration_sha256": reg["sha256"], "evaluation_sha256": result["sha256"],
                  "measurement_sha256": {k: reg["code_sha256"][k] for k in ("profile_features.py", "textsplit.py")},
                  "heldout": {k: v for k, v in result["instruments"][name].items() if k != "scores"},
                  "context": f"Opus 5.5 vs public pre-2022-11-30 explainers; {len(heldout) // 2} held-out pairs",
                  "reference_scores": {side: [s for s, r in zip(values, heldout) if r["source"] == side] for side in ("human", "ai")}}
    label_path = run / "profile-label-results.json"
    if label_path.exists():
        labels = read_json(label_path)
        if labels["evaluation_sha256"] != result["sha256"]:
            raise ValueError("labels not tied to sealed result")
        instrument.update(precision=labels["precision"], recall=labels["recall"])
    registry = read_json(a.into)
    if label_path.exists():
        import calibrate
        calibrate.promote_profile_tells(registry, labels, reg["questions"], a.id)
    if any(p["id"] == a.id for p in registry.get("profiles", [])):
        raise ValueError("profile id already promoted")
    registry.setdefault("profiles", []).append(instrument)
    save(a.into, registry, exclusive=False)


def cmd_explain(a):
    _, rows = measured(a.run)
    registry = read_json(a.defs)
    instrument = next(p for p in registry["profiles"] if p["id"] == a.id)
    row = next(r for r in rows if r["id"] == a.page)
    print(format_explanation(explain(row["features"], instrument)))


def recall_sheet(run):
    run = Path(run); reg, result = verified_result(run)
    rows = [r for r in pages(run) if r["split"] == "heldout"]
    answers = original_answers(run, pages(run), reg)
    rng = random.Random(reg["recall"]["seed"])
    jobs = jobs_for(rows, reg["questions"])
    byside = {side: [j for j in jobs if j["page"] in {r["id"] for r in rows if r["source"] == side}] for side in ("human", "ai")}
    key, sheet = {}, []
    # Broad, frozen nets deliberately over-include; the uniform sample still covers misses outside them
    nets = [r",|\band\b|\bor\b", r"\b\w+ing\b", r"\bnot\b|rather|more than|less", r"matter|important|key|crucial|significant",
            r"^(?:In |Looking|Put|At |Ultimately|The bottom|Here|That said)", r"\b(?:What|Whether|How|That|To|\w+ing)\b.*\bbe\b|\bwas\b|\bis\b",
            r"\bthat\b", r"\band\b|\bor\b", r"arguably|extent|ways|fair|sense|somewhat|perhaps|could", r"\b\w+(?:ing|ed)\b", r"\bof\b|(?:\b\w+\s+){3}", r"[:—?]| -- "]
    for side, pool in byside.items():
        sentences = [j for j in pool if len(j["questions"]) == 12]
        uniform = rng.sample(sentences, min(300, len(sentences)))
        selected = {j["id"]: {"job": j, "pi": {name: len(uniform) / len(sentences) for name in pf.SENTENCE_NAMES}} for j in uniform}
        uids = set(selected)
        for name, net in zip(pf.SENTENCE_NAMES, nets):
            expected = len(uniform) * sum(answers[j["page"]][j["unit"]][name] >= .5 for j in sentences) / len(sentences)
            if expected >= 15:
                continue
            net_ids = {j["id"] for j in sentences if re.search(net, j["state"]["sentence"], re.I)}
            candidates = [j for j in sentences if j["id"] not in uids and j["id"] in net_ids]
            enriched = rng.sample(candidates, min(40, len(candidates)))
            sampled_net = len(net_ids & uids) + len(enriched)
            sampled_outside = len(uids - net_ids)
            for j in uniform:
                is_net = j["id"] in net_ids
                population = len(net_ids) if is_net else len(sentences) - len(net_ids)
                selected[j["id"]]["pi"][name] = (sampled_net if is_net else sampled_outside) / population
            for j in enriched:
                record = selected.setdefault(j["id"], {"job": j, "pi": {}})
                record["pi"][name] = sampled_net / len(net_ids)
        for record in selected.values():
            j = record["job"]; item = f"r{len(sheet):05d}"
            sheet.append({"item": item, "state": j["state"], "questions": {n: reg["questions"][n] for n in record["pi"]}})
            key[item] = {"page": j["page"], "unit": j["unit"], "source": side,
                         "weights": {n: 1 / pi for n, pi in record["pi"].items()}, "uniform": j["id"] in uids}
        for name in pf.NAMES[12:15]:
            eligible = [j for j in pool if name in j["questions"]]
            sampled = rng.sample(eligible, min(60, len(eligible)))
            for j in sampled:
                item = f"r{len(sheet):05d}"
                sheet.append({"item": item, "state": j["state"], "questions": j["questions"]})
                key[item] = {"page": j["page"], "unit": j["unit"], "source": side,
                             "weights": {name: len(eligible) / len(sampled)}, "uniform": True}
    save_rows(run / "recall-sheet.jsonl", sheet)
    save(run / "recall-key.json", {"evaluation_sha256": result["sha256"], "items": key, "nets": nets})


def cmd_recall_sheet(a):
    recall_sheet(a.run)


def cmd_mark_set(a):
    run = Path(a.run); reg = registration(run)
    if (run / "profile-evaluation-seal.json").exists():
        raise ValueError("mark before seeing any result")
    rows = [r for r in pages(run) if r["split"] == "heldout" and r["pair"] not in set(a.exclude or [])]
    rng = random.Random(reg["marking"]["seed"])
    pairs = defaultdict(dict)
    for r in rows:
        pairs[r["pair"]][r["source"]] = r
    n = reg["marking"]["pages"]; practice_n = reg["marking"]["practice"]
    if len(pairs) < n + practice_n:
        raise ValueError("not enough unrecognised held-out pairs for marking and practice")
    chosen = rng.sample(sorted(pairs), n + practice_n)
    ai_count = rng.randint(math.ceil(n * .4), math.floor(n * .6))
    sides = ["ai"] * ai_count + ["human"] * (n - ai_count)
    rng.shuffle(sides)
    entries = [(pairs[pair][side], False) for pair, side in zip(chosen[:n], sides)]
    repeated = rng.sample(entries, reg["marking"]["repeats"])
    entries += repeated
    rng.shuffle(entries)
    practice = [(pairs[p][rng.choice(["ai", "human"])], True) for p in chosen[n:]]
    entries = practice + entries
    key, sheet = {}, []
    for r, is_practice in entries:
        opaque = rng.getrandbits(128).to_bytes(16).hex()
        units = textsplit.extract(r["text"], "html", positional=True)[1]
        sheet.append({"id": opaque, "practice": is_practice, "html": r["text"], "units": units,
                      "reasons": ["three-part list", "X, not Y", "punchline ending", "signposting", "hedging", "dash", "other"]})
        key[opaque] = {"page": r["id"], "pair": r["pair"], "source": r["source"], "practice": is_practice,
                       "sentence_ids": [u["id"] for u in units if u["kind"] == "sentence"]}
    save_rows(run / "mark-set.jsonl", sheet)
    save(run / "mark-key.json", {"registration_sha256": reg["sha256"], "items": key})
    os.chmod(run / "mark-key.json", 0o600)


def cmd_import_marks(a):
    run = Path(a.run); reg = registration(run)
    key = read_json(run / "mark-key.json")
    if key["registration_sha256"] != reg["sha256"]:
        raise ValueError("mark set not tied to registration")
    marks = read_rows(a.marks)
    if len(marks) != len(key["items"]) or {m["id"] for m in marks} != set(key["items"]):
        raise ValueError("submit each opaque marking id exactly once, including repeats and practice")
    out = []
    for m in marks:
        k = key["items"][m["id"]]
        if type(m.get("recognised")) is not bool or type(m.get("rating")) is not int or m["rating"] not in range(1, 6):
            raise ValueError("marks require recognised boolean and rating 1..5")
        if not isinstance(m.get("seconds"), (int, float)) or not math.isfinite(m["seconds"]) or m["seconds"] < 0:
            raise ValueError("marks require elapsed seconds")
        taps = m.get("taps", [])
        if not isinstance(taps, list) or any(t not in k["sentence_ids"] for t in taps) or len(taps) != len(set(taps)):
            raise ValueError("invalid or duplicate tapped sentence")
        out.append({**m, **k, "dropped": m["recognised"] or k["practice"]})
    # Recognising either copy excludes all copies of that page
    recognised = {m["page"] for m in out if m["recognised"]}
    for m in out:
        m["dropped"] |= m["page"] in recognised
    save(run / "imported-marks.json", {"registration_sha256": reg["sha256"], "marks": out})


def cmd_precision_sheet(a):
    import profile_labels
    profile_labels.precision_sheet(a.run)


def cmd_decide_labels(a):
    import profile_labels
    profile_labels.decide_labels(a.run, a.precision_labels, a.recall_labels)


def cmd_marks_report(a):
    import profile_labels
    profile_labels.marks_report(a.run)


def add_parser(sub, default_tells):
    root = sub.add_parser("profile", help="registered page-profile workflow")
    steps = root.add_subparsers(dest="step", required=True)
    def add(name, fn):
        p = steps.add_parser(name); p.add_argument("run"); p.set_defaults(fn=fn); return p
    p = add("corpus", cmd_corpus); p.add_argument("--sources", required=True)
    p = add("pair", cmd_pair); p.add_argument("--ai", required=True)
    p = add("register", cmd_register); p.add_argument("--defs", default=default_tells); p.add_argument("--banlist", required=True)
    p = add("run", cmd_run)
    p.add_argument("--cap-usd", type=float, required=True); p.add_argument("--provider", choices=list(jev.PROVIDERS), default="typesafe")
    p.add_argument("--env-file"); p.add_argument("--key-file"); p.add_argument("--workers", type=int, default=4); p.add_argument("--dry-run", action="store_true")
    p = add("features", cmd_features); p.add_argument("--banlist", required=True)
    add("fit", cmd_fit); add("evaluate", cmd_evaluate)
    p = add("promote", cmd_promote); p.add_argument("--into", default=default_tells); p.add_argument("--id", required=True)
    p = add("explain", cmd_explain); p.add_argument("--defs", default=default_tells); p.add_argument("--id", required=True); p.add_argument("--page", required=True)
    add("recall-sheet", cmd_recall_sheet)
    add("precision-sheet", cmd_precision_sheet)
    p = add("decide-labels", cmd_decide_labels); p.add_argument("--precision-labels", required=True); p.add_argument("--recall-labels", required=True)
    add("marks-report", cmd_marks_report)
    p = add("mark-set", cmd_mark_set); p.add_argument("--exclude", action="append", help="famous/recognisable pair id; repeat as needed")
    p = add("import-marks", cmd_import_marks); p.add_argument("--marks", required=True)
