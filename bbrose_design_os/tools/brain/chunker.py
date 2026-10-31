"""THE BRAIN — the register and the queue chunked per §section, each chunk's status MEASURED from the
register's own supersession idiom (§BH9(b), OWNER_BLOCKER_CLEARANCE.md:14236-14237: no in-place markers —
a supersession lives in the SUPERSEDING section and quotes the superseded passage), never inferred.

Chunks: every '## ' block (level 2), every '### ' sub-block (level 3) and every lettered item paragraph
(level 4: a line opening with an id such as **AD5(a) — … or **O1. …). A chunk carries the id its heading
OPENS with (a ruling: '## §AC — …', '## 2026-09-08 — OWNER GOAL §BH40: …', '## A. …', '### §BH18(a) — …',
'**AU6(a) — …'); a block whose heading only CITES ids ('## ANSWERED — §AD …', '## THE §AE6(a) AUDIT …',
every block of the review queue) carries no id of its own — it is UNCLASSIFIED and its refs are recorded,
so brain.ruling on a ruling lists the blocks about it.

Statuses:
  LIVE               — no later sentence of the same file names the chunk, whole, as superseded
  SUPERSEDED-BY §X   — a later sentence of the same file, inside chunk §X, names it whole as superseded
  UNCLASSIFIED       — the block opens with no id the idiom can name; its status is not measurable
  ABSENT             — (brain.ruling) an id that heads no chunk, e.g. §BH11, the skipped letter
A sentence superseding a quoted phrase, clause, citation, figure or row INSIDE a chunk leaves it LIVE and is
recorded beneath it as a note (scope PART); a quoted, conditional, negated or cross-file sentence is a note
of that kind. Every note carries the line it was measured at.
"""
import re

ID = r"§?[A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*"
ID_TOKEN_RE = re.compile(r"§[A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*|(?<![\w§/\-`])[A-Z]{1,2}[0-9]{1,2}(?:\([a-z0-9]{1,4}\))*(?![\w])")
DATE_RE = r"(?:\d{4}-\d{2}-\d{2}(?:\s*\([^)]*\))?\s+—\s+)?"
RULING_HEAD_RE = re.compile(r"^#{2,3}\s+" + DATE_RE + r"(?:\*\*)?(?:OWNER\s+(?:RULING/GOAL|RULING|GOAL|ROADMAP|TRANSCRIPTION\s+REPAIR)\s+|EXECUTOR-RULED\s+)?(§[A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*)")
LETTER_HEAD_RE = re.compile(r"^#{2,3}\s+([A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*)(?:\.\s|\s+—\s|\s+-\s|:\s)")
ITEM_RE = re.compile(r"^(?:\*\*(§?[A-Z]{1,3}[0-9]{1,3}(?:\([a-z0-9]{1,4}\))*)(?:\*\*\s|\.|:|\s+—|\s+-)|(§?[A-Z]{1,3}[0-9]{1,3}(?:\([a-z0-9]{1,4}\))*)(?:\.|:)\s)")
SUPERSEDE_RE = re.compile(r"supersed(?:e|es|ed|ing|ence)", re.I)
PART_WORDS = re.compile(r"\b(phrase|clause|citation|parenthetical|sentence|figure|word|words|line|paragraph|prohibition|"
                        r"instrument|value|values|hex|number|reading|row|rows|table|gloss|draft|drafts|text|passage|"
                        r"cell|column|field|identity|edition|application|only as to|as to|in place|those|the two|"
                        r"a number|numbers|message|entry|entries)\b", re.I)
COND_RE = re.compile(r"\b(if\b|until\b|on arrival|loses if|would be|would\b|may be|can be|once\b|when\b|unless\b|the moment\b|arrives?\b)|^\w+ing\b", re.I)
NEG_RE = re.compile(r"\b(not superseded|never superseded|is not|are not|supersede nothing|nothing to supersede|"
                    r"nothing dangling|no marker|does not supersede|do not supersede)\b", re.I)
DECLARE_RE = re.compile(r"\bstatus\s+(?:for|of)\s+(§?[A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*)\b"
                        r"[^.;]{0,60}?\bmeasures?\b[^.;]{0,30}?\bSUPERSEDED[\u2010-\u2015 -]BY\s+"
                        r"(§?[A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*)", re.I)


CLAUSE_SPLIT = re.compile(r"(?<=[.;:!?])\s+|,\s+(?:and|but|so|while|whereas)\s+|\s+—\s+")
QUOTE_CHARS = re.compile(r"[\"“”‘’*`]")


