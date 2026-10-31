"""Provenance envelope.

Every machine-inferred value carries where it came from, what evidence backed
it, how confident we are, when it was extracted and by which parser. Machine
inference and human confirmation live in SEPARATE blocks and never overwrite
each other — `human_confirmed` is only ever written by a person.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


#: §BH55 Phase 4 ("the wall-clock fixtures"). The one clock every dip0 and dip0c record is stamped with. It is the
#: reason `c3b3_known_limitations.md` L8 stands: the pilots write `recorded_at` / `generated_at` from it, so
#: re-running one re-touches the committed `examples_TEST_ONLY/` records and `git status` shows churn for a value
#: that encodes nothing. L8's own remedy — "Making the examples byte-stable would need a frozen clock in the
#: runner" — is this: set DIP0_CLOCK to an ISO-8601 instant and every record stamps that instead. Unset, nothing
#: changes. A value that will not parse is REFUSED rather than ignored, because a frozen clock that silently
#: falls back to the wall clock is worse than none: the run looks reproducible and is not.
CLOCK_ENV = "DIP0_CLOCK"


def now_iso() -> str:
    frozen = os.environ.get(CLOCK_ENV)
    if frozen:
        try:
            parsed = datetime.fromisoformat(frozen)
        except ValueError as exc:
            raise ValueError(
                "%s=%r is not an ISO-8601 instant; a frozen clock that cannot be read must refuse, "
                "not fall back to the wall clock" % (CLOCK_ENV, frozen)) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Inferred:
    """One machine-inferred value + its provenance."""

    value: Any
    source: str                       # e.g. "path_rule", "magic_bytes", "fontTools"
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0           # 0.0-1.0
    extracted_at: str = field(default_factory=now_iso)
    parser: str | None = None         # e.g. "fontTools/4.63.0"

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "source": self.source,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 3),
            "extracted_at": self.extracted_at,
            "parser": self.parser,
        }


def human_block() -> dict:
    """Human-curation fields. Machine code MUST leave these untouched."""
    return {
        "category": None,
        "license_status": None,
        "ownership_status": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "notes": "",
    }
