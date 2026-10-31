#!/usr/bin/env python
"""THE BRAIN — a local MCP server (stdio, JSON-RPC 2.0) over var/brain/brain.sqlite. Standard library only.

Four tools — search, ruling, material, lessons — served under the server name "brain", so a session sees
brain.search / brain.ruling / brain.material / brain.lessons. Every answer cites file:line. The server opens
the index READ-ONLY and writes nothing anywhere; it is never authoritative — the file and line it cites are.
"""
import sys, os, json, sqlite3, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sources as S
import embed

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "brain", "version": "1.0"}
FORBIDDEN_FIELDS = ("bytes", "content", "locator", "absolute_path", "preview_path", "url")

TOOLS = [
    {"name": "search", "description": "Search everything the brain indexes — the register and the review queue, the sitting reports, the WATCH notes, the launchers, the prompt files, the DIP-0A record. TWO rankings run and are returned together: full text (SQLite FTS5) and meaning (§BH42(a) embeddings). Every hit carries found_by = fts | semantic | fts+semantic, so a hit that only meaning found says so. The semantic ranking is beside the full-text one, never in place of it. Every hit cites file:line, and the cited file owns the truth.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "words, or an FTS5 expression (phrases in quotes, AND/OR/NOT); plain language works for the semantic half even when FTS5 rejects it"}, "kind": {"type": "string", "description": "optional: register|queue|sitting|watch|launcher|prompt|record"}, "limit": {"type": "integer", "default": 10}, "semantic": {"type": "boolean", "default": True, "description": "run the meaning ranking beside the full-text one"}}, "required": ["query"]}},
    {"name": "ruling", "description": "A §section of the register (or the queue) → its text, measured status (LIVE / SUPERSEDED-BY §X / UNCLASSIFIED / ABSENT), line range, what supersedes it and the partial supersessions recorded against it, each with the line it was measured at.",
     "inputSchema": {"type": "object", "properties": {"section": {"type": "string", "description": "e.g. §BH32(h), §BH11, §AC, BH18(a)"}, "text": {"type": "boolean", "default": True, "description": "include the section's full text"}}, "required": ["section"]}},
    {"name": "material", "description": "The DIP-0A inventory joined to the tier record, the owner grants and the §BH42(b) captions — by path fragment, sha256 (or prefix), font family, WHAT THE IMAGE SHOWS (\"gold foil rigid box\") or a palette colour (a #RRGGBB hex, matched within ΔE76 ≤ 12 of a measured dominant colour). Every row carries tier, tier source, evidence, grant state and a placement verdict. Captions are DERIVED and machine-written: evidence of nothing about rights. No bytes, no locator beyond the repo-relative materials/ path (the §BH39(d) retrieval interface).",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "a path fragment, a sha256 or its prefix, a family name, words describing what the image shows, or a #RRGGBB hex"}, "tier": {"type": "string", "description": "optional filter: PRODUCTION|REFERENCE|NOT_IN_TIER_RECORD"}, "limit": {"type": "integer", "default": 20}}, "required": ["query"]}},
    {"name": "lessons", "description": "Stop reports, refusals, scores, defect classes and instrument errors from the sittings and the register, by keyword and by pin class (records, identity, wit, manifest, seals, m7, two_roots, gitignore, ledger, gate, census).",
     "inputSchema": {"type": "object", "properties": {"keyword": {"type": "string"}, "pin_class": {"type": "string"}, "limit": {"type": "integer", "default": 10}}}},
]

PIN_CLASSES = {
    "records": ["record_integrity", "RECORD_KIND", "records"], "identity": ["protocol_identity", "identity"],
    "wit": ["TREE_CHECKS", "WIT", "denominator", "analyser"], "manifest": ["suite_file_manifest", "manifest"],
    "seals": ["tree seal", "seal"], "m7": ["M7 artefact", "M7 artefacts", "baseline"],
    "two_roots": ["two roots", "outer root", "inner root", "TWO ROOTS"], "gitignore": [".gitignore"],
    "ledger": ["ledger", "append-only"], "gate": ["gate", "refused", "REFUSED", "GEXIT"],
    "census": ["census-first", "census", "pin class"], "prediction": ["prediction", "sealed", "8-leg", "MISS"],
    # §BH44(a)(3) — A CHANGE TO THE MACHINE IS A CHANGE TO THE SUITE'S INPUTS. Before
    # installing, removing or upgrading any tool the code detects, census what asserts
    # that tool's presence or absence. The pin classes above are all facts about the
    # REPOSITORY; this one is the machine the repository runs on, which no other class
    # reached — which is why an owner-ruled `brew install ghostscript` refused a gate.
    "machine": ["a change to the machine", "system tool", "on PATH", "ghostscript",
                "env-detect", "installed", "uninstall", "upgrade"],
}


