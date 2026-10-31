"""Relocate bytes without relocating the rights attached to their original identity.

The manifest is path bijective. Equal bytes at two paths remain two identities.
No Django or database dependencies, so exports and offline tools share this seam.

Day 8 §1c (annotation, the house designs into materials/house-designs/): a later rename-only move of files the Day 6
manifest already placed is a second manifest, read after the Day 6 one (LATER_MANIFESTS). Each of its rows continues a
Day 6 row: ``from`` is that row's ``new_path`` with the same sha256, ``to`` the file's home now. The composed row keeps
``old_path`` — the identity that rights, tiers, grants, captions and placement key on — takes ``to`` as ``new_path``
and names the paths between in ``via``. The original path, each intermediate path and the new path all return that
row, and exactly one of them may hold the file. Anything else in a later manifest refuses (fail closed). With no later
manifest on disk every answer is the Day 6 answer.
"""
from pathlib import Path
from functools import lru_cache
import copy, hashlib, json

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_RELATIVE = 'docs/audit/day-6/library/manifest-2026-10-19.jsonl'
#: later rename-only moves, read after the Day 6 manifest in this order (Day 8 §1c: the house designs)
LATER_MANIFESTS = ('docs/audit/day-8/library/house-designs-manifest.jsonl',)


class MaterialPathError(ValueError):
    pass


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _relative(src, root):
    p = Path(src)
    if p.is_absolute():
        try:
            p = p.relative_to(root)
        except ValueError:
            try:
                p = (p.parent.resolve() / p.name).relative_to(root)
            except ValueError:
                return None
    if not p.parts or p.parts[0] != 'materials':
        return None
    if '..' in p.parts:
        raise MaterialPathError('Material path traversal')
    return p.as_posix()


@lru_cache(maxsize=8)
def _read_manifest(path, size, mtime_ns):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    old, new = {}, {}
    for row in rows:
        a, b = row['old_path'], row['new_path']
        if a in old or b in new or not a.startswith('materials/') or not b.startswith('materials/'):
            raise MaterialPathError('Ambiguous or unbounded migration manifest')
        old[a] = row; new[b] = row
    for key in old.keys() & new.keys():
        if old[key] != new[key]:
            raise MaterialPathError('Overlapping migration identities')
    return old, new


@lru_cache(maxsize=8)
def _read_moves(path, size, mtime_ns):
    """A later move manifest: {from: row}; bounded, one row per source and per destination."""
    moves, targets = {}, set()
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line); a, b = row['from'], row['to']
        for p in (a, b):
            if not p.startswith('materials/') or '..' in Path(p).parts:
                raise MaterialPathError('Unbounded move manifest')
        if a == b or a in moves or b in targets:
            raise MaterialPathError('Ambiguous move manifest')
        moves[a] = row; targets.add(b)
    return moves


@lru_cache(maxsize=8)
def _composed(day6_key, later_keys):
    """{path: composed row} for every Day 6 row a later manifest continues, under its original path, every
    intermediate path and its new path. Keyed by every manifest's (path, size, mtime), so a changed file is re-read."""
    old, new = _read_manifest(*day6_key)
    moves = {}
    for key in later_keys:
        for a, row in _read_moves(*key).items():
            if a in moves:
                raise MaterialPathError('Two move manifests move one path')
            moves[a] = row
    targets = {row['to'] for row in moves.values()}
    if targets & (old.keys() | new.keys()):
        raise MaterialPathError('A move destination is a migrated identity')
    composed, continued = {}, set()
    for start in moves:
        if start in targets:
            continue                                   # a later hop: composed from its chain's first row
        if start not in new:
            raise MaterialPathError('A move names a file the migration manifest does not place')
        base = new[start]; hops = []; path = start; seen = {start}
        while path in moves:
            hop = moves[path]
            if hop['sha256'] != base['sha256']:
                raise MaterialPathError('Move manifest disagrees with migration identity')
            hops.append(hop); continued.add(path); path = hop['to']
            if path in seen:
                raise MaterialPathError('Cyclic move manifests')
            seen.add(path)
        via = [p for p in [base['new_path']] + [h['to'] for h in hops[:-1]] if p != base['old_path']]
        row = dict(base, new_path=path, via=via)
        for name in [base['old_path']] + via + [path]:
            composed[name] = row
    if set(moves) - continued:
        raise MaterialPathError('A move continues no migrated row')
    return composed


def _later_keys(root):
    keys = []
    for relative in LATER_MANIFESTS:
        try:
            stat = (root / relative).stat()
        except FileNotFoundError:
            continue
        keys.append((str(root / relative), stat.st_size, stat.st_mtime_ns))
    return tuple(keys)


def migration_row(src, *, repo_root=REPO_ROOT, manifest_path=None):
    root = Path(repo_root).resolve(); relative = _relative(src, root)
    if relative is None:
        return None
    manifest = Path(manifest_path) if manifest_path else root / MANIFEST_RELATIVE
    if not manifest.exists():
        return None
    stat = manifest.stat(); old, new = _read_manifest(str(manifest), stat.st_size, stat.st_mtime_ns)
    later = _later_keys(root)
    if later:
        row = _composed((str(manifest), stat.st_size, stat.st_mtime_ns), later).get(relative)
        if row is not None:
            return row
    return old.get(relative) or new.get(relative)


def original_material_key(src, sha, *, repo_root=REPO_ROOT, manifest_path=None):
    root = Path(repo_root).resolve(); relative = _relative(src, root)
    row = migration_row(src, repo_root=root, manifest_path=manifest_path)
    if row:
        if sha != row['sha256']:
            raise MaterialPathError('Pinned material digest disagrees with migration identity')
        relative = row['old_path']
    return relative, sha


def resolve_material_file(src, *, repo_root=REPO_ROOT, expected_sha=None, manifest_path=None):
    root = Path(repo_root).resolve(); relative = _relative(src, root)
    path = Path(src) if Path(src).is_absolute() else root / src
    if relative is None:
        return path
    row = migration_row(src, repo_root=root, manifest_path=manifest_path)
    if row and expected_sha is not None and expected_sha != row['sha256']:
        raise MaterialPathError('Pinned material digest disagrees with migration identity')
    candidates = [root / name for name in dict.fromkeys([row['old_path'], *row.get('via', ()), row['new_path']])] if row else [path]
    present = []
    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root / 'materials')
        except ValueError as exc:
            raise MaterialPathError('Material path escapes corpus') from exc
        if candidate.exists():
            if not resolved.is_file():
                raise MaterialPathError('Material is not a regular file')
            present.append(resolved)
    if row and len(present) != 1:
        raise MaterialPathError('Migrated material missing or ambiguous')
    if not present:
        return path  # Preserve existing unavailable-path handling for unmapped assets.
    selected = present[0]; digest = row['sha256'] if row else expected_sha
    if digest and sha256(selected) != digest:
        raise MaterialPathError('Material bytes changed')
    return selected


def resolved_document_images(doc, *, skip=()):
    """Call only after placement policy; return a clone, never alter saved graphs."""
    from apps.ire.graph import Image
    selected={node.name for node,_ in doc.walk() if isinstance(node,Image) and node.name not in skip and migration_row(node.src,repo_root=REPO_ROOT)}
    if not selected:return doc
    result = copy.deepcopy(doc)
    for node, _ in result.walk():
        if isinstance(node, Image) and node.name in selected:
            node.src = str(resolve_material_file(node.src, repo_root=REPO_ROOT))
    return result
