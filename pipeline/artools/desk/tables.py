"""Tables: every API answer the note uses, in one shape, each a citable dataset of the run.

A table is rows of plain values with a key column, and the record of where it came from: the app, the view and its
parameters, the page it mirrors, the release, the period and the publishers behind it. Tables are written to
<run>/data/datasteg/ as CSV with a catalog.json entry in the pipeline's dataset format, so the publisher turns a
citation of a table into a numbered source with a link to the page, and counts the app in the article's draws_on.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from ..paths import read_json, write_json
from . import panel as panel_mod
from .api import Api, table_rows

ALLOWED = re.compile(r"^(money-flow|trade-flow|global-network|open-research)/[A-Za-z0-9_\-/.:]+$")
PUBLISHER_SHORT = {"Bank for International Settlements": "BIS", "International Monetary Fund": "IMF",
                   "United Nations Statistics Division": "UN Comtrade", "UN Statistics Division": "UN Comtrade",
                   "Korea Customs Service, via data.go.kr": "Korea Customs Service",
                   "Board of Governors of the Federal Reserve System": "Federal Reserve",
                   "Federal Reserve Board, via FRED (St. Louis Fed)": "Federal Reserve",
                   "European Central Bank": "ECB", "US Department of the Treasury": "US Treasury",
                   "datasteg trade-flow": None}        # an app is not a publisher: its sources are listed themselves
APP_VIA = {"money-flow": "money-flow", "trade-flow": "trade-flow", "global-network": "global-network",
           "open-research": "open-research"}
# publishers behind an app's views when an answer does not list them
APP_PUBLISHERS = {"money-flow": ["BIS", "IMF"], "trade-flow": ["UN Comtrade"], "global-network": ["BIS", "IMF", "UN Comtrade"],
                  "open-research": ["jejualps research archive"]}


def clean_url(u: str | None) -> str | None:
    if not u:
        return u
    s = urlsplit(u)
    q = "&".join(p for p in s.query.split("&") if p and not p.startswith("utm_"))
    return urlunsplit((s.scheme, s.netloc, s.path, q, s.fragment))


def publishers(sources: list[dict], app: str) -> list[str]:
    out = []
    for s in sources or []:
        p = PUBLISHER_SHORT.get(s.get("publisher"), s.get("publisher"))
        if p and p not in out:
            out.append(p)
    return out or list(APP_PUBLISHERS.get(app, []))


def _key_cols(cols: list[str], rows: list[dict]) -> list[str]:
    """The leading text columns that together identify a row (one for most views, three for a pair's channels)."""
    out = []
    for c in cols:
        vals = [r.get(c) for r in rows]
        if all(isinstance(v, str) or v is None for v in vals) and any(vals):
            out.append(c)
            if len({tuple(r.get(k) for k in out) for r in rows}) == len(rows):
                return out
        else:
            break
    return out[:1] or cols[:1]


def from_answer(name: str, path: str, params: dict, ans: dict, title: str | None = None) -> dict:
    t = ans.get("table") or {}
    cols = [c if isinstance(c, dict) else {"id": c} for c in t.get("columns", [])]
    ids = [c["id"] for c in cols]
    rows = table_rows(ans)
    if not rows:
        raise ValueError(f"{path}: the answer has no table rows")
    keys = _key_cols(ids, rows)
    for r in rows:
        r["_key"] = "/".join(str(r.get(k)) for k in keys)
    m = ans.get("meta") or {}
    app = path.split("/")[0]
    period = m.get("period") or {}
    return {"name": name, "app": app, "path": path, "params": params, "key": keys, "columns": cols, "rows": rows,
            "title": title or (m.get("summary") or path).split(":")[0].split(" (")[0][:110],
            "summary": m.get("summary"), "cite": clean_url(m.get("cite") or (ans.get("links") or {}).get("page")),
            "release": m.get("release"), "built": m.get("built"), "period": period,
            "sources": m.get("sources") or [], "publishers": publishers(m.get("sources") or [], app),
            "notes": m.get("notes") or []}


def pull(api: Api, name: str, path: str, params: dict | None = None) -> dict:
    path = path.strip("/").removeprefix("v1/")
    if not ALLOWED.match(path):
        raise ValueError(f"{path}: not a datasteg data view")
    params = {k: v for k, v in (params or {}).items() if k not in ("format", "lang", "release")}
    return from_answer(name, path, params, api.get(path, **params))


def from_panel(p: dict) -> dict:
    """The panel as a table (a datasteg desk calculation over the views it was joined from)."""
    cols = [{"id": "economy", "label": "Economy code"}, {"id": "name", "label": "Economy"},
            {"id": "region", "label": "Region"}, {"id": "advanced", "label": "Advanced economy"}]
    cols += [{"id": c, "label": v[0], "unit": v[1], "app": v[2], "view": v[3], "period": panel_mod.PERIOD.get(c)} for c, v in panel_mod.COLS.items()]
    cols += [{"id": c, "label": c.replace("_", " ")} for c in ("top_dest", "top_supplier", "top_export_chapter", "top_lender",
                                                               "top_dest_iso", "top_lender_iso", "chokepoint_worst")]
    # each row's periods (rule C2): the trade window joined at the funding quarter, the newest window, the lenders' quarter
    cols += [{"id": c, "label": c.replace("_", " ")} for c in ("goods_window_from", "goods_window_to", "goods_window_partial",
                                                               "goods_window_newest_to", "products_window_to", "lenders_quarter",
                                                               "chokepoint_year", "stress_trade_window_to")]
    rows = []
    for e, r in p["rows"].items():
        row = {c["id"]: r.get(c["id"]) for c in cols}
        row["_key"] = e
        rows.append(row)
    return {"name": "panel", "app": "desk", "path": None, "params": {}, "key": ["economy"], "columns": cols, "rows": rows,
            "title": f"Funding and trade side by side, {len(rows)} economies", "cite": None,
            "summary": "One row per Signal Board economy: money-flow's funding measures beside trade-flow's trade measures "
                       "(via global-network's country sheets), with the desk's own joins.",
            "release": None, "period": {"funding_quarter": p["quarter"], "stress_quarter": (p.get("quarters") or {}).get("stress") or p["quarter"]},
            "sources": [], "publishers": [],
            "inputs": ["board", "sovereign", "stress", "country"], "notes": []}


def panel_inputs(api: Api, p: dict) -> dict[str, dict]:
    """The four views the panel was joined from, as tables of their own, so a panel number is cited to the pages it
    came from: the board, the sovereign signals and the stress signals as the API gives them, and the country sheets
    as the columns the panel took from them."""
    out = {"board": pull(api, "board", "money-flow/board"),
           "sovereign": pull(api, "sovereign", "money-flow/sovereign"),
           "stress": pull(api, "stress", "global-network/stress")}
    out["board"]["title"] = "Signal Board: funding vulnerability and flows"
    out["sovereign"]["title"] = "Sovereign stress signals"
    out["stress"]["title"] = "Funding-and-trade stress signals"
    v = p["views"]["country"]
    cols = [{"id": "economy", "label": "Economy code"}, {"id": "name", "label": "Economy"}]
    cols += [{"id": c, "label": x[0], "unit": x[1]} for c, x in panel_mod.COLS.items() if x[3] == "country"]
    cols += [{"id": c, "label": c.replace("_", " ")} for c in ("top_dest", "top_supplier", "top_export_chapter", "top_lender")]
    rows = [{**{c["id"]: r.get(c["id"]) for c in cols}, "_key": e} for e, r in p["rows"].items()]
    out["country"] = {"name": "country", "app": "global-network", "path": "global-network/countries/{iso3}", "params": {},
                      "key": ["economy"], "columns": cols, "rows": rows, "title": "Country sheets: funding and goods trade by economy",
                      "summary": "Each economy's goods trade over the latest 12 months (UN Comtrade via trade-flow) and its bank "
                                 "lenders (BIS LBS via money-flow), from global-network's country sheets.",
                      "cite": clean_url(v.get("cite")), "release": v.get("release"), "built": v.get("built"),
                      "period": v.get("period") or {}, "sources": v.get("sources") or [],
                      "publishers": publishers(v.get("sources") or [], "global-network"), "notes": []}
    return out


# ------------------------------------------------------------------ the run's datasets

def dataset_id(name: str) -> str:
    return "ds-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _period_text(t: dict) -> tuple[str | None, list]:
    p = t.get("period") or {}
    shown = p.get("shown") or p.get("funding_quarter")
    lo = p.get("from")
    if isinstance(p.get("goods_window"), dict) and not lo:
        lo = None
    return p.get("freq"), [lo, shown]


def write_datasets(run: Path, tables: dict[str, dict]) -> list[dict]:
    """data/datasteg/<name>.csv and catalog.json. Returns the catalog."""
    d = run / "data" / "datasteg"
    d.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cat = []
    for name, t in tables.items():
        did = dataset_id(name)
        cols = [c["id"] for c in t["columns"]]
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(cols)
        for r in t["rows"]:
            w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
        f = d / f"{did}.csv"
        f.write_text(buf.getvalue(), encoding="utf-8")
        freq, span = _period_text(t)
        derived = t["app"] == "desk"
        pubs = t.get("publishers") or []
        via = f"datasteg {t['app']}"
        rec = {
            "id": did,
            "indicator": t["title"],
            "title": t["title"],
            "provider": "datasteg calculation" if derived else (f"{', '.join(pubs)} via {via}" if pubs else via),
            "source": "datasteg",
            "key": "desk join of " + ", ".join(t.get("inputs", [])) if derived
                   else "api.datasteg.com/v1/" + t["path"] + ("?" + "&".join(f"{k}={v}" for k, v in t["params"].items()) if t["params"] else ""),
            "url": t.get("cite"),
            "definition": t.get("summary"),
            "geo": None, "unit": "see columns", "frequency": freq, "span": span,
            "retrieved": now, "release": t.get("release"),
            "sha256": hashlib.sha256(buf.getvalue().encode()).hexdigest(),
            "licence": "derived views of open statistics; each publisher's terms apply",
            "attribution": ("Source: " + ", ".join(pubs) + f", via {via}" + (f" (release {t['release']})" if t.get("release") else "")
                            + "; datasteg calculation") if not derived else "datasteg calculation",
            "publishers": pubs, "app": t["app"],
            "publishable": True,
            "file": f"data/datasteg/{did}.csv",
            "validation": {"verdict": "pass", "checks": [{"check": "api answer", "status": "pass",
                                                          "detail": f"release {t.get('release')}, period {t.get('period')}"}]},
        }
        if derived:
            rec["inputs"] = [dataset_id(i) for i in t.get("inputs", [])]
        cat.append(rec)
    write_json(d / "catalog.json", cat)
    return cat


def csv_text(t: dict, cols: list[str] | None = None, max_rows: int = 60) -> str:
    """A table as compact CSV for a model's packet."""
    ids = [c["id"] for c in t["columns"] if cols is None or c["id"] in cols]
    rows = t["rows"]
    if len(rows) > max_rows:           # a long history: keep the ends and thin the middle
        step = max(1, (len(rows) - 16) // (max_rows - 16))
        rows = rows[:4] + rows[4:-12:step] + rows[-12:]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["_key"] + ids)
    for r in rows:
        w.writerow([r["_key"]] + ["" if r.get(c) is None else r.get(c) for c in ids])
    return buf.getvalue()


def describe(t: dict) -> str:
    """What a table is, for a model: name, source, period, columns with units."""
    cols = "; ".join(f"{c['id']} = {c.get('label', c['id'])}" + (f" [{c['unit']}]" if c.get("unit") else "")
                     + (f" ({c['app']})" if c.get("app") else "") for c in t["columns"])
    src = ", ".join(t.get("publishers") or []) or "desk calculation"
    return (f"TABLE {t['name']} — {t['title']}\n  from: {t['app']}" + (f" /{t['path']}" if t.get("path") else "")
            + f" · publishers: {src} · release: {t.get('release')} · period: {t.get('period')}\n"
            + (f"  what: {t['summary']}\n" if t.get("summary") else "")
            + f"  key column(s): {', '.join(t['key'])} · {len(t['rows'])} rows\n  columns: {cols}")


def save(run: Path, tables: dict[str, dict]) -> None:
    write_json(run / "analysis" / "tables.json", tables)


def load(run: Path) -> dict[str, dict]:
    return read_json(run / "analysis" / "tables.json", {}) or {}
