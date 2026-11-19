"""An article's cover: cover/cover.svg, the small picture next to it in every list (guides/covers.md).

The site inlines the drawing, so it must be safe markup: a short list of shape elements and attributes, no ids,
no links, no styles. Colours are classes (f-<name> fills, s-<name> strokes) that apps/web/app/site.css maps to
Glacier tokens, which is how a cover follows the light and dark themes. `check_svg` is the one gate: the stage's
`artools run done`, the preview and the publisher all call it."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .paths import read_json

SVG_NS = "http://www.w3.org/2000/svg"
VIEWBOX = "0 0 480 320"
MAX_BYTES = 12 * 1024
MAX_ELEMENTS = 80
MIN_STROKE, GOOD_STROKE = 4, 8

# name → Glacier token; site.css has a rule per name (tests keep the two in step)
PALETTE = {
    "frost": "surface-frost", "ice": "surface-ice", "paper": "surface", "line": "line",
    "deep": "deep", "strata": "deep-strata", "glint": "deep-glint",
    "glacier": "accent", "tarn": "link", "crevasse": "deep-accent",
    "focus": "viz-focus", "context": "viz-context", "ink": "ink", "ink2": "ink-secondary",
    **{f"seq{i}": f"seq-{i}00" for i in range(1, 8)},
    "warm": "viz-2", "lake": "viz-3", "ochre": "viz-4",
}
SHAPES = {"rect", "circle", "ellipse", "line", "polyline", "polygon", "path"}
ELEMENTS = SHAPES | {"g"}
GEOMETRY = {"x", "y", "width", "height", "rx", "ry", "cx", "cy", "r", "x1", "y1", "x2", "y2", "points", "d"}
PAINT = {"opacity", "fill-opacity", "stroke-opacity", "stroke-width", "stroke-linecap", "stroke-linejoin",
         "stroke-dasharray", "stroke-miterlimit", "fill-rule"}
ATTRS = GEOMETRY | PAINT | {"transform", "class", "fill", "stroke"}
ROOT_ATTRS = {"viewBox", "width", "height"}
SAFE_VALUE = re.compile(r"^[0-9a-zA-Z .,\-+()%]*$")   # numbers, path data, transforms, keywords; never url(…)


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if tag.startswith("{") else tag


def check_svg(text: str) -> dict:
    """{blocking, advisory, elements, bytes, palette} for a cover's markup."""
    blocking, advisory = [], []
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        blocking.append(f"cover.svg is {size} bytes; at most {MAX_BYTES} (fewer, simpler shapes)")
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
        return {"blocking": blocking + ["no DOCTYPE or ENTITY declarations"], "advisory": advisory, "elements": 0, "bytes": size}
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return {"blocking": blocking + [f"not well-formed XML: {e}"], "advisory": advisory, "elements": 0, "bytes": size}
    if root.tag != f"{{{SVG_NS}}}svg":
        blocking.append('the root must be <svg xmlns="http://www.w3.org/2000/svg">')
    if root.get("viewBox") != VIEWBOX:
        blocking.append(f'the root needs viewBox="{VIEWBOX}" (3:2, the thumbnail\'s shape); found {root.get("viewBox")!r}')
    for k in root.attrib:
        if _local(k) not in ROOT_ATTRS:
            advisory.append(f"root attribute {_local(k)} is dropped on the site")
    if root.get("width") or root.get("height"):
        advisory.append("width and height on the root are ignored; the viewBox sets the shape")

    used: dict[str, int] = {}
    count = 0

    def walk(el, fill_ok: bool, stroke: bool, width: float | None, where: str):
        nonlocal count
        for i, ch in enumerate(list(el)):
            if not isinstance(ch.tag, str):     # comments and processing instructions
                continue
            count += 1
            tag = _local(ch.tag)
            at = f"{where}/{tag}[{i + 1}]"
            if ch.tag != f"{{{SVG_NS}}}{tag}" or tag not in ELEMENTS:
                blocking.append(f"{at}: <{tag}> is not allowed; only {', '.join(sorted(ELEMENTS))}")
                continue
            if (ch.text or "").strip() or (ch.tail or "").strip():
                blocking.append(f"{at}: text content is not allowed")
            f_ok, s_on, w = fill_ok, stroke, width
            for k, v in ch.attrib.items():
                name = _local(k)
                if k.startswith("{") or name not in ATTRS:
                    blocking.append(f"{at}: attribute {name} is not allowed")
                    continue
                if name in ("fill", "stroke") and v != "none":
                    blocking.append(f"{at}: {name}={v[:40]!r}; colours are classes (f-<name>, s-<name>), the attribute may only be \"none\"")
                    continue
                if not SAFE_VALUE.match(v) or "url" in v.lower():
                    blocking.append(f"{at}: {name}={v[:40]!r} has characters a shape attribute doesn't need")
                    continue
                if name == "fill" and v == "none":
                    f_ok = True
                if name == "stroke" and v == "none":
                    s_on = False
                if name == "stroke-width":
                    try:
                        w = float(v)
                    except ValueError:
                        blocking.append(f"{at}: stroke-width {v!r} is not a number")
                if name in ("opacity", "fill-opacity", "stroke-opacity"):
                    try:
                        if not 0 <= float(v) <= 1:
                            raise ValueError
                    except ValueError:
                        blocking.append(f"{at}: {name} {v!r} must be a number from 0 to 1")
            for c in (ch.get("class") or "").split():
                kind, _, colour = c.partition("-")
                if kind not in ("f", "s") or colour not in PALETTE:
                    blocking.append(f"{at}: class {c!r} is not a palette colour (f-<name> or s-<name>; guides/covers.md)")
                    continue
                used[colour] = used.get(colour, 0) + (1 if tag in SHAPES else 0)
                if kind == "f":
                    f_ok = True
                else:
                    s_on = True
            if tag in SHAPES:
                if tag != "line" and not f_ok:
                    blocking.append(f"{at}: no f- class and no fill=\"none\" (the default fill is black)")
                if tag == "line" and not s_on:
                    blocking.append(f"{at}: a line needs an s- class to be seen")
                if s_on:
                    sw = 1.0 if w is None else w
                    if sw < MIN_STROKE:
                        blocking.append(f"{at}: stroke-width {sw:g} vanishes at phone size; at least {GOOD_STROKE}")
                    elif sw < GOOD_STROKE:
                        advisory.append(f"{at}: stroke-width {sw:g} is thin at phone size; {GOOD_STROKE} or more reads better")
            walk(ch, f_ok, s_on, w, at)

    walk(root, False, False, None, "svg")
    if count > MAX_ELEMENTS:
        blocking.append(f"{count} elements; at most {MAX_ELEMENTS} (a cover is a few shapes)")
    kids = [c for c in root if isinstance(c.tag, str)]
    bg = kids[0] if kids else None
    if bg is None or _local(bg.tag) != "rect" or [bg.get(k, "0") for k in ("x", "y")] != ["0", "0"] \
            or (bg.get("width"), bg.get("height")) != ("480", "320") or not re.search(r"\bf-", bg.get("class") or ""):
        blocking.append('the first element must be the background: <rect x="0" y="0" width="480" height="320" class="f-…"/>')
    if used.get("warm", 0) > 1:
        advisory.append(f"warm is on {used['warm']} shapes; keep the warm accent for one")
    if count and count < 3:
        advisory.append("fewer than three elements: is the subject there?")
    return {"blocking": blocking, "advisory": advisory, "elements": count, "bytes": size, "palette": sorted(used)}


def check(run: Path) -> dict:
    """`artools check cover`: the drawing's rules, plus the record's alt text."""
    svg = run / "cover" / "cover.svg"
    if not svg.is_file():
        return {"blocking": ["cover/cover.svg is missing"], "advisory": [], "ok": False}
    res = check_svg(svg.read_text(encoding="utf-8"))
    rec = read_json(run / "cover" / "cover.json", {}) or {}
    for lang in ("en", "ko"):
        alt = (rec.get("alt") or {}).get(lang) or ""
        if not alt:
            res["advisory"].append(f"cover.json: no alt text ({lang}) yet")
        elif re.search(r"\b(shows that|proves|means that)\b", alt, re.I):
            res["advisory"].append(f"cover.json alt ({lang}) argues; describe the picture instead")
    return {**res, "ok": not res["blocking"]}

