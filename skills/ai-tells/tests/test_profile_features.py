"""Synthetic feature fixtures; never client text or generated corpus pages."""
import math

import pytest

import check
import profile_features as pf
import textsplit


def units(text, fmt="markdown"):
    return textsplit.extract(text, fmt, positional=True)[1]


def answers_for(us, value=.1):
    qs = pf.questions(check.load_registry())
    return {r["id"]: {name: value for name in r["questions"]} for r in pf.requests(us, qs)}


def test_positions_keep_legacy_dictionaries_and_share_boundaries():
    text = "# A heading\n\n**Reason:** The toy runs. This is another sentence. A third sentence follows.\n\n- A list item follows.\n  It continues on another line."
    us = units(text)
    assert [{k: u[k] for k in ("kind", "text")} for u in us] == textsplit.extract(text, "markdown")[1]
    sentences = [u for u in us if u["kind"] == "sentence"]
    assert sentences[0]["paragraph"] == sentences[2]["paragraph"]
    assert sentences[0]["bold_leadin"] and not sentences[0]["list_item"]
    assert sentences[-1]["list_item"] and sentences[-1]["paragraph"] == sentences[-2]["paragraph"]
    assert all(s["section"] == 1 for s in sentences)


@pytest.mark.parametrize("text,fmt", [
    ("## A heading\n\n**Reason:** The toy runs. It runs again.\n\n- A list sentence follows.", "markdown"),
    ("<h2>A heading</h2><p><strong>Reason:</strong> The toy runs. It runs again.</p><ul><li>A list sentence follows.</li></ul>", "html")])
def test_one_rendering_preserves_lists_and_bold(text, fmt):
    us = units(text, fmt)
    rendered = pf.render(us)
    again = units(rendered, "html")
    assert again == us
    f = pf.measure(us, answers_for(us), ([], []))
    assert f["F17"]["rate"] == .5
    assert f["F18"]["rate"] == pytest.approx(1 / 3)


def test_fixed_question_shape_and_positional_units():
    us = units("## A heading\n\nFirst toy sentence here. Second toy sentence here. Last toy sentence here.\n\nAnother toy paragraph begins.\n\nFinal toy paragraph closes.")
    qs = pf.questions(check.load_registry())
    jobs = pf.requests(us, qs)
    sentences = [j for j in jobs if len(j["questions"]) == 12]
    assert len(sentences) == 5
    assert all(set(j["state"]) == {"sentence"} and list(j["questions"]) == pf.SENTENCE_NAMES for j in sentences)
    assert next(j for j in jobs if j["id"] == "p1")["state"]["last_sentence"] == "Last toy sentence here."
    assert len([j for j in jobs if j["id"].startswith("section:")]) == 1
    assert next(j for j in jobs if j["id"] == "page")["state"]["last_paragraph"] == "Final toy paragraph closes."
    for name in pf.SENTENCE_NAMES[:11]:
        assert qs[name] == check.load_registry()["tells"][name]["question"]


def test_code_counts_denominators_transforms_and_nonapplicability():
    us = units("## Heading: ignored\n\nThe toy — a sample – another sample -- ends; it can't fail at 12:30 or https://example.org/a:9. Label: robustly works.\n\n- A list; includes: punctuation.")
    f = pf.measure(us, answers_for(us), (["robust"], ["toy"]))
    assert f["F19"]["k"] == 3
    assert f["F20"]["k"] == 1
    assert f["F21"]["k"] == 1
    assert f["F22"]["k"] == 1
    assert f["F23"]["k"] == 2
    assert f["F13"]["n"] == 0 and f["F13"]["value"] is None
    assert f["F15"]["n"] == 0 and f["F15"]["value"] is None
    assert f["F20"]["n"] < f["F19"]["n"]
    assert f["F1"]["value"] == math.log(.5 / (f["F1"]["n"] + .5))
    assert f["F19"]["value"] == math.log(3.5 / f["F19"]["n"] * 1000)


def test_repeated_frame_requires_two_other_blocks_not_just_one():
    us = units("The toy begins here.\n\nThe toy repeats here.\n\nA different frame follows.")
    assert pf.measure(us, answers_for(us), ([], []))["F16"]["k"] == 0
    us += [dict(us[0], id="s9999", paragraph="p4", text="The toy repeats again.")]
    assert pf.measure(us, answers_for(us), ([], []))["F16"]["k"] == 3


def test_original_midpoint_and_missing_answers_fail_closed():
    us = units("A toy sentence appears. Another toy sentence follows.")
    answers = answers_for(us, .5)
    f = pf.measure(us, answers, ([], []))
    assert f["F1"]["k"] == 2
    assert pf.measure(us, answers, ([], []), soft=True)["F1"]["k"] == 1
    del answers["s0001"]["tricolon"]
    with pytest.raises(ValueError, match="missing"):
        pf.measure(us, answers, ([], []))


def test_cooccurrence_uses_distinct_rhetorical_members_and_own_opportunities():
    us = units("One toy sentence appears. Another toy sentence follows. Last toy sentence closes.\n\nA second paragraph appears.")
    a = answers_for(us, 0.)
    a["s0001"]["tricolon"] = 1
    a["s0002"]["participial_clause"] = 1
    f = pf.measure(us, a, ([], []))
    expected = ((1 - .75 ** 3) ** 2 + .25 ** 2) / 2
    assert f["F26"]["observed"] == .5
    assert f["F26"]["rate"] == pytest.approx(.5 - expected)
    a["s0002"]["participial_clause"] = 0
    a["s0002"]["tricolon"] = 1
    assert pf.measure(us, a, ([], []))["F26"]["observed"] == 0


def test_vocabulary_reads_only_lists_and_rejects_hash_drift(tmp_path, monkeypatch):
    path = tmp_path / "banlist.md"
    path.write_text('# Personal notes must not be counted\n\nWords (stem match): robust, delv\n\nPhrases: "deep dive"; "toy phrase"\n\nNOT banned: secret\n')
    monkeypatch.setattr(pf, "BANLIST_SHA256", pf.file_hash(path))
    assert pf.load_banlist(path) == (["robust", "delv"], ["deep dive", "toy phrase"])
    path.write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        pf.load_banlist(path)


def test_long_windows_headings_no_headings_and_oversized_sentence():
    sentence = "A synthetic toy sentence has exactly eleven small plain words here."
    for text in ("\n\n".join("## Section\n\n" + " ".join([sentence] * 35) for _ in range(8)),
                 " ".join([sentence] * 250), " ".join(["word"] * 2500) + "."):
        us = units(text)
        windows = pf.windows(us)
        sizes = [sum(len(u["text"].split()) for u in w if u["kind"] == "sentence") for w in windows]
        assert len(windows) >= 3 and all(250 <= n <= 1200 for n in sizes)
        assert sum(sizes) == sum(len(u["text"].split()) for u in us if u["kind"] == "sentence")
