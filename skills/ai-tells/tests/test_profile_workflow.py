"""Offline study lifecycle through the same loopback request path as check.py."""
import copy
import json
from pathlib import Path

import pytest

import calibrate
import check
import jev
import profile_corpus as pc
import profile_features as pf
import profile_labels as pl
import profile_model as pm
import profile_workflow as pw

TEXT = "<h2>A synthetic heading</h2><p>The toy has a red handle. A second sentence describes it. The handle fits a small hand.</p><p>Another paragraph explains the toy.</p><p>A final paragraph closes the note.</p>"


@pytest.fixture
def study(tmp_path, monkeypatch):
    run = tmp_path / "study"; run.mkdir()
    banlist = tmp_path / "banlist.md"
    banlist.write_text('Words (stem match): delv, robust\n\nPhrases: "deep dive"\n')
    monkeypatch.setattr(pf, "BANLIST_SHA256", pf.file_hash(banlist))
    monkeypatch.setattr(pc, "TARGETS", {"G1": 12})
    rows = []
    for pair in range(12):
        for side in ("ai", "human"):
            rows.append({"id": f"toy-{pair}:{side}", "pair": f"toy-{pair}", "source": side, "genre": "G1", "origin": "ux",
                         "split": "dev" if pair < 8 else "heldout", "text": TEXT, "words": pc.count_words(TEXT),
                         "rendered_sha256": pf.digest(TEXT), "revision": "synthetic", "licence": "synthetic"})
    pw.save_rows(run / "pages.jsonl", rows)
    pw.save(run / "manifest.json", pc.manifest(rows))
    return run, banlist


def register(study):
    run, banlist = study
    calibrate.main(["profile", "register", str(run), "--banlist", str(banlist)])
    return run, banlist


def features(study, mock_factory):
    run, banlist = register(study)
    mock = mock_factory()
    calibrate.main(["profile", "run", str(run), "--cap-usd", "1"])
    calibrate.main(["profile", "features", str(run), "--banlist", str(banlist)])
    return run, banlist, mock


def test_registration_is_exclusive_and_precedes_any_measurement(study):
    run, banlist = register(study)
    reg = pw.registration(run)
    assert len(reg["features"]) == 26 and len(reg["questions"]) == 15
    assert reg["pair_bootstraps"] == 2000 and reg["weight_refits"] == 1000 and reg["permutations"] == 50
    assert "Words (stem match)" not in json.dumps(reg)
    with pytest.raises(FileExistsError):
        register(study)
    (run / "profile-answers.jsonl").write_text("")
    with pytest.raises(ValueError, match="before"):
        register(study)


def test_manifest_corpus_and_code_are_hash_bound(study, monkeypatch):
    run, _ = register(study)
    hashes = pw.code_hashes()
    monkeypatch.setattr(pw, "code_hashes", lambda: {**hashes, "textsplit.py": "changed"})
    with pytest.raises(ValueError, match="code changed"):
        pw.registration(run)
    monkeypatch.setattr(pw, "code_hashes", lambda: hashes)
    with open(run / "pages.jsonl", "a") as f:
        f.write("\n")
    with pytest.raises(ValueError, match="corpus changed"):
        pw.registration(run)


def test_dry_run_cap_and_resume_do_not_read_credentials(study, monkeypatch, mock_factory):
    run, _ = register(study)
    mock = mock_factory()
    def forbidden(*args, **kwargs):
        raise AssertionError("no credential read should occur")
    original = jev.read_key
    monkeypatch.setattr(jev, "read_key", forbidden)
    calibrate.main(["profile", "run", str(run), "--cap-usd", "1", "--dry-run"])
    with pytest.raises(ValueError, match="cap"):
        calibrate.main(["profile", "run", str(run), "--cap-usd", "0.000001"])
    assert not mock.requests
    monkeypatch.setattr(jev, "read_key", original)
    calibrate.main(["profile", "run", str(run), "--cap-usd", "1"])
    sent = len(mock.requests)
    calibrate.main(["profile", "run", str(run), "--cap-usd", "1"])
    assert len(mock.requests) == sent
    sentence_bodies = [b for b in mock.requests if len(b["questions"]) == 12]
    assert len(sentence_bodies) == 120
    assert all(set(b["state"]) == {"sentence"} and list(b["questions"]) == pf.SENTENCE_NAMES for b in sentence_bodies)
    assert any(set(b["state"]) == {"paragraph", "last_sentence"} for b in mock.requests)
    assert any(set(b["state"]) == {"last_paragraph", "preceding_paragraphs"} for b in mock.requests)


