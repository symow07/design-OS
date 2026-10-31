"""Deterministic stepped kit and conservative, full-surface sightline proof.

No generative provider, capacity inference, image reconstruction or load rating.
Seat = bottle bottom; collars have holes and separate solid seats carry weight.
"""
from __future__ import annotations

import math

from apps.pipeline.services.assembly_spec import SURFACES, fact, facts


def value(obj, name):
    return getattr(obj, name).value


def sightlines(spec, seats, tread):
    """Certified lower bound over the complete surface, not sampled centre rays.

    Each preceding row is conservatively a full-width opaque wall to the full
    product envelope height. This overbounds circles, square vials, their caps
    and the lower decks/collars. At fixed obstacle exit y, the minimum ray z
    occurs at the nearest target y when eye z >= target bottom. We test that
    analytic bound. The row's entire decoration width is therefore covered.
    Report a *guaranteed visible fraction*, not an estimated actual fraction.
    The own collar and front riser/lip are included. Back panel is behind all
    targets. Side supports lie outside the convex eye-to-label x corridor.
    """
    e, r = spec.product_envelope, spec.rules
    bottom, dh = value(e, "decoration_bottom_mm"), value(e, "decoration_height_mm")
    if bottom is None or dh is None or value(e, "decoration_width_mm") is None:
        return [{"row": row+1, "visible_fraction_lower_bound": None, "passed": False,
                 "reason": "Kiss Me decoration region is unresolved; the S-2422 region cannot be transferred."} for row in range(3)]
    eye_y, eye_z = -value(r, "eye_front_mm"), value(r, "eye_above_base_mm")
    half_depth, ph = value(e, "depth_mm")/2, value(e, "height_mm")
    margin = value(r, "sightline_clearance_mm")
    rows = []
    for row, seat in enumerate(seats):
        cy = (row+.5)*tread
        near_y = cy-half_depth
        z0, z1 = seat+bottom, seat+bottom+dh
        blockers = []
        for prior in range(row):
            blockers.append((f"row {prior+1} conservative full-width product envelope", (prior+.5)*tread+half_depth, seats[prior]+ph))
        # A collar with a hole is bounded by an opaque plate at its top. Its
        # closest rim is before the target; using the target y is conservative.
        blockers.append(("own locating collar", near_y, seat+value(r, "collar_offset_mm")+value(r, "deck_thickness_mm")))
        blockers.append(("own riser", row*tread+value(r, "deck_thickness_mm"), seat))
        blockers.append(("front lip", value(r, "lip_thickness_mm"), seats[0]+value(r, "lip_height_mm")))
        cut, limiting = -math.inf, "none"
        for name, exit_y, top in blockers:
            if not eye_y < exit_y <= near_y:
                continue
            t = (exit_y-eye_y)/(near_y-eye_y)
            threshold = eye_z+(top+margin-eye_z)/t
            if threshold > cut:
                cut, limiting = threshold, name
        fraction = max(0., min(1., (z1-max(z0, cut))/dh))
        # If the eye is below the band bottom, the monotonic inequality used
        # above does not apply. Refuse instead of promoting a sampled result.
        valid_bound = eye_z >= z0 and near_y > value(r, "lip_thickness_mm")
        # A curved label must face the eye on its own bottle as well. The
        # visible angular interval is analytic: n dot (eye - surface) > 0.
        own_fraction = 1.
        if e.profile.value == "circle":
            radius=value(e,"width_mm")/2
            half_arc=value(e,"decoration_width_mm")/(2*radius)
            hole=value(spec.holes,"derived_size_mm")
            width=value(spec.envelope_requested,"width_mm")
            ligament=(width-4*hole)/5
            for col in range(4):
                cx=ligament+hole/2+col*(hole+ligament)
                a,b=width/2-cx,cy-eye_y
                rho=math.hypot(a,b)
                phi=math.atan2(a,b)
                limit=math.acos(min(1.,radius/rho))
                visible=max(0.,min(half_arc,phi+limit)-max(-half_arc,phi-limit))/(2*half_arc)
                own_fraction=min(own_fraction,visible)
        # Intersection lower bound; conservative even if occluded regions differ.
        fraction=max(0.,fraction+own_fraction-1.)
        passed = valid_bound and cut <= z0+1e-9 and own_fraction >= 1.-1e-12
        rows.append({"row": row+1, "seat_z_mm": seat, "front_surface_nearest_y_mm": near_y,
                     "decoration_z_mm": [z0, z1], "minimum_clear_target_z_mm": round(cut, 6),
                     "visible_fraction_lower_bound": round(fraction, 6) if valid_bound else None,
                     "passed": passed, "limiting_occluder": limiting, "own_surface_visible_fraction": round(own_fraction,6),
                     "method": "analytic full-width opaque-row bound; includes collar/riser/lip",
                     "reason": "Entire front decoration is clear with 0.25 mm ray margin." if passed else
                     ("Part of the curved decoration is hidden by its own bottle." if own_fraction < 1.-1e-12 else "The declared eye is below the lower decoration; this bound cannot certify visibility." if not valid_bound else "A preceding row or structural edge hides part of the front decoration.")})
    return rows


