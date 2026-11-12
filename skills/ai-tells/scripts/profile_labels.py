"""Blind label sheets and estimators for the sealed page study; no labeller calls."""
from collections import defaultdict
from pathlib import Path
import math
import random

import profile_features as pf


def precision_sheet(run):
    import profile_workflow as pw
    run = Path(run); reg, result = pw.verified_result(run)
    rows = [r for r in pw.pages(run) if r["split"] == "heldout"]
    answers = pw.original_answers(run, pw.pages(run), reg)
    jobs = pw.jobs_for(rows, reg["questions"])
    rng = random.Random(194)
    key, sheet = {}, []
    for name in pf.NAMES[:15]:
        eligible = [j for j in jobs if name in j["questions"]]
        hi = [j for j in eligible if answers[j["page"]][j["unit"]][name] >= .5]
        lo = [j for j in eligible if answers[j["page"]][j["unit"]][name] < .5]
        rng.shuffle(hi); rng.shuffle(lo)
        selected = hi[:40] + lo[:80 - min(40, len(hi))]
        for stratum, pool in (("hi", [j for j in selected if j in hi]), ("lo", [j for j in selected if j in lo])):
            rng.shuffle(pool)
            for n, j in enumerate(pool):
                opaque = f"l{rng.getrandbits(128):032x}"
                sheet.append({"item": opaque, "state": j["state"], "questions": {name: j["questions"][name]}})
                key[opaque] = {"name": name, "page": j["page"], "unit": j["unit"],
                               "split": "dev" if n % 2 == 0 else "heldout", "stratum": stratum}
    rng.shuffle(sheet)
    pw.save_rows(run / "precision-sheet.jsonl", sheet)
    pw.save(run / "precision-key.json", {"evaluation_sha256": result["sha256"], "items": key})


def labels(path, expected):
    import profile_workflow as pw
    rows = pw.read_rows(path)
    if len(rows) != len(expected) or {r["item"] for r in rows} != set(expected):
        raise ValueError("labels must cover every blind item exactly once")
    out = {}
    for r in rows:
        if set(r["labels"]) != set(expected[r["item"]]) or any(type(v) is not bool for v in r["labels"].values()):
            raise ValueError("labels must be booleans for each question on the blind item")
        if not r.get("labeller"):
            raise ValueError("labels must record the labeller")
        out[r["item"]] = r["labels"]
    return out


def weighted_recall(items, repeats=2000):
    """HT totals in the registered strata; paired pages, not tokens, set uncertainty."""
    import numpy as np
    bypage = defaultdict(lambda: [0., 0.])
    for item in items:
        if item["label"]:
            bypage[item["pair"]][1] += item["weight"]
            if item["probability"] >= .5:
                bypage[item["pair"]][0] += item["weight"]
    if not bypage:
        return {"recall": None, "ci": None, "weighted_positives": 0.}
    values = np.array(list(bypage.values()))
    point = values[:, 0].sum() / values[:, 1].sum()
    rng = np.random.default_rng(194)
    estimates = []
    for _ in range(repeats):
        totals = values[rng.integers(len(values), size=len(values))].sum(0)
        if totals[1]:
            estimates.append(totals[0] / totals[1])
    return {"recall": float(point), "ci": np.percentile(estimates, [2.5, 97.5]).tolist(),
            "weighted_positives": float(values[:, 1].sum())}


