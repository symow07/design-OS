#!/usr/bin/env python
"""THE BRAIN — the rebuild (§BH40(b)). Regenerates var/brain/brain.sqlite (SQLite FTS5) and the freshness
record var/brain/freshness.json from the sources in ONE run; derived, never hand-edited. It writes to
var/brain/ and, since §BH43(c) ruled a rebuild step emits the vault, to brain_vault/ at the git root — those
two directories and nothing else. The database is built in a temporary file and moved into place atomically; the freshness
record is written last, so a crash leaves no fresh record over a stale index.

    bbrose_design_os/venv/bin/python bbrose_design_os/tools/brain/rebuild.py          # prints the timing line
"""
import sys, os, json, time, sqlite3, pathlib, re, datetime, importlib.util
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sources as S
import embed
import caption_scope
import vault as vault_mod
import chunker

WINDOW = 40            # lines per text chunk
LESSON_RE = re.compile(r"\b(refus|REFUSED|defect|instrument|hard stop|HARD STOP|stop report|MISS\b|miss(ed|es)?\b|lesson|incident|"
                       r"false claim|not observed|census-first|pin class|unpredicted|error of mine|near-miss|caught)\b", re.I)
LESSON_DISPOSITIONS = ("stop-report", "refusal", "score")


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def windows(text, size=WINDOW):
    """(line_start, line_end, chunk_text) over paragraphs, merged up to `size` lines."""
    lines = text.split("\n"); out = []; start = 1; cur = []
    def flush(end):
        nonlocal cur, start
        body = "\n".join(cur).strip()
        if body: out.append((start, end, body))
        cur = []
    for i, l in enumerate(lines, 1):
        if not cur: start = i
        cur.append(l)
        if (not l.strip() and len(cur) >= size // 2) or len(cur) >= size:
            flush(i)
    flush(len(lines))
    return out


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def build(db_path):
    t0 = time.time(); stats = {}
    con = sqlite3.connect(db_path)
    con.executescript("""
    PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
    CREATE TABLE docs(id INTEGER PRIMARY KEY, kind TEXT, path TEXT, line_start INT, line_end INT, section_id TEXT, title TEXT, status TEXT, lesson INT, text TEXT);
    CREATE VIRTUAL TABLE docs_fts USING fts5(text, title, content='docs', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
    CREATE TABLE sections(id TEXT, path TEXT, short TEXT, level INT, parent TEXT, heading TEXT, line_start INT, line_end INT, status TEXT, superseded_by TEXT, superseded_at TEXT, notes TEXT, refs TEXT, measurable INT);
    CREATE INDEX sections_id ON sections(id);
    CREATE TABLE mentions(section_id TEXT, path TEXT, line_no INT, text TEXT);
    CREATE INDEX mentions_id ON mentions(section_id);
    CREATE TABLE materials(relative_path TEXT, sha256 TEXT, size INT, category TEXT, extension TEXT, mime TEXT, signature TEXT, ownership_status TEXT, license_status TEXT,
        family TEXT, faces TEXT, tier TEXT, tier_source TEXT, evidence TEXT, condition TEXT, granted_by TEXT, granted_at TEXT, grant_terms_class TEXT, grant_cite TEXT,
        inventory_line INT, tier_line INT, fonts_census_line INT);
    CREATE INDEX materials_path ON materials(relative_path); CREATE INDEX materials_sha ON materials(sha256); CREATE INDEX materials_family ON materials(family);
    CREATE TABLE captions(sha256 TEXT PRIMARY KEY, relative_path TEXT, image_set TEXT, tier TEXT, tier_source TEXT,
        grant_terms_class TEXT, subject TEXT, product_form TEXT, technique TEXT, finish TEXT, layout TEXT,
        text_seen TEXT, language TEXT, palette TEXT, model TEXT, machine_written INT);
    CREATE INDEX captions_path ON captions(relative_path);
    CREATE TABLE meta(key TEXT, value TEXT);
    """)
    docs = []
    def add(kind, path_label, ls, le, section_id, title, status, text, lesson=0):
        docs.append((kind, path_label, ls, le, section_id, title, status, 1 if (lesson or LESSON_RE.search(text)) else 0, text))

    # 1. the register and the queue: sections + windows tagged with their section
    reg_t = read_text(S.REGISTER); q_t = read_text(S.QUEUE)
    chunks, unresolved, n_sent = chunker.run(reg_t, q_t, S.label(S.REGISTER), S.label(S.QUEUE))
    for c in chunks:
        con.execute("INSERT INTO sections VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (c["id"], c["file"], c["short"], c["level"], c["parent"], c["heading"], c["line_start"], c["line_end"], c["status"],
                     c["superseded_by"], c["superseded_at"], json.dumps(c["notes"], ensure_ascii=False), json.dumps(c["refs"], ensure_ascii=False), 1 if c["measurable"] else 0))
    con.executemany("INSERT INTO mentions VALUES (?,?,?,?)", chunker.mentions({S.label(S.REGISTER): reg_t, S.label(S.QUEUE): q_t}))
    for label, text, kind in ((S.label(S.REGISTER), reg_t, "register"), (S.label(S.QUEUE), q_t, "queue")):
        l2 = sorted([c for c in chunks if c["file"] == label and c["level"] == 2], key=lambda c: c["line_start"])
        for ls, le, body in windows(text):
            sec = None
            for c in l2:
                if c["line_start"] <= ls <= c["line_end"]: sec = c; break
            add(kind, label, ls, le, sec["id"] if sec else None, (sec["heading"][:160] if sec else None), (sec["status"] if sec else None), body)
    stats.update(register_sections=sum(1 for c in chunks if c["short"] == "R"), queue_sections=sum(1 for c in chunks if c["short"] == "Q"),
                 supersession_sentences=n_sent, unresolved_targets=len(unresolved))
    con.execute("INSERT INTO meta VALUES (?,?)", ("unresolved_supersession_targets", json.dumps(unresolved, ensure_ascii=False)))

    # 2. the sittings (disposition from the import manifest), the WATCH notes, the launchers, the prompt files
    manifest = {}
    idx_path = S.SITTINGS / "INDEX.json"
    if idx_path.is_file():
        for r in json.loads(read_text(idx_path))["rows"]:
            if r.get("dest"): manifest[r["dest"]] = r["disposition"]
    for kind, path in S.enumerate_sources():
        if kind in ("register", "queue", "record", "grant"): continue
        label = S.label(path)
        if path.suffix.lower() == ".png": continue
        text = read_text(path)
        disp = manifest.get(label, "")
        lesson_file = any(d in disp for d in LESSON_DISPOSITIONS)
        title = "%s · %s" % (kind, path.name)
        if path.suffix.lower() == ".jsonl":
            for i, line in enumerate(text.split("\n"), 1):
                if line.strip(): add(kind, label, i, i, None, title, disp or None, line[:4000], lesson_file)
        else:
            for ls, le, body in windows(text):
                add(kind, label, ls, le, None, title, disp or None, body[:8000], lesson_file)

    # 3. the DIP-0A inventory joined to the tier record, the grants and the fonts census
    tiers = {}
    if S.TIERS.is_file():
        for i, line in enumerate(read_text(S.TIERS).split("\n"), 1):
            if line.strip():
                r = json.loads(line); tiers[(r["relative_path"], r["sha256"])] = (i, r)
    grants_by_evidence = {}
    if S.MATERIALS_GRANTS.is_file():
        sys.path.insert(0, str(S.INNER))
        try:
            from apps.ire import materials_owner_grant as MG
            for gi, g in enumerate(MG.MATERIAL_GRANTS):
                grants_by_evidence[g.get("evidence_path")] = (gi, g)
        except Exception as e:
            con.execute("INSERT INTO meta VALUES (?,?)", ("materials_grants_import_error", str(e)))
    font_grants = {}
    if S.FONT_GRANTS.is_file():
        try:
            from apps.ire import container_font_owner_grant as FG
            for gi, g in enumerate(FG.OWNER_GRANTS):
                for sha in g.get("face_sha256s", ()) or ():
                    font_grants[sha] = (gi, g)
        except Exception as e:
            con.execute("INSERT INTO meta VALUES (?,?)", ("font_grants_import_error", str(e)))
    fonts = {}
    if S.FONTS_CENSUS.is_file():
        for i, r in enumerate(json.loads(read_text(S.FONTS_CENSUS))):
            faces = r.get("faces") or []
            fam = "; ".join(sorted({f.get("family", "") for f in faces if f.get("family")}))
            fonts[r["sha256"]] = (i + 1, fam, json.dumps([{k: f.get(k) for k in ("family", "style", "full_name")} for f in faces], ensure_ascii=False))
    n_mat = 0
    if S.DAY6_FONTS_CENSUS.is_file():
        for i, r in enumerate(json.loads(read_text(S.DAY6_FONTS_CENSUS))['files']):
            faces=r.get('faces') or []
            family='; '.join(sorted({f.get('name_fields_raw',{}).get('1') or '' for f in faces}))
            fonts[r['source_sha256']] = (i+1, family, json.dumps([{'family':f.get('name_fields_raw',{}).get('1'),
                                                        'style':f.get('name_fields_raw',{}).get('2'),
                                                        'pool':f.get('pool'), 'engine_grant':False} for f in faces],ensure_ascii=False))
    if S.INVENTORY.is_file():
        for i, line in enumerate(read_text(S.INVENTORY).split("\n"), 1):
            if not line.strip(): continue
            r = json.loads(line)
            key = (r.get('original_source_path', r['relative_path']), r["sha256"]); tl, trow = tiers.get(key, (None, {}))
            # the tier row's evidence reads "<path> sha256:<digest>"; the grant is keyed by the path alone
            g = grants_by_evidence.get((trow.get("evidence") or "").split(" sha256:")[0]) if trow else None
            fg = font_grants.get(r["sha256"])
            fam, faces, fl = "", "", None
            if r["sha256"] in fonts: fl, fam, faces = fonts[r["sha256"]]
            grant_cite = None; terms = None
            if g: terms = g[1].get("terms_class"); grant_cite = "bbrose_design_os/apps/ire/materials_owner_grant.py MATERIAL_GRANTS[%d]" % g[0]
            elif fg: terms = fg[1].get("licence_id"); grant_cite = "bbrose_design_os/apps/ire/container_font_owner_grant.py OWNER_GRANTS[%d]" % fg[0]
            def val(x): return (x or {}).get("value") if isinstance(x, dict) else x
            con.execute("INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (r["relative_path"], r["sha256"], r.get("size_bytes"), val(r.get("category")), r.get("extension"), val(r.get("mime_detected")), val(r.get("signature_kind")),
                         val(r.get("ownership_status")), val(r.get("license_status")), fam, faces, trow.get("tier"), trow.get("tier_source"), trow.get("evidence"), trow.get("condition"),
                         trow.get("granted_by"), trow.get("granted_at"), terms, grant_cite, i, tl, fl))
            n_mat += 1
            add("record", S.label(S.INVENTORY), i, i, None, "record · " + r["filename"], trow.get("tier"),
                " ".join(x for x in (r["relative_path"], val(r.get("category")), fam, trow.get("tier"), val(r.get("license_status")), val(r.get("ownership_status"))) if x))
    stats["materials_rows"] = n_mat
    # 4. §BH42(b): the captions, machine-written. They describe what is visible and are
    #    evidence of nothing about rights: the tier beside each row is the tier record's,
    #    never the caption's. §BH43(a): they are read from the TRACKED record under
    #    docs/design_intelligence/captions/, not from var/ — so a rebuild with var/ deleted
    #    restores every caption and spends no dollar. The index built from them stays derived.
    caption_stats = {"state": "NO_CAPTIONS", "rows": 0}
    cap = caption_scope.read_tracked()
    if cap is not None:

        def flat(v):
            """A model may answer a field with a list; the column holds text either way."""
            if isinstance(v, (list, tuple)):
                return " | ".join(str(x) for x in v if x is not None) or None
            if isinstance(v, dict):
                return json.dumps(v, ensure_ascii=False)
            return v

        rows = []
        for c in cap.get("captions", []):
            from apps.ire.materials_paths import migration_row
            move=migration_row(c['path'],repo_root=S.OUTER)
            physical_path=move['new_path'] if move and move['sha256']==c['sha256'] else c['path']
            f = c.get("caption") or {}
            seen = f.get("text_seen") or []
            pal = c.get("palette") or []
            rows.append((c["sha256"], physical_path, c.get("set"), c.get("tier"), c.get("tier_source"),
                         c.get("grant_terms_class"), flat(f.get("subject")), flat(f.get("product_form")),
                         flat(f.get("technique")), flat(f.get("finish")), flat(f.get("layout")),
                         " | ".join(str(x) for x in seen), flat(f.get("language")),
                         json.dumps(pal, ensure_ascii=False), c.get("model"), 1))
            body = " ".join(str(x) for x in (
                " ".join(c.get("paths") or [c["path"]]), flat(f.get("subject")), flat(f.get("product_form")),
                flat(f.get("technique")), flat(f.get("finish")), flat(f.get("layout")),
                " ".join(str(x) for x in seen),
                " ".join(p.get("hex", "") for p in pal)) if x)
            add("caption", physical_path, 1, 1, None, "caption · %s" % physical_path.split("/")[-1],
                c.get("tier") or "NOT_IN_TIER_RECORD", body)
        con.executemany("INSERT OR REPLACE INTO captions VALUES (%s)" % ",".join("?" * 16), rows)
        caption_stats = {"state": "BUILT", "rows": len(rows), "model": cap.get("model"),
                         "spend_usd": cap.get("spend_usd"), "record_type": cap.get("record_type"),
                         "record": "docs/design_intelligence/captions", "tracked": True,
                         "spent_this_rebuild_usd": 0.0}
    # §BH42(e): coverage is REPORTED, never assumed — an image added or changed since the
    # last caption run is UNCAPTIONED, and the gate reads this rather than trusting silence.
    try:
        caption_stats["coverage"] = caption_scope.coverage()
    except Exception as exc:                      # a scope that will not resolve is a finding, not a crash
        caption_stats["coverage"] = {"state": "COVERAGE_UNMEASURABLE", "error": str(exc)[:200]}
    stats["captions"] = caption_stats
    con.execute("INSERT INTO meta VALUES (?,?)", ("captions", json.dumps(caption_stats)))
    con.executemany("INSERT INTO docs(kind, path, line_start, line_end, section_id, title, status, lesson, text) VALUES (?,?,?,?,?,?,?,?,?)", docs)
    con.execute("INSERT INTO docs_fts(docs_fts) VALUES ('rebuild')")
    stats["docs"] = len(docs); stats["lesson_docs"] = sum(d[7] for d in docs)
    con.execute("INSERT INTO meta VALUES (?,?)", ("stats", json.dumps(stats)))
    con.execute("INSERT INTO meta VALUES (?,?)", ("absent_sources", json.dumps(S.absent_sources())))
    # §BH42(a): the semantic layer, built from the same connection so the vectors and the
    # index describe one corpus. It is BESIDE the FTS index, never in place of it.
    t_embed = time.time()
    embedding = embed.build(con, S.BRAIN_DIR)
    embedding["seconds"] = round(time.time() - t_embed, 2)
    stats["embedding"] = embedding
    con.execute("INSERT INTO meta VALUES (?,?)", ("embedding", json.dumps(embedding)))
    # §BH43(c): THE VAULT. §BH40's hard stop said the brain writes nothing outside var/brain/;
    # §BH43(c) rules that a rebuild step emits into brain_vault/ at the git root, so the write set is
    # those two directories and nothing else. The vault is DERIVED AND DISPOSABLE and git-ignored.
    try:
        stats["vault"] = vault_mod.emit(con)
    except Exception as exc:                # a vault that will not build is a finding, not a crash
        stats["vault"] = {"state": "VAULT_UNBUILT", "error": str(exc)[:200]}
    con.commit(); con.close()
    return stats, time.time() - t0


