"""Intent (SCR-194 report): the checker takes any page or text and splits it into sentences with headings set apart."""
import textsplit

# Real sentences from the SCR-194 explainer check, including the abbreviation, citation and quote cases
HTML = """<!doctype html><html><head><title>x</title><style>p{color:red}</style></head><body>
<h2>What the agent knew</h2>
<p>They learn team practices, not a new tool. The figures from section 5 onward are a synthesis of those sources,
not any one author's model, and passages marked Inference are this document's own reasoning.</p>
<svg><text>Diagram label should not appear here</text></svg>
<script>var s = "Do not count this. Or this.";</script>
<ul><li>Rung 3 proves the brief was fetched, not that it was followed.</li></ul>
<p>See e.g. the design brief (Kinzel et al. 2008) for details. Dr. Smith agreed.</p>
</body></html>"""


def test_html_sentences_and_headings_apart_and_scripts_skipped():
    fmt, units = textsplit.extract(HTML)
    assert fmt == "html"
    assert units[0] == {"kind": "heading", "text": "What the agent knew"}
    sents = [u["text"] for u in units if u["kind"] == "sentence"]
    assert sents[0] == "They learn team practices, not a new tool."
    assert sents[1].startswith("The figures from section 5 onward") and sents[1].endswith("own reasoning.")
    assert "Rung 3 proves the brief was fetched, not that it was followed." in sents
    assert not any("Diagram label" in s or "Do not count" in s for s in sents)


def test_abbreviations_and_citations_do_not_split():
    sents = [u["text"] for u in textsplit.extract(HTML)[1] if u["kind"] == "sentence"]
    assert "See e.g. the design brief (Kinzel et al. 2008) for details." in sents
    assert "Dr. Smith agreed." in sents


def test_markdown_drops_code_links_and_marks():
    md = ("# Title here\n\nThe **checker** reads [the docs](https://x.example/a). It is cheap.\n\n"
          "```\nnot a sentence. at all.\n```\n\n- First item reads the diff, runs the tests and posts a comment.\n")
    fmt, units = textsplit.extract(md)
    assert fmt == "markdown"
    assert units[0] == {"kind": "heading", "text": "Title here"}
    sents = [u["text"] for u in units if u["kind"] == "sentence"]
    assert sents == ["The checker reads the docs.", "It is cheap.",
                     "First item reads the diff, runs the tests and posts a comment."]


def test_plain_text_title_is_heading_and_short_fragments_dropped():
    fmt, units = textsplit.extract("A short title\n\nThe order matters. Yes.\nIt still holds on two lines.\n")
    assert fmt == "plain"
    assert units[0]["kind"] == "heading"
    assert [u["text"] for u in units[1:]] == ["The order matters.", "It still holds on two lines."]
