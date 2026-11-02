"""Intent (SCR-194 report): keep a tell only if its AI-to-human ratio is 2x or more and held-out precision is 0.8
or more, with the rule set before labelling. Fixtures are the real pilot answers and labels (600 HAP-E-2
sentences, 40 labels per tell); the decision must reproduce the one recorded in SCR-194."""
import json
import os
import shutil

import pytest

import calibrate

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
RULE = {"min_ratio": 2.0, "min_heldout_precision": 0.8}


@pytest.fixture
def run(tmp_path):
    ans = calibrate.jl(f"{FIX}/pilot_ans.jsonl")
    ids = sorted({o["id"] for o in ans})
    calibrate.write_jl(tmp_path / "sample.jsonl", [{"id": i, "source": i.split(":")[1], "sentence": "s", "words": 20} for i in ids])
    shutil.copy(f"{FIX}/pilot_ans.jsonl", tmp_path / "ans.jsonl")
    shutil.copy(f"{FIX}/label_key.json", tmp_path / "label_key.json")
    shutil.copy(f"{FIX}/labels.jsonl", tmp_path / "labels.jsonl")
    return str(tmp_path)


def test_decision_reproduces_scr194(run):
    dec = {r["tell"]: r for r in calibrate.decide(run, rule=RULE)}
    p, t, c = dec["participial_clause"], dec["tricolon"], dec["corrective_framing"]
    assert (p["t_hi"], p["ratio"], p["heldout_precision"], p["kept"]) == (0.5, 2.83, 1.0, True)
    assert (t["t_hi"], t["ratio"], t["heldout_precision"], t["kept"]) == (0.7, 2.38, 1.0, True)
    assert (c["t_hi"], c["ratio"], c["kept"]) == (0.7, 4.14, False)  # ratio passes, held-out precision 0.71 fails
    assert c["heldout_precision"] == 0.71


def test_too_rare_never_kept(run):
    # Two yes answers, both on the AI side: a huge ratio but under 5 yes answers, so it cannot be kept
    ans = calibrate.jl(f"{run}/ans.jsonl")
    ai_ids = sorted({o["id"] for o in ans if o["id"].endswith(":ai")})[:2]
    for o in ans:
        o["answers"]["corrective_framing"] = 0.95 if o["id"] in ai_ids else 0.0
    calibrate.write_jl(f"{run}/ans.jsonl", ans)
    dec = {r["tell"]: r for r in calibrate.decide(run, rule=RULE)}
    c = dec["corrective_framing"]
    assert c["too_rare"] and not c["kept"]


def test_bands_take_smallest_cutoff_with_dev_precision_080():
    dev = [(0.55, False), (0.65, True), (0.75, True), (0.85, True), (0.2, False), (0.05, False)]
    t_hi, t_lo = calibrate.bands(dev)
    assert t_hi == 0.6  # at 0.5 precision is 3/4; at 0.6 it is 3/3
    assert t_lo == 0.5  # every dev label under 0.5 is a no


def test_register_refused_after_labels_and_sheet_needs_registration(run, tmp_path, capsys):
    with pytest.raises(SystemExit, match="before labelling"):
        calibrate.main(["register", run, "--tells", "tricolon"])
    os.remove(f"{run}/labels.jsonl")
    os.remove(f"{run}/label_key.json")
    with pytest.raises(SystemExit, match="register"):
        calibrate.main(["label-sheet", run])
    calibrate.main(["register", run, "--tells", "tricolon,participial_clause"])
    calibrate.main(["label-sheet", run])
    sheet = calibrate.jl(f"{run}/label_sheet.jsonl")
    assert len(sheet) == 80 and set(sheet[0]) == {"item", "tell", "sentence"}  # blind: no probability, no source
    key = json.load(open(f"{run}/label_key.json"))
    for t, lst in key.items():
        assert len(lst) == 40 and {x["split"] for x in lst} == {"dev", "heldout"}


def test_sample_changed_after_registration_is_refused(run):
    os.remove(f"{run}/labels.jsonl")
    calibrate.main(["register", run, "--tells", "tricolon"])
    with open(f"{run}/sample.jsonl", "a") as f:
        f.write("\n")
    with pytest.raises(SystemExit, match="changed after registration"):
        calibrate.main(["label-sheet", run])


def test_run_sends_candidate_and_resumes(run, mock_factory, capsys):
    m = mock_factory()
    for f in ("ans.jsonl", "labels.jsonl", "label_key.json"):
        os.remove(f"{run}/{f}")
    rows = calibrate.jl(f"{run}/sample.jsonl")[:10]
    calibrate.write_jl(f"{run}/sample.jsonl", rows)
    calibrate.main(["run", run, "--tells", "tricolon", "--cap-usd", "0.05"])
    assert len(m.requests) == 10 and all(set(b["questions"]) == {"tricolon"} for b in m.requests)
    calibrate.main(["run", run, "--tells", "tricolon", "--cap-usd", "0.05"])
    assert len(m.requests) == 10  # nothing resent
    assert json.load(open(f"{run}/spend_ledger.json"))["requests"] == 10


def test_promote_writes_status_and_baseline(run, tmp_path):
    os.makedirs(tmp_path / "x", exist_ok=True)
    json.dump(calibrate.decide(run, rule=RULE), open(f"{run}/decision.json", "w"))
    reg_path = tmp_path / "tells.json"
    shutil.copy(os.path.join(FIX, "tells_pilot_era.json"), reg_path)
    calibrate.main(["promote", run, "--into", str(reg_path), "--id", "t1", "--ai-source", "test"])
    reg = json.load(open(reg_path))
    assert reg["tells"]["tricolon"]["status"] == "kept"
    assert reg["tells"]["corrective_framing"]["status"] == "lead"  # ratio ok, precision short: stays a lead
    assert [b["calibration"] for b in reg["tells"]["tricolon"]["baselines"]] == ["scr194-pilot", "t1"]
    assert reg["tells"]["tricolon"]["baselines"][-1]["ai_source"] == "test"
    assert reg["calibrations"][-1]["id"] == "t1"


def test_promote_demotes_a_previously_kept_tell_that_fails_to_a_lead(run, tmp_path):
    # SCR-194 kept participial_clause against Haiku; a later calibration that fails it must not leave it kept
    dec = calibrate.decide(run, rule=RULE)
    for r in dec:
        if r["tell"] == "participial_clause":
            r["kept"] = False
    json.dump(dec, open(f"{run}/decision.json", "w"))
    reg_path = tmp_path / "tells.json"
    shutil.copy(os.path.join(FIX, "tells_pilot_era.json"), reg_path)
    calibrate.main(["promote", run, "--into", str(reg_path), "--id", "t2", "--ai-source", "test"])
    reg = json.load(open(reg_path))
    assert reg["tells"]["participial_clause"]["status"] == "lead"
    assert reg["tells"]["participial_clause"]["calibration"]["kept_by_rule"] is False