def _whole_scope(sentence: str, target: str) -> bool:
    """WHOLE only when, inside the clause, the target token itself is the subject of 'is superseded' (nothing but
    the token, an optional 's, and the verb between the clause start and the verb) or the bare object of
    'supersedes' (nothing but 'the' between the verb and the token). A part-noun, a quotation mark or another
    id in the subject span makes it PART."""
    bare = target[1:] if target.startswith("§") else target
    tok = r"§?" + re.escape(bare)
    for clause in CLAUSE_SPLIT.split(sentence):
        if not re.search(tok, clause): continue
        m = re.search(r"(.*?)" + tok + r"('s)?\s+(?:is|are|was|were)\s+(?:hereby\s+|now\s+|explicitly\s+)?superseded\b", clause, re.I)
        if m:
            before = m.group(1); poss = m.group(2)
            if poss: return False
            head = re.sub(r"^(the|this|that|and|so|then|also)\s+", "", before.strip(), flags=re.I)
            if head == "" or (not PART_WORDS.search(before) and not QUOTE_CHARS.search(before) and not ID_TOKEN_RE.search(before)):
                return True
            return False
        m = re.search(r"\bsupersedes?\s+(.*?)" + tok + r"\b(?!'s)", clause, re.I)
        if m:
            between = m.group(1).strip()
            return between in ("", "the", "all of", "the whole of")
    return False


def norm(tok: str) -> str:
    return tok if tok.startswith("§") else "§" + tok


def _in_quotes(s: str, pos: int) -> bool:
    return s[:pos].count('"') % 2 == 1 or s[:pos].count("“") > s[:pos].count("”")


def chunk_file(text: str, file_label: str, short: str):
    lines = text.split("\n")
    chunks = []
    for i, line in enumerate(lines, 1):
        level = 2 if line.startswith("## ") else 3 if line.startswith("### ") else None
        if level:
            refs = [norm(t) for t in ID_TOKEN_RE.findall(line)]
            m = RULING_HEAD_RE.match(line); primary = None
            if m: primary = m.group(1)
            else:
                lm = LETTER_HEAD_RE.match(line)
                if lm: primary = norm(lm.group(1))
            chunks.append({"file": file_label, "short": short, "level": level, "id": primary, "refs": list(dict.fromkeys(refs)),
                           "heading": line.strip(), "line_start": i, "line_end": None, "parent": None,
                           "measurable": primary is not None and short == "R"})
            continue
        im = ITEM_RE.match(line)
        prev_blank = i == 1 or not lines[i - 2].strip() or lines[i - 2].startswith("#")
        if im and chunks and prev_blank:
            tok = norm(im.group(1) or im.group(2))
            chunks.append({"file": file_label, "short": short, "level": 4, "id": tok, "refs": [tok], "heading": line.strip()[:160],
                           "line_start": i, "line_end": None, "parent": None, "measurable": short == "R"})
    for k, c in enumerate(chunks):
        nxt = None
        for j in range(k + 1, len(chunks)):
            if chunks[j]["level"] <= c["level"]:
                nxt = chunks[j]["line_start"]; break
        c["line_end"] = (nxt - 1) if nxt else len(lines)
        for j in range(k - 1, -1, -1):
            if chunks[j]["level"] < c["level"]:
                c["parent"] = chunks[j]["id"] or ("%s:%d" % (short, chunks[j]["line_start"])); break
    seen = {}
    for c in chunks:
        if c["id"] is None:
            c["id"] = "%s:%d" % (short, c["line_start"])
        else:
            n = seen.get(c["id"], 0) + 1; seen[c["id"]] = n
            if n > 1:
                c["also_of"] = c["id"]; c["id"] = "%s#%d" % (c["id"], n)
    return chunks


def _sentences(lines, start, end):
    out = []; buf = []; buf_line = None
    def flush():
        if buf:
            para = " ".join(buf)
            for s in re.split(r"(?<=[.!?;])\s+(?=[A-Z§*(\"'`])", para):
                if s.strip(): out.append((buf_line, s.strip()))
    for n in range(start, end + 1):
        raw = lines[n - 1]
        t = re.sub(r"^\s*>\s?", "", raw).replace("**", "").strip()
        if not t:
            flush(); buf = []; buf_line = None; continue
        if t.startswith("#"):
            flush(); buf = []; buf_line = None
            out.append((n, t.lstrip("# ").strip())); continue
        if buf_line is None: buf_line = n
        buf.append(t)
    flush()
    return out


def resolve(target: str, index: dict):
    t = target
    while t:
        if t in index: return t, target[len(t):]
        m = re.match(r"^(.*)\([a-z0-9]{1,4}\)$", t)
        if not m: break
        t = m.group(1)
    return None, target


