"""§BH43(c) — THE VAULT: generated markdown, Obsidian-ready, DERIVED AND DISPOSABLE.

A rebuild step emits brain_vault/ at the git root (vault/ until the clean-up of 2026-10-04). Every note carries a "generated from <source>
@ <commit>" header, nothing here is hand-edited, and a regeneration from scratch reproduces
the tree byte-for-byte — which is a claim only as strong as the least deterministic line in
this file, so the rules are stated where they are enforced:

  * <commit> is the commit that LAST TOUCHED THAT SOURCE (git log -1 -- <path>), never HEAD.
    HEAD moves on every unrelated commit, so a HEAD-stamped vault would differ after any
    commit at all and the freshness gate would then refuse it for ever.
  * A source git does not track — the DIP-0A records under the ignored var/, the executor's
    work directories — has no commit and says so, citing its content hash instead. An empty
    commit field would be a claim of provenance the file does not support.
  * Nothing iterates a set. Every ordering is an explicit sort, and every SELECT that reaches
    a note carries ORDER BY, because CPython randomises string hashing per process: an
    unsorted set passes a regeneration inside one process and fails across two.
  * No wall clock reaches a note.
  * Every slug carries a digest of its full key. Resolving collisions with a counter would
    make a name depend on the order two groups were visited in, and 60 real group names in
    this corpus collide once the unsafe characters are folded — one of them 20 ways.

§BH40's hard stop said the brain writes nothing outside var/brain/. §BH43(c) rules that a
rebuild step emits into brain_vault/ at the git root, so the write set is those two directories and
nothing else. The extension is the owner's, and is recorded rather than assumed.

THE LINE HOLDS: a thumbnail is a rendered byte. Only a PRODUCTION-tier content may carry one;
a REFERENCE group's thumbnail is named as withheld, with the reason, and never drawn.
"""
import collections, hashlib, json, os, pathlib, re, sqlite3, subprocess, unicodedata

HERE = pathlib.Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
import sources as S

OUTER = S.OUTER
VAULT = OUTER / "brain_vault"
VAULT_RECORD_TYPE = "brain_vault/1.0"

# The defect classes are not invented here: they are the pin classes the brain already answers
# by, defined at tools/brain/server.py:29 and used by the arc's census-first discipline.
PIN_CLASSES = {
    "records": ["record_integrity", "RECORD_KIND", "records"], "identity": ["protocol_identity", "identity"],
    "wit": ["TREE_CHECKS", "WIT", "denominator", "analyser"], "manifest": ["suite_file_manifest", "manifest"],
    "seals": ["tree seal", "seal"], "m7": ["M7 artefact", "M7 artefacts", "baseline"],
    "two_roots": ["two roots", "outer root", "inner root", "TWO ROOTS"], "gitignore": [".gitignore"],
    "ledger": ["ledger", "append-only"], "gate": ["gate", "refused", "REFUSED", "GEXIT"],
    "census": ["census-first", "census", "pin class"], "prediction": ["prediction", "sealed", "8-leg", "MISS"],
}

_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_RUNS = re.compile(r"[\s._-]{2,}")
_SECTION_REF = re.compile(r"§[A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*")
_COMMIT_CACHE = {}


def source_commit(rel):
    """The commit that last touched `rel`; `untracked:sha256:<16>` when git does not track it."""
    key = str(rel)
    if key in _COMMIT_CACHE:
        return _COMMIT_CACHE[key]
    sha = ""
    p = pathlib.Path(key)
    inside = not p.is_absolute()
    if inside:
        out = subprocess.run(["git", "log", "-1", "--format=%H", "--", key],
                             cwd=str(OUTER), capture_output=True, text=True)
        sha = out.stdout.strip() if out.returncode == 0 else ""
    if not sha:
        full = p if p.is_absolute() else (OUTER / key)
        if full.is_file():
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            sha = "untracked:sha256:%s" % h.hexdigest()[:16]
        else:
            sha = "absent"
    _COMMIT_CACHE[key] = sha
    return sha


