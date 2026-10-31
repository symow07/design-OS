"""§BH52(b) SLICE 1 — EXPLORATIONS IN HISTORY, labelled and never mistakable for accepted work.

An exploration (§BH51(a)) is ungoverned and disposable: no commit, no gate, no register entry, no prediction, and
it never claims a state it has not earned — an explored render is never verified, never accepted, never evidence,
and carries that in its record. The pictures live in a store OUTSIDE the repository, MEDIA_ROOT, both var/ trees
and every source the brain reads; /files/ resolves under MEDIA_ROOT only, so this module reads the store itself
(the divergence from "the authenticated path that already exists" is recorded in the §BH52 reading).

This module reads and never writes. A record is shown only when its status is the one exploration value and no key
or value in it claims a state; anything else is refused by name and its picture is not served.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

from apps.pipeline.services.rbv5_comparison_gate import FORBIDDEN_ACCEPTANCE_KEYS, FORBIDDEN_SCORE_KEYS

EXPLORATION_STATUS = "EXPLORATION — never verified, never accepted, never evidence"

#: the rbv5 comparison contract's key names, read from it (apps/pipeline/services/rbv5_comparison_gate.py:162-178),
#: and the two it does not refuse — "verified" and "verification" — which a record must not carry either
CLAIM_KEYS = frozenset(FORBIDDEN_ACCEPTANCE_KEYS | FORBIDDEN_SCORE_KEYS | {"verified", "verification"})
#: state values a record claims by carrying them anywhere
CLAIM_VALUES = frozenset({"VERIFIED_FOR_PRODUCTION", "GRANTED", "RECONSTRUCTED", "ACCEPTED", "APPROVED",
                          "PASS", "MEASURED_PASS", "READY", "PRODUCTION_READY"})

REFUSED_NO_STATUS = "REFUSED — the record does not carry the exploration status as its one status value"
REFUSED_CLAIM_KEY = "REFUSED — the record carries a key that claims a state: %s"
REFUSED_CLAIM_VALUE = "REFUSED — the record carries a state value it has not earned: %s"
REFUSED_UNREADABLE = "REFUSED — the record is not readable JSON"
REFUSED_PICTURE = "REFUSED — the picture is not a PNG inside its study"
#: §BH54(i): explorations are the owner's — served to the OWNER_ACCOUNT alone, every other signed-in account refused
#: by name, before any store byte is read; an unset OWNER_ACCOUNT serves nobody and says so
EXPLORATIONS_OWNER_ONLY = "EXPLORATIONS_OWNER_ONLY"
EXPLORATIONS_OWNER_UNSET = "EXPLORATIONS_OWNER_UNSET"
REFUSED_NOT_OWNER = ("%s: REFUSED — explorations are served to the owner account only; %s is not it (§BH54(i))"
                     % (EXPLORATIONS_OWNER_ONLY, "%s"))
REFUSED_OWNER_UNSET = ("%s: REFUSED — no owner account is named (OWNER_ACCOUNT is unset), so explorations are served "
                       "to nobody (§BH54(i))" % EXPLORATIONS_OWNER_UNSET)


def owner_account() -> str:
    return str(getattr(settings, "OWNER_ACCOUNT", "") or "").strip()


def owner_refusal(user) -> str | None:
    """§BH54(i): None for the owner account; else the refusal, by name with its code. A superuser is not the owner
    unless named — the second superuser on the record would otherwise be served."""
    owner = owner_account()
    if not owner:
        return REFUSED_OWNER_UNSET
    name = getattr(user, "get_username", lambda: "")()
    if name != owner:
        return REFUSED_NOT_OWNER % (name or "an anonymous account")
    return None

_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$")


def store_root() -> Path:
    return Path(getattr(settings, "EXPLORATION_STORE", None) or (Path.home() / "bbrose_explorations")).resolve()


def governed_roots() -> list:
    base = Path(settings.BASE_DIR).resolve()
    return [base, base.parent, Path(settings.MEDIA_ROOT).resolve(), base / "var", base.parent / "var",
            Path.home() / ".claude"]


def store_is_outside_governed_roots() -> bool:
    root = store_root()
    return not any(root == g or root.is_relative_to(g) for g in governed_roots())


def claims(record) -> str:
    """The first claim a record makes, by name, or '' when it makes none."""
    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if str(k).lower() in CLAIM_KEYS:
                    return REFUSED_CLAIM_KEY % k
                found = walk(v)
                if found:
                    return found
        elif isinstance(value, list):
            for v in value:
                found = walk(v)
                if found:
                    return found
        elif isinstance(value, str) and value.strip().upper() in CLAIM_VALUES:
            return REFUSED_CLAIM_VALUE % value
        return ""
    if not isinstance(record, dict) or record.get("status") != EXPLORATION_STATUS:
        return REFUSED_NO_STATUS
    return walk(record)


def _study_dir(study: str):
    if not _SLUG.match(study or ""):
        return None
    root = store_root()
    path = (root / study).resolve()
    return path if path.is_relative_to(root) and path.is_dir() and path != root else None


def _picture(study_dir: Path, entry: dict) -> dict:
    name = str(entry.get("picture") or "")
    shown = {"picture": name, "refused": "", "record": {}, "url": None, "file": None}
    if not _SLUG.match(name):
        shown["refused"] = REFUSED_PICTURE
        return shown
    try:
        record = json.loads((study_dir / (name + ".json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        shown["refused"] = REFUSED_UNREADABLE
        return shown
    shown["record"] = record
    shown["refused"] = claims(record)
    png = (study_dir / (name + ".png")).resolve()
    if not shown["refused"] and not (png.is_relative_to(study_dir) and png.is_file() and png.suffix == ".png"):
        shown["refused"] = REFUSED_PICTURE
    if not shown["refused"]:
        shown["file"] = png
        shown["url"] = "/dashboard/history/explorations/%s/%s.png" % (study_dir.name, name)
    return shown


def study(study: str):
    """One study: its index, and each picture with its record — or its refusal, by name."""
    study_dir = _study_dir(study)
    if study_dir is None:
        return None
    try:
        index = json.loads((study_dir / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"slug": study_dir.name, "refused": REFUSED_UNREADABLE, "pictures": [], "index": {}}
    index_claim = claims(index)
    pictures = [] if index_claim else [_picture(study_dir, e) for e in index.get("pictures", [])
                                       if isinstance(e, dict)]
    tasks = sorted({p["record"].get("task") for p in pictures if isinstance(p["record"].get("task"), int)})
    return {"slug": study_dir.name, "refused": index_claim, "index": index, "pictures": pictures, "tasks": tasks,
            "status": EXPLORATION_STATUS}


def studies() -> list:
    root = store_root()
    if not root.is_dir() or not store_is_outside_governed_roots():
        return []
    found = []
    for path in sorted(root.iterdir()):
        if path.is_dir() and (path / "index.json").is_file():
            s = study(path.name)
            if s is not None:
                found.append(s)
    return found


def for_task(task_id: int) -> list:
    return [s for s in studies() if task_id in s.get("tasks", [])]


def picture_file(study_slug: str, picture: str):
    """The PNG of a picture whose record carries no claim, bounded to its study — or None."""
    s = study(study_slug) if store_is_outside_governed_roots() else None
    if not s or s["refused"]:
        return None
    return next((p["file"] for p in s["pictures"] if p["picture"] == picture and p["file"]), None)