def measure(chunks, texts):
    """texts: {file_label: text}. Applies the idiom to every sentence carrying 'supersede', and to every
    sentence that DECLARES a status outright — "the status for §T ... measures SUPERSEDED-BY §B". A
    declaration names both ends itself, so it is measured directly and is not inferred from verb
    grammar: it overrides an inferred supersession and an inference never overrides it. Its
    conditionality is read from the clause the declaration sits in, not from the whole sentence, so a
    condition attached to a neighbouring clause does not veto it; a declaration inside quotation marks
    is a report of one, not one."""
    index = {}
    for c in chunks:
        if c["measurable"] and "#" not in c["id"]: index.setdefault((c["file"], c["id"]), c)
    for c in chunks:
        c["status"] = "LIVE" if c["measurable"] else "UNCLASSIFIED"
        c["superseded_by"] = None; c["superseded_at"] = None; c["notes"] = []
    unresolved = []; sentences_seen = 0; declarations = {}
    for c in chunks:
        if c["level"] != 2: continue
        lines = texts[c["file"]].split("\n")
        for line_no, s in _sentences(lines, c["line_start"], c["line_end"]):
            dv = DECLARE_RE.search(s)
            if dv and not _in_quotes(s, dv.start()):
                dcl = next((cl for cl in CLAUSE_SPLIT.split(s) if DECLARE_RE.search(cl)), s)
                if not (COND_RE.search(dcl) or NEG_RE.search(dcl)):
                    here = {k[1]: v for k, v in index.items() if k[0] == c["file"]}
                    tname, bname = norm(dv.group(1)), norm(dv.group(2))
                    tcid, tres = resolve(tname, here)
                    bcid, bres = resolve(bname, here)
                    if tcid is not None and tres == "" and bcid is not None and bres == "":
                        tgt = index[(c["file"], tcid)]
                        tgt["notes"].append({"kind": "DECLARED", "scope": "WHOLE", "by": bname,
                                             "file": c["file"], "line": line_no, "sentence": s[:400]})
                        declarations[(c["file"], tcid)] = (bname, line_no)
                    else:
                        unresolved.append({"target": tname if tcid is None else bname, "by": c["id"],
                                           "file": c["file"], "line": line_no, "sentence": s[:300]})
            mv = SUPERSEDE_RE.search(s)
            if not mv: continue
            sentences_seen += 1
            by = c["id"]
            for sc in chunks:      # the finest chunk the sentence sits in
                if sc["file"] == c["file"] and sc["level"] > 2 and sc["line_start"] <= line_no <= sc["line_end"] and sc["measurable"]:
                    if sc["level"] >= (3 if by == c["id"] else 4): by = sc["id"]
            targets = list(dict.fromkeys(norm(t) for t in ID_TOKEN_RE.findall(s)))
            quoted = _in_quotes(s, mv.start())
            kind0 = "QUOTED" if quoted else "NEGATED" if NEG_RE.search(s) else "CONDITIONAL" if COND_RE.search(s) else None
            if not targets:
                if re.search(r"\bthis section\b", s, re.I):
                    c["notes"].append({"kind": kind0 or "SELF", "scope": "WHOLE", "by": by, "file": c["file"], "line": line_no, "sentence": s[:400]})
                continue
            for t in targets:
                cid, residual = resolve(t, {k[1]: v for k, v in index.items() if k[0] == c["file"]})
                if cid is None:
                    # cross-file: a queue sentence about a register id (or the reverse) is a note on the target there
                    other_files = {k[0] for k in index if k[0] != c["file"]}
                    placed = False
                    for of in other_files:
                        ocid, _ = resolve(t, {k[1]: v for k, v in index.items() if k[0] == of})
                        if ocid is not None:
                            index[(of, ocid)]["notes"].append({"kind": "CROSS-FILE", "scope": "PART", "by": by, "file": c["file"], "line": line_no, "sentence": s[:400]}); placed = True; break
                    if placed: pass
                    else:
                        unresolved.append({"target": t, "by": by, "file": c["file"], "line": line_no, "sentence": s[:300]})
                    continue
                tgt = index[(c["file"], cid)]
                if tgt["id"] == by and residual == "": continue
                scope = "WHOLE" if residual == "" and _whole_scope(s, t) else "PART"
                later = line_no > tgt["line_end"]
                kind = kind0 or ("SUPERSESSION" if scope == "WHOLE" else "PARTIAL")
                if kind == "SUPERSESSION" and not later: kind = "IN-PLACE"
                note = {"kind": kind, "scope": scope, "by": by, "file": c["file"], "line": line_no, "sentence": s[:400]}
                tgt["notes"].append(note)
                if kind == "SUPERSESSION" and tgt["status"] == "LIVE":
                    tgt["status"] = "SUPERSEDED-BY " + by; tgt["superseded_by"] = by; tgt["superseded_at"] = "%s:%d" % (c["file"], line_no)
    for (file_label, cid), (bname, line_no) in declarations.items():
        tgt = index[(file_label, cid)]
        tgt["status"] = "SUPERSEDED-BY " + bname; tgt["superseded_by"] = bname
        tgt["superseded_at"] = "%s:%d" % (file_label, line_no)
    return chunks, unresolved, sentences_seen


def mentions(texts):
    """Every § token on every line of both files — the ABSENT answer's evidence and the cross-reference."""
    out = []
    for label, text in texts.items():
        for i, line in enumerate(text.split("\n"), 1):
            for t in dict.fromkeys(ID_TOKEN_RE.findall(line)):
                out.append((norm(t), label, i, line.strip()[:300]))
    return out


def run(register_text, queue_text, reg_label="OWNER_BLOCKER_CLEARANCE.md", q_label="OWNER_REVIEW_QUEUE.md"):
    chunks = chunk_file(register_text, reg_label, "R") + chunk_file(queue_text, q_label, "Q")
    chunks, unresolved, n = measure(chunks, {reg_label: register_text, q_label: queue_text})
    return chunks, unresolved, n
