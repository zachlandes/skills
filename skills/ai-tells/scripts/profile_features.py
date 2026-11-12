"""Named profile measurements and arithmetic shared by calibration and checking.

Standard library only; neither labels nor source classes enter feature extraction.
"""
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict

import textsplit

BANLIST_SHA256 = "c99ec1b9a80850e22319ac34514df5d381f53c765832278dffa79f284feb88a4"
SENTENCE_NAMES = ["tricolon", "participial_clause", "corrective_framing", "importance_flag",
                  "signpost_opener", "subject_clause_passive", "that_relative_subject", "paired_words",
                  "performed_hedging", "reduced_relative", "nominal_pileup", "staged_reveal"]
NAMES = SENTENCE_NAMES + ["paragraph_kicker", "section_opener_verdict", "closing_recap", "repeated_frame",
                         "bold_leadin", "list_share", "em_dash", "semicolon", "colon", "contraction",
                         "stock_vocabulary", "sentence_length_spread", "mean_sentence_length", "cooccurrence_excess"]
IDS = [f"F{i}" for i in range(1, 27)]
RHETORICAL = ["F1", "F2", "F3", "F4", "F5", "F9", "F12", "F13", "F14"]
GROUPS = {"jev_rhetorical": ["F1", "F2", "F3", "F4", "F5", "F9", "F12"],
          "jev_grammatical": ["F6", "F7", "F8", "F10", "F11"], "jev_positional": ["F13", "F14", "F15"],
          "format": ["F16", "F17", "F18"], "punctuation": ["F19", "F20", "F21", "F22"],
          "vocabulary": ["F23"], "rhythm": ["F24", "F25"], "cooccurrence": ["F26"]}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def definitions():
    units = ["sentences"] * 12 + ["paragraphs_3plus", "section_first_sentences", "pages_3plus_paragraphs",
                                  "blocks", "blocks", "sentences"] + ["words"] * 5 + ["page"] * 3
    rules = ["empirical_logit"] * 18 + ["log_per1k"] * 5 + ["identity"] * 3
    return {fid: {"name": name, "unit": unit, "transform": transform}
            for fid, name, unit, transform in zip(IDS, NAMES, units, rules)}


def question(question, counts, exclude, yes, no):
    return {"type": "noul", "instructions": {"question": question, "what_counts": counts,
            "not": exclude, "examples": {"yes": yes, "no": no}},
            "criteria": {"true": counts, "false": "The specified construction is absent."}}


def questions(registry):
    out = {name: registry["tells"][name]["question"] for name in SENTENCE_NAMES[:11]}
    out["staged_reveal"] = question(
        "Does `sentence` delay its main point behind a setup, then reveal it after a colon, dash or question?",
        "A setup promises or withholds a point; a colon, dash or question introduces the delayed point.",
        "NOT an ordinary label, definition, list, quoted speech, time or question seeking an answer.",
        "The surprising part is this: nobody used the result.", "The service listens on port 80.")
    out["paragraph_kicker"] = question(
        "Does `last_sentence` restate `paragraph` as a quotable closing line?",
        "The final sentence compresses an already supported point into a punchline or maxim.",
        "NOT a new fact, example, qualification or next step; NOT a necessary conclusion adding information.",
        "We tried every shortcut. Each failed under load. Speed without trust is no speed at all.",
        "We tried every shortcut. Each failed under load. The next trial starts Monday.")
    out["section_opener_verdict"] = question(
        "Does `sentence`, the first sentence after a heading, state a verdict before giving support?",
        "A conclusion or evaluative judgment placed at the start of a section before its reasons.",
        "NOT a topic introduction, neutral definition, factual chronology or instruction.",
        "This approach is the wrong choice for most teams.", "The protocol has two message types.")
    out["closing_recap"] = question(
        "Does `last_paragraph` only restate points already in `preceding_paragraphs`?",
        "The final paragraph recaps earlier claims without adding a fact, qualification or next action.",
        "NOT a conclusion adding new reasoning, an unanswered question or a concrete next step.",
        "In short, the cache is faster and cheaper, as the earlier tests showed.",
        "We will repeat the test on Monday with a larger cache.")
    return out


def load_banlist(path, expected=None):
    expected = BANLIST_SHA256 if expected is None else expected
    if file_hash(path) != expected:
        raise ValueError("banlist hash differs from registration")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    stems = re.search(r"^Words \(stem match\): (.+)$", text, re.M)
    phrases = re.search(r"^Phrases: (.+)$", text, re.M)
    if not stems or not phrases:
        raise ValueError("banlist needs Words (stem match) and Phrases lines")
    return [s.strip().casefold() for s in stems[1].split(",")], re.findall(r'"([^"]+)"', phrases[1])