def test_duplicate_replay_or_changed_shape_never_averaged_into_profile(study, mock_factory):
    run, _, _ = features(study, mock_factory)
    answers = pw.read_rows(run / "profile-answers.jsonl")
    with open(run / "profile-answers.jsonl", "a") as f:
        f.write(json.dumps(dict(answers[0], tag="replay1")) + "\n")
    with pytest.raises(ValueError, match="exactly one"):
        pw.original_answers(run, pw.pages(run), pw.registration(run))


def test_offline_end_to_end_fit_seal_promote_fallback_check_and_labels(study, mock_factory, tmp_path, capsys):
    run, banlist, mock = features(study, mock_factory)
    calibrate.main(["profile", "fit", str(run)])
    fitted = pw.read_json(run / "profile-fit.json")
    assert fitted["models"]["profile"]["active"] == []
    calibrate.main(["profile", "evaluate", str(run)])
    result = pw.read_json(run / "profile-evaluation.json")
    assert result["state"] == "complete" and not result["qualifies"]
    assert not result["H1"]["passed"] and not result["H2"]["tested"]
    assert len(result["diagnostics"]["importance"]) == 34
    with pytest.raises(FileExistsError):
        calibrate.main(["profile", "evaluate", str(run)])
    calibrate.main(["profile", "precision-sheet", str(run)])
    calibrate.main(["profile", "recall-sheet", str(run)])
    for kind in ("precision", "recall"):
        sheet = pw.read_rows(run / f"{kind}-sheet.jsonl")
        assert sheet and all(set(r) == {"item", "state", "questions"} for r in sheet)
        pw.save_rows(run / f"{kind}-labels.jsonl", [{"item": r["item"], "labels": {n: False for n in r["questions"]}, "labeller": "synthetic fixture"} for r in sheet])
    calibrate.main(["profile", "decide-labels", str(run), "--precision-labels", str(run / "precision-labels.jsonl"), "--recall-labels", str(run / "recall-labels.jsonl")])
    labels = pw.read_json(run / "profile-label-results.json")
    assert all(d["outcome"] == "too rare" for d in labels["decisions"])
    registry = tmp_path / "registry.json"
    pw.save(registry, check.load_registry())
    calibrate.main(["profile", "promote", str(run), "--into", str(registry), "--id", "synthetic-test"])
    promoted = pw.read_json(registry)
    instrument = promoted["profiles"][0]
    assert instrument["kind"] == "best single feature"
    assert all(t["status"] == "lead" for t in promoted["tells"].values())
    page = tmp_path / "toy.html"; page.write_text(TEXT)
    output = tmp_path / "checked.json"
    sent = len(mock.requests)
    assert check.main([str(page), "--tells-file", str(registry), "--banlist", str(banlist), "--json", str(output)]) == 0
    assert len(mock.requests) > sent
    report = pw.read_json(output)
    assert report["profiles"][0]["windows"][0]["kind"] == "best single feature"
    explanation = report["profiles"][0]["windows"][0]
    assert explanation["score"] == pytest.approx(explanation["human_reference_score"] + sum(c["contribution"] for c in explanation["contributions"]))
    assert "authorship" not in json.dumps(report)
    assert "PROFILE synthetic-test" in capsys.readouterr().out
    with pytest.raises(ValueError, match="already promoted"):
        calibrate.main(["profile", "promote", str(run), "--into", str(registry), "--id", "synthetic-test"])