def slug(kind, key, stem=None):
    """A readable stem plus a digest of the FULL key, so uniqueness is a property of the key
    rather than of the order two colliding names happened to be visited in."""
    text = unicodedata.normalize("NFC", str(stem if stem is not None else key))
    # Real names in this corpus carry a U+FFFF noncharacter (a font family), which the
    # filesystem refuses outright. Drop every control, format, surrogate, private-use and
    # unassigned code point rather than discovering them one OSError at a time.
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn"))
    text = _UNSAFE.sub("-", text).replace("/", "-")
    text = _RUNS.sub("-", text).strip(" .-")
    text = text[:72].strip(" .-")
    if not text or set(text) <= set("-. "):
        text = kind
    return "%s-%s" % (text, hashlib.sha1(("%s\x00%s" % (kind, key)).encode("utf-8")).hexdigest()[:8])


def link(target, label=None):
    return "[[%s|%s]]" % (target, label) if label else "[[%s]]" % target


def header(kind, source, note_id, title):
    """The §BH43(c) header. Deterministic: no clock, no HEAD, no machine name."""
    return ("---\n"
            "note_kind: %s\n"
            "note_id: %s\n"
            "title: %s\n"
            "generated_from: %s\n"
            "generated_at_commit: %s\n"
            "generator: tools/brain/vault.py\n"
            "hand_edited: false\n"
            "---\n\n"
            "> [!abstract] Generated from `%s` @ `%s`\n"
            "> DERIVED AND DISPOSABLE. This note is machine-written by `tools/brain/vault.py` and is\n"
            "> reproduced byte-for-byte by a rebuild. Do not edit it: the freshness gate compares a\n"
            "> digest of every note against the sources and refuses the commit when they disagree.\n"
            "> The cited file and line own the truth; this note is a view.\n\n"
            % (kind, _yaml(note_id), _yaml(title), _yaml(str(source)), source_commit(source),
               source, source_commit(source)))


def _yaml(text):
    t = str(text).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return '"%s"' % t


# ---------------------------------------------------------------------------------------
# The notes. Each builder returns {relative path: text} and reads only through ORDER BY.
# ---------------------------------------------------------------------------------------

def _register_lines():
    return S.REGISTER.read_text(encoding="utf-8", errors="replace").splitlines()


def _edges(con, rows):
    """The real citation graph, both directions.

    `sections.refs` is NOT it: chunker.py builds refs from the HEADING LINE ONLY and includes
    the row's own id, so only 130 of 838 register rows carry anything beyond themselves. The
    citations live in `mentions`, whose column `section_id` is a trap — it holds the §token
    FOUND ON THE LINE, not the section the line sits in. So each mention is resolved twice:
    the CITER is the finest chunk whose line range contains the mention, and the CITED is the
    chunk headed by that token (walking the id up when the exact token heads nothing).
    """
    by_path = collections.defaultdict(list)
    for r in rows:
        by_path[r[12]].append((r[5], r[6], r[3] if isinstance(r[3], int) else 0, r[0], r[2]))
    for path in by_path:
        by_path[path].sort(key=lambda t: (t[0], -t[4]))
    known = {(r[12], r[0]) for r in rows}
    ids_by_path = collections.defaultdict(set)
    for r in rows:
        ids_by_path[r[12]].add(r[0])

    def containing(path, line_no):
        best = None
        for (ls, le, _p, sid, level) in by_path.get(path, ()):
            if ls > line_no:
                break
            if line_no <= le and (best is None or level > best[0] or
                                  (level == best[0] and ls > best[1])):
                best = (level, ls, sid)
        return best[2] if best else None

    def resolve(token, path):
        t = token
        while t:
            if t in ids_by_path.get(path, ()):
                return t
            if t in ids_by_path.get(S.REGISTER.name, ()):
                return t
            t2 = re.sub(r"\([a-z0-9]{1,4}\)$", "", t)
            if t2 == t:
                return None
            t = t2
        return None

    cites = collections.defaultdict(set)
    cited_by = collections.defaultdict(set)
    for (token, path, line_no, _text) in con.execute(
            "SELECT section_id, path, line_no, text FROM mentions ORDER BY path, line_no, section_id"):
        citer = containing(path, line_no)
        if not citer:
            continue
        target = resolve(token, path)
        if not target or target == citer:
            continue
        cites[(path, citer)].add(target)
        cited_by[target].add((path, citer))
    return cites, cited_by


