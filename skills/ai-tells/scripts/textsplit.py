"""Turn a page or text (HTML, Markdown or plain) into sentences, with headings set apart.

Pure standard library, so the checker runs without a language model or a parser install.
A unit is {"kind": "sentence"|"heading", "text": str}. Only sentences go to Jev.
"""
import html
import re
from html.parser import HTMLParser

MIN_WORDS = 3
ABBREV = {"e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "fig", "figs", "no", "nos", "al", "cf",
          "approx", "inc", "ltd", "st", "jr", "sr", "u.s", "eq", "eqs", "sec", "vol", "pp", "ca", "est", "dept"}
_BOUNDARY = re.compile(r"""([.!?]+["'”’)\]]*)(\s+)""")
_OPENER = re.compile(r"""["'“‘(\[]*[A-Z]""")


def split_sentences(block):
    """Split one paragraph into sentences. Abbreviations, initials and "et al." do not end one."""
    block = re.sub(r"\s+", " ", block).strip()
    out, start = [], 0
    for m in _BOUNDARY.finditer(block):
        head = block[start:m.start(1)]
        tail = block[m.end():]
        if not tail or not _OPENER.match(tail):
            continue
        last = re.split(r"\s+", head)[-1].lstrip("(\"'“‘[") if head else ""
        if m.group(1)[0] == ".":
            low = last.lower()
            if low in ABBREV or re.fullmatch(r"[A-Z]", last) or re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]", last):
                continue
        out.append(block[start:m.end(1)].strip())
        start = m.end()
    rest = block[start:].strip()
    if rest:
        out.append(rest)
    return out


def _units(blocks):
    """blocks: (kind, text) pairs, kind 'p' or 'h'. Sentences under MIN_WORDS words are dropped."""
    units = []
    for kind, text in blocks:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if kind == "h":
            units.append({"kind": "heading", "text": text})
            continue
        for s in split_sentences(text):
            if len(s.split()) >= MIN_WORDS:
                units.append({"kind": "sentence", "text": s})
    return units


_SKIP = {"script", "style", "svg", "noscript", "template", "pre", "code", "head", "textarea"}
_BLOCK = {"p", "li", "td", "th", "div", "figcaption", "summary", "dt", "dd", "blockquote", "tr", "section",
          "article", "ul", "ol", "table", "br", "caption", "details", "main", "header", "footer", "aside", "nav"}
_HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.buf, self.skip, self.kind = [], [], 0, "p"

    def flush(self):
        if self.buf:
            self.blocks.append((self.kind, "".join(self.buf)))
        self.buf, self.kind = [], "p"

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif tag in _HEAD:
            self.flush(); self.kind = "h"
        elif tag in _BLOCK:
            self.flush()

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in _HEAD or tag in _BLOCK:
            self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.buf.append(data)


def from_html(text):
    p = _Html()
    p.feed(text)
    p.close()
    p.flush()
    return _units(p.blocks)


def _md_inline(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"(\*\*|__|\*|`)", "", s)
    return html.unescape(s)


def from_markdown(text):
    blocks, para, fence = [], [], False

    def flush():
        if para:
            blocks.append(("p", " ".join(para)))
        para.clear()

    for line in text.splitlines():
        s = line.strip()
        if s.startswith(("```", "~~~")):
            flush(); fence = not fence; continue
        if fence or s.startswith("|") or re.fullmatch(r"[-*_=]{3,}", s):
            if not fence:
                flush()
            continue
        if not s:
            flush(); continue
        m = re.match(r"(#{1,6})\s+(.*)", s)
        if m:
            flush(); blocks.append(("h", _md_inline(m.group(2)).rstrip("# "))); continue
        s = re.sub(r"^(?:>\s*)+", "", s)
        li = re.match(r"(?:[-*+]|\d+[.)])\s+(.*)", s)
        if li:
            flush(); s = li.group(1)
            blocks.append(("p", _md_inline(s))); continue
        para.append(_md_inline(s))
    flush()
    return _units(blocks)


def from_plain(text):
    blocks = []
    for para in re.split(r"\n\s*\n", text):
        flat = re.sub(r"\s+", " ", para).strip()
        if not flat:
            continue
        # A short block with no closing punctuation is a title or heading, not a sentence
        short_title = len(flat.split()) <= 10 and not re.search(r"[.!?][\"'”’)]?$", flat)
        blocks.append(("h" if short_title else "p", flat))
    return _units(blocks)


def detect_format(text, path=None):
    p = (path or "").lower()
    if p.endswith((".html", ".htm")):
        return "html"
    if p.endswith((".md", ".markdown")):
        return "markdown"
    if p.endswith(".txt"):
        return "plain"
    head = text.lstrip()[:2000].lower()
    if head.startswith("<!doctype html") or "<html" in head or re.search(r"<(p|div|h[1-6]|body)[\s>]", head):
        return "html"
    if re.search(r"^#{1,6}\s+\S", text, re.M) or re.search(r"\]\(https?://", text):
        return "markdown"
    return "plain"


def extract(text, fmt=None, path=None):
    fmt = fmt or detect_format(text, path)
    units = {"html": from_html, "markdown": from_markdown, "plain": from_plain}[fmt](text)
    return fmt, units
