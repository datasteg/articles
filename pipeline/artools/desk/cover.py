"""A note's cover: the small picture beside it in every list, drawn by code as an echo of its first figure.

guides/covers.md allows three ideas for a cover; the desk uses the third, the data echo, because it needs no
judgement: the shape of the note's main figure, without axes, labels or numbers, in Glacier's colour classes. Bars
become bars, a dumbbell its lines and dots, a scatter its cloud with the focus points marked, a line its curve.
The result goes through the same check as a drawn cover (artools/cover.py); a cover that fails is left out and the
note's card shows without a picture.
"""
from __future__ import annotations

from pathlib import Path

from ..cover import check_svg
from ..paths import write_json

W, H, PAD = 480, 320, 44


def _bars(ch: dict) -> list[str]:
    cats = (ch.get("categories") or [])[:7]
    top = max(abs(c["value"]) for c in cats) or 1
    step = (H - 2 * PAD) / len(cats)
    out = []
    for i, c in enumerate(cats):
        w = max(14, (W - 2 * PAD) * abs(c["value"]) / top)
        out.append(f'<rect x="{PAD}" y="{PAD + i * step + step * 0.14:.0f}" width="{w:.0f}" height="{step * 0.72:.0f}" rx="4" '
                   f'class="{"f-tarn" if c.get("highlight") else "f-seq3"}"/>')
    return out


def _dumbbell(ch: dict) -> list[str]:
    rows = (ch.get("rows") or [])[:6]
    vals = [v for r in rows for v in (r["from"], r["to"])]
    lo, hi = min(vals), max(vals)
    x = lambda v: PAD + 16 + (W - 2 * PAD - 32) * (v - lo) / ((hi - lo) or 1)   # noqa: E731
    step = (H - 2 * PAD) / len(rows)
    out = []
    for i, r in enumerate(rows):
        y = PAD + i * step + step / 2
        hl = r.get("highlight")
        out.append(f'<line x1="{x(r["from"]):.0f}" y1="{y:.0f}" x2="{x(r["to"]):.0f}" y2="{y:.0f}" stroke-width="8" stroke-linecap="round" '
                   f'class="{"s-tarn" if hl else "s-seq3"}"/>')
        out.append(f'<circle cx="{x(r["from"]):.0f}" cy="{y:.0f}" r="12" class="f-paper {"s-tarn" if hl else "s-seq4"}" stroke-width="8"/>')
        out.append(f'<circle cx="{x(r["to"]):.0f}" cy="{y:.0f}" r="14" class="{"f-tarn" if hl else "f-seq4"}"/>')
    return out


def _scatter(ch: dict) -> list[str]:
    pts = ch.get("points") or []
    xs, ys = [p["x"] for p in pts], [p["y"] for p in pts]
    fx = lambda v: PAD + (W - 2 * PAD) * (v - min(xs)) / ((max(xs) - min(xs)) or 1)          # noqa: E731
    fy = lambda v: H - PAD - (H - 2 * PAD) * (v - min(ys)) / ((max(ys) - min(ys)) or 1)      # noqa: E731
    ctx = [p for p in pts if p.get("group") != "focus"][:40]
    foc = [p for p in pts if p.get("group") == "focus"][:12]
    return ([f'<circle cx="{fx(p["x"]):.0f}" cy="{fy(p["y"]):.0f}" r="10" class="f-seq3"/>' for p in ctx]
            + [f'<circle cx="{fx(p["x"]):.0f}" cy="{fy(p["y"]):.0f}" r="15" class="f-tarn"/>' for p in foc])


def _line(ch: dict) -> list[str]:
    out = []
    series = ch.get("series") or []
    vals = [v for s in series for v in s["values"] if v is not None]
    lo, hi = min(vals), max(vals)
    for s in series[:3][::-1]:
        v = s["values"]
        keep = [(i, q) for i, q in enumerate(v) if q is not None]
        step = max(1, len(keep) // 60)
        pts = " ".join(f"{PAD + (W - 2 * PAD) * i / max(1, len(v) - 1):.0f},{H - PAD - (H - 2 * PAD) * (q - lo) / ((hi - lo) or 1):.0f}"
                       for i, q in keep[::step])
        out.append(f'<polyline points="{pts}" fill="none" stroke-width="10" stroke-linejoin="round" stroke-linecap="round" '
                   f'class="{"s-tarn" if s.get("color") == "focus" else "s-seq3"}"/>')
    return out


def _table(ch: dict) -> list[str]:
    n = min(5, len((ch.get("table") or {}).get("rows") or []) or 4)
    step = (H - 2 * PAD) / n
    out = []
    for i in range(n):
        y = PAD + i * step + step * 0.2
        out.append(f'<rect x="{PAD}" y="{y:.0f}" width="150" height="{step * 0.5:.0f}" rx="4" class="f-seq4"/>')
        out.append(f'<rect x="{PAD + 170}" y="{y:.0f}" width="{W - 2 * PAD - 170}" height="{step * 0.5:.0f}" rx="4" class="{"f-tarn" if i == 0 else "f-seq2"}"/>')
    return out


DRAW = {"bars": _bars, "dumbbell": _dumbbell, "scatter": _scatter, "line": _line, "table": _table}


def make(run: Path, charts: dict, order: list[str]) -> dict:
    """cover/cover.svg and cover.json from the first placed figure. Returns the check's result."""
    ch = next((charts[c] for c in order if c in charts), None) or next(iter(charts.values()), None)
    if not ch:
        return {"ok": False, "blocking": ["no figure to echo"]}
    try:
        shapes = DRAW[ch["form"]](ch)
    except Exception as e:
        return {"ok": False, "blocking": [f"{type(e).__name__}: {e}"]}
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">\n  <rect x="0" y="0" width="{W}" height="{H}" class="f-frost"/>\n  '
           + "\n  ".join(shapes) + "\n</svg>\n")
    res = check_svg(svg)
    d = run / "cover"
    d.mkdir(exist_ok=True)
    if res["blocking"]:
        (d / "cover.svg").unlink(missing_ok=True)
        return {"ok": False, **res}
    (d / "cover.svg").write_text(svg, encoding="utf-8")
    kind = {"bars": "Bars of different lengths", "dumbbell": "Pairs of dots joined by lines", "scatter": "A cloud of dots, a few marked",
            "line": "A line across time", "table": "Rows of a table"}[ch["form"]]
    write_json(d / "cover.json", {"alt": {"en": f"{kind}: the shape of the note's first figure, without labels"},
                                  "idea": "data echo", "of": ch["id"], "made_by": "artools/desk/cover.py"})
    return {"ok": True, **res}
