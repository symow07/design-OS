"""Resource guards (safeguard 3).

A `Budget` tracks a page's consumption against `Limits`. Reaching a limit is a
recorded event — never an exception, never a silent omission.

Two kinds of limit, deliberately distinguished:

* **sampling** — a bounded sample was taken while the *aggregate statistics
  remain complete* (e.g. `max_paths_detailed`). You approved exactly this:
  "the detailed outputs do not need to serialize every one of tens of thousands
  of paths when aggregate statistics and bounded samples are sufficient."
  Nothing is lost, so confidence is not reduced.
* **data_loss** — information we would otherwise have used was skipped (e.g. the
  xref sweep was cut short, a page timed out). Confidence *is* reduced.

`truncated` is true whenever any limit was reached, per the safeguard. Only
`data_loss` reduces confidence — "reduce confidence accordingly" means
proportional to actual impact, and a bounded sample has none.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import Limits

SAMPLING = "sampling"
DATA_LOSS = "data_loss"


@dataclass
class Budget:
    limits: Limits
    limits_hit: list[str] = field(default_factory=list)
    sampling_limits: list[str] = field(default_factory=list)
    data_loss_limits: list[str] = field(default_factory=list)
    skipped: dict[str, int] = field(default_factory=dict)
    _t0: float = field(default_factory=time.monotonic)
    _xref_skip_recorded: bool = False

    # --- recording ---------------------------------------------------------
    def hit(self, limit_name: str, value, kind: str = DATA_LOSS,
            skipped_kind: str | None = None, skipped_count: int = 0) -> None:
        entry = f"{limit_name}={value}"
        if entry not in self.limits_hit:
            self.limits_hit.append(entry)
        bucket = self.sampling_limits if kind == SAMPLING else self.data_loss_limits
        if entry not in bucket:
            bucket.append(entry)
        if skipped_kind and skipped_count:
            self.skipped[skipped_kind] = self.skipped.get(skipped_kind, 0) + skipped_count

    # --- queries -----------------------------------------------------------
    @property
    def truncated(self) -> bool:
        return bool(self.limits_hit)

    @property
    def data_loss(self) -> bool:
        return bool(self.data_loss_limits)

    @property
    def aggregates_complete(self) -> bool:
        """True when every statistic covers the whole document."""
        return not self.data_loss

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._t0

    def out_of_time(self) -> bool:
        if self.elapsed > self.limits.max_page_seconds:
            self.hit("max_page_seconds", self.limits.max_page_seconds, DATA_LOSS)
            return True
        return False

    def sample(self, seq, limit: int, limit_name: str, kind: str) -> list:
        """Bounded sample. Aggregates elsewhere still describe every item."""
        items = list(seq)
        if len(items) > limit:
            self.hit(limit_name, limit, SAMPLING,
                     skipped_kind=kind, skipped_count=len(items) - limit)
            return items[:limit]
        return items

    def xref_scan_range(self, xref_length: int) -> range:
        """Bounded xref sweep. Recorded ONCE per budget even if called again —
        a single logical sweep must not be counted several times."""
        stop = min(xref_length, self.limits.max_xref_scan)
        if xref_length > stop and not self._xref_skip_recorded:
            self._xref_skip_recorded = True
            self.hit("max_xref_scan", self.limits.max_xref_scan, DATA_LOSS,
                     skipped_kind="xref_objects", skipped_count=xref_length - stop)
        return range(1, stop)

    def render_zoom(self, width_pt: float, height_pt: float) -> float:
        """Zoom keeping the long edge within `max_render_px` and total pixels
        within `max_mask_pixels`. A preview clamp costs no analytical fidelity."""
        long_edge = max(width_pt, height_pt) or 1.0
        z = min(1.0, self.limits.max_render_px / long_edge)   # never upscale
        if long_edge > self.limits.max_render_px:
            self.hit("max_render_px", self.limits.max_render_px, SAMPLING)
        px = (width_pt * z) * (height_pt * z)
        if px > self.limits.max_mask_pixels:
            z *= (self.limits.max_mask_pixels / px) ** 0.5
            self.hit("max_mask_pixels", self.limits.max_mask_pixels, SAMPLING)
        return z

    # --- reporting ---------------------------------------------------------
    def confidence_penalty(self) -> float:
        if not self.data_loss:
            return 1.0
        return max(0.4, 1.0 - 0.15 * len(self.data_loss_limits))

    def to_dict(self) -> dict:
        return {
            "truncated": self.truncated,
            "data_loss": self.data_loss,
            "aggregates_complete": self.aggregates_complete,
            "limits_hit": list(self.limits_hit),
            "sampling_limits": list(self.sampling_limits),
            "data_loss_limits": list(self.data_loss_limits),
            "skipped": dict(self.skipped),
            "confidence_penalty": round(self.confidence_penalty(), 3),
            "elapsed_seconds": round(self.elapsed, 2),
            "limits": self.limits.to_dict(),
            "note": ("sampling limits bound the serialized detail only; aggregate "
                     "statistics remain complete. data_loss limits skip information "
                     "and reduce confidence."),
        }