def db():
    uri = "file:%s?mode=ro" % S.DB_PATH
    return sqlite3.connect(uri, uri=True)


def _cite(row):
    return "%s:%s-%s" % (row["path"], row["line_start"], row["line_end"]) if row["line_end"] and row["line_end"] != row["line_start"] else "%s:%s" % (row["path"], row["line_start"])


def _doc_hit(r, found_by, **extra):
    hit = {"cite": _cite(r), "kind": r["kind"], "section": r["section_id"], "title": r["title"],
           "status": r["status"], "found_by": found_by}
    hit.update(extra)
    return hit


def tool_search(args):
    """The full-text ranking and the meaning ranking, returned together and each labelled.

    §BH42(a): the semantic half is ranked BESIDE the FTS half and never replaces it. Every
    FTS hit is kept; a hit only the vectors found is appended and says found_by=semantic.
    """
    q = args["query"]; kind = args.get("kind"); limit = int(args.get("limit") or 10)
    want_semantic = args.get("semantic", True)
    con = db(); con.row_factory = sqlite3.Row
    sql = ("SELECT d.id, d.kind, d.path, d.line_start, d.line_end, d.section_id, d.title, d.status, "
           "snippet(docs_fts, 0, '[', ']', ' … ', 24) AS snip, bm25(docs_fts) AS score "
           "FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid WHERE docs_fts MATCH ?")
    params = [q]
    if kind: sql += " AND d.kind = ?"; params.append(kind)
    sql += " ORDER BY score LIMIT ?"; params.append(limit)
    fts_error = None
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        rows = []; fts_error = "FTS query error: %s" % e
    hits = [_doc_hit(r, "fts", snippet=r["snip"], fts_score=round(r["score"], 3)) for r in rows]
    by_id = {r["id"]: i for i, r in enumerate(rows)}

    semantic_state = "off"
    if want_semantic:
        near = embed.nearest(q, S.BRAIN_DIR, limit=limit * 4)
        if not near:
            semantic_state = "no vectors built — run tools/brain/rebuild.py"
        else:
            semantic_state = "on"
            added = 0
            for doc_id, score in near:
                if doc_id in by_id:
                    h = hits[by_id[doc_id]]
                    h["found_by"] = "fts+semantic"; h["semantic_score"] = round(score, 4)
                    continue
                if added >= limit:
                    continue
                r = con.execute("SELECT id, kind, path, line_start, line_end, section_id, title, status, text "
                                "FROM docs WHERE id = ?", (doc_id,)).fetchone()
                if r is None or (kind and r["kind"] != kind):
                    continue
                snippet = " ".join((r["text"] or "").split())[:240]
                hits.append(_doc_hit(r, "semantic", snippet=snippet, semantic_score=round(score, 4)))
                added += 1
    out = {"query": q, "hits": hits, "count": len(hits), "semantic": semantic_state,
           "ranking": "the full-text hits in their own order, then the hits only meaning found; found_by names which ranking reached each",
           "authority": "the cited file and line, not this answer"}
    if fts_error: out["fts_error"] = fts_error
    return out


def _norm_section(s):
    s = s.strip()
    if not s.startswith("§"): s = "§" + s
    return s


