"""The jury's comparison anchors (Day 8 §2b, D-D8-7): launched products' pictures, fetched once each under every guard
of the engine (robots per URL, SSRF and redirects, MIME allowlist, byte cap) into the web quarantine — research only:
never placed, never sent to an image model (``image_guard`` refuses anything under the quarantine), never in git.

A brand's own product page is read for the pictures it declares (og:image, twitter:image, its JSON-LD product images,
its own CDN's product pictures); each picture is fetched only where the host's robots.txt allows it. The trend board's
modes are not touched: brand sites stay links on the board; an anchor is the jury's, fetched for this alone.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from apps.pipeline.services import web_research as wr

PICTURE_TYPES = ("image/jpeg", "image/png", "image/webp")
PAGE_BYTE_LIMIT = 3 * 1024 * 1024
MAX_PICTURES_A_PAGE = 8
_IMG_RE = re.compile(r'''(?:src|data-src|content|href)\s*=\s*["']([^"']+\.(?:jpg|jpeg|png|webp)(?:\?[^"']*)?)["']''', re.I)
_JSONLD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def root(config=None) -> Path:
    config = config or wr.gateway_config()
    return Path(config["quarantine_root"]) / "day8-anchors"


def _jsonld_images(html: str) -> list:
    out = []
    for block in _JSONLD_RE.findall(html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                image = item.get("image")
                if isinstance(image, str):
                    out.append(image)
                elif isinstance(image, list):
                    out.extend(i if isinstance(i, str) else (i or {}).get("url", "") for i in image)
                elif isinstance(image, dict) and image.get("url"):
                    out.append(image["url"])
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
    return [u for u in out if u]


def pictures_declared(page_url: str, html: str) -> list:
    """The pictures a product page declares for itself, best first: og/twitter, JSON-LD product images, then images on
    the page's own host or its CDN whose names say product, packshot or the product's handle."""
    from apps.pipeline.services.trend_board import declared_pictures
    found = list(declared_pictures(page_url, html)) + [urljoin(page_url, u) for u in _jsonld_images(html)]
    handle = urlparse(page_url).path.rstrip("/").split("/")[-1].lower()
    for url in _IMG_RE.findall(html):
        absolute = urljoin(page_url, url if not url.startswith("//") else "https:" + url)
        low = absolute.lower()
        if any(word in low for word in ("packshot", "product", "pdp", handle[:18])) and "logo" not in low:
            found.append(absolute)
    import html as _html
    seen, out = set(), []
    for url in (_html.unescape(u) for u in found):       # a page's "&amp;" is "&" in the address it means
        key = re.sub(r"[?&](width|height|w|h|crop|v)=[^&]*", "", url)
        if url.startswith("http") and key not in seen:
            seen.add(key)
            out.append(url)
    return out[:MAX_PICTURES_A_PAGE]


def fetch(brand: str, page_url: str, *, http_get=None, robots=None, picture_urls=()) -> dict:
    """One product page read and its pictures fetched into ``<quarantine>/day8-anchors/<brand>/`` — each under every
    guard; the record says what was asked, what each host's robots answered, and what was kept."""
    from apps.pipeline.services.web_research_tavily import HostManners
    config = wr.gateway_config()
    manners = HostManners(config, delay=config["limits"]["per_domain_delay_s"], robots=robots)
    folder = root(config) / re.sub(r"[^a-z0-9]+", "-", brand.lower()).strip("-")
    folder.mkdir(parents=True, exist_ok=True)
    record = {"brand": brand, "page_url": page_url, "asked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
              "user_agent": config["user_agent"], "page": None, "pictures": []}
    urls = list(picture_urls)
    host = urlparse(page_url).hostname or ""
    why = manners.refused(page_url, host)
    if why is not None:
        record["page"] = {"refused": why}
    else:
        manners.polite(host)
        try:
            page = wr.governed_fetch(page_url, config, http_get=http_get, byte_limit=PAGE_BYTE_LIMIT,
                                     robots=manners.robots_of)
            html = page["body"].decode("utf-8", errors="replace")
            record["page"] = {"http_status": page["http_status"], "bytes": page["byte_count"]}
            urls += pictures_declared(page_url, html)
        except wr.WebPolicyError as exc:
            record["page"] = {"refused": exc.code, "why": str(exc)[:200]}
        except Exception as exc:  # noqa: BLE001 — a host that cannot be reached is said, never worked around
            record["page"] = {"refused": "HOST_UNREACHABLE", "why": type(exc).__name__}
    for url in dict.fromkeys(urls):
        h = urlparse(url).hostname or ""
        row = {"url": url}
        why = manners.refused(url, h)
        if why is not None:
            row["refused"] = why
            record["pictures"].append(row)
            continue
        manners.polite(h)
        try:
            got = wr.governed_fetch(url, config, http_get=http_get, robots=manners.robots_of)
            if got["mime_type"] not in PICTURE_TYPES:
                raise wr.WebPolicyError(wr.WEB_UNSUPPORTED_CONTENT_TYPE, got["mime_type"])
            sha = hashlib.sha256(got["body"]).hexdigest()
            ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[got["mime_type"]]
            path = folder / (sha[:16] + ext)
            path.write_bytes(got["body"])
            row.update(kept=str(path), sha256=sha, bytes=got["byte_count"], mime=got["mime_type"])
        except wr.WebPolicyError as exc:
            row.update(refused=exc.code, why=str(exc)[:160])
        except Exception as exc:  # noqa: BLE001
            row.update(refused="HOST_UNREACHABLE", why=type(exc).__name__)
        record["pictures"].append(row)
    (folder / "record.json").write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    return record


def crop(source, box, destination) -> dict:
    """An anchor cropped front-on to its closed lid (``box`` = left, top, right, bottom in source pixels), kept in the
    quarantine beside its source; returns the crop's record."""
    from PIL import Image
    source, destination = Path(source), Path(destination)
    with Image.open(source) as im:
        cut = im.convert("RGB").crop(tuple(int(v) for v in box))
        destination.parent.mkdir(parents=True, exist_ok=True)
        cut.save(destination, format="PNG", optimize=True)
    return {"source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "box_px": list(box), "crop": str(destination), "crop_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