def blocks(units, prose_only=False):
    grouped = defaultdict(list)
    for u in units:
        if u["kind"] == "sentence" and not (prose_only and u["list_item"]):
            grouped[u["paragraph"]].append(u)
    return dict(grouped)


def requests(units, qs):
    """One fixed 12-question sentence request, with separate positional passes."""
    out = []
    seen_sections = set()
    for u in units:
        if u["kind"] != "sentence":
            continue
        out.append({"id": u["id"], "state": {"sentence": u["text"]},
                    "questions": {n: qs[n] for n in SENTENCE_NAMES}})
        if u["section"] and u["section"] not in seen_sections:
            seen_sections.add(u["section"])
            out.append({"id": f"section:{u['section']}", "state": {"sentence": u["text"]},
                        "questions": {"section_opener_verdict": qs["section_opener_verdict"]}})
    paras = blocks(units, True)
    for pid, ss in paras.items():
        if len(ss) >= 3:
            out.append({"id": pid, "state": {"paragraph": " ".join(s["text"] for s in ss),
                        "last_sentence": ss[-1]["text"]}, "questions": {"paragraph_kicker": qs["paragraph_kicker"]}})
    if len(paras) >= 3:
        ps = [" ".join(s["text"] for s in ss) for ss in paras.values()]
        out.append({"id": "page", "state": {"last_paragraph": ps[-1], "preceding_paragraphs": ps[:-1]},
                    "questions": {"closing_recap": qs["closing_recap"]}})
    return out


def transform(fid, row):
    if not row["n"]:
        return None
    i = int(fid[1:])
    if i <= 18:
        return math.log((row["k"] + .5) / (row["n"] - row["k"] + .5))
    if i <= 23:
        return math.log((row["k"] + .5) / row["n"] * 1000)
    return row["rate"]


def measure(units, answers, banlist, soft=False):
    """Answers are original, untagged answers keyed by request id, never replay averages."""
    ss = [u for u in units if u["kind"] == "sentence"]
    if not ss:
        raise ValueError("page has no eligible sentences")
    bs, ps = blocks(units), blocks(units, True)
    first_sections = {}
    for s in ss:
        if s["section"]:
            first_sections.setdefault(s["section"], s)
    features = {}
    probabilities = defaultdict(dict)

    def add(fid, k, n, fired=(), **extra):
        rate = k / n if n else None
        if 19 <= int(fid[1:]) <= 23 and rate is not None:
            rate *= 1000
        features[fid] = {"k": k, "n": n, "rate": rate, "fired": list(fired), **extra}
        features[fid]["value"] = transform(fid, features[fid])

    def jev_feature(fid, items):
        name = NAMES[int(fid[1:]) - 1]
        values, fired = [], []
        for rid, display in items:
            p = answers.get(rid, {}).get(name)
            if not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError(f"missing or invalid original answer: {rid}/{name}")
            probabilities[fid][display] = p
            values.append(p if soft else float(p >= .5))
            if p >= .5:
                fired.append(display)
        add(fid, sum(values), len(items), fired)

    for fid in IDS[:12]:
        jev_feature(fid, [(s["id"], s["id"]) for s in ss])
    jev_feature("F13", [(pid, pid) for pid, sentences in ps.items() if len(sentences) >= 3])
    jev_feature("F14", [(f"section:{sec}", s["id"]) for sec, s in first_sections.items()])
    jev_feature("F15", [("page", next(reversed(ps)))] if len(ps) >= 3 else [])
    frames = {pid: tuple(re.findall(r"[\w’']+", " ".join(s["text"] for s in sentences).casefold())[:2])
              for pid, sentences in bs.items()}
    counts = Counter(v for v in frames.values() if len(v) == 2)
    fired = [pid for pid, frame in frames.items() if len(frame) == 2 and counts[frame] >= 3]
    add("F16", len(fired), len(bs), fired)
    fired = [pid for pid, sentences in bs.items() if sentences[0]["bold_leadin"]]
    add("F17", len(fired), len(bs), fired)
    fired = [s["id"] for s in ss if s["list_item"]]
    add("F18", len(fired), len(ss), fired)
    text = " ".join(s["text"] for s in ss)
    words = len(text.split())
    prose = " ".join(s["text"] for sentences in ps.values() for s in sentences)
    prose_words = len(prose.split())
    add("F19", len(re.findall(r"—| – |(?<=\w)\s*--\s*(?=\w)", text)), words)
    add("F20", prose.count(";"), prose_words)
    cleaned = re.sub(r"https?://\S+|\b\d{1,2}:\d{2}(?::\d{2})?\b", "", prose)
    add("F21", cleaned.count(":"), prose_words)
    add("F22", len(re.findall(r"\b\w+(?:n['’]t|['’](?:re|ve|ll|d|m))\b|\b(?:it|that|there|here|what|who|where|how)['’]s\b", text, re.I)), words)
    stems, phrases = banlist
    normalized = re.sub(r"\s+", " ", text.casefold().replace("’", "'"))
    vocab = sum(1 for token in re.findall(r"\b[\w-]+\b", normalized) if any(token.startswith(s) for s in stems))
    vocab += sum(len(re.findall(r"(?<!\w)" + re.escape(p.casefold()) + r"(?!\w)", normalized)) for p in phrases)
    add("F23", vocab, words)
    lengths = [len(s["text"].split()) for s in ss]
    mean = statistics.mean(lengths)
    add("F24", statistics.pstdev(lengths) / mean, 1)
    add("F25", mean, 1)
    observed, expected = [], []
    for pid, sentences in ps.items():
        present, chances = [], []
        for fid in RHETORICAL:
            eligible = ([pid] if len(sentences) >= 3 else []) if fid == "F13" else [s["id"] for s in sentences]
            vals = [probabilities[fid][i] for i in eligible if i in probabilities[fid]]
            present.append(1 - math.prod(1 - (p if soft else float(p >= .5)) for p in vals))
            rate = features[fid]["rate"] or 0
            chances.append(1 - (1 - rate) ** len(vals))

        def at_least_two(probs):
            zero = math.prod(1 - p for p in probs)
            one = sum(p * math.prod(1 - q for j, q in enumerate(probs) if j != i) for i, p in enumerate(probs))
            return max(0., 1 - zero - one)

        observed.append(at_least_two(present))
        expected.append(at_least_two(chances))
    obs = statistics.mean(observed) if observed else 0
    excess = obs - statistics.mean(expected) if expected else 0
    add("F26", excess, 1 if ps else 0, [pid for pid, p in zip(ps, observed) if p >= .5], observed=obs)
    return features