def tool_ruling(args):
    sid = _norm_section(args["section"]); want_text = args.get("text", True)
    con = db(); con.row_factory = sqlite3.Row
    # THE REGISTER RULES, THE QUEUE QUEUES. `sections` holds both documents, and 65 ids head a
    # block in BOTH. Ordering by level and line alone picked between two documents by a tiebreak
    # that encodes nothing about authority, and it returned the QUEUE for 23 of them — reporting
    # a LIVE ruling as UNCLASSIFIED every one of those times, because chunker gates `measurable`
    # on the register (chunker.py:92) and a row that is not measurable is forced to UNCLASSIFIED
    # (chunker.py:163). §BC and §AD0(a) — the transcription and prediction disciplines this arc
    # runs on — were two of the 23. The register is preferred, and the queue's block is NAMED in
    # the answer rather than silently discarded.
    r = con.execute("SELECT * FROM sections WHERE id = ? "
                    "ORDER BY CASE WHEN path = ? THEN 0 ELSE 1 END, level, line_start LIMIT 1",
                    (sid, S.REGISTER.name)).fetchone()
    if r is None:
        # ABSENT: no block heads this id — cite every line that mentions it instead of inventing a status
        ment = con.execute("SELECT path, line_no, text FROM mentions WHERE section_id = ? ORDER BY CASE WHEN path LIKE 'OWNER_BLOCKER%' THEN 0 ELSE 1 END, line_no LIMIT 60", (sid,)).fetchall()
        total = con.execute("SELECT count(*) FROM mentions WHERE section_id = ?", (sid,)).fetchone()[0]
        return {"section": sid, "status": "ABSENT", "note": "no block of the register or the queue is headed by this id; the lines that mention it are cited, the register's first",
                "mentions_total": total, "mentions": [{"cite": "%s:%d" % (m["path"], m["line_no"]), "text": m["text"][:300]} for m in ment], "authority": "the cited file and line"}
    notes = json.loads(r["notes"] or "[]")
    out = {"section": r["id"], "file": r["path"], "lines": "%d-%d" % (r["line_start"], r["line_end"]), "cite": "%s:%d-%d" % (r["path"], r["line_start"], r["line_end"]),
           "heading": r["heading"], "status": r["status"], "superseded_by": r["superseded_by"], "superseded_at": r["superseded_at"],
           "supersession_notes": [{"kind": n["kind"], "scope": n["scope"], "by": n["by"], "cite": "%s:%d" % (n.get("file", r["path"]), n["line"]), "sentence": n["sentence"]} for n in notes],
           "sub_sections": [s["id"] for s in con.execute("SELECT id FROM sections WHERE parent = ? ORDER BY line_start", (r["id"],)).fetchall()],
           "authority": "the cited file and line, not this answer"}
    also_in = con.execute("SELECT path, line_start, line_end, status FROM sections "
                          "WHERE id = ? AND path <> ? ORDER BY path, line_start",
                          (sid, r["path"])).fetchall()
    if also_in:
        out["also_headed_in"] = [{"cite": "%s:%d-%d" % (a["path"], a["line_start"], a["line_end"]),
                                  "status": a["status"]} for a in also_in]
        out["ruling_document"] = ("this id heads a block in more than one document; the answer is the "
                                  "register's, because the register rules and the queue queues — the "
                                  "other blocks are cited here and are not the ruling")
    if want_text:
        text = pathlib.Path(S.OUTER / r["path"]).read_text().split("\n")[r["line_start"] - 1: r["line_end"]]
        out["text"] = "\n".join(text)
    return out


