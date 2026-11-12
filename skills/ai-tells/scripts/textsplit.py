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


def _units(blocks, positional=False):
    """blocks: (kind, text) pairs, kind 'p' or 'h'. Sentences under MIN_WORDS words are dropped."""
    units, paragraph, section, sentence = [], 0, 0, 0
    for block in blocks:
        kind, text = block[:2]
        bold = block[2] if len(block) > 2 else False
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if kind == "h":
            section += 1
            unit = {"kind": "heading", "text": text}
            if positional:
                unit.update(id=f"h{section}", section=section)
            units.append(unit)
            continue
        paragraph += 1
        first = True
        for s in split_sentences(text):
            if len(s.split()) >= MIN_WORDS:
                sentence += 1
                unit = {"kind": "sentence", "text": s}
                if positional:
                    unit.update(id=f"s{sentence:04d}", paragraph=f"p{paragraph}", section=section,
                                list_item=kind == "li", bold_leadin=bold, first_in_block=first)
                units.append(unit)
                first = False
    return units


_SKIP = {"script", "style", "svg", "noscript", "template", "pre", "code", "head", "textarea"}
_BLOCK = {"p", "li", "td", "th", "div", "figcaption", "summary", "dt", "dd", "blockquote", "tr", "section",
          "article", "ul", "ol", "table", "br", "caption", "details", "main", "header", "footer", "aside", "nav"}
_HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}


class _Html(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks, self.buf, self.skip, self.kind = [], [], 0, "p"
        self.in_li, self.bold, self.bold_prefix, self.prefix_done = 0, 0, "", False

    def flush(self):
        if self.buf:
            lead = bool(self.bold_prefix.strip() and re.match(
                r"^\s*[.:]", "".join(self.buf)[len(self.bold_prefix):])) or self.bold_prefix.rstrip().endswith((":", "."))
            self.blocks.append((self.kind, "".join(self.buf), lead))
        self.buf, self.kind = [], "li" if self.in_li else "p"
        self.bold_prefix, self.prefix_done = "", False

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif tag in {"b", "strong"}:
            self.bold += 1
        elif tag in _HEAD:
            self.flush(); self.kind = "h"
        elif tag in _BLOCK:
            self.flush()
            if tag == "li":
                self.in_li += 1
            self.kind = "li" if self.in_li else "p"

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif self.skip:
            return
        elif tag in {"b", "strong"}:
            self.bold = max(0, self.bold - 1)
        elif tag in _HEAD or tag in _BLOCK:
            self.flush()
            if tag == "li":
                self.in_li = max(0, self.in_li - 1)
                self.kind = "li" if self.in_li else "p"

    def handle_data(self, data):
        if not self.skip:
            if not self.prefix_done:
                if self.bold:
                    self.bold_prefix += data
                elif data.strip():
                    self.prefix_done = True
            self.buf.append(data)


def from_html(text, positional=False):
    p = _Html()
    p.feed(text)
    p.close()
    p.flush()
    return _units(p.blocks, positional)


def _md_inline(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"(\*\*|__|\*|`)", "", s)
    return html.unescape(s)


def from_markdown(text, positional=False):
    blocks, para, fence = [], [], False
    para_kind = "p"

    def flush():
        if para:
            raw = " ".join(para)
            bold = bool(re.match(r"^(?:\*\*.+?\*\*|__.+?__)(?:[.:]|(?<=\*\*)\s|(?<=__)\s)", raw)
                        and re.match(r"^(?:\*\*[^*]+[.:]\*\*|__[^_]+[.:]__|\*\*[^*]+\*\*[.:]|__[^_]+__[.:])", raw))
            blocks.append((para_kind, _md_inline(raw), bold))
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
            flush(); para_kind = "p"; continue
        m = re.match(r"(#{1,6})\s+(.*)", s)
        if m:
            flush(); blocks.append(("h", _md_inline(m.group(2)).rstrip("# "))); continue
        s = re.sub(r"^(?:>\s*)+", "", s)
        li = re.match(r"(?:[-*+]|\d+[.)])\s+(.*)", s)
        if li:
            flush(); para_kind = "li"; para.append(li.group(1)); continue
        para.append(s)
    flush()
    return _units(blocks, positional)


def from_plain(text, positional=False):
    blocks = []
    for para in re.split(r"\n\s*\n", text):
        flat = re.sub(r"\s+", " ", para).strip()
        if not flat:
            continue
        # A short block with no closing punctuation is a title or heading, not a sentence
        short_title = len(flat.split()) <= 10 and not re.search(r"[.!?][\"'”’)]?$", flat)
        blocks.append(("h" if short_title else "p", flat))
    return _units(blocks, positional)


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


def extract(text, fmt=None, path=None, positional=False):
    fmt = fmt or detect_format(text, path)
    units = {"html": from_html, "markdown": from_markdown, "plain": from_plain}[fmt](text, positional=positional)
    return fmt, units
