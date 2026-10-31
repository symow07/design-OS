"""Qualification runner (2A-9B §5/§6/§7) — archetype adapters + matrix.

Generic (§11): an :class:`ArchetypeAdapter` supplies everything
archetype-specific; ``qualify()`` and ``qualification_matrix()`` work for
any adapter. Qualifying one archetype never validates another — each needs
its own adapter, domain, matrix and physical evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArchetypeAdapter:
    template: str
    version: str
    panel_sequence: list[str]
    #: 2A-9C slice 0 — the explicit closure capability declaration; the
    #: invariants, folded simulator and collision checks read THIS, never
    #: an assumption that every archetype has entry-slit ears.
    closure: object = None
    domain_constraints: tuple = ()
    #: what the user-supplied W/D/H MEAN for this archetype: "inner"
    #: (opposed-tuck) or "manufacture" (legacy engine archetypes)
    dims_semantics: str = "inner"
    #: optional per-archetype deterministic in-domain sampler
    in_domain_sampler: object = None
    _calc: object = None
    _collision: object = None
    _hashes: object = None

    # --- capability views (all derived from the closure model) -----------
    @property
    def top_tuck_panel(self):
        return self.closure.top_tuck_panel

    @property
    def bottom_tuck_panel(self):
        return self.closure.bottom_tuck_panel

    @property
    def dust_panels(self):
        return list(self.closure.dust_panels)

    @property
    def expected_slit_count(self):
        return self.closure.expected_slit_line_count

    @property
    def key(self) -> str:
        return f"{self.template}/{self.version}"

    def build_params(self, user: dict):
        from apps.dielines.validators.schema import DielineInputJSON
        return DielineInputJSON(
            template=self.template, template_version=self.version,
            unit="mm",
            dimensions={"width_mm": user["width_mm"],
                        "depth_mm": user["depth_mm"],
                        "height_mm": user["height_mm"]},
            print_settings={"bleed_mm": user.get("bleed_mm", 3.0),
                            "safe_margin_mm": user.get("safe_margin_mm", 4.0)},
            construction={"glue_tab_mm": user.get("glue_tab_mm", 12.0),
                          "board_thickness_mm": user["board_thickness_mm"],
                          "thickness_compensation": True},
            metadata={"product_name": "QUALIFICATION",
                      "product_type": "parametric fixture"},
        )

    def calculate(self, _inner_ignored=None, _coords_ignored=None):
        # invariants use this for the determinism re-run; always rebuilt
        # from the ORIGINAL user parameters (whatever their semantics)
        from apps.dielines.geometry.engine import calculate_dieline
        return calculate_dieline(self.build_params(dict(self._last_user)))

    def collision_report(self, coords):
        return self._collision(coords)

    def content_hashes(self, coords):
        return self._hashes(coords)


def opposed_tuck_adapter() -> ArchetypeAdapter:
    from apps.dielines.geometry import opposed_tuck
    from apps.dielines.qualification.closure import OPPOSED_TUCK_CLOSURE
    from apps.dielines.qualification.domain import OPPOSED_TUCK_DOMAIN
    return ArchetypeAdapter(
        template=opposed_tuck.TEMPLATE_ID, version="0.1",
        panel_sequence=["glue_tab", "main_a", "side_a", "main_b", "side_b"],
        closure=OPPOSED_TUCK_CLOSURE,
        domain_constraints=OPPOSED_TUCK_DOMAIN,
        _calc=opposed_tuck.calculate_opposed_tuck,
        _collision=opposed_tuck.collision_report,
        _hashes=opposed_tuck.geometry_content_hashes,
    )


#: 2A-9C: adapter registry — the qualification endpoint, the UI and the
#: report command look archetypes up here. Registration is explicit; a
#: template without an adapter has NO parametric qualification.
def _ste_adapter():
    from apps.dielines.qualification.legacy_tuck import ste_adapter
    return ste_adapter()


def _skynte_adapter():
    from apps.dielines.qualification.side_seam_qual import skynte_adapter
    return skynte_adapter()


def _rte_adapter():
    from apps.dielines.qualification.reverse_tuck_qual import rte_adapter
    return rte_adapter()


def _ste_12_adapter():
    from apps.dielines.qualification.dtuck_qual import ste_12_adapter
    return ste_12_adapter()


def _rte_12_adapter():
    from apps.dielines.qualification.dtuck_qual import rte_12_adapter
    return rte_12_adapter()


# 2A-9C archetypes keyed by template_id (current version); 2A-9D adds the
# 1.2 D-derived variants keyed by "<id>@1.2" so both versions qualify
# independently without either shadowing the other in the registry.
_ADAPTER_FACTORIES = {
    "reference_opposed_tuck_carton": opposed_tuck_adapter,
    "straight_tuck_end_carton": _ste_adapter,
    "skynte_foundation_tuck_carton": _skynte_adapter,
    "reverse_tuck_end_carton": _rte_adapter,
    "straight_tuck_end_carton@1.2": _ste_12_adapter,
    "reverse_tuck_end_carton@1.2": _rte_12_adapter,
}


def adapter_for(template_id: str) -> ArchetypeAdapter | None:
    factory = _ADAPTER_FACTORIES.get(template_id)
    return factory() if factory else None


def registered_adapters() -> list[str]:
    return sorted(_ADAPTER_FACTORIES)


@dataclass
class QualificationResult:
    user_params: dict
    supported: bool
    violations: list[str] = field(default_factory=list)
    geometry_hash: str = ""
    content_hashes: dict = field(default_factory=dict)
    invariant_failures: list[str] = field(default_factory=list)
    folded_all_ok: bool | None = None
    folded_checks: list[dict] = field(default_factory=list)
    dimensions: dict = field(default_factory=dict)
    derived: dict = field(default_factory=dict)


def qualify(user: dict, adapter: ArchetypeAdapter) -> QualificationResult:
    """Domain gate → generation → §3 invariants → folded checks →
    conversions, for one parameter combination."""
    from apps.dielines import registry
    from apps.dielines.geometry.engine import calculate_dieline
    from apps.dielines.qualification.domain import evaluate_domain
    from apps.dielines.qualification.invariants import check_invariants

    result = QualificationResult(user_params=dict(user), supported=False)
    violations = evaluate_domain(user, adapter.domain_constraints)
    if violations:
        result.violations = violations
        return result

    object.__setattr__(adapter, "_last_user", dict(user))
    coords = calculate_dieline(adapter.build_params(user))
    t = user["board_thickness_mm"]
    inner = ((user["width_mm"], user["depth_mm"], user["height_mm"])
             if adapter.dims_semantics == "inner" else
             (user["width_mm"] - 2 * t, user["depth_mm"] - 2 * t,
              user["height_mm"] - 2 * t))
    result.invariant_failures = check_invariants(
        coords, expected_inner=inner, adapter=adapter)
    folded = adapter.collision_report(coords)
    result.folded_all_ok = folded["all_ok"]
    result.folded_checks = folded["checks"]
    result.supported = (not result.invariant_failures
                        and bool(folded["all_ok"]))
    result.geometry_hash = registry.geometry_hash(
        adapter.template, adapter.version, {
            "width_mm": user["width_mm"], "depth_mm": user["depth_mm"],
            "height_mm": user["height_mm"],
            "bleed_mm": user.get("bleed_mm", 3.0),
            "safe_margin_mm": user.get("safe_margin_mm", 4.0),
            "glue_tab_mm": user.get("glue_tab_mm", 12.0),
            "board_thickness_mm": user["board_thickness_mm"],
        })
    result.content_hashes = adapter.content_hashes(coords)
    d = coords.derived
    result.dimensions = {
        "inner_mm": list(coords.dimensions.inner),
        "manufacture_mm": list(coords.dimensions.manufacture),
        "outer_mm": list(coords.dimensions.outer),
        "board_compensation": d.get("compensation_report", []),
        "closure_stack_allowance_mm": 2 * user["board_thickness_mm"],
        "score_compression_mm": "not modelled in 0.1 — physical-sample "
                                "assumption",
        "headspace_mm": 0.0,
    }
    result.derived = {
        "closure_face_mm": coords.dimensions.manufacture[1]
        - 2 * user["board_thickness_mm"],
        "major_tuck_reach_mm": d.get("tuck_flap_height_mm"),
        "dust_flap_depth_mm": d.get("dust_flap_height_mm"),
        "locking_ear_mm": d.get("tuck_lock_ear_mm"),
        "flat_mm": [coords.flat_width_mm, coords.flat_height_mm],
    }
    result._coords = coords
    return result


def qualification_matrix(fixtures: dict[str, dict],
                         adapter: ArchetypeAdapter,
                         render_dir: str | None = None) -> list[dict]:
    """§5 matrix: one labelled row per fixture, folded diagnostic
    optionally rendered per case."""
    import os
    rows = []
    for name, user in fixtures.items():
        result = qualify(user, adapter)
        row = {
            "case": name,
            "input": result.user_params,
            "outcome": ("SUPPORTED" if result.supported else
                        ("REJECTED_BY_DOMAIN" if result.violations
                         else "INVARIANT_FAILURE")),
            "violations": result.violations,
            "invariant_failures": result.invariant_failures,
            "geometry_hash": result.geometry_hash,
            "content_hashes": result.content_hashes,
            "dimensions": result.dimensions,
            "derived": result.derived,
            "folded_all_ok": result.folded_all_ok,
            "folded_checks": result.folded_checks,
        }
        if result.supported and render_dir:
            os.makedirs(render_dir, exist_ok=True)
            from apps.dielines.exporters.folded_diagnostic import (
                export_folded_diagnostic,
            )
            from apps.dielines.exporters.counter_display_files import write_carton_svg
            coords = result._coords
            write_carton_svg(coords, name, output_dir=render_dir)
            fold_png = os.path.join(render_dir, f"{name}_folded.png")
            export_folded_diagnostic(
                coords, fold_png,
                collision={"checks": result.folded_checks},
                closure=adapter.closure)
            row["renders"] = {
                "preview_svg": os.path.join(render_dir, f"{name}.svg"),
                "folded_diagnostic": fold_png,
            }
        rows.append(row)
    return rows


__all__ = ["ArchetypeAdapter", "QualificationResult", "qualify",
           "qualification_matrix", "opposed_tuck_adapter"]


def seeded_property_sweep(adapter: ArchetypeAdapter, *, seed: int,
                          n_in_domain: int = 150,
                          n_random: int = 250) -> dict:
    """§4 deterministic property sweep.

    ``n_in_domain`` combinations are sampled INSIDE the derived domain
    (every one must generate and hold every invariant); ``n_random``
    combinations are sampled across the whole raw parameter space (each
    must either qualify cleanly or be rejected by the domain with a named
    constraint — never crash, never emit distorted geometry). The seed is
    reported with every failure so a run reproduces directly.
    """
    import random
    rng = random.Random(seed)
    boards = [0.3, 0.4, 0.5, 0.7, 0.8, 1.0]
    glues = [6.0, 10.0, 12.0, 15.0]
    failures: list[dict] = []
    supported = rejected = 0

    def _record(kind, user, detail):
        failures.append({"kind": kind, "seed": seed, "params": user,
                         "detail": detail})

    for index in range(n_in_domain):
        if adapter.in_domain_sampler is not None:
            user = adapter.in_domain_sampler(rng)
            if user is None:
                continue
        else:
            # frozen opposed-tuck sampler — byte-stable with the committed
            # 2A-9B sweep counts (same rng consumption order)
            t = rng.choice(boards)
            glue = rng.choice(glues)
            depth = round(rng.uniform(max(12.0, 11.0 - t, glue + 3.0 - 2 * t),
                                      200.0), 1)
            w_min = max(12.0, depth + t + 20.0,
                        10.0 + 14.0 - t, 4.0 + 14.0 + 3 * t)
            if w_min >= 299.0:
                continue
            width = round(rng.uniform(w_min + 0.1, 300.0), 1)
            height = round(rng.uniform(max(width, depth,
                                           18 + 2 * t + 2.0) + 0.2, 600.0), 1)
            user = {"width_mm": width, "depth_mm": depth,
                    "height_mm": height,
                    "board_thickness_mm": t, "glue_tab_mm": glue,
                    "bleed_mm": rng.choice([2.0, 3.0, 5.0]),
                    "safe_margin_mm": rng.choice([3.0, 4.0, 8.0])}
        result = qualify(user, adapter)
        if result.violations:
            _record("IN_DOMAIN_SAMPLE_REJECTED", user, result.violations)
        elif not result.supported:
            _record("INVARIANT_FAILURE", user,
                    result.invariant_failures
                    or [c for c in result.folded_checks if not c["ok"]])
        else:
            supported += 1

    for index in range(n_random):
        user = {"width_mm": round(rng.uniform(10.0, 320.0), 1),
                "depth_mm": round(rng.uniform(10.0, 320.0), 1),
                "height_mm": round(rng.uniform(40.0, 650.0), 1),
                "board_thickness_mm": round(rng.uniform(0.2, 1.2), 2),
                "glue_tab_mm": round(rng.uniform(5.0, 16.0), 1),
                "bleed_mm": 3.0, "safe_margin_mm": 4.0}
        try:
            result = qualify(user, adapter)
        except Exception as exc:  # noqa: BLE001 — a crash IS the failure
            _record("CRASH", user, [repr(exc)])
            continue
        if result.violations:
            rejected += 1
        elif result.supported:
            supported += 1
        else:
            _record("INVARIANT_FAILURE", user, result.invariant_failures)

    return {"seed": seed, "in_domain_samples": n_in_domain,
            "random_samples": n_random, "supported": supported,
            "rejected_by_domain": rejected, "failures": failures}


#: §5 representative fixtures per archetype (min/max/small/deep/... +
#: golden task fixture + inside/outside boundary pairs). The opposing-tuck
#: set is FROZEN — it must reproduce the committed 2A-9B matrix.
_FIXTURES: dict[str, dict[str, dict]] = {
    "reference_opposed_tuck_carton": {
        "small_shallow": {"width_mm": 34.0, "depth_mm": 12.0,
                          "height_mm": 61.0, "board_thickness_mm": 0.5,
                          "glue_tab_mm": 8.0, "bleed_mm": 3.0,
                          "safe_margin_mm": 4.0},
        "small_deep": {"width_mm": 40.0, "depth_mm": 19.0,
                       "height_mm": 65.0, "board_thickness_mm": 0.5,
                       "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                       "safe_margin_mm": 4.0},
        "medium_shallow": {"width_mm": 70.0, "depth_mm": 15.0,
                           "height_mm": 100.0, "board_thickness_mm": 0.5,
                           "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                           "safe_margin_mm": 4.0},
        "medium_deep": {"width_mm": 70.0, "depth_mm": 49.0,
                        "height_mm": 110.0, "board_thickness_mm": 0.5,
                        "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                        "safe_margin_mm": 4.0},
        "large_shallow": {"width_mm": 250.0, "depth_mm": 40.0,
                          "height_mm": 300.0, "board_thickness_mm": 0.8,
                          "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                          "safe_margin_mm": 4.0},
        "large_deep": {"width_mm": 279.0, "depth_mm": 258.0,
                       "height_mm": 320.0, "board_thickness_mm": 0.8,
                       "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                       "safe_margin_mm": 4.0},
        "tall_narrow": {"width_mm": 33.0, "depth_mm": 12.0,
                        "height_mm": 590.0, "board_thickness_mm": 0.3,
                        "glue_tab_mm": 8.0, "bleed_mm": 3.0,
                        "safe_margin_mm": 4.0},
        "nearly_square": {"width_mm": 95.0, "depth_mm": 74.0,
                          "height_mm": 96.0, "board_thickness_mm": 0.5,
                          "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                          "safe_margin_mm": 4.0},
        "task_50_exact": {"width_mm": 90.0, "depth_mm": 32.0,
                          "height_mm": 92.0, "board_thickness_mm": 0.5,
                          "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                          "safe_margin_mm": 4.0},
        "inside_dust_pair_boundary": {
            "width_mm": 52.5, "depth_mm": 32.0, "height_mm": 92.0,
            "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "outside_dust_pair_boundary": {
            "width_mm": 52.0, "depth_mm": 32.0, "height_mm": 92.0,
            "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "inside_depth_floor": {
            "width_mm": 90.0, "depth_mm": 12.0, "height_mm": 92.0,
            "board_thickness_mm": 0.5, "glue_tab_mm": 6.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "outside_depth_floor": {
            "width_mm": 90.0, "depth_mm": 11.9, "height_mm": 92.0,
            "board_thickness_mm": 0.5, "glue_tab_mm": 6.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "outside_height_rule": {
            "width_mm": 92.0, "depth_mm": 32.0, "height_mm": 92.0,
            "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "inside_board_max": {
            "width_mm": 90.0, "depth_mm": 32.0, "height_mm": 92.0,
            "board_thickness_mm": 1.0, "glue_tab_mm": 12.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "outside_board_max": {
            "width_mm": 90.0, "depth_mm": 32.0, "height_mm": 92.0,
            "board_thickness_mm": 1.01, "glue_tab_mm": 12.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "outside_glue_clearance": {
            "width_mm": 34.0, "depth_mm": 12.0, "height_mm": 61.0,
            "board_thickness_mm": 0.5, "glue_tab_mm": 14.0,
            "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    },
}

_FIXTURES["straight_tuck_end_carton"] = {
    "small_shallow": {"width_mm": 20.0, "depth_mm": 12.0, "height_mm": 61.0,
                      "board_thickness_mm": 0.5, "glue_tab_mm": 6.0,
                      "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "small_deep": {"width_mm": 25.0, "depth_mm": 18.0, "height_mm": 75.0,
                   "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                   "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "medium_shallow": {"width_mm": 60.0, "depth_mm": 20.0,
                       "height_mm": 130.0, "board_thickness_mm": 0.5,
                       "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                       "safe_margin_mm": 4.0},
    "medium_deep": {"width_mm": 60.0, "depth_mm": 45.0, "height_mm": 150.0,
                    "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "large_shallow": {"width_mm": 150.0, "depth_mm": 60.0,
                      "height_mm": 380.0, "board_thickness_mm": 0.5,
                      "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                      "safe_margin_mm": 4.0},
    "large_deep": {"width_mm": 220.0, "depth_mm": 170.0,
                   "height_mm": 560.0, "board_thickness_mm": 0.8,
                   "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                   "safe_margin_mm": 4.0},
    "tall_narrow": {"width_mm": 20.0, "depth_mm": 14.0, "height_mm": 580.0,
                    "board_thickness_mm": 0.3, "glue_tab_mm": 8.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "nearly_square": {"width_mm": 80.0, "depth_mm": 63.0, "height_mm": 81.0,
                      "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                      "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "measured_reference_28x28x120": {
        "width_mm": 28.0, "depth_mm": 28.0, "height_mm": 120.0,
        "board_thickness_mm": 0.3, "glue_tab_mm": 10.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "historical_task50_ste_90x25x92": {
        "width_mm": 90.0, "depth_mm": 25.0, "height_mm": 92.0,
        "board_thickness_mm": 0.35, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "inside_dust_pair_boundary": {
        "width_mm": 50.5, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_dust_pair_boundary": {
        "width_mm": 50.4, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "inside_lip_boundary": {
        "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 107.4,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_lip_boundary": {
        "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 107.2,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_board_min": {
        "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
        "board_thickness_mm": 0.29, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
}

_FIXTURES["skynte_foundation_tuck_carton"] = {
    "small_shallow": {"width_mm": 22.0, "depth_mm": 12.0, "height_mm": 65.0,
                      "board_thickness_mm": 0.3, "glue_tab_mm": 6.0,
                      "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "small_deep": {"width_mm": 30.0, "depth_mm": 22.0, "height_mm": 80.0,
                   "board_thickness_mm": 0.3, "glue_tab_mm": 10.0,
                   "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "medium_shallow": {"width_mm": 55.0, "depth_mm": 20.0,
                       "height_mm": 130.0, "board_thickness_mm": 0.5,
                       "glue_tab_mm": 10.0, "bleed_mm": 3.0,
                       "safe_margin_mm": 4.0},
    "medium_deep": {"width_mm": 60.0, "depth_mm": 45.0, "height_mm": 150.0,
                    "board_thickness_mm": 0.5, "glue_tab_mm": 10.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "wide_near_cap": {"width_mm": 72.0, "depth_mm": 40.0, "height_mm": 200.0,
                      "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                      "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "tall_narrow": {"width_mm": 20.0, "depth_mm": 14.0, "height_mm": 300.0,
                    "board_thickness_mm": 0.3, "glue_tab_mm": 8.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "nearly_square_capped": {"width_mm": 60.0, "depth_mm": 47.0,
                             "height_mm": 62.0, "board_thickness_mm": 0.5,
                             "glue_tab_mm": 10.0, "bleed_mm": 3.0,
                             "safe_margin_mm": 4.0},
    "task_47_reference_42x32x140": {
        "width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0,
        "board_thickness_mm": 0.30, "glue_tab_mm": 10.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "inside_width_cap": {"width_mm": 73.3, "depth_mm": 40.0,
                         "height_mm": 200.0, "board_thickness_mm": 0.5,
                         "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                         "safe_margin_mm": 4.0},
    "outside_width_cap": {"width_mm": 73.5, "depth_mm": 40.0,
                          "height_mm": 200.0, "board_thickness_mm": 0.5,
                          "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                          "safe_margin_mm": 4.0},
    "inside_dust_pair_boundary": {
        "width_mm": 50.5, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 10.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_dust_pair_boundary": {
        "width_mm": 50.4, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 10.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_height_rule": {
        "width_mm": 60.0, "depth_mm": 40.0, "height_mm": 60.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 10.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
}

# RTE shares STE's ratio formulas, so its fixture band matches STE's;
# the fixtures here are RTE-specific (its own reference case + mirror
# boundary probes).
_FIXTURES["reverse_tuck_end_carton"] = {
    "small_shallow": {"width_mm": 20.0, "depth_mm": 12.0, "height_mm": 61.0,
                      "board_thickness_mm": 0.5, "glue_tab_mm": 6.0,
                      "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "small_deep": {"width_mm": 25.0, "depth_mm": 18.0, "height_mm": 75.0,
                   "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                   "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "medium_shallow": {"width_mm": 60.0, "depth_mm": 20.0,
                       "height_mm": 130.0, "board_thickness_mm": 0.5,
                       "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                       "safe_margin_mm": 4.0},
    "medium_deep": {"width_mm": 60.0, "depth_mm": 45.0, "height_mm": 150.0,
                    "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "large_shallow": {"width_mm": 150.0, "depth_mm": 60.0,
                      "height_mm": 380.0, "board_thickness_mm": 0.5,
                      "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                      "safe_margin_mm": 4.0},
    "large_deep": {"width_mm": 220.0, "depth_mm": 170.0,
                   "height_mm": 560.0, "board_thickness_mm": 0.8,
                   "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                   "safe_margin_mm": 4.0},
    "tall_narrow": {"width_mm": 20.0, "depth_mm": 14.0, "height_mm": 580.0,
                    "board_thickness_mm": 0.3, "glue_tab_mm": 8.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "nearly_square": {"width_mm": 80.0, "depth_mm": 63.0, "height_mm": 81.0,
                      "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                      "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "representative_60x20x130": {
        "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 10.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "inside_dust_pair_boundary": {
        "width_mm": 50.5, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_dust_pair_boundary": {
        "width_mm": 50.4, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "inside_lip_boundary": {
        "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 107.4,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_lip_boundary": {
        "width_mm": 60.0, "depth_mm": 20.0, "height_mm": 107.2,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
}

_D12 = {
    "small_shallow": {"width_mm": 20.0, "depth_mm": 12.0, "height_mm": 61.0,
                      "board_thickness_mm": 0.5, "glue_tab_mm": 6.0,
                      "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "small_deep": {"width_mm": 30.0, "depth_mm": 22.0, "height_mm": 80.0,
                   "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                   "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "medium_shallow": {"width_mm": 60.0, "depth_mm": 20.0,
                       "height_mm": 130.0, "board_thickness_mm": 0.5,
                       "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                       "safe_margin_mm": 4.0},
    "medium_deep": {"width_mm": 70.0, "depth_mm": 55.0, "height_mm": 150.0,
                    "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "wide_short_1v1_reject": {"width_mm": 90.0, "depth_mm": 25.0,
                              "height_mm": 92.0, "board_thickness_mm": 0.5,
                              "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                              "safe_margin_mm": 4.0},
    "large_shallow_1v1_reject": {"width_mm": 200.0, "depth_mm": 40.0,
                                 "height_mm": 250.0,
                                 "board_thickness_mm": 0.5,
                                 "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                                 "safe_margin_mm": 4.0},
    "tall_narrow": {"width_mm": 20.0, "depth_mm": 14.0, "height_mm": 580.0,
                    "board_thickness_mm": 0.3, "glue_tab_mm": 8.0,
                    "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "nearly_square_capped": {"width_mm": 60.0, "depth_mm": 47.0,
                             "height_mm": 62.0, "board_thickness_mm": 0.5,
                             "glue_tab_mm": 12.0, "bleed_mm": 3.0,
                             "safe_margin_mm": 4.0},
    "large_deep": {"width_mm": 260.0, "depth_mm": 200.0, "height_mm": 560.0,
                   "board_thickness_mm": 0.8, "glue_tab_mm": 12.0,
                   "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "inside_dust_pair_boundary": {
        "width_mm": 50.5, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_dust_pair_boundary": {
        "width_mm": 50.3, "depth_mm": 40.0, "height_mm": 130.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
    "outside_height_rule": {
        "width_mm": 60.0, "depth_mm": 40.0, "height_mm": 60.0,
        "board_thickness_mm": 0.5, "glue_tab_mm": 12.0,
        "bleed_mm": 3.0, "safe_margin_mm": 4.0},
}
_FIXTURES["straight_tuck_end_carton@1.2"] = dict(_D12)
_FIXTURES["reverse_tuck_end_carton@1.2"] = dict(_D12)

#: property-sweep seed per archetype (frozen once reports are committed)
_SWEEP_SEEDS = {"reference_opposed_tuck_carton": 20260722,
                "straight_tuck_end_carton": 20260723,
                "skynte_foundation_tuck_carton": 20260724,
                "reverse_tuck_end_carton": 20260725,
                "straight_tuck_end_carton@1.2": 20260726,
                "reverse_tuck_end_carton@1.2": 20260727}


def fixtures_for(template_id: str) -> dict[str, dict]:
    return dict(_FIXTURES.get(template_id, {}))


def sweep_seed_for(template_id: str) -> int:
    return _SWEEP_SEEDS.get(template_id, 20260722)