def _lab(rgb):
    def f(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    def k(t): return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = k(x), k(y), k(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _de76(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _tier_cite() -> str:
    """The tier record the brain actually read, as a repository-relative path (§BH55 Phase 4: it is tracked now, and
    a machine that still holds only the ignored audit output cites that one)."""
    try:
        return str(S.TIERS.relative_to(S.OUTER))
    except ValueError:
        return str(S.TIERS)


def _placement(tier):
    """§BH37/§BH39 inside the brain: only a PRODUCTION row with its record may be placed."""
    if tier == "PRODUCTION":
        return {"may_place": True,
                "note": "PRODUCTION in the tier record: placeable with its credit in the record and visible where the terms say (§BH39(d))"}
    return {"may_place": False,
            "note": "%s: its bytes may never be placed in an output; the caption may be read, the file may not be used (§BH37/§BH39)"
                    % (tier or "NOT_IN_TIER_RECORD")}


def _caption_paths(con, q, limit):
    """Paths whose CAPTION answers the query — by words, or by a palette colour."""
    hexq = re.fullmatch(r"#?([0-9a-fA-F]{6})", q.strip())
    if hexq:
        want = _lab(tuple(int(hexq.group(1)[i:i + 2], 16) for i in (0, 2, 4)))
        out = []
        for r in con.execute("SELECT relative_path, palette FROM captions"):
            best = None
            for entry in json.loads(r["palette"] or "[]"):
                h = entry.get("hex", "").lstrip("#")
                if len(h) != 6:
                    continue
                d = _de76(want, _lab(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))))
                if best is None or d < best[0]:
                    best = (d, entry)
            if best and best[0] <= 12.0:
                out.append((best[0], r["relative_path"], {"matched_hex": best[1]["hex"],
                                                          "share": best[1].get("share"),
                                                          "delta_e76": round(best[0], 2)}))
        out.sort(key=lambda x: x[0])
        return {p: why for _d, p, why in out[:limit]}
    words = [w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) > 2]
    if not words:
        return {}
    found = {}
    # the words half: FTS over the caption documents, ranked, any term matching
    try:
        rows = con.execute(
            "SELECT d.path, bm25(docs_fts) AS score FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid "
            "WHERE docs_fts MATCH ? AND d.kind = 'caption' ORDER BY score LIMIT ?",
            (" OR ".join(words), limit)).fetchall()
        for r in rows:
            found[r["path"]] = {"matched": "caption words", "fts_score": round(r["score"], 3)}
    except sqlite3.OperationalError:
        pass
    # the meaning half: the same vectors the search tool ranks with, restricted to captions
    for doc_id, score in embed.nearest(q, S.BRAIN_DIR, limit=limit * 20):
        row = con.execute("SELECT path, kind FROM docs WHERE id = ?", (doc_id,)).fetchone()
        if row is None or row["kind"] != "caption":
            continue
        if row["path"] in found:
            found[row["path"]]["matched"] = "caption words and meaning"
            found[row["path"]]["semantic_score"] = round(score, 4)
        elif len(found) < limit * 2:
            found[row["path"]] = {"matched": "caption meaning", "semantic_score": round(score, 4)}
    return found


def tool_material(args):
    q = args["query"].strip(); tier = args.get("tier"); limit = int(args.get("limit") or 20)
    con = db(); con.row_factory = sqlite3.Row
    is_hex = bool(re.fullmatch(r"[0-9a-f]{8,64}", q))
    caption_why = {}
    if is_hex:
        where = "sha256 LIKE ?"; params = [q + "%"]
    else:
        caption_why = _caption_paths(con, q, limit)
        clauses = ["relative_path LIKE ?", "family LIKE ?"]; params = ["%" + q + "%", "%" + q + "%"]
        if caption_why:
            clauses.append("relative_path IN (%s)" % ",".join("?" * len(caption_why)))
            params.extend(caption_why)
        where = "(" + " OR ".join(clauses) + ")"
    if tier:
        where += " AND tier IS NULL" if tier == "NOT_IN_TIER_RECORD" else " AND tier = ?"
        if tier != "NOT_IN_TIER_RECORD":
            params.append(tier)
    rows = con.execute("SELECT * FROM materials WHERE %s ORDER BY relative_path LIMIT ?" % where,
                       params + [limit]).fetchall()
    out = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        for f in FORBIDDEN_FIELDS: d.pop(f, None)
        if d.get("tier") is None:
            d["tier"] = "NOT_IN_TIER_RECORD"; d["tier_note"] = "no row in the tier record: outside the three governed folders (§BH36 tiers cover materials/17-10-2024, ALL..MOCKUP, ADOBE STOCK)"
        d["cite"] = {"inventory": "var/design_intelligence/audits/dip0/inventory/inventory.jsonl:%s" % r["inventory_line"],
                     "tier": ((_tier_cite() + ":%s") % r["tier_line"]) if r["tier_line"] else None,
                     "grant": r["grant_cite"]}
        d["placement"] = _placement(r["tier"])
        cap = con.execute("SELECT subject, product_form, technique, finish, layout, text_seen, language, palette, model "
                          "FROM captions WHERE relative_path = ?", (r["relative_path"],)).fetchone()
        if cap is not None:
            d["caption"] = {k: cap[k] for k in cap.keys() if k != "palette"}
            d["caption"]["palette"] = json.loads(cap["palette"] or "[]")
            d["caption"]["machine_written"] = True
            d["caption"]["rights_note"] = ("DERIVED and machine-written: evidence of nothing about rights. "
                                           "The tier above is the tier record's, never this caption's.")
            if r["relative_path"] in caption_why:
                d["caption"]["matched_by"] = caption_why[r["relative_path"]]
        out.append(d)
    return {"query": q, "rows": out, "count": len(out), "no_bytes_no_locator": True,
            "captions": "DERIVED, machine-written, evidence of nothing about rights",
            "authority": "the cited record lines; the tier record is the seam's, the register rules it"}