def test_fit_only_receives_dev_and_features_tamper_refused(study, mock_factory, monkeypatch):
    run, _, _ = features(study, mock_factory)
    real = pm.fit_all
    def dev_only(rows):
        assert all(r["split"] == "dev" for r in rows)
        return real(rows)
    monkeypatch.setattr(pm, "fit_all", dev_only)
    calibrate.main(["profile", "fit", str(run)])
    with open(run / "features.jsonl", "a") as f:
        f.write("\n")
    with pytest.raises(ValueError, match="changed"):
        calibrate.main(["profile", "evaluate", str(run)])
    assert not (run / "profile-evaluation-seal.json").exists()


def test_interrupted_evaluation_spends_holdout(study, mock_factory, monkeypatch):
    run, _, _ = features(study, mock_factory)
    calibrate.main(["profile", "fit", str(run)])
    def interrupted(*args):
        raise RuntimeError("simulated interruption")
    monkeypatch.setattr(pm, "evaluate", interrupted)
    with pytest.raises(RuntimeError):
        calibrate.main(["profile", "evaluate", str(run)])
    assert (run / "profile-evaluation-seal.json").exists()
    with pytest.raises(FileExistsError):
        calibrate.main(["profile", "evaluate", str(run)])


def test_explanation_zero_for_nonapplicable_caveats_and_additivity():
    from test_profile_model import simulated
    dev = simulated(100)
    model = pm.fit(dev)
    features = copy.deepcopy(dev[0]["features"])
    features["F1"]["value"] = None
    instrument = {"id": "synthetic", "kind": "profile", "context": "synthetic fixture", "model": model,
                  "questions": pf.questions(check.load_registry()), "medians": {fid: {"human": 1, "ai": 2} for fid in pf.IDS},
                  "reference_scores": {"ai": [0, 1], "human": [-1, 0]}}
    report = pw.explain(features, instrument)
    assert report["contributions"][0]["contribution"] == 0
    assert report["contributions"][0]["caveat"]
    assert report["contributions"][0]["name"].startswith("Does")
    assert "not applicable" in pw.format_explanation(report)


@pytest.mark.parametrize("hits,ratio_hi,precision_ci,expected", [
    ((24, 100), 1.5, [.1, .4], "too rare"), ((25, 25), 1.9, None, "rejected"),
    ((25, 25), 2.1, [.2, .79], "rejected"), ((25, 25), 2.1, [.2, .81], "inconclusive")])
def test_outcome_floor_and_uncertainty(hits, ratio_hi, precision_ci, expected):
    record = {"human_yes": hits[0], "ai_yes": hits[1], "ci_hi": ratio_hi, "heldout_ci": precision_ci, "kept": False}
    assert calibrate.outcome_class(record) == expected


def test_historical_migration_via_promote_is_idempotent_and_keeps_passes(tmp_path):
    registry = tmp_path / "registry.json"; pw.save(registry, check.load_registry())
    record = tmp_path / "calibrations.md"; record.write_text("# History\n\nHistorical results stay here.\n")
    args = ["promote", "--reclassify", "--into", str(registry), "--calibrations", str(record)]
    calibrate.main(args)
    after = registry.read_bytes(), record.read_bytes()
    calibrate.main(args)
    assert after == (registry.read_bytes(), record.read_bytes())
    reg = pw.read_json(registry)
    assert reg["tells"]["tricolon"]["status"] == "kept"
    assert reg["tells"]["corrective_framing"]["status"] == "lead"
    assert reg["tells"]["corrective_framing"]["calibration"]["outcome"] == "inconclusive on HAP-E-2"
    assert reg["tells"]["paired_words"]["calibration"]["outcome"] == "rejected"
    assert "inconclusive on HAP-E-2" in record.read_text()
