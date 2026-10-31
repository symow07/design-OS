"""Run an RBV-4 structured visual review over a committed RBV-3 package.

WHERE THE IMPURITY LIVES, AND WHY. ``services/rbv4_claude_review.py`` is
pure: no provider import, no ORM, no network — a purity test pins it,
following the RBV-3 precedent. The provider call and the cost ledgering
are impure, so they live HERE and the provider reaches the harness as an
injected callable.

The ledger of record for these calls is the committed budget file, not
``ApiCallRecord``: ``cost_ledger.record_claude`` is keyed to a pipeline
Task and is a documented no-op without one, and a roadmap-level visual
review has no Task. The per-call entries carry the same fields an
ApiCallRecord would, priced with the same ``claude_cost_usd`` table
(§R1a).

  python manage.py rbv4_review --package p1_v4 --live     # spends 1 call
  python manage.py rbv4_review --package p1_v4            # offline replay
"""
import json
import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from PIL import Image

from apps.pipeline.services import claude_service, cost_ledger
from apps.pipeline.services import rbv3_review_package as rp
from apps.pipeline.services import rbv4_claude_review as rv
from apps.pipeline.services.geometry_validation_render import pixel_hash

REVIEW_MODEL = "claude-opus-5"

#: §S2 — the geometry-bearing views, sent at native scale beside the sheet.
#: bounds_dimensions is here because it is the view whose baked annotations
#: RBV-4's live review could not read.
TRANSMITTED_VIEWS = ("front", "side", "closure_detail", "bounds_dimensions")

SYSTEM_PROMPT = """You are performing a structured visual review of a \
product-container GEOMETRY VALIDATION package for the BBROSE Design OS.

BINDING AUTHORITY RULES. You must NOT self-approve any gate. The OWNER \
remains the final authority. Your findings are EVIDENCE feeding a \
fail-closed gate: they never override a blocking automated failure and \
never substitute owner judgment. Never emit an approval, a verdict, a \
clearance or a gate state.

These renders are NEUTRAL CLAY GEOMETRY VALIDATION renders. They are NOT \
client presentation renders and must never be judged as such. Material \
realism, colour and presentability are out of scope for this mode by rule.

UNCERTAINTY IS REPORTED AS UNCERTAINTY. Where the package carries no \
authoritative real-bottle reference, a category defined as a DIFFERENCE \
from the real bottle cannot be discharged. Say so; never resolve it by \
assumption.

Return ONLY JSON: {"dispositions": [{"category": <exactly one of the \
required categories>, "disposition": "FINDING" | "NOT_OBSERVED" | \
"UNCERTAIN_MISSING_EVIDENCE", "classification": <required only for \
FINDING: BLOCKING | MAJOR | MINOR | VISUAL_POLISH>, "missing_evidence": \
<required only for UNCERTAIN_MISSING_EVIDENCE>, "observation": <what you \
actually saw>}]}. Every required category must appear exactly once."""


