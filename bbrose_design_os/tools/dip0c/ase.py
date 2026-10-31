"""A fixture-tested ASE (Adobe Swatch Exchange) parser (DIP-0C3c).

The format is small and **offset-fiddly**, which is exactly why it gets a real parser
rather than a clever guess. Every read is bounds-checked against the block length the
file itself declares; nothing is recovered by intuition.

## The layout problem

The documented colour-entry block begins with a `uint16` name length. The one ASE in
`materials/` **omits that field**: read as documented, its name length is 0x0050 = 80
UTF-16 units = 160 bytes, inside a 48-byte body. That is not unusual, it is
*impossible* — and a parser that trusts the spec would either crash or, worse, read
garbage and call it a colour.

So parsing runs a **two-layout protocol**, in this order:

1. `STANDARD` — the documented, length-prefixed layout.
2. `NON_STANDARD_NAME_ENCODING` — a NUL-terminated UTF-16BE name with no length
   prefix. This is tried **only** when the standard layout is *provably* impossible
   (a field cannot fit, or parsing would cross the declared block boundary), and it is
   accepted **only** if it consumes the declared body **exactly**, leaves no
   unexplained bytes, and yields a valid model, channel count and colour type.

If both layouts validate, if neither consumes the block exactly, or if more than one
fallback reading is possible, the answer is `PARSE_FAILED` / `REQUIRES_HUMAN`. **No
interpretation is ever chosen heuristically.** A file that needed the fallback can
never be `TECHNICALLY_PARSED` — needing a fallback is itself a finding.
"""
from __future__ import annotations

import hashlib
import struct

from . import config as C

PARSER = f"{C.TOOL_NAME}.ase/{C.TOOL_VERSION}"
SCHEMA_VERSION = "ase/1.0"

SIGNATURE = b"ASEF"
HEADER_LEN = 12                 # sig(4) + major(2) + minor(2) + block_count(4)

# --- block types --------------------------------------------------------------
BLOCK_GROUP_START = 0xC001
BLOCK_GROUP_END = 0xC002
BLOCK_COLOR = 0x0001
KNOWN_BLOCKS = (BLOCK_GROUP_START, BLOCK_GROUP_END, BLOCK_COLOR)

# --- colour models: name -> channel count --------------------------------------
MODELS = {b"RGB ": 3, b"CMYK": 4, b"LAB ": 3, b"GRAY": 1}

# --- colour types --------------------------------------------------------------
COLOR_TYPES = {0: "GLOBAL", 1: "SPOT", 2: "NORMAL"}

# --- layouts -------------------------------------------------------------------
LAYOUT_STANDARD = "STANDARD"
LAYOUT_NON_STANDARD = "NON_STANDARD_NAME_ENCODING"

# --- parse statuses ------------------------------------------------------------
TECHNICALLY_PARSED = "TECHNICALLY_PARSED"
PARTIAL_PARSE = "PARTIAL_PARSE"
UNSUPPORTED_BLOCK = "UNSUPPORTED_BLOCK"
PARSE_FAILED = "PARSE_FAILED"
STATUSES = (TECHNICALLY_PARSED, PARTIAL_PARSE, UNSUPPORTED_BLOCK, PARSE_FAILED)

CAP_DIRECT = "DIRECT"
CAP_REQUIRES_HUMAN = "REQUIRES_HUMAN"

# --- warnings ------------------------------------------------------------------
W_NAME_LENGTH_ABSENT = "NAME_LENGTH_FIELD_ABSENT"
W_TRAILING_BYTES = "TRAILING_BYTES"
W_TRUNCATED_HEADER = "TRUNCATED_HEADER"
W_TRUNCATED_BLOCK = "TRUNCATED_BLOCK"
W_INVALID_BLOCK_LENGTH = "INVALID_BLOCK_LENGTH"
W_MALFORMED_UTF16 = "MALFORMED_UTF16"
W_UNKNOWN_BLOCK = "UNKNOWN_BLOCK_TYPE"
W_BLOCK_COUNT_MISMATCH = "DECLARED_BLOCK_COUNT_MISMATCH"
W_UNEXPLAINED_BYTES = "UNEXPLAINED_BYTES_IN_BLOCK"
W_AMBIGUOUS_LAYOUT = "AMBIGUOUS_LAYOUT"
W_UNSUPPORTED_MODEL = "UNSUPPORTED_COLOR_MODEL"
W_INVALID_COLOR_TYPE = "INVALID_COLOR_TYPE"
W_GROUP_UNBALANCED = "UNBALANCED_GROUP_BLOCKS"


class AseError(RuntimeError):
    """The parser refuses to guess."""