def solve(spec):
    e, rules, holes, requested = spec.product_envelope, spec.rules, spec.holes, spec.envelope_requested
    w, d, h = [value(requested, k) for k in ("width_mm", "depth_mm", "height_mm")]
    size, web = value(holes, "derived_size_mm"), value(holes, "minimum_web_mm")
    back, ht = value(rules, "back_web_mm"), value(rules, "header_thickness_mm")
    edge = value(holes, "edge_margin_mm")
    width_need = 4*size+3*web+2*max(web,edge)
    minimum_tread = max(size+web,size+2*edge)
    depth_need = 3*minimum_tread+back+ht
    tread = (d-back-ht)/3
    actual_web = (w-4*size)/5
    clearance = size-value(e, "width_mm")
    checks = []
    def check(key, passed, words, **measurements):
        checks.append({"check": key, "passed": bool(passed), "words": words, **measurements})
    check("width", width_need <= w, f"4 x {size:g} + 5 x {web:g} mm web = {width_need:g} mm; requested width {w:g} mm; margin {w-width_need:g} mm.", required_mm=width_need, available_mm=w)
    check("depth", depth_need <= d, f"3 x {minimum_tread:g} mm treads (hole {size:g} + two {edge:g} edge margins) + {back:g} back web + {ht:g} header = {depth_need:g} mm; requested depth {d:g} mm; margin {d-depth_need:g} mm.", required_mm=depth_need, available_mm=d)
    check("clearance", clearance > 0, f"Hole {size:g} minus product {value(e,'width_mm'):g} = {clearance:g} mm nominal total clearance ({clearance/2:g} per side). Zero clearance is refused.")
    check("support_corridor", actual_web+size/2-value(e,"width_mm")/2 >= value(rules,"deck_thickness_mm"), "Side support webs must stay outside every eye-to-decoration ray corridor.")
    base = value(rules, "base_thickness_mm")
    step = value(rules, "fixed_riser_mm") if value(rules, "riser_rule") == "fixed" else None
    if step is None and value(e, "decoration_bottom_mm") is not None and tread > 0:
        for candidate in range(math.ceil(value(rules,"deck_thickness_mm")), math.ceil(value(e,"height_mm")*2)+1):
            if all(r["passed"] for r in sightlines(spec, [base,base+candidate,base+2*candidate], tread)):
                step = float(candidate)
                break
    auto_failed = step is None
    # Diagnostic geometry is explicitly separate from a solution. Missing
    # decoration data never gets silently replaced to obtain a visibility pass.
    if step is None:
        step = 20.
    seats = [base+i*step for i in range(3)]
    table = sightlines(spec, seats, tread) if tread > 0 else []
    need_h = seats[-1]+value(e,"height_mm")+value(rules,"header_height_mm")
    check("height", need_h <= h, f"Back seat {seats[-1]:g} + bottle {value(e,'height_mm'):g} + header {value(rules,'header_height_mm'):g} = {need_h:g} mm; requested height {h:g} mm; shortfall {max(0.,need_h-h):g} mm. Bottle height uses the unresolved datum provisionally.", required_mm=need_h, available_mm=h)
    check("sightline", bool(table) and all(r["passed"] for r in table) and not auto_failed,
          "Kiss Me 16 x16 x98 mm has no declared decoration region: full-surface visibility is unresolved. The 32 x60 mm cylindrical serum region cannot be transferred." if value(e,"decoration_bottom_mm") is None else
          "All three complete decoration surfaces must be clear from the fixed proposed eye; no artwork is reduced or moved.")
    positions = []
    for row, seat in enumerate(seats):
        for col in range(4):
            positions.append({"id": f"r{row+1}-c{col+1}", "row": row+1, "col": col+1,
                              "x_mm": actual_web+size/2+col*(size+actual_web), "y_mm": (row+.5)*tread, "z_mm": seat,
                              "product_spec_hash": spec.product.spec_hash.value if e.profile.value == "circle" else None,
                              "source": "Derived from declared grid, hole size, actual web, tread and seat elevations"})
    if tread <= 0 or actual_web < 0:
        positions = []  # refuse unrenderable negative geometry, never shrink units
    decks = [{"row": i+1, "seat_elevation_mm": fact(z, source=f"Base {base:g} + row index {i} x rise {step:g}"),
              "tread_depth_mm": fact(tread, source="(Requested depth - back web - header thickness) / 3"),
              "riser_height_mm": fact(z if i==0 else step, source="Seat above base plane" if i==0 else "Difference between consecutive seat elevations"),
              "thickness_mm": rules.deck_thickness_mm.model_dump()} for i,z in enumerate(seats)]
    top = seats[-1]
    dimensions = {"header.front":(w,value(rules,"header_height_mm")),"header.back":(w,value(rules,"header_height_mm")),
                  "side.left":(d,top),"side.right":(d,top),"base.front":(w,base),"lip.front":(w,value(rules,"lip_height_mm"))}
    dimensions.update({f"riser.{i+1}.front":(w,base if i==0 else step) for i in range(3)})
    surfaces = [{"id": fact(s, source="Owner Day 3 required surface IDs"),
                 "width_mm":fact(dimensions[s][0],source="Derived assembly face width"),"height_mm":fact(dimensions[s][1],source="Derived assembly face height"),
                 "bleed_mm":fact(3.),"safe_mm":fact(min(4.,min(dimensions[s])/4),source="At most 4 mm, bounded to one quarter of the shorter provisional face"),"required_languages":spec.required_languages.model_dump(),
                 "copy_slots":fact([],source="Empty until Day 4 artwork binding"),
                 "required_copy":fact(spec.required_copy_by_surface.value.get(s,[]),"owner_provided",spec.source_brief.source),
                 "artwork":fact(None,"unresolved","Day 4 only, after accepted-concept fidelity master")} for s in SURFACES]
    material = value(rules,"material") or value(rules,"provisional_material")
    thickness = value(rules,"thickness_mm") or value(rules,"provisional_thickness_mm")
    parts = [{"part":"base / first solid seat","qty":1,"nominal_size_mm":[w,d,thickness]},
             *[{"part":f"row {i+1} solid seat","qty":1,"nominal_size_mm":[w,tread,thickness]} for i in (1,2)],
             *[{"part":f"row {i+1} locating collar; four openings","qty":1,"nominal_size_mm":[w,tread,thickness]} for i in range(3)],
             *[{"part":f"riser {i+1}","qty":1,"nominal_size_mm":[w,base if i==0 else step,thickness]} for i in range(3)],
             {"part":"rear support / header panel","qty":1,"nominal_size_mm":[w,h,thickness]},
             {"part":"stepped side support web","qty":2,"nominal_size_mm":[d,top,thickness]},
             {"part":"low front lip","qty":1,"nominal_size_mm":[w,value(rules,"lip_height_mm"),thickness]}]
    for p in parts:p.update(material=material,thickness_mm=thickness,status="PROVISIONAL nominal envelope; no cut or joining allowance")
    unresolved = [{"field":p,"reason":f["source"]} for p,f in facts(spec.model_dump()) if f["authority"]=="unresolved"]
    assumed = [{"field":p,**f} for p,f in facts(spec.model_dump()) if f["authority"]=="proposed"]
    assumed += [{"field":f"decks.{i}.{k}",**v} for i,deck in enumerate(decks) for k,v in deck.items() if isinstance(v,dict)]
    status = "solution_provisional" if all(c["passed"] for c in checks) else "refused"
    return dict(schema_version="assembly_solution/1.0",status=status,checks=checks,positions=positions,decks=decks,
                envelope_requested=[w,d,h],envelope_realised=[w,d,max(h,seats[-1]+value(e,"height_mm"))] if positions else None,
                required_height_mm=need_h,uniform_rise_mm=step,diagnostic_rise_only=auto_failed,
                tread_mm=tread,actual_edge_web_mm=actual_web,nominal_clearance_per_side_mm=clearance/2,
                viewpoint={"x_mm":w/2,"y_mm":-value(rules,"eye_front_mm"),"z_mm":value(rules,"eye_above_base_mm"),"authority":"proposed","source":"Owner requested provisional 500 mm front / 350 mm above base"},
                sightline_table=table,print_surfaces=surfaces,hole_schedule=[dict(p,profile=holes.profile.value,size_mm=size) for p in positions],
                preliminary_parts=parts,provenance=assumed,unresolved=unresolved,
                no_load_rating=True,physical_verification="unresolved",artwork_bound=False,
                refusal_reasons=[c["words"] for c in checks if not c["passed"]])


def accept_legacy_tray(tray):
    """An arithmetic grid cannot satisfy the new assembly contract."""
    return {"status":"refused","reasons":["Not a stepped assembly: no three distinct seat elevations.",
            "No declared hole schedule or exact twelve exported bottle instances.","No full-surface sightline proof or requested envelope check."],
            "legacy_fit":tray}