def tool_lessons(args):
    kw = (args.get("keyword") or "").strip(); pc = (args.get("pin_class") or "").strip().lower(); limit = int(args.get("limit") or 10)
    terms = []
    if kw: terms.append('"%s"' % kw.replace('"', '') if " " in kw or "-" in kw else kw)
    if pc:
        if pc not in PIN_CLASSES: return {"error": "unknown pin class %r" % pc, "pin_classes": sorted(PIN_CLASSES)}
        terms.append("(" + " OR ".join('"%s"' % t for t in PIN_CLASSES[pc]) + ")")
    if not terms: return {"error": "give a keyword and/or a pin_class", "pin_classes": sorted(PIN_CLASSES)}
    q = " AND ".join(terms)
    con = db(); con.row_factory = sqlite3.Row
    sql = ("SELECT d.id, d.kind, d.path, d.line_start, d.line_end, d.section_id, d.title, d.status, d.lesson, "
           "snippet(docs_fts, 0, '[', ']', ' … ', 32) AS snip, bm25(docs_fts) AS score "
           "FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid WHERE docs_fts MATCH ? AND (d.lesson = 1 OR d.kind IN ('register', 'queue')) "
           "ORDER BY d.lesson DESC, score LIMIT ?")
    try:
        rows = con.execute(sql, (q, limit)).fetchall()
    except sqlite3.OperationalError as e:
        return {"error": "FTS query error: %s" % e, "query": q}
    return {"query": q, "hits": [{"cite": _cite(r), "kind": r["kind"], "section": r["section_id"], "section_status": r["status"], "title": r["title"], "lesson_flag": bool(r["lesson"]), "snippet": r["snip"]} for r in rows], "count": len(rows),
            "lesson_sources": "first the documents flagged as lessons (the sittings' stop reports, refusals and scores; register and queue paragraphs carrying refusal, defect, instrument, hard-stop or miss vocabulary), then any register or queue paragraph that matches — a ruling that carries a rule is a lesson too", "authority": "the cited file and line"}


HANDLERS = {"search": tool_search, "ruling": tool_ruling, "material": tool_material, "lessons": tool_lessons}


def handle(msg):
    mid = msg.get("id"); method = msg.get("method"); params = msg.get("params") or {}
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO,
                                                        "instructions": "Every answer cites file:line; the cited file owns the truth. Before citing a §section, call ruling and cite its status. Before claiming an asset absent, call material and state the query. Before proposing, call lessons."}}
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name"); args = params.get("arguments") or {}
        fn = HANDLERS.get(name)
        if fn is None:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "unknown tool %r" % name}}
        if not S.DB_PATH.is_file():
            res = {"error": "no index at %s — run tools/brain/rebuild.py" % S.DB_PATH}
        else:
            try:
                res = fn(args)
            except Exception as e:
                res = {"error": "%s: %s" % (type(e).__name__, e)}
        fresh = S.read_freshness()
        res["index_built_at"] = (fresh or {}).get("built_at")
        return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=1)}], "isError": "error" in res}}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found: %s" % method}}


def main():
    inp = sys.stdin.buffer; out = sys.stdout.buffer
    for raw in inp:
        raw = raw.strip()
        if not raw: continue
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        resp = handle(msg)
        if resp is not None:
            out.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8")); out.flush()


if __name__ == "__main__":
    main()