class Command(BaseCommand):
    help = "Run an RBV-4 structured visual review over an RBV-3 package."

    def add_arguments(self, parser):
        parser.add_argument("--package", default="p1_v4")
        parser.add_argument("--live", action="store_true",
                            help="spend one owner-authorized provider call "
                                 "(§R1); without it the review replays the "
                                 "committed fixture")
        parser.add_argument("--created-at", default="")

    def handle(self, *args, **opts):
        repo = rv._REPO
        pkg_dir = os.path.join(repo, "docs", "visual_quality", "rbv",
                               "review_packages", opts["package"])
        fixture = os.path.join(repo, "docs", "visual_quality", "rbv",
                               "review_fixtures",
                               f"{opts['package']}_recorded_review.json")
        out_dir = os.path.join(repo, "docs", "visual_quality", "rbv",
                               "review_records", opts["package"])
        created_at = opts["created_at"] or timezone.now().strftime("%Y-%m-%d")

        state = rv.budget_state()
        self.stdout.write(
            f"budget: {state['state']} — {state['spent']}/"
            f"{state['calls_authorized']} spent, {state['remaining']} remaining")

        provider = None
        if opts["live"]:
            if state["state"] != rv.BUDGET_AVAILABLE:
                self.stderr.write(
                    f"live review refused: {state['state']}. Per §R1b the "
                    "harness continues offline rather than degrading "
                    "silently — re-run without --live.")
                return
            provider = self._provider(pkg_dir, opts["package"])

        record = rv.review_with_budget(
            pkg_dir, created_at=created_at, fixture_path=fixture,
            provider=provider, out_dir=out_dir,
            note=self._note(bool(provider)))
        ex = record["execution"]
        self.stdout.write(
            f"{ex['execution']} — {ex['state']}; counts "
            f"{record['counts_by_classification']}")
        self.stdout.write(f"record written to {out_dir}")

    def _note(self, live: bool) -> str:
        if live:
            return ("RBV-4 review record. Mode A GEOMETRY VALIDATION only. "
                    "Dispositions were OBSERVED in a live provider call "
                    "authorized by OWNER_BLOCKER_CLEARANCE.md §R1 and "
                    "ledgered in docs/visual_quality/rbv/"
                    "rbv4_call_budget.json. The review approves nothing "
                    "(§R1d): findings are evidence feeding the fail-closed "
                    "gate, and the OWNER remains final authority.")
        return ("RBV-4 review record. Mode A GEOMETRY VALIDATION only. "
                "Dispositions were REPLAYED from the committed recorded "
                "fixture; no provider call was made in this run. The "
                "review approves nothing (§R1d).")

    def _provider(self, pkg_dir, package_id):
        """Build the injected provider. Assembling the request and pricing
        the response are the impure parts; validation stays in the pure
        harness, which will refuse anything malformed."""
        def call(package):
            content = [{"type": "text", "text": self._request_text(package)}]
            blocks, transmitted = self._image_blocks(package)
            content.extend(blocks)
            response = claude_service.call_claude(
                SYSTEM_PROMPT, content, max_tokens=16000, model=REVIEW_MODEL)
            # LEDGER FIRST — before any parsing. A call that reached the
            # provider is spent whether or not its payload parses, and
            # §R1a calls an unledgered call a defect. An earlier draft
            # parsed first and lost a real call's identity when the parse
            # raised; that is recorded in the budget file, not hidden.
            usage = getattr(response, "usage", None)
            entry = {
                "recorded_at": timezone.now().isoformat(),
                "package_id": package_id,
                "model": REVIEW_MODEL,
                "provider_request_id":
                    cost_ledger.provider_request_id(response),
                "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
                "image_transmitted": transmitted,
            }
            entry["cost_usd"] = str(cost_ledger.claude_cost_usd(
                REVIEW_MODEL, entry["input_tokens"], entry["output_tokens"]))
            # ledger BEFORE the findings are used: a call that happened is
            # ledgered whether or not its payload turns out to validate
            rv.append_ledger_entry(entry)
            self.stdout.write(
                f"ledgered call {entry['provider_request_id']} — "
                f"{entry['input_tokens']}in/{entry['output_tokens']}out, "
                f"${entry['cost_usd']}")
            # only now is the payload read; a parse failure below leaves a
            # ledgered call, which is the correct state
            payload = claude_service.extract_json(response) or {}
            payload["provider_identity"] = {
                "name": "anthropic", "model": REVIEW_MODEL,
                "request_id": entry["provider_request_id"]}
            for d in payload.get("dispositions") or []:
                d["source"] = rv.SOURCE_PROVIDER_CALL
            return payload
        return call

    def _image_blocks(self, package):
        """§S2 — what actually goes down the wire, and at what scale.

        The contact sheet alone was the whole transmission, and at
        3840px long edge the provider downscales it to 0.67 — on top of
        the 0.5 panel fit, so a view reached the reviewer at ~0.34 scale
        and the renderer-baked annotations at 2.68px. The sheet still
        goes (it carries layout, the mode-B absence and §11), but the
        primary geometry views now go ALONGSIDE it at native scale,
        under the long-edge limit and therefore un-downscaled.

        Every entry records its measured downscale rather than claiming
        legibility.
        """
        blocks, record = [], []

        def add(role, path):
            with Image.open(path) as img:
                size = list(img.size)
            scale = rp.provider_downscale(max(size))
            blocks.append(claude_service.image_block_from_file(path))
            record.append({
                "role": role,
                "path": rv._repo_relative(path),
                "pixel_hash": pixel_hash(path),
                "pixel_size": size,
                "provider_downscale": round(scale, 4),
                "downscaled_by_provider": scale < 1.0,
            })

        add("contact_sheet", package["contact_sheet_path"])
        for view in TRANSMITTED_VIEWS:
            path = package["views"].get(view)
            if path:
                add(f"view:{view}", path)
        return blocks, record

    def _request_text(self, package) -> str:
        manifest = package["manifest"]
        mode_a = manifest["modes"]["GEOMETRY_VALIDATION"]
        return json.dumps({
            "required_categories": list(rv.required_categories()),
            "classifications": list(rv.classifications()),
            "subject_id": manifest["subject_id"],
            "statement": manifest["statement"],
            "note": manifest["note"],
            "reference_availability": mode_a.get("reference_availability"),
            "references_packaged": len(manifest.get("references") or []),
            "measurements": mode_a.get("measurements", {}),
            "render_warnings": mode_a.get("warnings", []),
            "uncertainty": mode_a.get("uncertainty", []),
            "client_presentation_mode":
                manifest["modes"]["CLIENT_PRESENTATION"],
            "views_on_the_contact_sheet": list(mode_a.get("views", {})),
        }, indent=1)