def sections_notes(con, reg_lines, queue_lines):
    """One note per §section: status header, the text, [[links]] both ways, the line range."""
    rows = list(con.execute(
        "SELECT id, short, level, parent, heading, line_start, line_end, status, superseded_by, "
        "       superseded_at, refs, measurable, path FROM sections ORDER BY path, id, line_start"))
    # A section note is identified by (PATH, id), not by id: 65 ids appear in BOTH the register
    # and the review queue, and keying by id alone silently dropped one of each pair. The two
    # files are different documents saying different things under the same name, so each keeps
    # its own note and each note says which file it came from.
    row_slugs, primary, cites, cited_by = {}, {}, {}, collections.defaultdict(set)
    siblings = collections.defaultdict(list)
    for r in rows:
        sid, ls, path = r[0], r[5], r[12]
        row_slugs[(path, sid)] = slug("section", "%s::%s" % (path, sid),
                                      "%s-%s" % (sid, pathlib.PurePosixPath(path).stem[:18]))
        siblings[sid].append((path, ls))
    for sid in siblings:
        siblings[sid] = sorted(siblings[sid])
        # a [[link]] to a bare §id resolves to the REGISTER's note where one exists, because the
        # register is the ruling and the queue is the queue
        reg = [(pth, ls) for (pth, ls) in siblings[sid] if pth == S.REGISTER.name]
        primary[sid] = row_slugs[((reg or siblings[sid])[0][0], sid)]
    cites, cited_by = _edges(con, rows)
    # Line ranges NEST: a level-2 range contains its level-3 and level-4 children verbatim, so
    # 144 register parents would re-emit every child's text. The body is the OWN text — up to
    # the first child — while the citation range stays the full one.
    first_child = {}
    by_path_rows = collections.defaultdict(list)
    for r in rows:
        by_path_rows[r[12]].append(r)
    for path, rs in by_path_rows.items():
        for r in rs:
            kids = [c[5] for c in rs if c[2] > r[2] and c[5] > r[5] and c[5] <= r[6]]
            first_child[(path, r[0])] = min(kids) if kids else None
    out = {}
    for (sid, short, level, parent, heading, ls, le, status, sup_by, sup_at, _refs, measurable, path) in rows:
        body = ["# %s\n" % sid,
                "| | |\n|---|---|\n",
                "| **document** | `%s` |\n" % path,
                "| **status** | `%s` |\n" % (status or "UNCLASSIFIED"),
                "| **level** | %d |\n" % (level or 0),
                "| **lines** | `%s:%d-%d` |\n" % (path, ls, le),
                "| **measurable** | %s |\n" % ("yes" if measurable else "no"),
                "| **short** | `%s` |\n" % (short or ""),
                ]
        if sup_by:
            body.append("| **superseded by** | %s |\n" % link(primary.get(sup_by, sup_by), sup_by))
        if sup_at:
            body.append("| **superseded at** | `%s` |\n" % sup_at)
        if parent:
            body.append("| **parent** | %s |\n" % link(primary.get(parent, parent), parent))
        others = [(pth, o) for (pth, o) in siblings[sid] if pth != path]
        if others:
            body.append("| **same id in another document** | %s |\n"
                        % ", ".join(link(row_slugs[(pth, sid)], "%s in %s" % (sid, pathlib.PurePosixPath(pth).stem))
                                    for pth, _o in others))
        body.append("\n## Heading\n\n%s\n" % (heading or "").strip())
        it_cites = sorted(cites.get((path, sid), ()))
        body.append("\n## Cites\n\n")
        body.append("".join("- %s\n" % link(primary[c], c) for c in it_cites if c in primary) or "- (none)\n")
        back = sorted({b for (_p, b) in cited_by.get(sid, ())})
        body.append("\n## Cited by\n\n")
        body.append("".join("- %s\n" % link(primary[b], b) for b in back if b in primary) or "- (none)\n")
        lines = reg_lines if path == S.REGISTER.name else queue_lines
        fc = first_child.get((path, sid))
        own_end = (fc - 1) if fc else le
        text = "\n".join(lines[max(0, ls - 1):own_end])
        body.append("\n## Text\n\n")
        if fc:
            body.append("(its own text, lines %d-%d; the children below carry the rest)\n\n" % (ls, own_end))
        body.append("```text\n%s\n```\n" % text.replace("```", "``​`"))
        out["sections/%s.md" % row_slugs[(path, sid)]] = header(
            "section", path, "%s::%s" % (path, sid),
            "%s — %s" % (sid, status or "UNCLASSIFIED")) + "".join(body)
    return out, primary


