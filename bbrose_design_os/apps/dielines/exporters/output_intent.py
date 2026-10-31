"""PDF/X OutputIntent + ICC profile identity contract (2A-6-CORR-1 §9).

reportlab's public canvas API cannot attach an ICC OutputIntent, so the
production PDF historically had none — a gap the Gate-2 validator surfaces
as `MISSING_OUTPUT_INTENT` rather than hiding. This module closes it by
post-processing the finished PDF with PyMuPDF, and — equally important —
records WHICH profile was embedded so the readiness report can be audited.

Policy (unchanged, hardened):

  * **No guessed default.** WHICH CMYK profile is the print shop's decision.
    Without `PRODUCTION_ICC_PROFILE_PATH` nothing is embedded and the
    validator's failure stands. A wrong intent is worse than none — the file
    would claim a colour space the plates were not built for.
  * **CMYK only.** An RGB monitor profile, a grayscale profile, a Lab
    profile or a malformed file is REFUSED with a specific reason.
  * **Identity is recorded**: path, SHA-256, ICC description, colour-space
    class, device/profile class, profile version, and the validation result
    — all published into the production-readiness report.
  * Preview PDFs may be produced without a profile only when marked
    `PREVIEW_ONLY_NO_OUTPUT_INTENT`; they are never production deliverables.
"""
from __future__ import annotations

import hashlib
import logging
import os
import struct
from dataclasses import asdict, dataclass, field

from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_CONDITION = "FOGRA39"

#: Marker for a PDF generated without an output intent.
PREVIEW_ONLY_NO_OUTPUT_INTENT = "PREVIEW_ONLY_NO_OUTPUT_INTENT"

# ICC header: data-colour-space signature → component count.
_COLOUR_SPACES = {
    b"CMYK": ("CMYK", 4), b"RGB ": ("RGB", 3), b"GRAY": ("GRAY", 1),
    b"Lab ": ("Lab", 3), b"XYZ ": ("XYZ", 3),
}
# ICC header: profile/device class signature.
_DEVICE_CLASSES = {
    b"prtr": "output (printer)", b"mntr": "display (monitor)",
    b"scnr": "input (scanner)", b"link": "device link",
    b"spac": "colour space", b"abst": "abstract", b"nmcl": "named colour",
}
#: Only an output (printer) profile describes a press condition.
_REQUIRED_DEVICE_CLASS = b"prtr"

_MIN_ICC_BYTES = 128            # the header alone is 128 bytes


class ICCProfileError(ValueError):
    """The configured ICC profile cannot serve as a production intent."""


@dataclass
class ICCProfileIdentity:
    """Everything the readiness report must record about the profile."""
    configured: bool = False
    path: str = ""
    filename: str = ""
    sha256: str = ""
    size_bytes: int = 0
    description: str = ""
    colour_space: str = ""
    components: int = 0
    device_class: str = ""
    device_class_code: str = ""
    profile_version: str = ""
    valid: bool = False
    validation_result: str = "NOT_CONFIGURED"
    detail: str = ""
    output_condition: str = ""
    registry_name: str = ""
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def output_intent_settings() -> tuple[str, str, str]:
    """(icc_path, output_condition, registry) from settings."""
    return (
        str(getattr(settings, "PRODUCTION_ICC_PROFILE_PATH", "") or "").strip(),
        str(getattr(settings, "PRODUCTION_OUTPUT_CONDITION", "")
            or _DEFAULT_CONDITION).strip(),
        str(getattr(settings, "PRODUCTION_OUTPUT_REGISTRY", "")
            or "http://www.color.org").strip(),
    )