def render(units):
    """One HTML template for all public sources and generated pages."""
    import html
    out, current = [], []

    def flush():
        if current:
            tag = "li" if current[0]["list_item"] else "p"
            text = html.escape(" ".join(s["text"] for s in current))
            if current[0]["bold_leadin"]:
                m = re.match(r"^(.+?[.:])(\s|$)", text)
                if m:
                    text = "<strong>" + m[1] + "</strong>" + text[m.end(1):]
            out.append(f"<{tag}>{text}</{tag}>")
            current.clear()
    for u in units:
        if u["kind"] == "heading":
            flush(); out.append("<h2>" + html.escape(u["text"]) + "</h2>")
        else:
            if current and current[0]["paragraph"] != u["paragraph"]:
                flush()
            current.append(u)
    flush()
    return "\n".join(out)


def windows(units, maximum=1200, minimum=250):
    """Prefer heading boundaries; preserve sentence ids across windows."""
    words = lambda us: sum(len(u["text"].split()) for u in us if u["kind"] == "sentence")
    if words(units) <= maximum:
        return [units]
    sections, chunk = [], []
    for u in units:
        if u["kind"] == "heading" and words(chunk):
            sections.append(chunk); chunk = []
        if u["kind"] == "sentence" and len(u["text"].split()) > maximum:
            tokens = u["text"].split()
            for i in range(0, len(tokens), maximum):
                part = dict(u, text=" ".join(tokens[i:i + maximum]), id=f"{u['id']}.{i // maximum + 1}")
                chunk.append(part)
        else:
            chunk.append(u)
    if chunk:
        sections.append(chunk)
    out, chunk = [], []
    for section in sections:
        if words(chunk) >= minimum and words(chunk) + words(section) > maximum:
            out.append(chunk); chunk = []
        for u in section:
            if u["kind"] == "sentence":
                block_words = words([v for v in section if v.get("paragraph") == u["paragraph"]])
                paragraph_break = (u["first_in_block"] and words(chunk) >= minimum and block_words <= maximum
                                   and words(chunk) + block_words > maximum)
                if paragraph_break or words(chunk) + words([u]) > maximum:
                    out.append(chunk); chunk = []
            chunk.append(u)
    if chunk:
        if out and words(chunk) < minimum:
            while words(chunk) < minimum and out[-1]:
                donor = out[-1].pop()
                need = minimum - words(chunk)
                if donor["kind"] == "sentence" and len(donor["text"].split()) > need:
                    tokens = donor["text"].split()
                    out[-1].append(dict(donor, text=" ".join(tokens[:-need]), id=donor["id"] + ".head"))
                    chunk.insert(0, dict(donor, text=" ".join(tokens[-need:]), id=donor["id"] + ".tail"))
                else:
                    chunk.insert(0, donor)
        out.append(chunk)
    return [u for u in out if words(u)]
