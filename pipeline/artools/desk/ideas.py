"""Ideas (20 Nov 2026, the owner): a preview of choosing the note's topic from what is new, by the questions the public
would ask. articles.datasteg.com exists to give timely, useful information from datasteg's data; the screens alone
(leads.py) found patterns first and a reason to read them after, and the owner found the topics dull.

One pass a day, writing nothing but /data/articles/desk/ideas/<date>.json (shown on the admin site):

1. What is new (code): the apps' changes since the desk last looked, the releases read in the last 45 days, the papers
   the open-research archive received in the last 30 days, and what the screens found in the panel today.
2. The questions (role `ideas`, Opus): 10 to 15 questions a reader without economics would ask about what is new, each
   answerable from datasteg's data, with what the panel shows (the writer's reading of the numbers it was given).
3. The readers (role `ideas-readers`, Sonnet): three readers score each headline, "would I read it" and "is it of use
   to me", 0 to 10.
4. The rank (code): interest, substance (a "no difference" answer counts less) and timeliness; the top question is the
   one this process would write. The lead the current pipeline chose that day is shown beside it.
5. Korean: qkr drafts each headline (profile headline), as every Korean string on the sites.

The preview never writes a note, and the daily note is still chosen by the screens until the owner decides otherwise.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .. import runlib
from ..paths import RUNS, read_json, write_json
from . import config, roles
from .api import DESK, Api

IDEAS = DESK / "ideas"
PERSONAS = ("office", "student", "exporter")
FRESH = {"C": 1.0, "R": 0.8, "D": 0.6, "L": 0.4}     # a change today, a new paper, a release of the last 45 days, a screen's lead


def _panel_csv(t: dict) -> str:
    """The panel's values (the period and window columns left out: the description gives the periods)."""
    keys = [c["id"] for c in t.get("columns") or [] if not str(c["id"]).startswith(("goods_window", "products_window", "lenders_quarter",
                                                                                    "chokepoint_year", "stress_trade_window"))]
    rows = t.get("rows") or []
    fmt = lambda v: ("" if v is None else f"{v:.4g}" if isinstance(v, float) else str(v))     # noqa: E731
    return "\n".join([",".join(keys)] + [",".join(fmt(r.get(k)) for k in keys) for r in rows])


def gather(api: Api) -> dict:
    from . import leads as leads_mod, panel as panel_mod, run as run_mod, tables as tables_mod, watch
    snap = watch.snapshot(api)
    changed = watch.changes(snap, watch.load())
    today = dt.date.today().isoformat()
    releases = watch.recent(snap, today)
    research = run_mod._research(api)
    panel = panel_mod.build(api)
    t = tables_mod.from_panel(panel)
    found = [l for l in leads_mod.find(panel, api, changed) if "error" not in l]
    recent = [{"date": h["at"][:10], "title": h.get("title"), "outcome": h.get("outcome")} for h in leads_mod.history()[-10:]]
    return {"today": today, "changed": changed[:20], "releases": releases[:12], "research": research[:40], "leads": found[:12],
            "panel": t, "recent": recent}


def packet(g: dict) -> str:
    from . import run as run_mod, tables as tables_mod
    leads = [{k: l.get(k) for k in ("key", "screen", "claim", "economies", "numbers")} for l in g["leads"]]
    return (f"Date: {g['today']}\n\n## What changed in datasteg's apps since the desk last looked\n"
            + ("\n".join(f"- C{i} [{c['app']}] {c['what']}" for i, c in enumerate(g["changed"], 1)) or "- nothing new today")
            + "\n\n## Releases datasteg read in the last 45 days\n"
            + ("\n".join(f"- D{i} {r['what']} (feeds {', '.join(r['views'])})" for i, r in enumerate(g["releases"], 1)) or "- none")
            + "\n\n## Papers and speeches the open-research archive received in the last 30 days\n"
            + ("\n".join(f"- R{i} {d['title']} ({d.get('series') or d.get('kind')}, {d.get('date')}; topic {(d.get('topic') or {}).get('label') if isinstance(d.get('topic'), dict) else d.get('topic') or '—'})"
                         for i, d in enumerate(g["research"], 1)) or "- none")
            + "\n\n## Patterns the desk's screens found in the panel today\n"
            + "\n".join(f"- L{i} {json.dumps(l, ensure_ascii=False)}" for i, l in enumerate(leads, 1))
            + "\n\n## The panel (36 economies, latest quarter)\n" + tables_mod.describe(g["panel"]).split("\n  columns:")[0]
            + "\n```csv\n" + _panel_csv(g["panel"]) + "\n```"
            + "\n\n## " + run_mod.PULL_MENU
            + "\n\n## Notes the desk wrote recently (do not repeat)\n" + json.dumps(g["recent"], ensure_ascii=False))


def score(q: dict, s: dict) -> dict:
    marks = [x.get(k) for p in PERSONAS for x in [s.get(p) or {}] for k in ("read", "useful") if isinstance(x.get(k), (int, float))]
    interest = sum(marks) / len(marks) if marks else 0.0
    substance = 0.4 if q.get("answer_kind") == "no_difference" else 1.0
    fresh = max([FRESH.get(str(r)[:1], 0.0) for r in q.get("from") or []] or [0.0])
    return {"interest": round(interest, 2), "substance": substance, "fresh": fresh,
            "score": round(0.5 * interest / 10 + 0.25 * substance + 0.25 * fresh, 3)}