def lesson_notes(con, section_slugs):
    """One note per lesson: the documents the brain already flags with lesson = 1."""
    rows = list(con.execute(
        "SELECT id, kind, path, line_start, line_end, section_id, title, status, text "
        "FROM docs WHERE lesson = 1 ORDER BY path, line_start, id"))
    out, index = {}, []
    for (_id, kind, path, ls, le, sec, title, status, text) in rows:
        key = "%s:%d" % (path, ls or 0)
        sl = slug("lesson", key, "%s-%s" % (pathlib.PurePosixPath(path).name, ls or 0))
        index.append((key, sl, kind, path, ls, title))
        body = ["# Lesson — %s\n\n" % (title or pathlib.PurePosixPath(path).name),
                "| | |\n|---|---|\n",
                "| **kind** | `%s` |\n" % kind,
                "| **cite** | `%s:%s` |\n" % (path, ls),
                "| **status** | `%s` |\n" % (status or ""),
                ]
        if sec and sec in section_slugs:
            body.append("| **section** | %s |\n" % link(section_slugs[sec], sec))
        fired = sorted(c for c in set(_SECTION_REF.findall(text or "")) if c in section_slugs)
        body.append("\n## Sections it names\n\n")
        body.append("".join("- %s\n" % link(section_slugs[c], c) for c in fired) or "- (none)\n")
        classes = sorted(k for k, terms in PIN_CLASSES.items()
                         if any(t.lower() in (text or "").lower() for t in terms))
        body.append("\n## Defect classes it fired\n\n")
        body.append("".join("- %s\n" % link(slug("defect", k, k), k) for k in classes) or "- (none)\n")
        body.append("\n## Text\n\n```text\n%s\n```\n" % (text or "").replace("```", "``​`"))
        out["lessons/%s.md" % sl] = header("lesson", path, key, title or key) + "".join(body)
    return out, index


def defect_class_notes(con, lesson_index, section_slugs):
    """One note per defect class, linked to the sittings that fired it.

    The classes are the brain's own pin classes (tools/brain/server.py:29), not a taxonomy
    invented for the vault: they are what the census-first discipline already names.
    """
    texts = {}
    for (_id, path, ls, text) in con.execute(
            "SELECT id, path, line_start, text FROM docs WHERE lesson = 1 ORDER BY path, line_start, id"):
        texts["%s:%d" % (path, ls or 0)] = text or ""
    by_key = {k: sl for (k, sl, _kind, _p, _ls, _t) in lesson_index}
    meta = {k: (kind, path) for (k, _sl, kind, path, _ls, _t) in lesson_index}
    out = {}
    for name in sorted(PIN_CLASSES):
        terms = PIN_CLASSES[name]
        hits = sorted(k for k, t in texts.items() if any(term.lower() in t.lower() for term in terms))
        sittings = sorted({meta[k][1] for k in hits if k in meta and meta[k][0] == "sitting"})
        body = ["# Defect class — `%s`\n\n" % name,
                "| | |\n|---|---|\n",
                "| **terms** | %s |\n" % ", ".join("`%s`" % t for t in terms),
                "| **lessons that fired it** | %d |\n" % len(hits),
                "| **sittings that fired it** | %d |\n" % len(sittings),
                "| **defined at** | `tools/brain/server.py:29` |\n",
                "\n## Lessons\n\n"]
        body.append("".join("- %s `%s`\n" % (link(by_key[k]), k) for k in hits if k in by_key) or "- (none)\n")
        body.append("\n## Sittings that fired it\n\n")
        body.append("".join("- `%s`\n" % p for p in sittings) or "- (none)\n")
        out["defect-classes/%s.md" % slug("defect", name, name)] = header(
            "defect-class", "tools/brain/server.py", name, "Defect class %s" % name) + "".join(body)
    return out