def main():
    t0 = time.time()
    S.BRAIN_DIR.mkdir(parents=True, exist_ok=True)
    tmp = S.BRAIN_DIR / ("brain.sqlite.tmp-%d" % os.getpid())
    if tmp.exists(): tmp.unlink()
    hashes = S.current_source_hashes()               # hashed BEFORE the build: the record describes what was read
    stats, build_s = build(tmp)
    os.replace(tmp, S.DB_PATH)
    total = time.time() - t0
    record = {"record_type": S.FRESHNESS_RECORD_TYPE, "built_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "rebuild_seconds": round(total, 2), "build_seconds": round(build_s, 2), "source_count": len(hashes), "sources": hashes,
              "absent_sources": S.absent_sources(), "stats": stats, "index_bytes": S.DB_PATH.stat().st_size, "db": str(S.DB_PATH)}
    ftmp = S.FRESHNESS_PATH.with_suffix(".json.tmp")
    ftmp.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n"); os.replace(ftmp, S.FRESHNESS_PATH)
    emb = stats.get("embedding") or {}
    print("BRAIN_REBUILD_OK seconds=%.2f sources=%d docs=%d sections=%d+%d materials=%d vectors=%d embed_seconds=%.2f index_bytes=%d" % (
        total, len(hashes), stats["docs"], stats["register_sections"], stats["queue_sections"], stats["materials_rows"],
        emb.get("vectors", 0), emb.get("seconds", 0.0), record["index_bytes"]), end="")
    caps = stats.get("captions") or {}
    cov = caps.get("coverage") or {}
    v = stats.get("vault") or {}
    print(" captions=%d coverage=%s vault=%s" % (caps.get("rows", 0), cov.get("state", "NONE"),
                                                 v.get("notes", v.get("state", "NONE"))))
    if total > embed.REBUILD_BOUND_SECONDS:
        print("BRAIN_REBUILD_OVER_BOUND seconds=%.2f bound=%d — §BH42(a) raised the bound to five minutes; over it is a stop, not a gate step" % (
            total, embed.REBUILD_BOUND_SECONDS), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
