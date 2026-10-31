"""Import reference design files for the Creative Director (2026-07-04).

Takes a directory of past production designs — .ai/.pdf (PDF-compatible,
e.g. manufacturer artwork files) or plain images — rasterizes them, downscales
to a vision-friendly size, and drops them in MEDIA_ROOT/references/. The
Creative Director attaches the newest few as vision blocks so directions are
grounded in how real BBROSE packaging actually looks (wordmark lockup, motif
style, typography conventions, finish discipline).

Rasterization uses macOS ``sips`` or poppler's ``pdftoppm`` — whichever is on
PATH (dev-machine tooling; re-run the command wherever the files live).

    manage.py import_design_references ../design_models
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_PDFLIKE_EXTS = {".ai", ".pdf"}
_MAX_SIDE = 1200  # vision-friendly; keeps per-image token cost modest


def _rasterize_pdf(src: Path, out_png: Path) -> bool:
    """PDF/.ai → PNG via sips (macOS) or pdftoppm (poppler). True on success."""
    with tempfile.TemporaryDirectory() as td:
        tmp_pdf = Path(td) / "ref.pdf"
        shutil.copyfile(src, tmp_pdf)
        if shutil.which("sips"):
            proc = subprocess.run(
                ["sips", "-s", "format", "png", str(tmp_pdf), "--out", str(out_png)],
                capture_output=True, text=True,
            )
            if proc.returncode == 0 and out_png.exists():
                return True
        if shutil.which("pdftoppm"):
            stem = Path(td) / "page"
            proc = subprocess.run(
                ["pdftoppm", "-png", "-f", "1", "-l", "1", "-r", "120",
                 str(tmp_pdf), str(stem)],
                capture_output=True, text=True,
            )
            produced = sorted(Path(td).glob("page*.png"))
            if proc.returncode == 0 and produced:
                shutil.copyfile(produced[0], out_png)
                return True
    return False


class Command(BaseCommand):
    help = "Rasterize reference design files (.ai/.pdf/images) into MEDIA_ROOT/references/"

    def add_arguments(self, parser):
        parser.add_argument("directory", help="Folder containing the reference files")
        parser.add_argument("--force", action="store_true",
                            help="Re-import files that already have a PNG")
        parser.add_argument("--no-tag", action="store_true",
                            help="Skip the vision tagging pass (register only)")
        parser.add_argument("--retag", action="store_true",
                            help="Re-run vision tagging for already-tagged references")
        parser.add_argument("--deep", action="store_true",
                            help="Run the deep part-by-part anatomy study for "
                                 "references that don't have one yet (resumable)")
        parser.add_argument("--redeep", action="store_true",
                            help="Re-run the anatomy study even when present")

    def handle(self, *args, **opts):
        src_dir = Path(opts["directory"]).expanduser().resolve()
        if not src_dir.is_dir():
            raise CommandError(f"not a directory: {src_dir}")

        out_dir = Path(settings.MEDIA_ROOT) / "references"
        out_dir.mkdir(parents=True, exist_ok=True)

        from PIL import Image

        from apps.core.models import DesignReference

        done = skipped = failed = 0
        registered = []
        for src in sorted(src_dir.iterdir()):
            ext = src.suffix.lower()
            if ext not in _IMAGE_EXTS | _PDFLIKE_EXTS:
                continue
            safe_stem = "".join(
                c if (c.isalnum() or c in "-_") else "_" for c in src.stem
            )
            out_png = out_dir / f"ref_{safe_stem}.png"
            if out_png.exists() and not opts["force"]:
                skipped += 1
                # Register legacy imports that predate the index model.
                ref, _ = DesignReference.objects.get_or_create(
                    name=safe_stem,
                    defaults={"image_path": f"references/{out_png.name}",
                              "source_file": src.name},
                )
                registered.append(ref)
                continue

            try:
                if ext in _PDFLIKE_EXTS:
                    if not src.open("rb").read(5).startswith(b"%PDF"):
                        self.stderr.write(f"  not PDF-compatible, skipped: {src.name}")
                        failed += 1
                        continue
                    if not _rasterize_pdf(src, out_png):
                        self.stderr.write(
                            f"  rasterize failed (need sips or pdftoppm): {src.name}")
                        failed += 1
                        continue
                else:
                    shutil.copyfile(src, out_png)

                with Image.open(out_png) as im:
                    im = im.convert("RGB")
                    im.thumbnail((_MAX_SIDE, _MAX_SIDE))
                    im.save(out_png, "PNG", optimize=True)
                ref, _ = DesignReference.objects.update_or_create(
                    name=safe_stem,
                    defaults={"image_path": f"references/{out_png.name}",
                              "source_file": src.name},
                )
                registered.append(ref)
                done += 1
                self.stdout.write(f"  imported: {src.name} -> {out_png.name}")
            except Exception as exc:  # noqa: BLE001 — per-file, keep going
                failed += 1
                self.stderr.write(f"  failed: {src.name} — {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"references: {done} imported, {skipped} already present, {failed} failed "
            f"-> {out_dir}"
        ))

        # --- vision tagging pass (2026-07-06): one call per untagged file so
        # the Creative Director can select references BY PRODUCT. Resumable —
        # already-tagged rows are skipped unless --retag.
        if not opts["no_tag"]:
            from apps.pipeline.services.reference_index import tag_reference
            to_tag = [r for r in registered
                      if opts["retag"] or not (r.product_type or r.tags)]
            if not to_tag:
                self.stdout.write("tagging: nothing to tag")
            else:
                self.stdout.write(
                    f"tagging: {len(to_tag)} reference(s) via vision...")
                ok = 0
                for ref in to_tag:
                    if tag_reference(ref,
                                     log=lambda m: self.stdout.write(f"  {m}")):
                        ok += 1
                self.stdout.write(self.style.SUCCESS(
                    f"tagging: {ok}/{len(to_tag)} tagged"
                ))

        # --- deep anatomy pass (2026-07-07): a second, part-by-part study of
        # each file (layout grid, typography, motif inventory, palette hexes,
        # back-panel conventions) injected into the Creative Director and
        # Prompt Engineer. Opt-in (--deep), resumable, ~$0.02-0.04/file.
        if not (opts["deep"] or opts["redeep"]):
            return
        from apps.pipeline.services.reference_index import (
            analyze_reference_anatomy,
        )
        to_study = [r for r in registered if opts["redeep"] or not r.anatomy]
        if not to_study:
            self.stdout.write("anatomy: nothing to study")
            return
        self.stdout.write(
            f"anatomy: deep-studying {len(to_study)} reference(s)...")
        ok = 0
        for ref in to_study:
            if analyze_reference_anatomy(
                    ref, log=lambda m: self.stdout.write(f"  {m}")):
                ok += 1
        self.stdout.write(self.style.SUCCESS(
            f"anatomy: {ok}/{len(to_study)} studied"
        ))
