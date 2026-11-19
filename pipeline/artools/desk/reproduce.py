"""Get the data: the section at the end of a data note that tells a reader where each table came from and how to
fetch it again, built by code from the run's datasets, never written by a model.

Each item is one datasteg view the note read: its page on the app (to explore it) and the api.datasteg.com call that
returns the same table. The `code` block is a few `curl` lines a reader can paste. money-flow keeps dated releases,
so its lines ask for the release the note used; trade-flow and global-network answer with their latest build, so
their lines name the period instead. Words (heading, intro, note, labels) are English here and go to qkr for the
Korean edition like every other string (desk/korean.py); URLs and code are copied unchanged into both editions.
"""
from __future__ import annotations

import re
from urllib.parse import urlencode

from ..content import CITE, TOKEN
from .api import BASE
from .tables import dataset_id

APP_ORDER = ("money-flow", "trade-flow", "global-network", "open-research")
PINNED = {"money-flow"}          # apps whose API keeps dated releases (GET /v1/<app>/releases)
DOCS = "https://www.datasteg.com/en/technology/api"
MAX_ITEMS, MAX_CALLS = 8, 4

HEADING = "Get the data"
INTRO = ("Every number in this note was read from datasteg's public pages and its free API. Open a page to explore the "
         "data, or run the lines below to fetch the same tables as CSV. Each answer names its release, its period and "
         "the statistics it comes from.")
NOTE_PINNED = "The money-flow lines ask for the release this note used; the other apps answer with their latest data."
NOTE_LATEST = "The apps answer with their latest data, so a later release may differ from the figures here."


def _used(draft: dict, facts: list[dict], charts: dict) -> list[str]:
    """Dataset ids the note rests on: cited in the text, behind a fact it uses, or drawn in a chart."""
    fmap = {f["id"]: f for f in facts}
    blob = str(draft)
    ids = [c.strip() for m in CITE.finditer(blob) for c in m.group(1).split(",")]
    ids += [c for k in draft.get("keyNumbers") or [] for c in k.get("cite") or []]
    ids += [i for m in TOKEN.finditer(blob) if m.group(1) in fmap for i in fmap[m.group(1)].get("inputs") or []]
    ids += [s for ch in charts.values() for s in (ch.get("meta") or {}).get("sources") or []]
    return list(dict.fromkeys(ids))


def _base(ids: list[str], catalog: list[dict]) -> list[dict]:
    """The views behind the ids: a desk join (the panel) stands for the views it was joined from."""
    cmap = {d["id"]: d for d in catalog}
    out = {}

    def add(did, depth=0):
        d = cmap.get(did) or cmap.get(dataset_id(did))
        if not d:
            return
        if d.get("inputs") and depth < 4:
            for i in d["inputs"]:
                add(i, depth + 1)
        elif d.get("app") in APP_ORDER:
            out[d["id"]] = d
    for i in ids:
        add(i)
    return list(out.values())


def _page(url: str | None, path: str, economy: str | None) -> str | None:
    if not url:
        return None
    if economy and path.startswith("global-network/countries/") and re.fullmatch(r"https://global-network\.datasteg\.com/en/?", url):
        return f"https://global-network.datasteg.com/en/c/{economy}"
    return url


def build(draft: dict, facts: list[dict], charts: dict, catalog: list[dict], tables: dict, brief: dict) -> dict | None:
    by_id = {dataset_id(n): t for n, t in tables.items()}
    names = {r["_key"]: r.get("name") for r in (tables.get("panel") or {}).get("rows") or []}
    focus = [e for e in (brief.get("focus") or brief.get("economies") or []) if isinstance(e, str) and len(e) == 3]
    items, calls = [], []
    views = _base(_used(draft, facts, charts), catalog)
    views.sort(key=lambda d: (APP_ORDER.index(d["app"]), 0 if (by_id.get(d["id"]) or {}).get("params") else 1, d["id"]))
    for d in views[:MAX_ITEMS]:
        t = by_id.get(d["id"]) or {}
        path = t.get("path") or ""
        if not path:
            continue
        economy = focus[0] if "{iso3}" in path and focus else None
        path = path.replace("{iso3}", economy) if economy else path
        if "{" in path:
            continue
        params = dict(t.get("params") or {})
        if d["app"] in PINNED and d.get("release"):
            params["release"] = d["release"]
        api = f"{BASE}/v1/{path}" + (f"?{urlencode(params)}" if params else "")
        # name the economy a view is about when its title does not (a bank view for one debtor, a country sheet)
        who = [names.get(v) or v for v in ([economy] if economy else []) + [v for k, v in params.items() if k in ("debtor", "economy")]
               if isinstance(v, str) and re.fullmatch(r"[A-Z]{3}", v)]
        who = [w for w in dict.fromkeys(who) if w and w not in d["title"]]
        label = d["title"] + (f" ({', '.join(who)})" if who else "")
        file = (re.sub(r"[^a-z0-9]+", "-", d["id"].removeprefix("ds-")).strip("-") or "data") + (f"-{economy.lower()}" if economy and economy.lower() not in d["id"] else "")
        items.append({"label": label, "app": d["app"], "page": _page(d.get("url"), path, economy), "api": api,
                      "release": d.get("release"), "_file": file})
    # the copy-and-paste lines: one view from each app in turn, so the block shows how each side is fetched
    queue = {a: [i for i in items if i["app"] == a] for a in APP_ORDER}
    while len(calls) < MAX_CALLS and any(queue.values()):
        for a in APP_ORDER:
            if queue[a] and len(calls) < MAX_CALLS:
                i = queue[a].pop(0)
                calls.append(f'curl -s "{i["api"]}{"&" if "?" in i["api"] else "?"}format=csv" -o {i["_file"]}.csv')
    for i in items:
        i.pop("_file")
    if not items:
        return None
    pinned = any(i["app"] in PINNED for i in items)
    return {"heading": HEADING, "intro": INTRO, "note": NOTE_PINNED if pinned and any(i["app"] not in PINNED for i in items)
            else None if pinned else NOTE_LATEST,
            "items": items, "code": "\n".join(calls), "docs": DOCS}