def material_notes(con):
    """One note per material group — a font FAMILY, or a PACK (the directory the bytes sit in).

    THE LINE HOLDS. A thumbnail is a rendered byte of the asset. Only a PRODUCTION-tier content
    may carry one; for every other tier the thumbnail is NAMED AS WITHHELD with its reason and
    is never drawn. That is §BH37/§BH39's placement rule and §BH43(b)'s "a REFERENCE caption is
    read, its bytes are never placed", applied to the one surface that would otherwise leak them.
    """
    rows = list(con.execute(
        "SELECT relative_path, sha256, size, category, extension, family, tier, tier_source, "
        "       condition, granted_by, granted_at, grant_terms_class, grant_cite, "
        "       ownership_status, license_status "
        "FROM materials ORDER BY relative_path"))
    caps = {}
    for r in con.execute("SELECT sha256, relative_path, tier, subject, product_form, technique, "
                         "finish, layout, text_seen, language, palette, model "
                         "FROM captions ORDER BY sha256"):
        caps[r[0]] = r
    groups = collections.OrderedDict()
    for r in rows:
        rel, sha, size, cat, ext, family, tier = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        key = ("family:%s" % family) if family else ("pack:%s" % pathlib.PurePosixPath(rel).parent)
        groups.setdefault(key, []).append(r)
    renders = S.BRAIN_DIR / "renders"
    out, stats = {}, {"groups": 0, "thumbnails": 0, "withheld": 0}
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda r: r[0])
        gkind, gname = key.split(":", 1)
        sl = slug("material", key, gname)
        tiers = collections.Counter((m[6] or "NOT_IN_TIER_RECORD") for m in members)
        terms = sorted({m[11] for m in members if m[11]})
        credit = sorted({(m[8] or "").strip() for m in members if (m[8] or "").strip()})
        granted = sorted({m[9] for m in members if m[9]})
        body = ["# %s — `%s`\n\n" % ("Family" if gkind == "family" else "Pack", gname),
                "| | |\n|---|---|\n",
                "| **group kind** | `%s` |\n" % gkind,
                "| **members** | %d |\n" % len(members),
                "| **bytes** | %d |\n" % sum(int(m[2] or 0) for m in members),
                "| **tiers** | %s |\n" % ", ".join("`%s`×%d" % (t, n) for t, n in sorted(tiers.items())),
                "| **grant terms** | %s |\n" % (", ".join("`%s`" % t for t in terms) or "(none recorded)"),
                "| **granted by** | %s |\n" % (", ".join("`%s`" % g for g in granted) or "(none)"),
                "| **credit condition** | %s |\n" % (" · ".join("`%s`" % c[:120] for c in credit) or "(none)"),
                ]
        placeable = sorted(m[0] for m in members if m[6] == "PRODUCTION")
        body.append("| **may be placed** | %s |\n"
                    % ("%d of %d (PRODUCTION only)" % (len(placeable), len(members)) if placeable
                       else "no — no PRODUCTION member"))
        body.append("\n## Placement\n\n")
        body.append("Only a PRODUCTION-tier member may have its bytes placed in an output. Every other\n"
                    "member here is read-only evidence: its caption may be read, its bytes may not be placed.\n")
        # --- thumbnails: PRODUCTION only, and the withholding is named ----------------------
        body.append("\n## Thumbnails\n\n")
        drew = 0
        for m in members:
            sha, tier = m[1], m[6]
            if not sha:
                continue
            jpg = renders / ("%s.jpg" % sha[:16])
            if not jpg.is_file():
                continue
            if tier == "PRODUCTION":
                body.append("- `%s`\n\n  ![[%s]]\n" % (m[0], jpg.name))
                drew += 1
            else:
                body.append("- `%s` — THUMBNAIL WITHHELD: tier `%s` is not PRODUCTION, and a rendered\n"
                            "  byte of a non-PRODUCTION asset may not be placed in an output.\n"
                            % (m[0], tier or "NOT_IN_TIER_RECORD"))
                stats["withheld"] += 1
        if not drew and "WITHHELD" not in "".join(body[-3:]):
            body.append("- (no render exists for any member)\n")
        stats["thumbnails"] += drew
        # --- captions and palettes ----------------------------------------------------------
        body.append("\n## Captions\n\n")
        wrote = 0
        for m in members:
            c = caps.get(m[1])
            if not c:
                continue
            wrote += 1
            body.append("### `%s`\n\n" % m[0])
            body.append("- **tier** `%s` — a caption is evidence of NOTHING about rights\n" % (c[2] or ""))
            for label, idx in (("subject", 3), ("product form", 4), ("technique", 5),
                               ("finish", 6), ("layout", 7), ("text seen", 8), ("language", 9)):
                if c[idx]:
                    body.append("- **%s** %s\n" % (label, str(c[idx]).replace("\n", " ")))
            try:
                pal = json.loads(c[10] or "[]")
            except ValueError:
                pal = []
            if pal:
                body.append("- **palette (measured from the rendered pixels)** %s\n"
                            % " ".join("`%s`" % p.get("hex", "") for p in pal))
            body.append("- **captioned by** `%s`, machine-written\n\n" % (c[11] or ""))
        if not wrote:
            body.append("(no member of this group is captioned)\n")
        body.append("\n## Members\n\n")
        body.extend("- `%s` — tier `%s`, %s bytes\n" % (m[0], m[6] or "NOT_IN_TIER_RECORD", m[2] or 0)
                    for m in members[:400])
        if len(members) > 400:
            body.append("- … and %d more, elided at 400 to keep the note readable\n" % (len(members) - 400))
        src = "var/design_intelligence/audits/dip0/inventory/inventory.jsonl"
        out["materials/%s.md" % sl] = header("material-group", src, key, gname) + "".join(body)
        stats["groups"] += 1
    return out, stats


