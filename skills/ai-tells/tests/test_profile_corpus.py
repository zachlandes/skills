import json
from xml.sax.saxutils import quoteattr

import pytest

import profile_corpus as pc
import profile_features as pf
import textsplit

HUMAN = " ".join(["A wooden toy has a plain red handle and four wheels."] * 24)
AI = " ".join(["This painted model rolls quietly along flat paths near the garden."] * 24)


def test_rst_keeps_only_registered_sections_and_ignores_code():
    raw = "PEP: 9999\nTitle: A toy\n\nAbstract\n========\nA toy has four wheels.\n\n.. code-block:: python\n\n   print('skip this code')\n\nMotivation\n==========\nA child can push the toy.\n\nRationale and Goals\n===================\nThis section is not registered.\n\nRationale\n=========\nThe handle stays low.\n\nReferences\n==========\nReferences are not prose here."
    md = pc.rst_to_markdown(raw)
    assert "four wheels" in md and "push the toy" in md and "handle stays low" in md
    assert "print" not in md and "not registered" not in md and "References" not in md
    rendered = pc.normalize(md, "markdown")
    assert sum(u["kind"] == "heading" for u in textsplit.extract(rendered)[1]) == 3


@pytest.mark.parametrize("source,path,raw", [
    ("peps", "peps/pep-9999.rst", "Abstract\n========\n" + HUMAN + "\n\nMotivation\n==========\n" + HUMAN),
    ("kubernetes", "content/en/docs/concepts/toy.md", "---\ntitle: ignored\n---\n## Shape\n\n" + HUMAN + "\n\n## Motion\n\n" + HUMAN),
    ("mdn", "files/en-us/learn/toy/index.md", "## Shape\n\n" + HUMAN + "\n\n## Motion\n\n" + HUMAN),
    ("go", "_content/blog/toy.article", "* Shape\n\n" + HUMAN + "\n\n* Motion\n\n" + HUMAN)])
def test_pinned_source_conversions_record_full_revision_and_hashes(source, path, raw, monkeypatch):
    spec = pc.SOURCES[source]
    full = spec["revision"].ljust(40, "0")
    calls = []
    def snapshot(root, *args):
        calls.append(args)
        if args[0] == "rev-parse":
            return full.encode() + b"\n"
        if args[0] == "ls-tree":
            return (path + "\nprivate/unregistered.md\n").encode()
        if args[0] == "show":
            assert args[1] == f"{full}:{path}"
            return raw.encode()
        raise AssertionError(args)
    monkeypatch.setattr(pc, "git", snapshot)
    rows = list(pc.repo_pages(source, "/synthetic-public-snapshot"))
    assert len(rows) == 1 and rows[0]["revision"] == full and rows[0]["rendered_sha256"] == pf.digest(rows[0]["text"])
    assert spec["repo"] in rows[0]["url"] and rows[0]["licence"] == spec["licence"]
    assert calls[0][1] == spec["revision"] + "^{commit}"


def test_stackexchange_public_export_hash_cutoff_top_answer_no_code_and_attribution(tmp_path):
    attrs = [
        {"Id": "1", "PostTypeId": "1", "CreationDate": "2020-01-01", "Title": "How does the toy roll?", "Body": "<p>A public question.</p>"},
        {"Id": "2", "ParentId": "1", "PostTypeId": "2", "CreationDate": "2020-01-02", "Score": "4", "Body": "<p>" + HUMAN + "</p>", "OwnerUserId": "123"},
        {"Id": "3", "ParentId": "1", "PostTypeId": "2", "CreationDate": "2020-01-02", "LastEditDate": "2023-01-01", "Score": "12", "Body": "<p>" + HUMAN + "</p>"},
        {"Id": "4", "ParentId": "1", "PostTypeId": "2", "CreationDate": "2020-01-02", "Score": "20", "Body": "<code>example</code><p>" + HUMAN + "</p>"}]
    path = tmp_path / "Posts.xml"
    path.write_text("<posts>" + "".join("<row " + " ".join(k + "=" + quoteattr(v) for k, v in a.items()) + "/>" for a in attrs) + "</posts>")
    rows = list(pc.stackexchange_pages("ux", path, pf.file_hash(path)))
    assert len(rows) == 1 and rows[0]["id"] == "ux:2" and rows[0]["author"] == "123"
    assert rows[0]["question"]["body"] == attrs[0]["Body"]
    with pytest.raises(ValueError, match="hash"):
        list(pc.stackexchange_pages("ux", path, "wrong"))
    with pytest.raises(ValueError, match="registered"):
        list(pc.stackexchange_pages("private-company", path, pf.file_hash(path)))


def human(i, origin="ux", genre="G1"):
    text = pc.normalize(HUMAN, "markdown")
    return {"id": f"toy-{i}", "origin": origin, "genre": genre, "text": text, "words": pc.count_words(text),
            "rendered_sha256": pf.digest(text), "revision": "synthetic-public", "licence": "synthetic"}


def generation(i):
    return {"id": f"toy-{i}", "model": "claude-opus-5-5", "effort": "high", "thinking": "adaptive",
            "prompt": "Synthetic test prompt", "system": "Synthetic test system", "text": AI}


def test_pair_filters_seed_spares_and_exact_source_stratified_half_split():
    humans = [human(i, "ux" if i < 3 else "pm") for i in range(6)]
    ai = [generation(i) for i in range(6)]
    result = pc.pair_pages(humans, ai, {"G1": 6})
    assert result == pc.pair_pages(humans, ai, {"G1": 6})
    assert sum(r["split"] == "dev" for r in result) == 6
    for origin in ("ux", "pm"):
        ndev = sum(r["origin"] == origin and r["split"] == "dev" for r in result)
        assert ndev in (2, 4)
    assert all(len({r["split"] for r in result if r["pair"] == h["id"]}) == 1 for h in humans)
    ai[0]["text"] = HUMAN
    with pytest.raises(ValueError, match="insufficient"):
        pc.pair_pages(humans, ai, {"G1": 6})
    ai[0] = generation(0); ai[0]["text"] = "As an AI, " + AI
    with pytest.raises(ValueError, match="insufficient"):
        pc.pair_pages(humans, ai, {"G1": 6})
    ai[0] = generation(0); ai[0]["effort"] = "medium"
    with pytest.raises(ValueError, match="registered"):
        pc.pair_pages(humans, ai, {"G1": 6})
    chosen = pc.sample_humans([human(i) for i in range(12)], {"G1": 10})
    assert len(chosen) == 12
    with pytest.raises(ValueError, match="supply"):
        pc.sample_humans([human(0)], {"G1": 10})


def test_brief_rejects_source_copy_and_more_than_twelve_facts():
    h = human(0)
    brief = {"title": "Toy", "problem": "Transport", "proposal": "Handle", "facts": ["Wood", "Paint"]}
    pc.check_brief(h, brief)
    brief["facts"] = ["A wooden toy has a plain red handle"]
    with pytest.raises(ValueError, match="copies"):
        pc.check_brief(h, brief)
    brief["facts"] = ["Wood"] * 13
    with pytest.raises(ValueError):
        pc.check_brief(h, brief)
