import json

import pytest

import calibrate
import profile_corpus as pc
import profile_labels as pl
import profile_workflow as pw
from test_profile_workflow import study, register


def test_mark_set_blind_heldout_one_side_repeats_practice_import_and_recognition(study, monkeypatch, tmp_path):
    run, _ = study
    original = pw.read_rows(run / "pages.jsonl")[:2]
    rows = []
    for p in range(48):
        for row in original:
            rows.append(dict(row, id=f"toy-{p}:{row['source']}", pair=f"toy-{p}", split="dev" if p < 5 else "heldout"))
    (run / "pages.jsonl").unlink(); (run / "manifest.json").unlink()
    pw.save_rows(run / "pages.jsonl", rows); pw.save(run / "manifest.json", pc.manifest(rows))
    monkeypatch.setattr(pc, "TARGETS", {"G1": 48})
    register(study)
    calibrate.main(["profile", "mark-set", str(run)])
    sheet = pw.read_rows(run / "mark-set.jsonl")
    key = pw.read_json(run / "mark-key.json")["items"]
    assert len(sheet) == 47 and sum(r["practice"] for r in sheet) == 3
    assert all(set(r) == {"id", "practice", "html", "units", "reasons"} for r in sheet)
    assert all(len(r["id"]) == 32 for r in sheet)
    assert all(int(k["pair"].split("-")[1]) >= 5 for k in key.values())
    unique = {k["pair"]: k["source"] for k in key.values() if not k["practice"]}
    assert len(unique) == 40 and 16 <= sum(s == "ai" for s in unique.values()) <= 24
    assert len({k["page"] for k in key.values()}) == 43
    assert (run / "mark-key.json").stat().st_mode & 0o777 == 0o600
    copies = {}
    for opaque, k in key.items():
        copies.setdefault(k["page"], []).append(opaque)
    duplicate_ids = next(v for v in copies.values() if len(v) == 2)
    marks = [{"id": r["id"], "rating": 3, "recognised": r["id"] == duplicate_ids[0], "seconds": 1.2, "taps": ["s0001"]} for r in sheet]
    path = tmp_path / "marks.jsonl"
    pw.save_rows(path, marks)
    calibrate.main(["profile", "import-marks", str(run), "--marks", str(path)])
    imported = pw.read_json(run / "imported-marks.json")["marks"]
    assert all(m["dropped"] for m in imported if m["id"] in duplicate_ids)
    assert sum(m["dropped"] for m in imported) == 5
    with pytest.raises(FileExistsError):
        calibrate.main(["profile", "mark-set", str(run)])


def test_weighted_recall_uses_inverse_inclusion_weights_not_raw_label_counts():
    items = [{"pair": "one", "label": True, "probability": .9, "weight": 1},
             {"pair": "two", "label": True, "probability": .2, "weight": 3}]
    result = pl.weighted_recall(items, repeats=100)
    assert result["recall"] == .25 and result["weighted_positives"] == 4
    assert result["ci"][0] <= .25 <= result["ci"][1]
    assert pl.weighted_recall([dict(items[0], label=False)])["recall"] is None


def test_label_import_does_not_coerce_strings_or_accept_missing_items(tmp_path):
    path = tmp_path / "labels.jsonl"
    pw.save_rows(path, [{"item": "blind", "labels": {"tricolon": "false"}, "labeller": "synthetic"}])
    with pytest.raises(ValueError, match="booleans"):
        pl.labels(path, {"blind": ["tricolon"]})
    with pytest.raises(ValueError, match="every"):
        pl.labels(path, {"blind": ["tricolon"], "missing": ["tricolon"]})