def korean(work: Path, qs: list[dict]) -> str | None:
    """qkr drafts each headline; a headline qkr could not draft shows none (never a Korean of our own). Returns the
    error when qkr could not be reached."""
    from . import korean as ko_mod
    for q in qs:
        q["headline_ko"] = None
    try:
        ko_mod._RUN[:] = [work]
        ko_mod.health()
        todo = [{"id": q["id"], "kind": "chart", "chart": None, "path": ["headline"], "profile": "headline",
                 "sent": ko_mod.normalise(q["headline"])} for q in qs]
        got = ko_mod._draft(todo, config.load()["korean"])
    except Exception as e:      # qkr down: the preview shows the English only, and says so
        return f"{type(e).__name__}: {e}"
    for q, it in zip(qs, todo):
        st: dict = {}
        ko_mod._take({**it, "en": q["headline"]}, got.get(q["id"]) or {}, st, "draft")
        q["headline_ko"] = st.get("ko") if st.get("status") == "ok" else None
    return None


def chosen_today(today: str) -> dict | None:
    """The lead the current pipeline wrote today, if it wrote one."""
    r = read_json(RUNS / f"{today.replace('-', '')}-desk" / "desk" / "result.json", None)
    return {"run": f"{today.replace('-', '')}-desk", "title": r.get("title"), "lead": r.get("lead"), "status": r.get("status")} if r else None


def make(force: bool = False) -> dict:
    today = dt.date.today().isoformat()
    out_p = IDEAS / f"{today}.json"
    if out_p.is_file() and not force:
        return {"skipped": f"today's ideas are written ({out_p.name})"}
    work = IDEAS / today
    (work / "logs").mkdir(parents=True, exist_ok=True)
    t0 = dt.datetime.now()
    g = gather(Api())
    cached = read_json(work / "answers.json", {}) or {}
    w = cached.get("ideas") or roles.call(work, "ideas", packet(g))["data"] or {}
    write_json(work / "answers.json", {**cached, "ideas": w})
    qs = [q for q in w.get("questions") or [] if isinstance(q, dict) and q.get("headline")][:15]
    for i, q in enumerate(qs, 1):
        q["id"] = f"Q{i}"
    rp = "\n".join(f"### {q['id']}\nHeadline: {q['headline']}\nThe question: {q.get('question')}" for q in qs)
    rd = cached.get("readers") or ((roles.call(work, "ideas-readers", rp)["data"] or {}) if qs else {})
    write_json(work / "answers.json", {**cached, "ideas": w, "readers": rd})
    marks = {x.get("id"): x for x in rd.get("scores") or [] if isinstance(x, dict)}
    for q in qs:
        q["readers"] = {p: (marks.get(q["id"]) or {}).get(p) for p in PERSONAS}
        q.update(score(q, marks.get(q["id"]) or {}))
    qs.sort(key=lambda q: -q["score"])
    ko_error = korean(work, qs) if qs else None
    res = {"date": today, "made": runlib.now(), "seconds": (dt.datetime.now() - t0).seconds,
           "cost_usd": round(roles.spent(work), 2),
           "new": {"changed": [c["what"] for c in g["changed"]], "releases": [r["what"] for r in g["releases"]],
                   "research": [{"title": d["title"], "series": d.get("series"), "date": d.get("date"), "url": d.get("url")} for d in g["research"]],
                   "leads": [{"key": l["key"], "screen": l["screen"], "claim": l.get("claim"), "score": l.get("score")} for l in g["leads"]]},
           "questions": qs, "pick": qs[0]["id"] if qs else None, "korean_error": ko_error,
           "pipeline": chosen_today(today), "note": w.get("note")}
    write_json(out_p, res)
    return {"date": today, "questions": len(qs), "pick": qs[0]["headline"] if qs else None, "cost_usd": res["cost_usd"]}


def question(ref: str) -> dict:
    """A question of the preview by its reference, <date>:<Q id>: the question, the screen lead it rests on (its key) and
    the titles of the papers it draws on."""
    date, _, qid = ref.partition(":")
    d = read_json(IDEAS / f"{date}.json", None)
    if not d:
        raise SystemExit(f"no ideas for {date}")
    q = next((x for x in d["questions"] if x["id"] == qid), None)
    if not q:
        raise SystemExit(f"no question {qid} on {date}")
    lead = next((d["new"]["leads"][int(r[1:]) - 1]["key"] for r in q.get("from") or [] if r.startswith("L") and r[1:].isdigit()
                 and int(r[1:]) <= len(d["new"]["leads"])), None)
    papers = [d["new"]["research"][int(r[1:]) - 1]["title"] for r in q.get("from") or [] if r.startswith("R") and r[1:].isdigit()
              and int(r[1:]) <= len(d["new"]["research"])]
    return {**q, "ref": ref, "lead_key": lead, "papers": papers}


def recent(days: int = 14) -> list[Path]:
    return sorted(IDEAS.glob("????-??-??.json"))[-days:]