# §BH55 Phase 4 ("the vault-note skip"; §BH45(e)(3) queued it — quoted, not fixed). This allowed ONE parenthesised
# part after the front id, so a subject whose id carries a second part or a compound matched nothing and fell out of
# the vault entirely. Measured over `git log --format=%s --no-merges` when it was widened: 180 subjects carry a front
# tag, it matched 159, and the 21 it skipped were §BH52(b)(d), the ten commits of the §BH50(f) chain, §BH48(b)(i) and
# (ii), §BH44(c)+(d) — the one that was quoted — §BH42(b)+(c), §BH37(2)(3), §BH32(e)(h), §BH32(d)(i) and (ii),
# §BH30(h)(i)(j) and §BH30(b)(c). Every §BH44 commit was among them, so the vault held no §BH44 note at all: not a
# line missing from a note, a whole front missing from the vault. Any number of parts now, joined or not by "+", with
# whatever follows read as before — 180 of 180, and the front id is still group 1.
# §BH60, 2026-09-21 — WIDENED A SECOND TIME, for the same class and found the same way: by a gate refusing.
# The §BH61 build landed as `fix(§BH61/§BH61(a)/§BH61(b)): …` — three full ids joined by slashes, because it
# carried one concern ruled across three blocks. The pattern above allowed any number of PARENTHESISED parts
# after ONE id but nothing after a `/`, so `[^)]*` ran into the `)` of `(a)` and the whole commit fell out of
# the vault. Measured over `git log --format=%s --no-merges` when it was widened: it gains exactly one subject,
# that one, and files it under §BH61 — the front id is still group 1 and every previously-matching subject
# still matches.
# §BH69, 2026-09-26 — WIDENED A THIRD TIME, for the same class, found by the suite run before a seal (the gate could
# not have: it runs before the commit it tests exists). The §BH69(2) colours commit (606b54f) quoted his sentence in
# its tag — `feat(§BH69(2), the owner's goal ..., "shows me, in words, what it took from it (layout, colours, mood,
# finish, type style)"): …` — and `[^)]*` stopped at the `)` inside the quote, so the commit reached no note and every
# later gate would have refused. What follows the id may now hold a parenthesised part: `(?:\([^()]*\)|[^)])*`, whose
# second branch is the old `[^)]` itself, so nothing the pattern matched before can stop matching. Measured over
# `git log --format=%s --no-merges` when it was widened: 270 subjects carry a front tag; it gains exactly one subject,
# that one, filed under §BH69; none is lost and no subject moves to another front; the front id is still group 1.
_FRONT_RE = re.compile(r"^\s*\w+\((§[A-Z]{1,3}[0-9]{0,3})((?:\+?\([a-z0-9]{1,4}\))*)"
                       r"(?:/§[A-Z]{1,3}[0-9]{0,3}(?:\([a-z0-9]{1,4}\))*)*"
                       r"(?:\([^()]*\)|[^)])*\):")