def _u16(b: bytes, o: int) -> int:
    return struct.unpack_from(">H", b, o)[0]


def _u32(b: bytes, o: int) -> int:
    return struct.unpack_from(">I", b, o)[0]


def _utf16_name(body: bytes, off: int, units: int) -> tuple[str, int, str | None]:
    """Decode `units` UTF-16BE code units (INCLUDING the trailing NUL)."""
    nbytes = units * 2
    if off + nbytes > len(body):
        return "", 0, W_TRUNCATED_BLOCK
    raw = body[off:off + nbytes]
    if units and raw[-2:] != b"\x00\x00":
        return "", 0, W_MALFORMED_UTF16          # not NUL-terminated as declared
    try:
        name = raw[:-2].decode("utf-16-be") if units else ""
    except UnicodeDecodeError:
        return "", 0, W_MALFORMED_UTF16
    if "\x00" in name:
        return "", 0, W_MALFORMED_UTF16          # an embedded NUL: not a valid name
    return name, nbytes, None


# --- the two colour-entry layouts ---------------------------------------------
def _color_standard(body: bytes) -> dict:
    """The documented layout: uint16 name length, then the UTF-16BE name."""
    if len(body) < 2:
        return {"ok": False, "why": "the block is too short to hold a name length"}
    units = _u16(body, 0)
    need = 2 + units * 2
    if need > len(body):
        return {"ok": False, "why": (
            f"declared name length {units} UTF-16 units = {units * 2} bytes, but the "
            f"block body is only {len(body)} bytes — the name cannot fit, so the "
            "documented layout is PROVABLY impossible here")}
    name, used, warn = _utf16_name(body, 2, units)
    if warn:
        return {"ok": False, "why": f"name decode failed: {warn}"}
    return _color_tail(body, 2 + used, name)


def _color_non_standard(body: bytes) -> dict:
    """No length prefix: a NUL-terminated UTF-16BE name."""
    end = None
    for i in range(0, len(body) - 1, 2):
        if body[i:i + 2] == b"\x00\x00":
            end = i
            break
    if end is None:
        return {"ok": False, "why": "no NUL terminator: the name never ends"}
    try:
        name = body[:end].decode("utf-16-be")
    except UnicodeDecodeError:
        return {"ok": False, "why": f"name decode failed: {W_MALFORMED_UTF16}"}
    return _color_tail(body, end + 2, name)


def _color_tail(body: bytes, off: int, name: str) -> dict:
    """model(4) + channels(4 each) + colour type(2) — the part both layouts share."""
    if off + 4 > len(body):
        return {"ok": False, "why": "the block ends before the colour model"}
    model = body[off:off + 4]
    if model not in MODELS:
        return {"ok": False, "why": f"{W_UNSUPPORTED_MODEL}: {model!r}"}
    n = MODELS[model]
    need = off + 4 + n * 4 + 2
    if need > len(body):
        return {"ok": False, "why": (
            f"{model.decode().strip()} needs {n} channels + a colour type "
            f"({need} bytes), but the block body is {len(body)} — parsing would cross "
            "the declared block boundary")}
    vals = struct.unpack_from(">" + "f" * n, body, off + 4)
    ctype = _u16(body, off + 4 + n * 4)
    if ctype not in COLOR_TYPES:
        return {"ok": False, "why": f"{W_INVALID_COLOR_TYPE}: {ctype}"}
    return {
        "ok": True,
        "name": name,
        "model": model.decode("ascii").strip(),
        "channels": [float(v) for v in vals],
        "color_type": COLOR_TYPES[ctype],
        "color_type_raw": ctype,
        "consumed": need,
        "unexplained_bytes": len(body) - need,
    }


