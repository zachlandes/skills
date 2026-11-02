"""Intent (SCR-194 report): one Jev request per sentence pinned to jev-1.14.0, asking only the kept tells;
flagged sentences with bands and rates against baselines; leads never shown as tells; spend cap in code;
the key only in the request header."""
import json

import pytest

import os

import check
import jev
from conftest import FAKE_KEY

# Pinned registry from the SCR-194 pilot, so these tests do not move when a later calibration changes tells.json
PILOT = os.path.join(os.path.dirname(__file__), "fixtures", "tells_pilot_era.json")

TEXT = """Notes on the build

The server crashed overnight, leaving three teams without a build. Testing every change by hand takes about an hour.
The new process is faster, cheaper and easier to audit. This is not a tooling problem; it is a trust problem.
"""


def yes_for(tell, sentence):
    hot = {"participial_clause": "leaving three teams", "tricolon": "faster, cheaper and easier",
           "corrective_framing": "not a tooling problem"}
    if tell in hot and hot[tell] in sentence:
        return 0.95
    return 0.2 if (tell == "tricolon" and "hand takes" in sentence) else 0.02


def write(tmp_path, text=TEXT, name="in.txt"):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_one_request_per_sentence_kept_tells_only_pinned(tmp_path, mock_factory, capsys):
    m = mock_factory(yes_if=yes_for)
    assert check.main([write(tmp_path), "--tells-file", PILOT, "--json", str(tmp_path / "r.json")]) == 0
    assert len(m.requests) == 4  # 4 sentences, heading not sent
    for body in m.requests:
        assert body["model"] == "jev-1.14.0"
        assert set(body["questions"]) == {"participial_clause", "tricolon"}
        assert set(body["state"]) == {"sentence"}
    rep = json.load(open(tmp_path / "r.json"))
    assert [f["sentence"][:21] for f in rep["tells"]["participial_clause"]["flagged"]] == ["The server crashed ov"]
    tri = rep["tells"]["tricolon"]
    assert [f["p"] for f in tri["flagged"]] == [0.95]
    assert tri["unsure"] == []  # 0.2 is below the tricolon t_lo of 0.5
    assert rep["leads"] == {}
    assert tri["baselines"][-1]["human"]["per1k"] > 0 and tri["vs_human"] is not None


def test_leads_listed_apart_and_never_in_tells(tmp_path, mock_factory, capsys):
    m = mock_factory(yes_if=yes_for)
    check.main([write(tmp_path), "--tells-file", PILOT, "--leads", "--json", str(tmp_path / "r.json")])
    out = capsys.readouterr().out
    assert "corrective_framing" in m.requests[0]["questions"]
    assert "signpost_opener" not in m.requests[0]["questions"]  # rejected tells are never asked
    rep = json.load(open(tmp_path / "r.json"))
    assert "corrective_framing" not in rep["tells"] and "corrective_framing" in rep["leads"]
    assert out.index("TELLS (validated)") < out.index("LEADS (not validated")
    assert "baselines" not in rep["leads"]["corrective_framing"]


def test_key_only_in_header(tmp_path, mock_factory, capsys):
    m = mock_factory(yes_if=yes_for)
    check.main([write(tmp_path), "--tells-file", PILOT, "--json", str(tmp_path / "r.json")])
    cap = capsys.readouterr()
    assert set(m.auth) == {"Bearer " + FAKE_KEY}
    assert FAKE_KEY not in cap.out + cap.err + (tmp_path / "r.json").read_text()
    assert all(FAKE_KEY not in json.dumps(b) for b in m.requests)


def test_estimate_over_cap_sends_nothing(tmp_path, mock_factory):
    m = mock_factory()
    with pytest.raises(SystemExit) as e:
        check.main([write(tmp_path), "--cap-usd", "0.000001"])
    assert "exceeds the cap" in str(e.value)
    assert m.requests == []


def test_ledger_stops_requests_mid_run(mock_factory):
    m = mock_factory()
    body = jev.build_body({"sentence": "The server crashed overnight, leaving three teams without a build."},
                          {"tricolon": check.load_registry(PILOT)["tells"]["tricolon"]["question"]})
    one = jev.estimate_tokens(body)
    ledger = jev.Ledger(None, jev.usd(one * 2.5))  # room for two reserved requests at a time, then the actual usage
    results = [jev.ask(body, FAKE_KEY, ledger, jev.endpoint_for()) for _ in range(40)]
    sent = [r for r in results if "answers" in r]
    refused = [r for r in results if r.get("error", "").startswith("spend cap")]
    assert len(sent) == len(m.requests) and refused
    assert ledger.spent <= jev.usd(one * 2.5)


def test_other_model_in_response_is_an_error(tmp_path, mock_factory):
    mock_factory(yes_if=yes_for, model_override="jev-1.13.0")
    assert check.main([write(tmp_path), "--tells-file", PILOT]) == 1


def test_non_loopback_test_endpoint_refused(monkeypatch):
    monkeypatch.setenv("AITELLS_TEST_ENDPOINT", "https://example.com/v1")
    with pytest.raises(jev.JevError):
        jev.endpoint_for()


def test_key_sources(tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("OTHER_SECRET=nope\nexport TYPESAFE_API_KEY='abc123'\n")
    assert jev.read_key(env_file=str(env)) == "abc123"
    kf = tmp_path / "k"
    kf.write_text("filekey\n")
    kf.chmod(0o644)
    with pytest.raises(jev.JevError, match="private"):
        jev.read_key(key_file=str(kf))
    kf.chmod(0o600)
    assert jev.read_key(key_file=str(kf)) == "filekey"
    env.write_text("OTHER_SECRET=nope\n")
    with pytest.raises(jev.JevError) as e:
        jev.read_key(env_file=str(env))
    assert "nope" not in str(e.value)


def test_unknown_or_rejected_tell_cannot_be_forced():
    reg = check.load_registry(PILOT)
    with pytest.raises(SystemExit):
        check.select_tells(reg, ["signpost_opener"], leads=True)
    with pytest.raises(SystemExit):
        check.select_tells(reg, ["corrective_framing"], leads=False)


def test_shipped_registry_is_consistent():
    """A kept tell must have passed its latest calibration and carry baselines; no tell may be asked without a question."""
    reg = check.load_registry()
    assert reg["model"] == jev.MODEL
    for name, t in reg["tells"].items():
        assert t["status"] in ("kept", "lead", "rejected"), name
        assert {"question", "what_counts", "not", "examples"} <= set(t["question"]["instructions"]), name
        if t["status"] == "kept":
            assert t["calibration"]["kept_by_rule"] is True and t["baselines"], name
            assert t["calibration"]["ratio"] >= 2.0 and t["calibration"]["heldout_precision"] >= 0.8, name