def front_notes(con_sittings, section_slugs):
    """One note per front (a §BH-goal) with its commits, its scores and its report.

    The commits come from git, which every clone has. The scores and the goal reports are the
    executor's, and they live in archive/work/bhNN_<what it holds>/ (git-ignored) — so they are cited by
    path and content hash and their presence is stated, rather than being silently embedded as
    though the repository carried them. A note whose source is machine-local says so in its own
    header, which is what `untracked:sha256:` is for.
    """
    log = subprocess.run(["git", "log", "--format=%H%x09%s", "--no-merges"],
                         cwd=str(OUTER), capture_output=True, text=True)
    commits = collections.defaultdict(list)
    for line in log.stdout.splitlines():
        if "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        m = _FRONT_RE.match(subject)
        if m:
            commits[m.group(1)].append((sha, subject))
    out = {}
    for front in sorted(commits):
        rows = list(reversed(commits[front]))          # oldest first: the chain as it was built
        n = front.lstrip("§").lower()
        # The executor's sealed predictions, scores and goal reports live in archive/work/, which
        # git does not track (until 2026-10-04: ~/bhNN_work/) — bh42 alone holds thousands of files, and
        # this front is writing into its own directory as the vault is generated. Enumerating it
        # would make a note change whenever a working file lands, so the vault would go stale for
        # a reason that has nothing to do with the repository and the freshness gate would refuse
        # the commit. The directory is therefore NAMED, never walked; what was IMPORTED from it
        # under §BH40(a)/§BH42(ii) is tracked evidence and is linked below instead.
        wdir = work_dir(n)
        evid = sorted({r[0] for r in con_sittings.execute(
            "SELECT DISTINCT path FROM docs WHERE kind = 'sitting' AND path LIKE ? ORDER BY path",
            ("%%/sittings/%s/%%" % n,))})
        body = ["# Front %s\n\n" % front,
                "| | |\n|---|---|\n",
                "| **commits** | %d |\n" % len(rows),
                "| **imported evidence files** | %d |\n" % len(evid),
                "| **executor work directory** | `%s` (git-ignored; named, never walked) |\n" % wdir,
                ]
        if front in section_slugs:
            body.append("| **ruling** | %s |\n" % link(section_slugs[front], front))
        body.append("\n## Commits, oldest first\n\n")
        body.extend("- `%s` %s\n" % (sha[:12], subject.split(" — ")[0][:150]) for sha, subject in rows)
        body.append("\n## Imported evidence (tracked)\n\n")
        body.extend("- `%s`\n" % e for e in evid[:200])
        if len(evid) > 200:
            body.append("- … and %d more\n" % (len(evid) - 200))
        if not evid:
            body.append("(nothing under docs/design_intelligence/sittings/%s/ — this front's evidence\n"
                        "was not imported, or was imported under another front's batch)\n" % n)
        body.append("\n## Scores and reports\n\n"
                    "The §AD0(a) sealed predictions, their scores and the goal report for this front are\n"
                    "the executor's working records in `%s`, which git does not track. That\n"
                    "directory is NAMED here and deliberately NOT enumerated: it is written to while this\n"
                    "vault is generated, so walking it would make this note change for reasons the\n"
                    "repository cannot see, and the freshness gate would then refuse commits that are\n"
                    "perfectly clean. What was imported from it is tracked, and is listed above.\n" % wdir)
        out["fronts/%s.md" % slug("front", front, front)] = header(
            "front", "git log", front, "Front %s" % front) + "".join(body)
    return out, sorted(commits)


def index_note(counts, section_slugs, fronts_present):
    body = ["# The system, mapped\n\n",
            "This vault is a VIEW. It is generated by `tools/brain/vault.py` as a step of\n"
            "`tools/brain/rebuild.py`, it is git-ignored, and it is disposable: delete it and a\n"
            "rebuild reproduces it byte-for-byte. Nothing here is authoritative — the file and\n"
            "line each note cites own the truth.\n\n",
            "## What is here\n\n",
            "| notes | what |\n|---|---|\n"]
    for k in sorted(counts):
        body.append("| %d | %s |\n" % (counts[k], k))
    body.append("\n## The register\n\n")
    live = sorted(s for s in section_slugs if s.startswith("§BH"))
    body.append("Every §section of `%s` has a note carrying its status, its text, the register\n"
                "line range, and links in both directions — what it cites and what cites it.\n\n"
                % S.REGISTER.name)
    body.append("### The §BH arc\n\n")
    body.extend("- %s\n" % link(section_slugs[s], s) for s in live)
    body.append("\n## The fronts\n\n")
    body.extend("- %s\n" % link(slug("front", f, f), f) for f in sorted(fronts_present))
    body.append("\n## The defect classes\n\n")
    body.extend("- %s\n" % link(slug("defect", k, k), k) for k in sorted(PIN_CLASSES))
    body.append("\n## The materials\n\n"
                "One note per group — a font family, or the pack a set of bytes sits in. Each carries\n"
                "its tier, its grant state, its credit condition, the captions and measured palettes of\n"
                "its members, and thumbnails ONLY where the member is PRODUCTION tier. A non-PRODUCTION\n"
                "thumbnail is named as withheld: a caption may be read, the bytes may not be placed.\n")
    return {"index.md": header("index", S.REGISTER.name, "index", "The system, mapped") + "".join(body)}