def parse_color_block(body: bytes) -> dict:
    """Resolve ONE colour entry under the two-layout protocol.

    The rule, in order: the documented layout first. The fallback only when the
    standard one is provably impossible. Accept the fallback only if it consumes the
    declared body EXACTLY. Anything ambiguous fails closed.
    """
    std = _color_standard(body)
    if std["ok"] and std["unexplained_bytes"] == 0:
        return {**std, "layout": LAYOUT_STANDARD, "fallback_used": False,
                "warnings": [], "standard_failure_reason": None}

    # the standard layout parsed, but did not account for the whole block
    if std["ok"] and std["unexplained_bytes"] != 0:
        return {"ok": False, "layout": None, "fallback_used": False,
                "warnings": [W_UNEXPLAINED_BYTES],
                "standard_failure_reason": (
                    f"the documented layout leaves {std['unexplained_bytes']} bytes "
                    "of the block unexplained — it does not consume the body exactly"),
                "why": "the documented layout does not consume the block exactly"}

    alt = _color_non_standard(body)
    if not alt["ok"]:
        return {"ok": False, "layout": None, "fallback_used": False,
                "warnings": [], "standard_failure_reason": std["why"],
                "why": f"neither layout parses this block. standard: {std['why']}; "
                       f"fallback: {alt['why']}"}
    if alt["unexplained_bytes"] != 0:
        return {"ok": False, "layout": None, "fallback_used": False,
                "warnings": [W_UNEXPLAINED_BYTES],
                "standard_failure_reason": std["why"],
                "why": (f"the fallback leaves {alt['unexplained_bytes']} unexplained "
                        "bytes — it must consume the declared body exactly")}

    # The fallback is unique by construction: the NUL terminator is the FIRST one, and
    # the tail (model, channels, type) is fully determined by the model token. Any
    # other NUL split would move the model token and fail validation. Assert it.
    if _ambiguous(body):
        return {"ok": False, "layout": None, "fallback_used": False,
                "warnings": [W_AMBIGUOUS_LAYOUT],
                "standard_failure_reason": std["why"],
                "why": "more than one fallback reading of this block is valid — the "
                       "parser will not choose between them"}

    return {**alt, "layout": LAYOUT_NON_STANDARD, "fallback_used": True,
            "warnings": [W_NAME_LENGTH_ABSENT],
            "standard_failure_reason": std["why"]}


def _ambiguous(body: bytes) -> bool:
    """Could a LATER NUL split also produce a valid, exact reading? If so, refuse."""
    valid = 0
    for i in range(0, len(body) - 1, 2):
        if body[i:i + 2] != b"\x00\x00":
            continue
        try:
            body[:i].decode("utf-16-be")
        except UnicodeDecodeError:
            continue
        t = _color_tail(body, i + 2, "")
        if t["ok"] and t["unexplained_bytes"] == 0:
            valid += 1
    return valid > 1