DOWNLOAD = "All the tables, chart data and numbers behind this note, as CSV files in one ZIP"
ZIP = "data.zip"
_CSV_SAFE = re.compile(r"[^a-z0-9]+")


def _csv(rows: list[list]) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue()


def bundle(run, draft: dict, facts: list[dict], charts: dict, catalog: list[dict], tables: dict, rep: dict | None) -> dict | None:
    """<run>/download/data.zip: what a reader needs to check the note without calling the API. Every table the note
    read (as the run fetched it), each chart's own data, and every number in the text with its formula and inputs,
    plus a README naming the sources, releases and licences. Built by code from the run's files, so it holds the
    values the note was written from, not a later release. The archive is the same for the same inputs (fixed dates)."""
    import datetime as dt
    import zipfile
    from pathlib import Path
    from ..content import render_tokens
    from .text import _plain, _tx
    run = Path(run)
    fmap = {f["id"]: f for f in facts}
    used_facts = [fmap[m.group(1)] for m in TOKEN.finditer(str(draft)) if m.group(1) in fmap]
    used_facts = list({f["id"]: f for f in used_facts}.values())
    ids = set(_used(draft, facts, charts)) | {dataset_id(n) for f in used_facts for n in f.get("tables") or []}
    ids |= {d["id"] for d in _base(list(ids), catalog)}
    cmap = {d["id"]: d for d in catalog}
    files: dict[str, str] = {}
    listed = []
    for did in sorted(ids, key=lambda i: (i != "ds-panel", i)):
        d = cmap.get(did)
        src = run / "data" / "datasteg" / f"{did}.csv"
        if not d or not src.is_file():
            continue
        name = f"tables/{did.removeprefix('ds-')}.csv"
        files[name] = src.read_text(encoding="utf-8")
        listed.append((name, d))
    for cid, ch in sorted(charts.items()):
        t = ch.get("table") or {}
        cols = t.get("columns") or []
        if not cols:
            continue
        files[f"charts/{cid}.csv"] = _csv([[_tx(c.get("label")) or c["key"] for c in cols]]
                                          + [[_tx(r.get(c["key"])) if isinstance(r.get(c["key"]), dict) else r.get(c["key"]) for c in cols]
                                             for r in t.get("rows") or []])
    files["numbers.csv"] = _csv([["id", "as_printed", "value", "unit", "period", "what", "formula", "tables", "sources"]]
                                + [[f["id"], render_tokens("{{" + f["id"] + "}}", fmap, "en"), f.get("value"), f.get("unit"),
                                    f.get("period"), f.get("label"), f.get("formula"), " ".join(f.get("tables") or []),
                                    " ".join(f.get("inputs") or [])] for f in sorted(used_facts, key=lambda f: int(f["id"][1:]) if f["id"][1:].isdigit() else 0)])
    if len(files) < 2:
        return None
    title = _plain(draft.get("title") or "", fmap)
    wd = max([len(n) for n, _ in listed] + [len("charts/*.csv")]) + 2
    lines = [title, "=" * min(len(title), 100), "",
             "The data behind this datasteg data note, as the desk read them when it wrote the note.", "",
             f"{'numbers.csv':<{wd}}every number in the text: the figure as printed, its unrounded value, its period,",
             f"{'':<{wd}}what it measures, and the formula that computed it from the tables (cell, ratio, rank, median ...)",
             f"{'charts/*.csv':<{wd}}the values each chart draws, one file per chart"]
    lines += [f"{n:<{wd}}{d['title']}" for n, d in listed]
    lines += ["", "tables/panel.csv is the desk's join of the funding and trade views: one row per economy.", "", "Sources", "-------"]
    seen = set()
    for _, d in listed:
        for x in ([cmap[i] for i in d.get("inputs") or [] if i in cmap] if d.get("inputs") else [d]):
            if x["id"] in seen:
                continue
            seen.add(x["id"])
            lines += [f"- {x['provider']}: {x['title']}", f"  {x.get('key')}" + (f"  (release {x['release']})" if x.get("release") else ""),
                      f"  retrieved {str(x.get('retrieved'))[:10]}; {x.get('licence')}"]
    if rep and rep.get("code"):
        lines += ["", "Fetch the latest data again", "--------------------------", rep["code"]]
    lines += ["", f"API documentation: {DOCS}",
              "Each publisher's terms apply to its statistics (BIS, IMF, UN Comtrade); cite them with datasteg as the source of the calculation."]
    files["README.txt"] = "\n".join(lines) + "\n"
    out = run / "download" / ZIP
    out.parent.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().timetuple()[:3] + (0, 0, 0)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ["README.txt", "numbers.csv"] + sorted(k for k in files if k not in ("README.txt", "numbers.csv")):
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, files[name])
    return {"label": DOWNLOAD, "file": ZIP, "files": len(files), "bytes": out.stat().st_size}


def localise(rep: dict | None, lang: str) -> dict | None:
    """Page and docs links in the edition's language (the apps serve /en/ and /ko/); the API calls stay as they are."""
    if not rep or lang == "en":
        return rep
    sw = lambda u: re.sub(r"^(https://[a-z-]+\.datasteg\.com)/en(/|$)", rf"\1/{lang}\2", u) if isinstance(u, str) else u  # noqa: E731
    return {**rep, "docs": sw(rep.get("docs")), "items": [{**i, "page": sw(i.get("page"))} for i in rep.get("items") or []]}
