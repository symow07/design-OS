"""§BH54(b) (k) 4 — EACH PIECE'S ROOM, SHOWN AS HE TYPES.

The room is MEASURED, never estimated: the back panel's own composer (`apps/ire/back_panel.compose_back_panel`) over the
seven sections as the governed sheet would draw them — the product's written copy, the words being typed in place of a
piece, the placeholder where a piece has none — at the size the production-method record gives BODY_BACK, in the task's
own back zone (or the zone as typed in the loop's form). A piece's room is the number of copy lines it may have with
ALL SEVEN sections still inside the panel. Over its room a piece is still saved: "an over-room warning that informs
rather than refuses." Reads; writes nothing.
"""
from __future__ import annotations

import math

NO_ZONE = "this task has no confirmed back print zone, so no room can be measured — the words are saved all the same"
NO_FACE = "the face the copy is set in could not be measured here, so no room can be stated — the words are saved all the same"


def rooms(task, typed: dict | None = None, back_zone: dict | None = None) -> dict:
    """{"pieces": {piece: {copy_lines, room_lines, over, state, line}}, "fits", "total_line", …}."""
    from apps.ire import back_panel
    from apps.ire.container_production_method import build_production_methods
    from apps.pipeline.targets import container as C

    from . import owner_channel
    from .models import COPY_PIECES
    output = task.packaging_outputs.exclude(spec_sheet=None).order_by("-pk").first()
    spec = (output.spec_sheet or {}) if output is not None else {}
    zones = [dict(z) for z in (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []]
    zone = back_panel.back_zone(zones)
    if zone is None:
        return {"pieces": {}, "fits": None, "reason": NO_ZONE, "total_line": NO_ZONE}
    zone.update(back_zone or {})                                  # the zone as typed in the form, moved in memory
    typed = typed or {}
    written = owner_channel.written_copy(task.product)
    sections, _codes = C._back_sections_from_record(task.product)
    sections = [dict(s, text=typed[s["heading"]]) if s.get("heading") in typed else s for s in sections]
    methods = build_production_methods(zones, spec.get("container_profile/1.0") or {})
    _group, record = back_panel.compose_back_panel(sections, zone, 0.0, 0.0, methods_record=methods)
    if not record.get("fit_measured"):
        return {"pieces": {}, "fits": None, "reason": NO_FACE, "total_line": NO_FACE}
    pitch, required, available = record["line_height_mm"], record["height_required_mm"], record["height_available_mm"]
    size, overflow = record["size_pt"], record["overflow_mm"]
    pieces = {}
    for index, section in enumerate(record["sections"]):
        heading = section["heading"]
        if heading not in COPY_PIECES:
            continue
        copy_lines = sum(1 for e in record["lines"] if e["section"] == index and e["role"] == "copy")
        others = required - copy_lines * pitch                   # what every other line and gap needs
        room_lines = max(0, math.floor((available - others) / pitch + 1e-9))
        state = "typed" if heading in typed else "written" if heading in written else "unwritten"
        words = "%d line%s at %g pt · room for %d" % (copy_lines, "" if copy_lines == 1 else "s", size, room_lines)
        if state == "unwritten":
            words = "unwritten — the placeholder takes %s" % words
        over = copy_lines > room_lines
        pieces[heading] = {"copy_lines": copy_lines, "room_lines": room_lines, "over": over, "state": state,
                           "line": ("OVER ITS ROOM — %s; the panel overflows by %g mm. It is saved all the same if you "
                                    "save it." % (words, overflow)) if over and state != "unwritten" else words}
    total = "All seven sections need %g mm of the %g mm the back zone (%g × %g) gives at %g pt in a %g mm column — %s" % (
        required, available, float(zone["width"]), float(zone["height"]), size, record["column_mm"],
        "they fit." if record["fits"] else "over by %g mm: what the edge excludes is not drawn, and it blocks." % overflow)
    return {"pieces": pieces, "fits": record["fits"], "required_mm": required, "available_mm": available,
            "overflow_mm": overflow, "column_mm": record["column_mm"], "size_pt": size, "line_height_mm": pitch,
            "zone": {"width": float(zone["width"]), "height": float(zone["height"])}, "total_line": total}
