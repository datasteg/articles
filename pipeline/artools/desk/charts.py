"""Charts: a writer's figure request turned into a chart file, with every value read from the run's tables.

The writer says what to draw (the table, the rows, the columns, the form) and writes the words (headline, title,
how to read it, notes, alt text). This module reads the values, picks the axis range and ticks, builds the table view
every chart carries, and fills the source line from the tables' publishers. A request that names a row or a column
the table does not have is refused with the reason, so the writer can correct it; nothing is drawn from typed values.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from ..content import TOKEN, render_tokens
from ..paths import write_json
from .facts import FactError, _cond
from .tables import dataset_id

FORMS = ("bars", "dumbbell", "scatter", "line", "table")
# a table is a small summary beside the charts, never a data dump: the chart's own table view holds every row
MAX_ROWS = {"bars": 16, "dumbbell": 14, "scatter": 40, "table": 6}
MAX_TABLE_COLS = 4


class ChartError(ValueError):
    pass


# the apps' column labels lead with their internal codes ("J5 Dual dependence", "A2 on gross reserves"); readers
# do not know them, so a chart never shows one
_CODE = re.compile(r"^(?:[ABGJRV]\d{1,2}|[VF])\b\s*[:–-]?\s*")


def plain(label: str) -> str:
    out = _CODE.sub("", str(label or "")).strip()
    out = re.sub(r"\s*\((?:money-flow|trade-flow|global-network)\)$", "", out)
    return (out[:1].upper() + out[1:]) if out else str(label or "")


def _nice(lo: float, hi: float, count: int = 4) -> list[float]:
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    err = raw / mag
    step = (10 if err >= 7.5 else 5 if err >= 3.5 else 2 if err >= 1.5 else 1) * mag
    a, b = math.floor(lo / step) * step, math.ceil(hi / step) * step
    out, v = [], a
    while v <= b + step / 2:
        out.append(round(v, 10))
        v += step
    return [int(x) if float(x).is_integer() else x for x in out]


def _axis(values: list[float], label: str, unit: str | None, zero: bool) -> dict:
    lo, hi = min(values), max(values)
    if zero:
        lo, hi = min(lo, 0), max(hi, 0)
    ticks = _nice(lo, hi)
    span = ticks[-1] - ticks[0]
    dec = 0 if span >= 20 else 1 if span >= 2 else 2
    return {"label": {"en": label}, "unit": unit or "", "domain": [ticks[0], ticks[-1]], "ticks": ticks, "format": {"decimals": dec}}


def _col(t: dict, cid: str) -> dict:
    for c in t["columns"]:
        if c["id"] == cid:
            return c
    raise ChartError(f"table {t['name']} has no column {cid!r}; columns: {[c['id'] for c in t['columns']][:40]}")


def _unit(c: dict) -> str:
    u = (c.get("unit") or "").strip()
    return {"score": "", "index": "", "count": "", "ratio": ""}.get(u, u)


def _pick(t: dict, spec: dict, need: list[str], form: str) -> list[dict]:
    """The rows a figure draws: listed keys in the listed order, or a filter with a sort and a limit."""
    rows = t["rows"]
    sel = spec.get("rows")
    if isinstance(sel, list) and sel:
        by = {r["_key"]: r for r in rows}
        missing = [k for k in sel if k not in by]
        if missing:
            raise ChartError(f"table {t['name']} has no rows {missing}; keys look like {[r['_key'] for r in rows[:6]]}")
        out = [by[k] for k in sel]
    else:
        sel = sel if isinstance(sel, dict) else {}
        try:
            test = _cond(sel.get("where"))
            out = [r for r in rows if test(r)]
        except FactError as e:
            raise ChartError(str(e)) from e
        sort = sel.get("sort") or (need[0] if need else None)
        if sort:
            _col(t, sort)
            out = [r for r in out if isinstance(r.get(sort), (int, float))]
            out.sort(key=lambda r: r[sort], reverse=sel.get("order", "desc") != "asc")
        if sel.get("limit"):
            out = out[: int(sel["limit"])]
    out = [r for r in out if all(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool) for c in need)]
    if len(out) < 2:
        raise ChartError(f"figure {spec.get('id')}: fewer than two rows have values for {need}")
    if form in MAX_ROWS and len(out) > MAX_ROWS[form]:
        raise ChartError(f"figure {spec.get('id')}: {len(out)} rows; a {form} chart takes at most {MAX_ROWS[form]} (set rows.limit or list the keys)")
    return out


def _label(r: dict, spec: dict) -> str:
    return str(r.get(spec.get("label") or "name") or r["_key"])


def _text(spec: dict, key: str, facts: dict, required: bool = True) -> dict | None:
    v = spec.get(key)
    if not v or not str(v).strip():
        if required:
            raise ChartError(f"figure {spec.get('id')}: {key} is missing")
        return None
    return {"en": render_tokens(str(v).strip(), facts, "en")}


def _period_of(t: dict) -> str | None:
    p = t.get("period") or {}
    w = p.get("goods_window") if isinstance(p.get("goods_window"), dict) else None
    return p.get("shown") or p.get("funding_quarter") or (w or {}).get("to")


def build(spec: dict, tables: dict[str, dict], facts: dict[str, dict], catalog: dict[str, dict]) -> dict:
    """One chart file (contracts/content.md § charts) from a figure request."""
    cid = str(spec.get("id") or "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", cid):
        raise ChartError(f"figure id {cid!r}: lower-case letters, digits and hyphens")
    form = spec.get("form")
    if form not in FORMS:
        raise ChartError(f"figure {cid}: form {form!r}; one of {FORMS}")
    if spec.get("table") not in tables:
        raise ChartError(f"figure {cid}: no table {spec.get('table')!r}; tables: {sorted(tables)}")
    t = tables[spec["table"]]
    hl = set(spec.get("highlight") or [])
    ch = {"id": cid, "form": form, "headline": _text(spec, "headline", facts), "title": _text(spec, "title", facts),
          "subtitle": _text(spec, "subtitle", facts), "alt": _text(spec, "alt", facts),
          "howToRead": _text(spec, "howToRead", facts, required=form in ("dumbbell", "scatter")),
          "notes": [{"en": render_tokens(str(n), facts, "en")} for n in spec.get("notes") or [] if str(n).strip()]}
    cols: list[str] = []
    if form == "bars":
        v = spec.get("value")
        c = _col(t, v)
        rows = _pick(t, spec, [v], form)
        ch["axes"] = {"x": _axis([r[v] for r in rows], spec.get("axis_label") or c.get("label", v), _unit(c), zero=True)}
        ch["categories"] = [{"id": r["_key"], "label": {"en": _label(r, spec)}, "value": r[v], "highlight": r["_key"] in hl} for r in rows]
        ch["valueFormat"] = {"decimals": ch["axes"]["x"]["format"]["decimals"] + (1 if ch["axes"]["x"]["format"]["decimals"] < 2 else 0),
                             "suffix": "%" if _unit(c).startswith("%") else ""}
        ref = spec.get("reference")     # a line at a computed fact, such as the board's median
        if isinstance(ref, dict) and ref.get("fact") in facts and isinstance(facts[ref["fact"]]["value"], (int, float)):
            f = facts[ref["fact"]]
            ch["referenceLines"] = [{"axis": "x", "value": f["value"], "label": {"en": str(ref.get("label") or f["label"])}}]
        cols = [v]
    elif form == "dumbbell":
        a, b = spec.get("from"), spec.get("to")
        ca, cb = _col(t, a), _col(t, b)
        rows = _pick(t, {**spec, "rows": spec.get("rows") or {"sort": b}}, [a, b], form)
        ch["axes"] = {"x": _axis([r[a] for r in rows] + [r[b] for r in rows], spec.get("axis_label") or cb.get("label", b), _unit(cb), zero=False)}
        ch["rows"] = [{"id": r["_key"], "label": {"en": _label(r, spec)}, "from": r[a], "to": r[b], "highlight": r["_key"] in hl} for r in rows]
        ch["fromLabel"] = {"en": str(spec.get("fromLabel") or plain(ca.get("label", a)))}
        ch["toLabel"] = {"en": str(spec.get("toLabel") or plain(cb.get("label", b)))}
        cols = [a, b]
    elif form == "scatter":
        x, y = spec.get("x"), spec.get("y")
        cx, cy = _col(t, x), _col(t, y)
        rows = _pick(t, {**spec, "rows": spec.get("rows") or {"sort": x}}, [x, y], form)
        ch["axes"] = {"x": _axis([r[x] for r in rows], spec.get("x_label") or cx.get("label", x), _unit(cx), zero=False),
                      "y": _axis([r[y] for r in rows], spec.get("y_label") or cy.get("label", y), _unit(cy), zero=False)}
        # a crowded scatter names only the points in focus and the outliers; the table view names every row
        named = {r["_key"] for r in rows}
        if len(rows) > 16:
            mx, my = sorted(r[x] for r in rows)[len(rows) // 2], sorted(r[y] for r in rows)[len(rows) // 2]
            sx, sy = (max(r[x] for r in rows) - min(r[x] for r in rows)) or 1, (max(r[y] for r in rows) - min(r[y] for r in rows)) or 1
            far = sorted(rows, key=lambda r: -(((r[x] - mx) / sx) ** 2 + ((r[y] - my) / sy) ** 2))[:6]
            named = hl | {r["_key"] for r in far}
        ch["points"] = [{"id": r["_key"], "label": {"en": _label(r, spec) if r["_key"] in named else ""}, "x": r[x], "y": r[y],
                         "group": "focus" if r["_key"] in hl else "context"} for r in rows]
        cols = [x, y]
    elif form == "line":
        x = spec.get("x") or t["key"][0]
        _col(t, x)
        series = spec.get("series") or []
        if not 1 <= len(series) <= 4:
            raise ChartError(f"figure {cid}: a line chart takes one to four series")
        rows = [r for r in t["rows"] if r.get(x)]
        if spec.get("since"):
            rows = [r for r in rows if str(r[x]) >= str(spec["since"])]
        if len(rows) < 6:
            raise ChartError(f"figure {cid}: fewer than six periods in table {t['name']}")
        xs = [str(r[x])[:7] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r[x])) else str(r[x]) for r in rows]
        vals = []
        ch["series"] = []
        for i, s in enumerate(series):
            c = _col(t, s.get("col"))
            v = [r.get(s["col"]) if isinstance(r.get(s["col"]), (int, float)) else None for r in rows]
            if sum(1 for q in v if q is not None) < 4:
                raise ChartError(f"figure {cid}: series {s['col']} has fewer than four values")
            vals += [q for q in v if q is not None]
            ch["series"].append({"id": s["col"], "label": {"en": str(s.get("label") or plain(c.get("label", s["col"])))}, "values": v,
                                 "color": "focus" if s.get("focus") or len(series) == 1 else ("context" if len(series) == 2 else i + 1),
                                 "endLabel": True})
            cols.append(s["col"])
        c0 = _col(t, series[0]["col"])
        years = sorted({k[:4] for k in xs})
        stepy = max(1, round(len(years) / 6))
        ch["axes"] = {"x": {"type": "time", "label": {"en": spec.get("x_label") or "Period"}, "format": "year",
                            "ticks": [next(k for k in xs if k.startswith(y)) for y in years[::stepy]]},
                      "y": _axis(vals, spec.get("y_label") or spec.get("axis_label") or c0.get("label", series[0]["col"]), _unit(c0), zero=False)}
        ch["x"] = xs
    else:   # table
        cols = [c for c in spec.get("columns") or [] if c != (spec.get("label") or "name")]
        if not 1 <= len(cols) <= MAX_TABLE_COLS:
            raise ChartError(f"figure {cid}: a table takes one to {MAX_TABLE_COLS} value columns; draw a comparison of more as a chart")
        for c in cols:
            _col(t, c)
        rows = _pick(t, {**spec, "rows": spec.get("rows") or {"sort": cols[0]}}, [], form)
    # the table view: the same rows as the picture, so every value is readable without it. Its headers are the
    # writer's own names for what is drawn (series, the two ends of a dumbbell, the axis), else the column's label
    # without the app's code
    label_col = spec.get("label") or "name"
    named = {s.get("col"): s.get("label") for s in spec.get("series") or [] if isinstance(s, dict)} if form == "line" else \
        {spec.get("from"): spec.get("fromLabel"), spec.get("to"): spec.get("toLabel")} if form == "dumbbell" else \
        {spec.get("x"): spec.get("x_label"), spec.get("y"): spec.get("y_label")} if form == "scatter" else \
        {spec.get("value"): spec.get("axis_label")} if form == "bars" else {}
    tcols = [{"key": "label", "label": {"en": str(spec.get("row_label") or ("Period" if form == "line" else "Economy"))}}]
    for c in cols:
        meta = _col(t, c)
        head = str(named.get(c) or plain(meta.get("label", c)))
        tcols.append({"key": c, "label": {"en": head}, "align": "right" if any(isinstance(r.get(c), (int, float)) for r in rows) else "left"})
    trows = []
    for i, r in enumerate(rows):
        row = {"label": (ch["x"][i] if form == "line" else str(r.get(label_col) or r["_key"]))}
        row.update({c: r.get(c) for c in cols})
        trows.append(row)
    ch["table"] = {"columns": tcols, "rows": trows}
    did = dataset_id(t["name"])
    if did not in catalog:
        raise ChartError(f"figure {cid}: table {t['name']} is not a dataset of this run")
    d = catalog[did]
    # a figure drawn from the panel is cited to the views its columns came from, not to the whole join
    from .panel import views_of
    used = [dataset_id(v) for v in views_of(cols)] if t["name"] == "panel" else [did]
    used = [u for u in used if u in catalog] or [did]
    pubs = list(dict.fromkeys(p for u in used for p in (catalog[u].get("publishers") or [])))
    d = {**d, "app": None, "inputs": used} if t["name"] == "panel" else d
    ch["meta"] = {"sources": used, "provider": d["provider"], "keys": [d["key"]],
                  "definition": {"en": "; ".join(plain(_col(t, c).get("label", c)) for c in cols)},
                  "lastObservation": _period_of(t) or (trows[-1]["label"] if form == "line" else None),
                  "retrieved": (d.get("retrieved") or "")[:10], "licence": d.get("licence"),
                  "attribution": {"en": (", ".join(pubs) + " via datasteg " + _apps(d, catalog) + "; datasteg calculation") if pubs else "datasteg calculation"}}
    return {k: v for k, v in ch.items() if v is not None}


def _apps(d: dict, catalog: dict) -> str:
    apps = [d.get("app")] if d.get("app") not in (None, "desk") else [(catalog.get(i) or {}).get("app") for i in d.get("inputs", [])]
    return ", ".join(dict.fromkeys(a for a in apps if a and a != "desk")) or "apps"


def typed_numbers(spec: dict, allow: list) -> list[str]:
    """Digits a figure's words type by hand (outside fact tokens, years, dates and quarters): each is a problem."""
    out = []
    for k in ("headline", "title", "subtitle", "howToRead", "alt", "axis_label", "x_label", "y_label", "fromLabel", "toLabel"):
        texts = [spec.get(k)] if isinstance(spec.get(k), str) else []
        for text in texts + ([n for n in spec.get("notes") or [] if isinstance(n, str)] if k == "headline" else []):
            bare = TOKEN.sub(" ", text)
            for a in allow:
                bare = a.sub(" ", bare)
            out += [f"figure {spec.get('id')}.{k}: typed number '{m.group(0)}' — use a fact token" for m in re.finditer(r"\d[\d,.]*", bare)]
    return out


def write(run: Path, charts: list[dict]) -> None:
    d = run / "charts"
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.json"):
        old.unlink()
    for ch in charts:
        write_json(d / f"{ch['id']}.json", ch)
