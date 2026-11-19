"""Watch: what changed in the apps since the desk last looked.

Each app says in its own way that it has new data:
- money-flow cuts a dated release when a published file changed (daily 07:30 KST); its manifest lists every source
  dataset with the vintage it was read at and the newest period it holds, so the watch can tell "BIS LBS has a new
  quarter" from "a weekly series moved";
- trade-flow has no release log: its version and the newest month its windows reach are compared;
- global-network follows its two parents; its version is compared;
- open-research receives documents every night: the newest received date and the month's count are compared.
The state is /data/articles/desk/state.json, written only after a desk run finished, so a failed morning looks again.
"""
from __future__ import annotations

import datetime as dt

from ..paths import read_json, write_json
from .api import DESK, Api

STATE = DESK / "state.json"
# which panel views a money-flow source dataset feeds (config/method.yaml of money-flow, coarse on purpose)
FEEDS = {"bis.LBS": ["board", "country"], "bis.CBS": ["board"], "bis.DSS": ["board"], "bis.TC": ["board"], "bis.GLI": ["board"],
         "imf.IRFCL": ["board", "stress"], "imf.IIP": ["board"], "imf.BOP": ["board", "stress"], "imf.WEO": ["sovereign"],
         "imf.PIP": ["pairs"], "imf.DIP": ["pairs"], "oecd.LTY": ["sovereign"]}


def snapshot(api: Api) -> dict:
    """What the apps show now, in the terms the watch compares."""
    h = api.health(refresh=True)
    snap = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "apps": {a: (h.get(a) or {}).get("release") for a in ("money-flow", "trade-flow", "global-network", "open-research", "articles")},
            "datasets": {}, "periods": {}, "research": {}}
    try:
        rel = api.get(f"money-flow/releases/{snap['apps']['money-flow']}")
        for d in rel["data"].get("datasets", []):
            snap["datasets"][d["dataset"]] = {"vintage": d.get("vintage"), "newest": d.get("newest"), "name": d.get("name"),
                                              "publisher": d.get("publisher"), "freq": d.get("freq")}
    except Exception as e:   # a missing manifest must not stop the desk: the release tag alone still tells "new data"
        snap["datasets_error"] = str(e)[:200]
    try:
        snap["periods"]["board_quarter"] = (api.get("money-flow/board")["meta"].get("period") or {}).get("shown")
        p = api.get("trade-flow/economies/KOR")["meta"].get("period") or {}
        snap["periods"].update(trade_window_to=p.get("shown"), trade_newest_month=p.get("newest"), trade_complete_year=p.get("complete_a"))
    except Exception as e:
        snap["periods_error"] = str(e)[:200]
    try:
        new = api.get("open-research/new", max_age_h=6, limit=50)["data"]
        docs = new.get("documents") or []
        snap["research"] = {"end": new.get("end"), "received_in_window": new.get("received_in_window"),
                            "latest": [{"title": d.get("title"), "kind": d.get("kind"), "date": d.get("date"),
                                        "series": d.get("series"), "topic": (d.get("topic") or {}).get("label"),
                                        "url": d.get("url"), "page": d.get("page")} for d in docs[:50]]}
    except Exception as e:
        snap["research_error"] = str(e)[:200]
    return snap


def changes(now: dict, before: dict | None) -> list[dict]:
    """What is new since the state: [{app, kind, what, views}], newest data first. With no state everything is new."""
    out = []
    before = before or {}
    for ds, d in (now.get("datasets") or {}).items():
        old = (before.get("datasets") or {}).get(ds)
        if old is None and before.get("datasets"):
            out.append({"app": "money-flow", "kind": "dataset", "dataset": ds, "views": FEEDS.get(ds, []),
                        "what": f"{d.get('name') or ds} is new in money-flow (newest {d.get('newest')})"})
        elif old and old.get("newest") != d.get("newest"):
            out.append({"app": "money-flow", "kind": "period", "dataset": ds, "views": FEEDS.get(ds, []),
                        "what": f"{d.get('name') or ds} ({d.get('publisher')}): newest period {old.get('newest')} → {d.get('newest')}"})
        elif old and old.get("vintage") != d.get("vintage"):
            out.append({"app": "money-flow", "kind": "vintage", "dataset": ds, "views": FEEDS.get(ds, []),
                        "what": f"{d.get('name') or ds} ({d.get('publisher')}): re-read at vintage {d.get('vintage')} (was {old.get('vintage')}), newest {d.get('newest')}"})
    for k, label in (("board_quarter", "money-flow's Signal Board quarter"), ("trade_window_to", "trade-flow's latest 12-month window"),
                     ("trade_newest_month", "trade-flow's newest month"), ("trade_complete_year", "trade-flow's last complete year")):
        a, b = (before.get("periods") or {}).get(k), (now.get("periods") or {}).get(k)
        if b and a != b:
            out.append({"app": "money-flow" if k == "board_quarter" else "trade-flow", "kind": "period",
                        "views": ["board", "stress"] if k == "board_quarter" else ["country", "stress"],
                        "what": f"{label}: {a or 'not seen before'} → {b}"})
    for app in ("money-flow", "trade-flow", "global-network"):
        a, b = (before.get("apps") or {}).get(app), (now.get("apps") or {}).get(app)
        if b and a != b:
            out.append({"app": app, "kind": "release", "views": [], "what": f"{app} release {a or 'not seen before'} → {b}"})
    a, b = (before.get("research") or {}).get("end"), (now.get("research") or {}).get("end")
    if b and a != b:
        seen = {d.get("url") for d in (before.get("research") or {}).get("latest") or []}
        fresh = [d for d in (now["research"].get("latest") or []) if d.get("url") not in seen]
        out.append({"app": "open-research", "kind": "documents", "views": [], "documents": fresh[:20],
                    "what": f"open-research received documents to {b}: {len(fresh)} not seen before"
                            + (f", newest “{fresh[0]['title']}”" if fresh else "")})
    order = {"period": 0, "dataset": 1, "vintage": 2, "documents": 3, "release": 4}
    return sorted(out, key=lambda c: order.get(c["kind"], 9))


def load() -> dict | None:
    return read_json(STATE, None)


def commit(snap: dict) -> None:
    write_json(STATE, snap)


def recent(snap: dict | None, today: str | None = None, days: int = 45) -> list[dict]:
    """The statistics behind the apps' views that datasteg read in the last `days` days, newest first: a note may
    still be timely when it is the first look at a release the desk saw before (a new quarter of BIS bank positions
    stays news for some weeks). The vintage is when money-flow read the data, close to but not the publisher's date."""
    today = today or dt.date.today().isoformat()
    cut = (dt.date.fromisoformat(today) - dt.timedelta(days=days)).isoformat()
    out = []
    for ds, d in ((snap or {}).get("datasets") or {}).items():
        if ds in FEEDS and d.get("vintage") and str(d["vintage"])[:10] >= cut and d.get("newest"):
            out.append({"dataset": ds, "vintage": str(d["vintage"])[:10], "newest": d["newest"], "views": FEEDS[ds],
                        "what": f"{d.get('name') or ds} ({d.get('publisher')}): data to {d['newest']}, read on {str(d['vintage'])[:10]}"
                                f" (available since {dt.date.fromisoformat(str(d['vintage'])[:10]):%B %Y})"})
    return sorted(out, key=lambda x: x["vintage"], reverse=True)