def decide_labels(run, precision_path, recall_path):
    import calibrate
    import numpy as np
    import profile_model as pm
    import profile_workflow as pw
    run = Path(run); reg, result = pw.verified_result(run)
    pkey, rkey = pw.read_json(run / "precision-key.json"), pw.read_json(run / "recall-key.json")
    if any(k["evaluation_sha256"] != result["sha256"] for k in (pkey, rkey)):
        raise ValueError("label sheet belongs to another evaluation")
    p_labels = labels(precision_path, {i: [k["name"]] for i, k in pkey["items"].items()})
    r_labels = labels(recall_path, {i: k["weights"] for i, k in rkey["items"].items()})
    pages = pw.pages(run)
    byid = {r["id"]: r for r in pages}
    answers = pw.original_answers(run, pages, reg)
    heldout = [r for r in pages if r["split"] == "heldout"]
    ix = pm.paired_indices(heldout)
    jobs = pw.jobs_for(heldout, reg["questions"])
    precision, recall, decisions = {}, {}, []
    for fid, name in zip(pf.IDS[:15], pf.NAMES[:15]):
        points = [(answers[k["page"]][k["unit"]][name], p_labels[item][name], k["split"])
                  for item, k in pkey["items"].items() if k["name"] == name]
        hi, lo = calibrate.bands([(p, label) for p, label, split in points if split == "dev"])
        hy = [label for p, label, split in points if split == "heldout" and p >= hi]
        profile_yes = [label for p, label, split in points if split == "heldout" and p >= .5]
        precision[fid] = sum(profile_yes) / len(profile_yes) if profile_yes else None
        counts = []
        for page in heldout:
            probs = [answers[j["page"]][j["unit"]][name] for j in jobs if j["page"] == page["id"] and name in j["questions"]]
            counts.append([sum(p >= hi for p in probs), len(probs)])
        counts = np.array(counts)
        ay, an = counts[ix[:, 0]].sum(0); hy_count, hn = counts[ix[:, 1]].sum(0)
        rng = np.random.default_rng(194)
        ratios = []
        for _ in range(reg["pair_bootstraps"]):
            sample = ix[rng.integers(len(ix), size=len(ix))]
            a, na = counts[sample[:, 0]].sum(0); h, nh = counts[sample[:, 1]].sum(0)
            ratios.append(((a + .5) / (na + .5)) / ((h + .5) / (nh + .5)))
        ratio = ((ay + .5) / (an + .5)) / ((hy_count + .5) / (hn + .5))
        low, high = np.percentile(ratios, [2.5, 97.5])
        prec = sum(hy) / len(hy) if hy else None
        row = {"tell": name, "feature": fid, "t_hi": hi, "t_lo": lo, "human_yes": int(hy_count), "human_n": int(hn),
               "ai_yes": int(ay), "ai_n": int(an), "ratio": float(ratio), "ci_lo": float(low), "ci_hi": float(high),
               "heldout_precision": prec, "heldout_yes": len(hy), "heldout_ci": list(calibrate.wilson(sum(hy), len(hy))) if hy else None,
               "kept": bool(ratio >= 2 and prec is not None and prec >= .8 and min(ay, hy_count) >= 25)}
        row["outcome"] = calibrate.outcome_class(row)
        decisions.append(row)
        recall[fid] = {}
        for side in ("human", "ai"):
            items = [{"pair": byid[k["page"]]["pair"], "label": r_labels[item][name], "weight": k["weights"][name],
                      "probability": answers[k["page"]][k["unit"]][name]}
                     for item, k in rkey["items"].items() if k["source"] == side and name in k["weights"]]
            recall[fid][side] = weighted_recall(items)
    pw.save(run / "profile-label-results.json", {"evaluation_sha256": result["sha256"], "precision": precision,
            "recall": recall, "decisions": decisions, "precision_labels_sha256": pf.file_hash(precision_path),
            "recall_labels_sha256": pf.file_hash(recall_path), "genres": sorted({r["genre"] for r in heldout})})


def marks_report(run):
    import numpy as np
    import profile_model as pm
    import profile_workflow as pw
    run = Path(run); reg, result = pw.verified_result(run)
    imported = pw.read_json(run / "imported-marks.json")
    if imported["registration_sha256"] != reg["sha256"]:
        raise ValueError("marks belong to another registration")
    bypage = defaultdict(list)
    for mark in imported["marks"]:
        if not mark["dropped"]:
            bypage[mark["page"]].append(mark)
    # Repeats measure consistency; they do not give a page extra weight
    marks = [copies[0] for copies in bypage.values()]
    consistency = []
    for copies in bypage.values():
        if len(copies) == 2:
            a, b = copies
            ta, tb = set(a["taps"]), set(b["taps"])
            consistency.append({"rating_difference": abs(a["rating"] - b["rating"]),
                                "tap_jaccard": len(ta & tb) / len(ta | tb) if ta | tb else 1.})
    if not marks:
        raise ValueError("no unrecognised marked pages")
    heldout = [r for r in pw.read_rows(run / "features.jsonl") if r["split"] == "heldout"]
    source = np.array([m["source"] == "ai" for m in marks])
    rating = np.array([m["rating"] for m in marks])
    out = {"pages": len(marks), "seconds": sum(m["seconds"] for m in imported["marks"]), "consistency": consistency,
           "captain_source_auc": pm.auc(rating, source) if 0 < sum(source) < len(source) else None, "instruments": {}}
    for name in ("profile", "B2"):
        page_scores = dict(zip([r["id"] for r in heldout], result["instruments"][name]["scores"]))
        s = np.array([page_scores[m["page"]] for m in marks])
        definitive = np.array([m["rating"] != 3 for m in marks])
        y = rating[definitive] >= 4
        def ranks(values):
            return np.array([sum(values < v) + (sum(values == v) + 1) / 2 for v in values])
        sr, rr = ranks(s), ranks(rating)
        corr = float(np.corrcoef(sr, rr)[0, 1]) if sr.std() and rr.std() else None
        out["instruments"][name] = {"rating_auc": pm.auc(s[definitive], y) if 0 < sum(y) < len(y) else None, "spearman": corr}
    labels_path = run / "profile-label-results.json"
    confirmed = set()
    if labels_path.exists():
        confirmed = {pf.NAMES[pf.IDS.index(fid)] for fid, p in pw.read_json(labels_path)["precision"].items() if p is not None and p >= .8}
    answers = pw.original_answers(run, pw.pages(run), reg)
    tp, total_taps, total_flags = 0, 0, 0
    for m in marks:
        flagged = {sid for sid, values in answers[m["page"]].items() if sid.startswith("s") and
                   any(values.get(name, 0) >= .5 for name in confirmed & set(pf.SENTENCE_NAMES))}
        tapped = set(m["taps"])
        tp += len(flagged & tapped); total_taps += len(tapped); total_flags += len(flagged)
    out["named_tells_vs_taps"] = {"recall": tp / total_taps if total_taps else None,
                                  "precision": tp / total_flags if total_flags else None, "confirmed_questions": sorted(confirmed)}
    pw.save(run / "marks-report.json", out)