def describe_profile(icc_path: str = "") -> ICCProfileIdentity:
    """Parse + validate the configured (or given) ICC profile.

    Never raises: an unreadable or unsuitable profile comes back with
    ``valid=False`` and a specific ``validation_result``.
    """
    configured_path, condition, registry = output_intent_settings()
    path = (icc_path or configured_path).strip()
    ident = ICCProfileIdentity(configured=bool(path), path=path,
                               output_condition=condition,
                               registry_name=registry)
    if not path:
        ident.validation_result = "NOT_CONFIGURED"
        ident.detail = (
            "no PRODUCTION_ICC_PROFILE_PATH configured — the print shop's "
            "CMYK profile is a business decision and is never guessed"
        )
        return ident

    ident.filename = os.path.basename(path)
    if not os.path.exists(path):
        ident.validation_result = "FILE_NOT_FOUND"
        ident.detail = f"configured ICC profile not found: {path}"
        ident.errors.append(ident.validation_result)
        return ident

    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        ident.validation_result = "UNREADABLE"
        ident.detail = f"could not read the ICC profile: {exc}"
        ident.errors.append(ident.validation_result)
        return ident

    ident.size_bytes = len(data)
    ident.sha256 = hashlib.sha256(data).hexdigest()

    if len(data) < _MIN_ICC_BYTES:
        ident.validation_result = "MALFORMED"
        ident.detail = (f"file is {len(data)} bytes — shorter than the "
                        f"{_MIN_ICC_BYTES}-byte ICC header")
        ident.errors.append(ident.validation_result)
        return ident

    declared_size = struct.unpack(">I", data[0:4])[0]
    if data[36:40] != b"acsp":
        ident.validation_result = "MALFORMED"
        ident.detail = "missing the 'acsp' ICC signature — not an ICC profile"
        ident.errors.append(ident.validation_result)
        return ident
    if declared_size != len(data):
        ident.validation_result = "MALFORMED"
        ident.detail = (f"header declares {declared_size} bytes but the file "
                        f"is {len(data)}")
        ident.errors.append(ident.validation_result)
        return ident

    major, minor = data[8], data[9] >> 4
    ident.profile_version = f"{major}.{minor}"
    class_code = data[12:16]
    ident.device_class_code = class_code.decode("ascii", "replace")
    ident.device_class = _DEVICE_CLASSES.get(class_code, "unknown")
    space = data[16:20]
    name, components = _COLOUR_SPACES.get(
        space, (space.decode("ascii", "replace").strip(), 0))
    ident.colour_space = name
    ident.components = components
    ident.description = _profile_description(data) or ident.filename

    if space != b"CMYK":
        ident.validation_result = "NOT_CMYK"
        ident.detail = (
            f"profile colour space is {ident.colour_space!r}"
            + (" (an RGB monitor profile is not a press condition)"
               if space == b"RGB " else "")
            + " — a production output intent must be CMYK"
        )
        ident.errors.append(ident.validation_result)
        return ident
    if class_code != _REQUIRED_DEVICE_CLASS:
        ident.validation_result = "NOT_AN_OUTPUT_PROFILE"
        ident.detail = (f"profile class is {ident.device_class!r} — a "
                        "production intent needs an output (printer) profile")
        ident.errors.append(ident.validation_result)
        return ident

    ident.valid = True
    ident.validation_result = "VALID_CMYK_OUTPUT_PROFILE"
    ident.detail = (f"{ident.description} · {ident.colour_space}/"
                    f"{ident.components} · v{ident.profile_version}")
    return ident


def _profile_description(data: bytes) -> str:
    """The 'desc' tag text, best effort (ICC v2 'desc' and v4 'mluc')."""
    try:
        count = struct.unpack(">I", data[128:132])[0]
        for i in range(min(count, 200)):
            off = 132 + i * 12
            sig, toff, tsize = struct.unpack(">4sII", data[off:off + 12])
            if sig != b"desc":
                continue
            tag = data[toff:toff + tsize]
            if tag[0:4] == b"desc":                    # ICC v2
                length = struct.unpack(">I", tag[8:12])[0]
                return tag[12:12 + length].split(b"\x00")[0].decode(
                    "ascii", "replace").strip()
            if tag[0:4] == b"mluc":                    # ICC v4
                n_records = struct.unpack(">I", tag[8:12])[0]
                if n_records:
                    rlen, roff = struct.unpack(">II", tag[20:28])
                    return tag[roff:roff + rlen].decode(
                        "utf-16-be", "replace").strip("\x00").strip()
    except (struct.error, IndexError, UnicodeDecodeError):
        return ""
    return ""


def attach_output_intent(pdf_path: str, log=None) -> tuple[bool, ICCProfileIdentity]:
    """Embed the configured CMYK profile as a PDF/X OutputIntent.

    Returns ``(attached, identity)``. Never raises: a failure must not
    destroy a valid production PDF — the validator reports the missing
    intent instead, and the identity carries the exact reason.
    """
    log = log or (lambda msg, level="info": None)
    ident = describe_profile()
    if not ident.valid:
        return False, ident

    try:
        import fitz
    except ImportError:
        ident.validation_result = "PYMUPDF_UNAVAILABLE"
        ident.detail = "PyMuPDF unavailable — cannot attach an OutputIntent"
        ident.errors.append(ident.validation_result)
        return False, ident

    try:
        with open(ident.path, "rb") as fh:
            icc_bytes = fh.read()
        doc = fitz.open(pdf_path)
        try:
            stream_xref = doc.get_new_xref()
            doc.update_object(stream_xref, f"<< /N {ident.components} >>")
            doc.update_stream(stream_xref, icc_bytes, compress=True)

            intent_xref = doc.get_new_xref()
            doc.update_object(intent_xref, (
                "<< /Type /OutputIntent /S /GTS_PDFX "
                f"/OutputCondition ({ident.output_condition}) "
                f"/OutputConditionIdentifier ({ident.output_condition}) "
                f"/RegistryName ({ident.registry_name}) "
                f"/Info ({ident.description[:120]}) "
                f"/DestOutputProfile {stream_xref} 0 R >>"
            ))
            doc.xref_set_key(doc.pdf_catalog(), "OutputIntents",
                             f"[ {intent_xref} 0 R ]")
            doc.saveIncr()
        finally:
            doc.close()
    except Exception as exc:  # noqa: BLE001 — never destroy a valid PDF
        logger.warning("OutputIntent attachment failed: %s", exc)
        ident.validation_result = "ATTACHMENT_FAILED"
        ident.detail = f"OutputIntent attachment failed: {exc}"
        ident.errors.append(ident.validation_result)
        return False, ident

    log(f"Dieline: PDF/X OutputIntent attached ({ident.output_condition}, "
        f"{ident.description})")
    return True, ident


__all__ = [
    "attach_output_intent",
    "describe_profile",
    "output_intent_settings",
    "ICCProfileIdentity",
    "ICCProfileError",
    "PREVIEW_ONLY_NO_OUTPUT_INTENT",
]