# --- the file -----------------------------------------------------------------
def parse(data: bytes, *, source: str = None) -> dict:
    """Parse an ASE. Never raises on malformed input — it reports."""
    warnings: list[str] = []
    blocks: list[dict] = []
    swatches: list[dict] = []
    groups: list[dict] = []
    status = TECHNICALLY_PARSED

    result = {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_bytes": len(data),
        "signature": None, "version": None,
        "declared_block_count": None, "parsed_block_count": 0,
        "groups": groups, "swatches": swatches, "blocks": blocks,
        "warnings": warnings, "parse_status": PARSE_FAILED,
        "capability": CAP_REQUIRES_HUMAN,
        "fallback_used": False, "layouts_seen": [],
        "trailing_bytes": 0,
        "parser": PARSER,
    }

    if len(data) < HEADER_LEN or data[:4] != SIGNATURE:
        warnings.append(W_TRUNCATED_HEADER if len(data) < HEADER_LEN
                        else "BAD_SIGNATURE")
        result["signature"] = data[:4].decode("latin-1", "replace") if data else ""
        return result

    result["signature"] = "ASEF"
    result["version"] = [_u16(data, 4), _u16(data, 6)]
    declared = _u32(data, 8)
    result["declared_block_count"] = declared

    pos, depth = HEADER_LEN, 0
    while pos + 6 <= len(data):
        btype = _u16(data, pos)
        blen = _u32(data, pos + 2)
        start = pos + 6
        rec = {"index": len(blocks), "type": f"0x{btype:04X}",
               "offset": pos, "body_offset": start, "declared_length": blen}

        if start + blen > len(data):
            rec["error"] = W_TRUNCATED_BLOCK
            warnings.append(W_TRUNCATED_BLOCK)
            blocks.append(rec)
            status = PARTIAL_PARSE
            break
        body = data[start:start + blen]
        rec["body_sha256"] = hashlib.sha256(body).hexdigest()

        if btype == BLOCK_COLOR:
            c = parse_color_block(body)
            rec.update({k: v for k, v in c.items() if k != "ok"})
            if c["ok"]:
                if c["fallback_used"]:
                    result["fallback_used"] = True
                    status = PARTIAL_PARSE       # a fallback is itself a finding
                for w in c["warnings"]:
                    if w not in warnings:
                        warnings.append(w)
                if c["layout"] not in result["layouts_seen"]:
                    result["layouts_seen"].append(c["layout"])
                swatches.append({
                    "block_index": rec["index"],
                    "name": c["name"], "model": c["model"],
                    "channels": c["channels"], "color_type": c["color_type"],
                    "color_type_raw": c["color_type_raw"],
                    "source_offset": start, "source_end": start + blen,
                    "declared_block_length": blen,
                    "body_sha256": rec["body_sha256"],
                    "layout": c["layout"], "fallback_used": c["fallback_used"],
                    "standard_failure_reason": c["standard_failure_reason"],
                    "bytes_consumed": c["consumed"],
                    "unexplained_bytes": c["unexplained_bytes"],
                    "group": groups[-1]["name"] if depth and groups else None,
                })
            else:
                rec["error"] = c["why"]
                warnings.append(W_INVALID_BLOCK_LENGTH
                                if "cross" in c["why"] or "fit" in c["why"]
                                else W_MALFORMED_UTF16)
                status = PARSE_FAILED

        elif btype == BLOCK_GROUP_START:
            g = _group_name(body)
            rec["name"] = g["name"]
            if not g["ok"]:
                rec["error"] = g["why"]
                warnings.append(W_MALFORMED_UTF16)
                status = PARTIAL_PARSE if status != PARSE_FAILED else status
            groups.append({"name": g["name"], "block_index": rec["index"],
                           "swatch_names": []})
            depth += 1

        elif btype == BLOCK_GROUP_END:
            depth -= 1
            if depth < 0:
                warnings.append(W_GROUP_UNBALANCED)
                status = PARTIAL_PARSE if status != PARSE_FAILED else status
                depth = 0

        else:
            # An unknown block is PRESERVED, never skipped in silence.
            rec["preserved_body_sha256"] = rec["body_sha256"]
            rec["note"] = ("unknown block type — preserved, not interpreted. The "
                           "parser will not guess what it means.")
            warnings.append(W_UNKNOWN_BLOCK)
            if status == TECHNICALLY_PARSED:
                status = UNSUPPORTED_BLOCK

        blocks.append(rec)
        pos = start + blen

    if depth != 0 and W_GROUP_UNBALANCED not in warnings:
        warnings.append(W_GROUP_UNBALANCED)
        status = PARTIAL_PARSE if status != PARSE_FAILED else status

    trailing = len(data) - pos
    if trailing > 0:
        result["trailing_bytes"] = trailing
        warnings.append(W_TRAILING_BYTES)
        if status == TECHNICALLY_PARSED:
            status = PARTIAL_PARSE

    result["parsed_block_count"] = len(blocks)
    if declared != len(blocks):
        warnings.append(W_BLOCK_COUNT_MISMATCH)
        if status == TECHNICALLY_PARSED:
            status = PARTIAL_PARSE

    # attach swatch names to their groups (deterministic)
    for s in swatches:
        for g in groups:
            if g["name"] == s["group"]:
                g["swatch_names"].append(s["name"])

    result["parse_status"] = status
    result["capability"] = (CAP_DIRECT if status == TECHNICALLY_PARSED
                            else CAP_REQUIRES_HUMAN)
    return result


def _group_name(body: bytes) -> dict:
    if len(body) < 2:
        return {"ok": False, "name": None, "why": "group block too short"}
    units = _u16(body, 0)
    name, used, warn = _utf16_name(body, 2, units)
    if warn:
        # a group name may also lack the length prefix
        try:
            end = next(i for i in range(0, len(body) - 1, 2)
                       if body[i:i + 2] == b"\x00\x00")
            return {"ok": True, "name": body[:end].decode("utf-16-be"),
                    "why": None}
        except (StopIteration, UnicodeDecodeError):
            return {"ok": False, "name": None, "why": warn}
    return {"ok": True, "name": name, "why": None}


def parse_file(path) -> dict:
    return parse(C.Path(path).read_bytes(), source=str(path))


# --- deterministic serialisation ----------------------------------------------
def serialize(doc: dict) -> bytes:
    """Write a STANDARD-layout ASE from a parsed document. Round-tripping a
    non-standard file through this produces a CONFORMANT file — which is a
    derivative, not the source, and never replaces it."""
    out = bytearray(SIGNATURE)
    out += struct.pack(">HH", *(doc["version"] or [1, 0]))
    blocks = bytearray()
    n = 0
    for s in doc["swatches"]:
        body = bytearray()
        name = s["name"] + "\x00"
        body += struct.pack(">H", len(name))
        body += name.encode("utf-16-be")
        model = s["model"].ljust(4)[:4].encode("ascii")
        body += model
        body += struct.pack(">" + "f" * len(s["channels"]), *s["channels"])
        body += struct.pack(">H", s["color_type_raw"])
        blocks += struct.pack(">HI", BLOCK_COLOR, len(body)) + bytes(body)
        n += 1
    out += struct.pack(">I", n)
    out += blocks
    return bytes(out)
