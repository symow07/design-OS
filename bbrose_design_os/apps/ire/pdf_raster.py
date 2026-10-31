"""DPI-capable PDF rasterization with verified effective resolution.

``rasterize.pdf_to_png`` selected ``sips`` before any DPI-capable backend,
and sips ignores the requested DPI. Nothing verified the output size, so
four identical 150-dpi images were read as proof of resolution
stability. A rasterizer that silently ignores a resolution request can
falsify any resolution-dependence test, so this module fails closed
instead: a backend is DPI_CAPABLE only after a capability test shows that
distinct DPI requests produce correspondingly scaled pixel dimensions,
and every render is checked against dimensions predicted from the page
box before it is returned.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

CAPABILITY_SCHEMA = "pdf_rasterizer_capability/1.0"
MANIFEST_SCHEMA = "pdf_rasterization_manifest/1.0"

DPI_CAPABILITY_UNAVAILABLE = "PDF_RASTERIZER_DPI_CAPABILITY_UNAVAILABLE"
EFFECTIVE_DPI_MISMATCH = "PDF_RASTERIZER_EFFECTIVE_DPI_MISMATCH"
RUNTIME_PARITY_FAILED = "PDF_RASTERIZER_RUNTIME_PARITY_FAILED"

#: rasterizers round to whole pixels; anything beyond this is a real error
DIMENSION_TOLERANCE_PX = 1


class RasterError(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(code, detail)
        self.code, self.detail = code, detail


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def page_geometry(pdf_path: str, page: int = 0) -> dict:
    import fitz
    doc = fitz.open(pdf_path)
    p = doc[page]
    r = p.cropbox
    out = {"page_width_pt": round(r.width, 4),
           "page_height_pt": round(r.height, 4),
           "rotation": int(p.rotation), "page_count": doc.page_count}
    doc.close()
    return out


def displayed_points(geom):
    w, h = geom['page_width_pt'], geom['page_height_pt']
    return (h, w) if geom['rotation'] % 180 == 90 else (w, h)


def expected_dimensions(geom: dict, dpi: int) -> tuple[int, int]:
    """Predicted pixels from the page box, accounting for rotation."""
    w = geom["page_width_pt"] * dpi / 72.0
    h = geom["page_height_pt"] * dpi / 72.0
    if geom["rotation"] % 180 == 90:
        w, h = h, w
    return round(w), round(h)


def probe_backends() -> list[dict]:
    """§3 — declare capability; never infer it from argument acceptance."""
    import shutil
    out = []
    try:
        import fitz
        out.append({"backend": "pymupdf", "identity": "PyMuPDF (fitz)",
                    "version": getattr(fitz, "__doc__", "") or "unknown",
                    "repo_managed": True, "explicit_dpi_claimed": True,
                    "page_selection": True, "transparency": True,
                    "dimensions_predictable": True, "available": True})
    except Exception:                                        # noqa: BLE001
        out.append({"backend": "pymupdf", "available": False,
                    "explicit_dpi_claimed": False, "repo_managed": True})
    out.append({"backend": "pdftoppm", "repo_managed": False,
                "available": bool(shutil.which("pdftoppm")),
                "explicit_dpi_claimed": True, "dimensions_predictable": True})
    out.append({"backend": "sips", "repo_managed": False,
                "available": bool(shutil.which("sips")),
                "explicit_dpi_claimed": False,
                "dimensions_predictable": False,
                "rejection_reason": "sips accepts no DPI argument in the "
                                    "invocation used here and silently "
                                    "renders at its own default"})
    return out


def certify_backend(backend: str, fixture_pdf: str,
                    dpis=(72, 144, 288, 576)) -> dict:
    """§9 — DPI_CAPABLE only when distinct DPI requests scale the output."""
    geom = page_geometry(fixture_pdf)
    rows, ok = [], True
    for dpi in dpis:
        try:
            r = _render(backend, fixture_pdf, dpi, verify=False)
            ew, eh = expected_dimensions(geom, dpi)
            match = (abs(r["width"] - ew) <= DIMENSION_TOLERANCE_PX
                     and abs(r["height"] - eh) <= DIMENSION_TOLERANCE_PX)
            rows.append({"dpi": dpi, "width": r["width"],
                         "height": r["height"], "expected": [ew, eh],
                         "effective_dpi_x": round(r["width"] * 72.0
                                                  / displayed_points(geom)[0], 2),
                         "dimensions_match": match, "sha256_16": r["sha"][:16]})
            ok = ok and match
        except Exception as e:                               # noqa: BLE001
            rows.append({"dpi": dpi, "error": type(e).__name__})
            ok = False
    scaled = (len({(r.get("width"), r.get("height")) for r in rows})
              == len(rows))
    return {"schema_version": CAPABILITY_SCHEMA, "backend": backend,
            "page_geometry": geom, "renders": rows,
            "distinct_dimensions_per_dpi": scaled,
            "all_dimensions_match_prediction": ok,
            "dpi_capable": bool(ok and scaled),
            "note": "identical hashes alone can never certify stability; "
                    "pixel dimensions and effective DPI are the evidence",
            "certified_at": datetime.now(timezone.utc).isoformat()}


def _render(backend: str, pdf_path: str, dpi: int, out_png: str | None = None,
            page: int = 0, verify: bool = True) -> dict:
    import tempfile
    tmp = out_png or os.path.join(tempfile.mkdtemp(), "r.png")
    if backend == "pymupdf":
        import fitz
        doc = fitz.open(pdf_path)
        pix = doc[page].get_pixmap(dpi=dpi)
        pix.save(tmp)
        doc.close()
    elif backend == "pdftoppm":
        import shutil
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "in.pdf")
            shutil.copyfile(pdf_path, src)
            stem = os.path.join(td, "p")
            subprocess.run(["pdftoppm", "-png", "-f", str(page + 1),
                            "-l", str(page + 1), "-r", str(dpi), src, stem],
                           capture_output=True, check=True)
            got = sorted(f for f in os.listdir(td) if f.endswith(".png"))
            shutil.copyfile(os.path.join(td, got[0]), tmp)
    else:
        raise RasterError(DPI_CAPABILITY_UNAVAILABLE,
                          f"backend {backend!r} is not DPI-capable")
    from PIL import Image
    with Image.open(tmp) as im:
        w, h = im.size
    res = {"path": tmp, "width": w, "height": h, "sha": _sha(tmp)}
    if verify:
        geom = page_geometry(pdf_path, page)
        ew, eh = expected_dimensions(geom, dpi)
        if (abs(w - ew) > DIMENSION_TOLERANCE_PX
                or abs(h - eh) > DIMENSION_TOLERANCE_PX):
            raise RasterError(EFFECTIVE_DPI_MISMATCH,
                              {"requested_dpi": dpi, "expected": [ew, eh],
                               "actual": [w, h], "backend": backend})
    return res


def render_verified(pdf_path: str, out_png: str, dpi: int, *,
                    page: int = 0, capability: dict | None = None) -> dict:
    """§6/§7 — render, verify against the predicted size, and return a
    full provenance manifest. Fails closed when no backend qualifies."""
    backends = probe_backends()
    cap = capability
    chosen = None
    for b in backends:
        if not b.get("available") or not b.get("explicit_dpi_claimed"):
            continue
        if cap and cap.get("backend") == b["backend"]:
            if cap.get("dpi_capable"):
                chosen = b["backend"]
                break
            continue
        chosen = b["backend"]
        break
    if chosen is None:
        raise RasterError(DPI_CAPABILITY_UNAVAILABLE,
                          {"requested_dpi": dpi, "backends": backends,
                           "remediation": "install pdftoppm/poppler, or make "
                                          "PyMuPDF importable in this runtime"})
    geom = page_geometry(pdf_path, page)
    ew, eh = expected_dimensions(geom, dpi)
    r = _render(chosen, pdf_path, dpi, out_png, page=page, verify=True)
    return {"schema_version": MANIFEST_SCHEMA,
            "source_pdf": pdf_path, "source_sha256": _sha(pdf_path),
            "page": page, "page_geometry": geom, "requested_dpi": dpi,
            "expected_dimensions": [ew, eh],
            "actual_dimensions": [r["width"], r["height"]],
            "width_error_px": r["width"] - ew,
            "height_error_px": r["height"] - eh,
            "effective_dpi_x": round(r["width"] * 72.0
                                     / displayed_points(geom)[0], 3),
            "effective_dpi_y": round(r["height"] * 72.0
                                     / displayed_points(geom)[1], 3),
            "backend": chosen, "output_png": out_png,
            "output_sha256": r["sha"],
            "dimension_verification": "PASSED",
            "capability_certification": (cap or {}).get("dpi_capable"),
            "rendered_at": datetime.now(timezone.utc).isoformat()}


def rasterizer_identity() -> dict:
    """§8 — the identity that repo, worker and web must agree on."""
    b = [x for x in probe_backends() if x.get("available")]
    return {"backends_available": [x["backend"] for x in b],
            "preferred": next((x["backend"] for x in b
                               if x.get("explicit_dpi_claimed")), None),
            "pymupdf_version": next((x.get("version") for x in b
                                     if x["backend"] == "pymupdf"), None)}