def _rmtree(p):
    p = pathlib.Path(p)
    for child in sorted(p.rglob("*"), reverse=True):
        if child.is_dir():
            child.rmdir()
        else:
            child.unlink()
    p.rmdir()


def write_notes(vault_dir, notes):
    """Written in sorted order, LF endings, UTF-8, no clock. The directory is REPLACED, not
    merged: a note whose source is gone must vanish, or the vault accumulates orphans that no
    regeneration reproduces."""
    vault_dir = pathlib.Path(vault_dir)
    staging = vault_dir.with_name(vault_dir.name + ".new")
    if staging.exists():
        _rmtree(staging)
    for rel in sorted(notes):
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(notes[rel])
    if vault_dir.exists():
        _rmtree(vault_dir)
    os.replace(staging, vault_dir)
    return {"notes": len(notes), "bytes": sum(len(t.encode("utf-8")) for t in notes.values())}


def digest(vault_dir=None):
    """A sha256 over (relative path, bytes) of every note, sorted. The freshness gate compares
    this: it refuses a hand-edited note as surely as a stale one, because both move the bytes."""
    vault_dir = pathlib.Path(vault_dir or VAULT)
    if not vault_dir.is_dir():
        return None
    h = hashlib.sha256()
    files = sorted(p for p in vault_dir.rglob("*") if p.is_file())
    for p in files:
        h.update(str(p.relative_to(vault_dir)).encode("utf-8")); h.update(b"\x00")
        h.update(p.read_bytes()); h.update(b"\x00")
    return {"notes": len(files), "sha256": h.hexdigest()}


def emit(con, vault_dir=None):
    """The rebuild step. Returns the record the freshness file carries."""
    vault_dir = pathlib.Path(vault_dir or VAULT)
    reg = _register_lines()
    queue = (S.QUEUE.read_text(encoding="utf-8", errors="replace").splitlines()
             if S.QUEUE.is_file() else [])
    notes = {}
    sec, section_slugs = sections_notes(con, reg, queue)
    notes.update(sec)
    les, lesson_index = lesson_notes(con, section_slugs)
    notes.update(les)
    notes.update(defect_class_notes(con, lesson_index, section_slugs))
    mats, mstats = material_notes(con)
    notes.update(mats)
    fronts, front_ids = front_notes(con, section_slugs)
    notes.update(fronts)
    counts = {"§section": len(sec), "lesson": len(les), "defect class": len(PIN_CLASSES),
              "material group": len(mats), "front": len(fronts)}
    notes.update(index_note(counts, section_slugs, front_ids))
    written = write_notes(vault_dir, notes)
    d = digest(vault_dir)
    return {"record_type": VAULT_RECORD_TYPE, "dir": "brain_vault", "tracked": False,
            "notes": written["notes"], "bytes": written["bytes"], "sha256": d["sha256"],
            "counts": counts, "thumbnails": mstats["thumbnails"],
            "thumbnails_withheld": mstats["withheld"],
            "thumbnail_rule": "PRODUCTION tier only; every other tier is named as withheld"}


def work_dir(n):
    """Front n's archived work directory, archive/work/<n>_<what it holds>/ (the clean-up of 2026-10-04 moved
    ~/<n>_work/ there under a name saying what it holds). Only archive/work/'s own top level is listed to find
    the one name; the directory itself is never walked. Machine-local, so absence is said, never guessed."""
    base = OUTER / "archive" / "work"
    hits = sorted(p.name for p in base.glob(n + "_*") if p.is_dir()) if base.is_dir() else []
    if len(hits) == 1:
        return "archive/work/%s/" % hits[0]
    return "archive/work/%s_*/ (%s on this machine)" % (n, "%d matches" % len(hits) if hits else "none")
