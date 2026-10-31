"""THE BRAIN — the sources (§BH40(a)), enumerated one way for the rebuild, the freshness record and the gate test.

Every path here is READ. Nothing in this module writes. The enumeration is deterministic and machine-local
only where a source is machine-local by the owner's ruling (the DIP-0A records under the git-ignored var/,
the executor's prompt files under ~/.claude).
"""
import hashlib, os, pathlib, json

OUTER = pathlib.Path(__file__).resolve().parents[3]            # the git root (the brain sits in bbrose_design_os/tools/brain/ since 2026-10-04)
INNER = OUTER / "bbrose_design_os"                              # the Django root
HOME = pathlib.Path.home()
MEMORY_DIR = HOME / ".claude" / "projects" / "-Users-symow-Desktop-bbrose-systemOS" / "memory"
BRAIN_DIR = pathlib.Path(os.environ.get("BRAIN_DIR") or (OUTER / "var" / "brain"))
DB_PATH = BRAIN_DIR / "brain.sqlite"
FRESHNESS_PATH = BRAIN_DIR / "freshness.json"
FRESHNESS_RECORD_TYPE = "brain_freshness/1.0"

REGISTER = OUTER / "OWNER_BLOCKER_CLEARANCE.md"
QUEUE = OUTER / "OWNER_REVIEW_QUEUE.md"
SITTINGS = OUTER / "docs" / "design_intelligence" / "sittings"
WATCH = OUTER / "docs" / "design_intelligence" / "watch"
CLAUDE_MD = OUTER / "CLAUDE.md"
GATE_LAUNCHERS = ("guarded_commit.sh", "tier2_gate.py", "record_integrity.py", "extent_gate.py", "flake_gate.py")
LAUNCHER_DOCS = ("NEXT_SESSION_LAUNCHER.md", "NEXT_NODE_LAUNCHER.md", "OWNER_BLOCKER_SESSION.md"); LAUNCHERS = INNER / "docs" / "archive" / "launchers"  # off the top level since the clean-up of 2026-10-04
INVENTORY = OUTER / "var" / "design_intelligence" / "audits" / "dip0" / "inventory" / "inventory.jsonl"
# §BH55 Phase 4: the tier record is tracked evidence now (docs/), not an ignored audit output; the ignored copy is
# read only where the tracked one is absent, so a machine mid-migration still indexes what it has
TIERS = OUTER / "docs" / "design_intelligence" / "tiers" / "materials_tiers.jsonl"
if not TIERS.exists():
    TIERS = OUTER / "var" / "design_intelligence" / "audits" / "dip0" / "tiers" / "materials_tiers.jsonl"
MATERIALS_GRANTS = INNER / "apps" / "ire" / "materials_owner_grant.py"
FONT_GRANTS = INNER / "apps" / "ire" / "container_font_owner_grant.py"
FONTS_CENSUS = SITTINGS / "bh27" / "census_rows.json"
DAY6_FONTS_CENSUS = OUTER / 'docs/audit/day-6/library/fonts-census.json'
MATERIALS_MIGRATION = OUTER / 'docs/audit/day-6/library/manifest-2026-10-19.jsonl'
# Day 8 §1c: the later move the resolver reads after the Day 6 manifest (apps/ire/materials_paths.LATER_MANIFESTS) — the
# captions' physical paths in the index follow it, so its hash is part of the freshness record
MATERIALS_MOVES = (OUTER / 'docs/audit/day-8/library/house-designs-manifest.jsonl',)

KINDS = ("register", "queue", "sitting", "watch", "launcher", "prompt", "record", "grant")


def label(path: pathlib.Path) -> str:
    """The citation form: repo-relative where the file is in the repo, absolute otherwise (the prompt files)."""
    try:
        return str(path.resolve().relative_to(OUTER))
    except ValueError:
        return str(path.resolve())


def enumerate_sources():
    """[(kind, path)] — every file the brain reads, in one fixed order. Absent optional files are skipped
    and named in absent_sources() so the record says what was not there."""
    out = []
    out.append(("register", REGISTER)); out.append(("queue", QUEUE))
    for root, kind in ((SITTINGS, "sitting"), (WATCH, "watch")):
        if root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.name != ".DS_Store":
                    out.append((kind, p))
    for name in GATE_LAUNCHERS:
        p = INNER / "tools" / name
        if p.is_file(): out.append(("launcher", p))
    for p in sorted(LAUNCHERS.glob("LAUNCHER_*.md")):
        out.append(("launcher", p))
    for name in LAUNCHER_DOCS:
        p = LAUNCHERS / name
        if p.is_file(): out.append(("launcher", p))
    if CLAUDE_MD.is_file(): out.append(("prompt", CLAUDE_MD))
    if MEMORY_DIR.is_dir():
        for p in sorted(MEMORY_DIR.glob("*.md")):
            out.append(("prompt", p))
    for p in (INVENTORY, TIERS, DAY6_FONTS_CENSUS, MATERIALS_MIGRATION) + MATERIALS_MOVES:
        if p.is_file(): out.append(("record", p))
    for p in (MATERIALS_GRANTS, FONT_GRANTS):
        if p.is_file(): out.append(("grant", p))
    return out


def absent_sources():
    """The optional sources that were not on disk at enumeration time — recorded, never silently skipped."""
    absent = []
    for name, p in (("CLAUDE.md", CLAUDE_MD), ("memory dir", MEMORY_DIR), ("inventory", INVENTORY), ("tiers", TIERS),
                    ("sittings", SITTINGS), ("watch", WATCH), ("launchers", LAUNCHERS)):
        if not p.exists(): absent.append({"name": name, "path": label(p)})
    return absent


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def current_source_hashes():
    """{label: sha256} for every enumerated source, as the freshness record stores them."""
    return {label(p): sha256_file(p) for _, p in enumerate_sources()}


def read_freshness(path: pathlib.Path = None):
    path = path or FRESHNESS_PATH
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def compare_freshness(record, current=None):
    """The gate's question: does the record agree with the sources on disk NOW?
    Returns (fresh: bool, findings: [str]) — every disagreement named by path."""
    findings = []
    if record is None:
        return False, ["NO_FRESHNESS_RECORD: no record at %s — run tools/brain/rebuild.py" % FRESHNESS_PATH]
    if record.get("record_type") != FRESHNESS_RECORD_TYPE:
        findings.append("RECORD_TYPE: %r is not %s" % (record.get("record_type"), FRESHNESS_RECORD_TYPE))
    current = current if current is not None else current_source_hashes()
    recorded = record.get("sources", {})
    for k in sorted(set(recorded) - set(current)):
        findings.append("SOURCE_GONE: %s was indexed and is no longer enumerated" % k)
    for k in sorted(set(current) - set(recorded)):
        findings.append("SOURCE_NEW: %s is enumerated and was not indexed" % k)
    for k in sorted(set(current) & set(recorded)):
        if current[k] != recorded[k]:
            findings.append("SOURCE_CHANGED: %s" % k)
    return (not findings), findings
