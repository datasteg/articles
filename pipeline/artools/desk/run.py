"""One desk run, start to queue: watch → leads → editor → data → analyst → writer ⇄ reviewers → judge.

Code holds the loop. A model is called once per role per round, with a packet this module assembles and a JSON answer
it validates; a call that cannot be used is sent back once with the reason. The loop ends when a round has no
blocking issue, when the rounds or the note's budget run out, or when a stage fails. The judge then scores the note
on the standard's eight dimensions against the benchmark set. A note that passes waits in the queue for the editor's
approval; one that does not is shelved with its scores and reasons. Nothing here publishes.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import runlib
from ..paths import ARTICLES, CONFIG, CONTENT, RUNS, load_yaml, read_json, write_json
from . import claims as claims_mod, config, cover as cover_mod, facts as facts_mod, inference as inference_mod, judge as judge_mod, leads as leads_mod, panel as panel_mod, polish as polish_mod, review, roles, tables as tables_mod, text, watch
from .api import DESK, Api

PULL_MENU = """Views you may pull (path · parameters). Economies are ISO alpha-3 codes of the 36 economies in the panel, plus USA for pairs.
- global-network/pairs/{a}/{b} · history=goods|bank|portfolio|fdi|ratio (a series since 2006; without it, both directions of goods, bank claims, portfolio holdings and direct investment at their own periods, and the finance-to-trade ratio)
- global-network/stress · economy=ISO3 (the seven joint signals by quarter since 2005 for one economy) or quarter=YYYY-MM-DD (all 36 at an earlier quarter)
- global-network/shocks/{id} · id = covid-2020 | iran-war-2026 | gfc-2008 | russia-ukraine-2022; economy=ISO3 (month-by-month replay through trade links, with funding flows before and after)
- money-flow/board · quarter=YYYY-MM-DD (the board at an earlier quarter end, back to 2005-03-31)
- money-flow/sovereign · economy=ISO3 (seven fiscal and external rules by year, with IMF projections)
- money-flow/markets/bank/lender-cut · debtor=ISO3, lender=ISO3, cut_pct=10..50 (first-round loss if one banking system cut its loans, against net reserves)
- money-flow/markets/{market} · market = bank | bonds | equity | fdi; debtor=ISO3 or creditor=ISO3 (largest holders or holdings, at most 25)
- money-flow/pulse (weekly: Treasuries in custody for foreign officials, Fed swap lines, the broad dollar index, TIC flows)
- trade-flow/economies/{iso3} · direction=exports|imports, product=HS:85 (partners and HS chapters as shares)
- trade-flow/flows/{a}/{b} (both directions as shares of world trade and of each side's trade, ten years of 12-month windows, mirror ratios)
- trade-flow/chains/{chain} · chain = batteries | semiconductors | solar | steel | aluminium | copper | magnets | plastics | textiles | fertiliser; economy=ISO3 (each stage's exporter concentration and, with economy, its share at every stage)
- trade-flow/tools/cut-supplier · stage, exporter=ISO3, cut=1..100 (who loses what share of imports if one exporter of a chain stage is cut)"""


PAGES = """- money-flow World page: the Signal Board ranks the 36 economies by a funding vulnerability score against a bank-and-bond flow score, and lists the largest withdrawals of the quarter. Sovereign page: seven fiscal and external rules per economy.
- trade-flow: each economy's partners and products as shares; ten chains with the exporter concentration of each stage and its chokepoints.
- global-network country sheet: one economy's funding and trade on one page. Stress page: seven signals per economy, each a funding quantity against a trade quantity (import cover; financing need over exports; a double hit; partner stress; dual dependence, which measures how far an economy's lenders and customers overlap; the dollar channel; commodities against buffers). No page ranks or counts economies across the group on a joined measure, and none compares the two sides' partners by name."""


def log(run: Path, msg: str) -> None:
    line = f"{dt.datetime.now().strftime('%H:%M:%S')} {msg}"
    print(line, file=sys.stderr, flush=True)
    with (run / "logs" / "desk.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def stage(run: Path, name: str, **fields) -> None:
    runlib.set_stage(run, name, **fields)


def _done(run: Path, name: str, **fields) -> None:
    stage(run, name, state="done", ended=runlib.now(), **fields)


def _published() -> list[dict]:
    out = []
    for m in sorted((CONTENT / "articles").glob("*/meta.json")):
        meta = read_json(m, {}) or {}
        en = read_json(m.parent / "en.json", {}) or {}
        out.append({"slug": meta.get("slug"), "type": meta.get("type"), "date": meta.get("date"), "title": en.get("title")})
    return out


def caveats() -> str:
    c = config.load().get("caveats") or []
    return ("\n\n## Known traps in these data (config/desk.yaml)\n" + "\n".join(f"- {x}" for x in c)) if c else ""


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)


# ------------------------------------------------------------------ packets

def editor_packet(shortlist: list[dict], changed: list[dict], tables: dict, today: str, research: list[dict] | None = None,
                  releases: list[dict] | None = None, rewrite: dict | None = None) -> str:
    topics = [t["id"] for t in (load_yaml(CONFIG / "topics.yaml") or {}).get("topics", [])]
    recent = [{"date": h["at"][:10], "lead": h["key"], "title": h.get("title"), "outcome": h.get("outcome"),
               "about": leads_mod.subjects(h.get("run"))} for h in leads_mod.history()[-10:]]
    leads = [{k: l.get(k) for k in ("key", "screen", "claim", "why", "economies", "numbers", "score", "fresh", "covered_recently", "pulls")}
             for l in shortlist]
    covered = leads_mod.recent_subjects()
    return (f"Date: {today}\n\n## What changed in the apps since the desk last looked (a `hook` of kind data names one by its id)\n"
            + ("\n".join(f"- C{i} [{c['app']}] {c['what']}" for i, c in enumerate(changed[:20], 1)) or "- nothing: the data are as they were at the last note")
            + "\n\n## Releases behind the views read in the last 45 days (a `hook` of kind data may name one by its id, when the note is about what it shows)\n"
            + ("\n".join(f"- D{i} {r['what']} (feeds {', '.join(r['views'])})" for i, r in enumerate((releases or [])[:12], 1)) or "- none")
            + "\n\n## Leads found by the screens today (best score first)\n" + _j(leads)
            + "\n\n## Notes the desk wrote recently (do not repeat)\n" + (_j(recent) if recent else "none yet")
            + "\n\n## Economies a recent note was about (prefer others; the date is the note's)\n" + (_j(covered) if covered else "none")
            + "\n\n## Research received by the open-research archive in the last 30 days (titles only, not evidence; a `hook` of kind research names one by its id)\n"
            + ("\n".join(f"- R{i} {d['title']} ({d.get('series') or d.get('kind')}, {d.get('date')})" for i, d in enumerate((research or [])[:40], 1)) or "none")
            + "\n\n## Articles already published on articles.datasteg.com\n" + _j(_published())
            + "\n\n## What the apps' own pages already show (a note must add to these, not repeat them)\n" + PAGES
            + caveats()
            + "\n\n## Tables every note already has\n" + "\n".join(tables_mod.describe(t).split("\n")[0] for t in tables.values())
            + "\n\n## " + PULL_MENU + "\n\n## Topic ids\n" + ", ".join(topics)
            + (("\n\n## This is a rewrite (`rewrite_of`)\nThe desk writes the lead " + str(rewrite.get("lead")) + " again: it is the note "
                + str(rewrite.get("run")) + ", taken back or held for this reason: " + str(rewrite.get("why"))
                + ". Choose this lead (it is on the list for that reason, not as a repeat), give `rewrite_of` as "
                + json.dumps({"run": rewrite.get("run"), "why": rewrite.get("why")}, ensure_ascii=False)
                + " in your brief, and write the brief afresh from today's data. The old note's title was: "
                + json.dumps(rewrite.get("title"), ensure_ascii=False)) if rewrite else ""))


def tables_block(tables: dict, full: bool = True, only: set | None = None) -> str:
    """Tables for a packet. full: with the values as CSV (the analyst and the referee compute from them); otherwise
    what a figure request needs: the columns and the row keys. only: the tables to include (all by default)."""
    out = []
    for name, t in tables.items():
        if only is not None and name not in only:
            continue
        out.append(tables_mod.describe(t))
        if full and t["rows"]:
            out.append("```csv\n" + tables_mod.csv_text(t) + "```")
        elif t["rows"]:
            keys = [f"{r['_key']}" + (f" ({r['name']})" if r.get("name") and r["name"] != r["_key"] else "") for r in t["rows"]]
            shown = keys if len(keys) <= 45 else keys[:6] + [f"… {len(keys) - 12} more …"] + keys[-6:]
            out.append("  row keys: " + ", ".join(shown))
    return "\n\n".join(out)


def analyst_packet(brief: dict, lead: dict, tables: dict, problems: list | None = None, have: list[dict] | None = None,
                   requests: list | None = None, claims: list[dict] | None = None) -> str:
    p = "## The editor's brief\n" + _j(brief) + "\n\n## The lead as the screens found it (numbers to be recomputed, not copied)\n" \
        + _j({k: lead.get(k) for k in ("claim", "why", "numbers")}) + caveats() + "\n\n## Tables\n" + tables_block(tables)
    if have:
        p += "\n\n## Facts already computed (keep; do not repeat)\n" + facts_mod.sheet(have)
    if claims:
        p += ("\n\n## Claims already in the ledger (keep; add a claim only for a new number the requests need, with the next id)\n"
              + claims_mod.sheet(claims, {f["id"]: f for f in have or []}))
    if requests:
        p += ("\n\n## More numbers asked for by the writer and the reviewers\nReturn only the new facts, as expressions. "
              "If a request cannot be computed from these tables, leave it out.\n" + _j(requests))
    if problems:
        p += "\n\n## Problems with your earlier request (fix or drop these, and return the whole list again)\n" + _j(problems)
    return p


def writer_packet(brief: dict, analyst: dict, fact_list: list[dict], tables: dict, research: list[dict], catalog: list[dict],
                  previous: dict | None = None, reviews: dict | None = None, build_problems: list | None = None,
                  claims: list[dict] | None = None) -> str:
    ds = [{"cite": f"[[{d['id']}]]", "what": d["title"], "from": d["provider"], "release": d.get("release")} for d in catalog
          if d["id"] != "ds-panel"]      # the join itself is not a source: its numbers are cited to the views they came from
    p = ("## The editor's brief\n" + _j(brief) + "\n\n## The analyst's verdict and cautions\n"
         + _j({"verdict": analyst.get("verdict"), "cautions": analyst.get("cautions")})
         + caveats()
         + "\n\n## Fact sheet (the only numbers you may use)\n" + facts_mod.sheet(fact_list)
         + (("\n\n## Claim ledger (the only claims the title, dek, key numbers, findings and chart headlines may state; cite each in `claims`)\n"
             + claims_mod.sheet(claims, {f["id"]: f for f in fact_list})) if claims else "")
         + "\n\n## Sources you may cite\n" + _j(ds)
         + "\n\n## Tables (for figures: table names, column ids and row keys; the values are in the fact sheet)\n"
         + tables_block(tables, full=False)
         + "\n\n## Recent research received by the open-research archive (titles only; for related_reading)\n"
         + "\n".join(f"- {d['title']} ({d.get('series') or d.get('kind')}, {d.get('date')})" for d in research[:40]))
    if previous:
        p += "\n\n## Your previous answer\n```json\n" + _j(previous) + "\n```"
    if build_problems:
        p += ("\n\n## The previous answer could not be built\nFix exactly these and return the whole object again:\n"
              + "\n".join(f"- {x}" for x in build_problems))
    if reviews:
        p += "\n\n## Reviews of the previous draft\n" + _j(reviews)
    return p


def review_packets(draft: dict, fact_list: list[dict], charts: dict, tables: dict, brief: dict, mech: dict,
                   claims: list[dict] | None = None, cmap: dict | None = None) -> dict:
    fmap = {f["id"]: f for f in fact_list}
    marked = text.article(draft, fmap, charts, "review")
    sheet = facts_mod.sheet(fact_list)
    ledger = ("\n\n## Claim ledger (what the data support; each surface string cites the claim it states)\n" + claims_mod.sheet(claims, fmap)
              + "\n\n## Which claim each surface string cites\n" + _j(cmap or {})) if claims else ""
    return {
        "referee": ("## The editor's brief (thesis, finding type, comparison and rival readings)\n" + _j({k: brief.get(k) for k in ("question", "thesis", "finding_type", "comparison", "hook", "why_now", "why_these", "conventional", "twist", "rival_readings", "concept")})
                    + caveats()
                    + "\n\n## The draft\n" + marked + "\n\n## Fact sheet\n" + sheet + ledger + "\n\n## Tables\n"
                    + tables_block(tables, only={"panel"} | {t for f in fact_list for t in f.get("tables") or []})),
        "reader": "## The article\n" + text.article(draft, fmap, charts, "reader"),
        "checker": ("## The draft\n" + marked + "\n\n## Fact sheet\n" + sheet + ledger + caveats()
                    + "\n\n## Mechanical checks already run (do not repeat)\n" + _j({"blocking": mech["blocking"], "advisory": mech["advisory"][:12]})),
    }


# ------------------------------------------------------------------ the run

def idea_block(q: dict, research: list[dict]) -> str:
    """The question the editor chose on the ideas preview: the note answers it (20 Nov 2026, the owner)."""
    papers = [d for d in research if d.get("title") in (q.get("papers") or [])]
    return ("\n\n## The editor chose this question on the ideas preview (" + q["ref"] + "): write the brief for it\n"
            "The note answers this question for readers who never studied economics. Choose the lead it rests on"
            + (f" ({q['lead_key']})" if q.get("lead_key") else "") + ", frame the finding as the answer to the question, and "
            "compute every number again: what the preview read in the panel is a guess, not a fact.\n"
            + json.dumps({k: q.get(k) for k in ("headline", "question", "answer", "data", "korea")}, ensure_ascii=False, indent=1)
            + ("\nPapers it draws on (a hook of kind research may name them by their R id above): "
               + "; ".join(d["title"] for d in papers) if papers else ""))


def _research(api: Api) -> list[dict]:
    try:
        docs = api.get("open-research/new", max_age_h=12, limit=50)["data"].get("documents") or []
    except Exception:
        return []
    return [{"title": d.get("title"), "kind": d.get("kind"), "series": d.get("series"), "date": d.get("date"),
             "url": d.get("url"), "authors": d.get("authors"), "slug": d.get("slug")} for d in docs]


def _related(titles: list, research: list[dict]) -> list[dict]:
    by = {d["title"]: d for d in research}
    out = []
    for t in titles or []:
        d = by.get(t)
        if d and d.get("url"):
            out.append({"ref": f"open-research:{d.get('slug')}", "title": d["title"], "institution": d.get("series"),
                        "date": d.get("date"), "url": d["url"],
                        "why": {"en": "Received by the research archive this month; on the same subject as this note."}})
    return out[:3]


HOOK_SCREENS = {"event": {"shock"}, "extreme": {"own_extremes", "decoupled", "movers"}}


def check_hook(brief: dict, changed: list[dict], research: list[dict], shortlist: list[dict], releases: list[dict] | None = None) -> list[str]:
    """Why the brief's reason for writing today cannot be used (empty when it can). A note needs a hook the packet
    shows: a data change (C<n>), a research title received this month (R<n>), an event replay or a reading at an
    extreme of the economy's own past (a lead key from those screens); and it says why these economies and not others."""
    out = []
    h = brief.get("hook")
    if not isinstance(h, dict):
        return ["`hook` is missing: name what makes this note timely today, from the packet (see “Why now”)"]
    kind, ref = h.get("kind"), str(h.get("ref") or "").strip()
    keys = {l["key"]: l for l in shortlist}
    if kind == "data" and re.fullmatch(r"D\d+", ref):
        if not 1 <= int(ref[1:]) <= min(12, len(releases or [])):
            out.append(f"hook.ref {ref!r}: a release hook names one of the releases listed as D1, D2 … (today there are {len((releases or [])[:12])})")
    elif kind == "data":
        m = re.fullmatch(r"C(\d+)", ref)
        c = changed[int(m[1]) - 1] if m and 1 <= int(m[1]) <= min(20, len(changed)) else None
        if not c:
            out.append(f"hook.ref {ref!r}: a data hook names one of the changes listed as C1, C2 … or a release D1, D2 … (today there are {len(changed[:20])} changes)")
        elif c.get("kind") == "documents":
            out.append(f"hook.ref {ref}: new research documents are a research hook (R<n>), not a data change")
    elif kind == "research":
        m = re.fullmatch(r"R(\d+)", ref)
        if not (m and 1 <= int(m[1]) <= min(40, len(research))):
            out.append(f"hook.ref {ref!r}: a research hook names one of the titles listed as R1, R2 … (today there are {len(research[:40])})")
    elif kind in HOOK_SCREENS:
        l = keys.get(ref)
        if not l or l.get("screen") not in HOOK_SCREENS[kind]:
            out.append(f"hook.ref {ref!r}: an {kind} hook names a lead from the screens {sorted(HOOK_SCREENS[kind])} on today's list")
    else:
        out.append(f"hook.kind {kind!r}: one of data, research, event, extreme")
    if len(str(h.get("what") or "").split()) < 6:
        out.append("hook.what: say in a sentence what happened or what is new, with its date or period")
    if len(str(brief.get("why_these") or "").split()) < 8:
        out.append("`why_these` is missing: say why these economies, and not the others the lead or the panel offers")
    return out


def check_finding(brief: dict) -> list[str]:
    """R1: the brief names the finding type and the comparison it needs."""
    out = []
    if brief.get("finding_type") not in claims_mod.FINDING_TYPES:
        out.append(f"`finding_type` must be one of {list(claims_mod.FINDING_TYPES)}: what kind of finding the note will test")
    if len(str(brief.get("comparison") or "").split()) < 6:
        out.append("`comparison`: say what the finding must be read against (both groups, the economy's own past with its window, "
                   "the median of all economies with data, the alternative explanation it rules out)")
    return out


def _budget_left(run: Path) -> float:
    return config.load()["budget"]["usd_per_note"] - roles.spent(run)


def note(run_id: str | None = None, offline: bool = False, lead_key: str | None = None, max_rounds: int | None = None,
         rewrite_of: str | None = None, rewrite_why: str | None = None, idea: str | None = None) -> dict:
    cfg = config.load()
    # a question the editor chose on the ideas preview (desk/ideas.py, 20 Nov 2026): its screen's lead, if it rests on
    # one, and the question itself for the editor's brief
    chosen = None
    if idea:
        from . import ideas as ideas_mod
        chosen = ideas_mod.question(idea)
        lead_key = lead_key or chosen.get("lead_key")
    today = dt.date.today().isoformat()
    api = Api(offline=offline)
    # --- watch and leads (no model)
    snap = watch.snapshot(api) if not offline else (watch.load() or {})
    changed = watch.changes(snap, watch.load()) if not offline else []
    panel = panel_mod.build(api)
    base_panel = tables_mod.from_panel(panel)
    # --- preflight (R10): the apps' own consistency checks, the panel's periods and the registry copies, before any
    # model is paid for; a failure means no note today, with the reason
    if (cfg.get("claims") or {}).get("preflight") and not offline:
        from . import preflight
        pf = preflight.check(base_panel)
        if not pf["ok"]:
            return {"status": "preflight-failed", "why": "; ".join(pf["problems"]), "checked": pf["checked"]}
    rewrite = None
    if rewrite_of:
        old = read_json(RUNS / rewrite_of / "desk" / "result.json", {}) or {}
        ob = read_json(RUNS / rewrite_of / "desk" / "brief.json", {}) or {}
        lead_key = lead_key or ob.get("lead") or old.get("lead")
        rewrite = {"run": rewrite_of, "why": rewrite_why or "rewritten with the refined pipeline", "lead": lead_key, "title": old.get("title")}
    found = [l for l in leads_mod.find(panel, api, changed, keep=lead_key) if "error" not in l]
    if lead_key:
        found = [l for l in found if l["key"] == lead_key] or found
    if not found:
        return {"status": "no-lead", "why": "the screens found nothing new today", "changed": len(changed)}
    shortlist = found[: cfg["leads"]["shortlist"]]
    rid = run_id or f"{dt.date.today():%Y%m%d}-desk"
    n = 2
    while (RUNS / rid).exists():
        rid, n = f"{run_id or f'{dt.date.today():%Y%m%d}-desk'}-{n}", n + 1
    runlib.new("Data desk note", rid, pipeline=cfg["pipeline"], model="desk roles (config/desk.yaml)", effort=None)
    run = RUNS / rid
    (run / "desk").mkdir(exist_ok=True)
    write_json(run / "desk" / "watch.json", {"snapshot": snap, "changed": changed})
    write_json(run / "desk" / "leads.json", found)
    _done(run, "desk-watch", note=f"{len(changed)} changes")
    _done(run, "desk-leads", note=f"{len(found)} leads")
    log(run, f"run {rid}: {len(changed)} changes, {len(found)} leads; shortlist {[l['key'] for l in shortlist]}"
             + (f"; a rewrite of {rewrite_of}" if rewrite_of else ""))
    base = {"panel": base_panel, **tables_mod.panel_inputs(api, panel)}
    try:
        return _write(run, api, cfg, today, shortlist, changed, base, snap, max_rounds, offline, rewrite, chosen)
    except (roles.RoleError, Exception) as e:   # the run stays on disk with its logs; the morning's cron reports it
        log(run, f"FAILED: {type(e).__name__}: {e}")
        write_json(run / "desk" / "result.json", {"status": "failed", "error": f"{type(e).__name__}: {e}", "cost_usd": roles.spent(run)})
        raise


def analyse(run: Path, brief: dict, lead: dict, tables: dict, cfg: dict) -> tuple[list[dict], dict, list[dict]]:
    """The analyst's facts and claim ledger (R2). Facts that cannot be computed and claims that fail code's checks go
    back to the analyst once together; a ledger without a usable finding claim stops the note."""
    need_claims = (cfg.get("claims") or {}).get("required", True)
    an = roles.call(run, "analyst", analyst_packet(brief, lead, tables))
    fact_list, problems = facts_mod.compute(an["data"].get("facts") or [], tables)
    claims, cprob = claims_mod.resolve(an["data"].get("claims") or [], fact_list)
    claims, cprob2, cautions = claims_mod.validate(claims, fact_list, tables, brief)
    cprob += cprob2
    if need_claims and not an["data"].get("claims"):
        cprob.append({"claim": None, "problem": "the answer has no `claims`: write the claim ledger beside the facts"})
    if (problems and len(problems) > max(2, len(fact_list) // 6)) or (need_claims and cprob):
        an = roles.call(run, "analyst", analyst_packet(brief, lead, tables, problems=problems + [{"claims": cprob}] if cprob else problems))
        fact_list, problems = facts_mod.compute(an["data"].get("facts") or [], tables)
        claims, cprob = claims_mod.resolve(an["data"].get("claims") or [], fact_list)
        claims, cprob2, cautions = claims_mod.validate(claims, fact_list, tables, brief)
        cprob += cprob2
    if len(fact_list) < 10:
        raise roles.RoleError(f"analyst: only {len(fact_list)} facts could be computed ({problems[:3]})")
    if need_claims and not any(c.get("finding") for c in claims):
        raise roles.RoleError(f"analyst: no usable claim ledger ({cprob[:3]})")
    analyst = {"verdict": an["data"].get("verdict"), "cautions": (an["data"].get("cautions") or []) + cautions,
               "dropped": problems, "claims_dropped": cprob}
    return fact_list, analyst, claims


def _paths_of(issue: dict, draft: dict, charts: dict, fmap: dict) -> list[str]:
    """Where in the draft a reviewer's issue sits: the dotted path of the string its quote comes from (claim-map style
    for the surface: title, dek, keyNumbers.0, findings.1, figure:<id>), or [] when it cannot be told."""
    q = str(issue.get("quote") or "")
    words = [w for w in re.findall(r"[A-Za-z]{4,}", q)]
    where = str(issue.get("where") or "")
    cands = []
    from .queue import _walk
    for path, v in _walk(draft):
        if isinstance(v, str) and path and path[0] not in ("reproduce", "citations", "byline", "disclaimer", "whyNowLabel"):
            cands.append((".".join(map(str, path)), text._plain(v, fmap)))
    for cid, ch in charts.items():
        for k in ("headline", "title", "subtitle", "howToRead", "alt"):
            if text._tx(ch.get(k)):
                cands.append((f"figure:{cid}" + ("" if k == "headline" else f".{k}"), text._tx(ch.get(k))))
    if words:
        best = max(cands, key=lambda c: sum(w in c[1] for w in words), default=None)
        if best and sum(w in best[1] for w in words) >= 0.7 * len(words):
            return [best[0]]
    keys = [k.strip() for k in where.split(",")]
    if len(keys) > 1 and all(k in ("title", "dek", "whyNow") or re.fullmatch(r"(keyNumbers|findings)\.\d+|figure:[\w-]+(\.\w+)?", k) for k in keys):
        return keys           # an inference issue names the surface strings it came from
    m = re.match(r"figure[: ]+([\w-]+)", where)
    if m and m.group(1) in charts:
        return [f"figure:{m.group(1)}"]
    if where in ("title", "dek", "whyNow") or re.fullmatch(r"(keyNumbers|findings)\.\d+", where):
        return [where]
    return []


def _surface_key(path: str) -> str:
    """keyNumbers.0.label → keyNumbers.0; figure:x.subtitle → figure:x; sections.1.blocks.2.text stays."""
    m = re.match(r"(keyNumbers\.\d+|findings\.\d+|figure:[\w-]+)", path)
    return m.group(1) if m else path


def _changed_paths(old: dict | None, new: dict, old_charts: dict, new_charts: dict) -> set[str]:
    from .queue import _walk
    if old is None:
        return set()
    o = {".".join(map(str, p)): v for p, v in _walk(old)}
    n = {".".join(map(str, p)): v for p, v in _walk(new)}
    out = {k for k in set(o) | set(n) if o.get(k) != n.get(k)}
    for cid in set(old_charts) | set(new_charts):
        for k in ("headline", "title", "subtitle", "howToRead", "alt"):
            a, b = text._tx((old_charts.get(cid) or {}).get(k)), text._tx((new_charts.get(cid) or {}).get(k))
            if a != b:
                out.add(f"figure:{cid}" + ("" if k == "headline" else f".{k}"))
    return out


def converge(blocking: list[dict], earlier: list[dict], changed: set[str], draft: dict, charts: dict, fmap: dict) -> tuple[list[dict], list[dict]]:
    """R6: in a later round a reviewer may raise a new blocking issue only on a string that changed since the last
    draft, or as an error of fact. Issues are keyed by claim and path; an issue on a path an earlier round raised is
    not new. Returns (blocking kept, demoted to advisory)."""
    seen_paths = {p for b in earlier for p in (b.get("paths") or [])}
    seen_claims = {c for b in earlier for c in (b.get("claims") or [])}
    keep, demoted = [], []
    for b in blocking:
        paths = _paths_of(b, draft, charts, fmap)
        b["paths"] = paths
        if b.get("owner") in ("mechanical", "inference") or str(b.get("kind") or "").lower() in ("fact", "claim_shape_fact"):
            keep.append(b)
            continue
        new = not (set(paths) & seen_paths) and not (set(b.get("claims") or []) & seen_claims)
        touched = any(p in changed or _surface_key(p) in {_surface_key(c) for c in changed} or any(c.startswith(p + ".") for c in changed)
                      for p in paths)
        if new and paths and not touched:
            demoted.append({**b, "issue": f"(raised late, on a string that did not change) {b.get('issue')}"})
        else:
            keep.append(b)
    return keep, demoted


def _write(run, api, cfg, today, shortlist, changed, base, snap, max_rounds, offline, rewrite=None, chosen=None) -> dict:
    ccfg = cfg.get("claims") or {}
    # --- editor
    stage(run, "desk-editor", state="running", started=runlib.now())
    research = _research(api)
    releases = watch.recent(snap, today)
    packet = editor_packet(shortlist, changed, base, today, research, releases, rewrite) + (idea_block(chosen, research) if chosen else "")
    ed = roles.call(run, "editor", packet)
    brief = ed["data"]
    # a note needs a reason to be written today and a reason to be about these economies (config note.require_hook),
    # and since 18 Nov 2026 a finding type and the comparison it needs (R1); a brief without them goes back once
    def brief_problems(b):
        if b.get("lead") is None:
            return []
        return (check_hook(b, changed, research, shortlist, releases) if cfg["note"].get("require_hook") else []) \
            + (check_finding(b) if ccfg.get("required", True) else [])
    hook_problems = brief_problems(brief)
    if hook_problems:
        log(run, f"editor: brief not usable ({hook_problems[:2]}); asked again")
        ed = roles.call(run, "editor", packet + "\n\n## Your previous answer could not be used\n```json\n" + _j(brief) + "\n```\n"
                        + "\n".join(f"- {p}" for p in hook_problems)
                        + "\nFix these and answer again. If no lead on the list has a hook the packet shows, answer "
                          "{\"lead\": null, \"why\": \"…\"}: there is no note today.")
        brief = ed["data"]
        hook_problems = brief_problems(brief)
        if hook_problems:
            brief = {"lead": None, "why": "no lead had a usable brief: " + "; ".join(hook_problems[:3]), "rejected": brief}
    if brief.get("lead") is None:        # the editor may pass: no note today
        write_json(run / "desk" / "brief.json", brief)
        runlib.set_stage(run, "desk-editor", state="done", ended=runlib.now(), note="no lead worth a note")
        result = {"run": run.name, "status": "no-lead", "why": brief.get("why"), "cost_usd": roles.spent(run)}
        write_json(run / "desk" / "result.json", result)
        if not offline and snap and not rewrite:
            watch.commit(snap)
        log(run, f"editor: no note today: {brief.get('why')}")
        return result
    lead = next((l for l in shortlist if l["key"] == brief.get("lead")), shortlist[0])
    brief["lead"] = lead["key"]
    if rewrite:
        brief["rewrite_of"] = {"run": rewrite["run"], "why": rewrite["why"]}
    write_json(run / "desk" / "brief.json", brief)
    runlib.set_stage(run, "desk-editor", state="done", ended=runlib.now(), note=lead["key"])
    with runlib.locked(run):
        m = runlib.load(run)
        m["question"] = brief.get("question") or m["question"]
        write_json(run / "run.json", m)
    log(run, f"editor: lead {lead['key']} — {brief.get('working_title')} ({brief.get('finding_type')})")
    # --- data: the lead's pulls and the editor's
    stage(run, "desk-data", state="running", started=runlib.now())
    tables = dict(base)
    wanted = {p["name"]: p for p in (lead.get("pulls") or []) + (brief.get("pulls") or []) if isinstance(p, dict) and p.get("name") and p.get("path")}
    skipped = []
    for name, p in list(wanted.items())[:8]:
        try:
            tables[name] = tables_mod.pull(api, name, p["path"], p.get("params") or {})
        except Exception as e:
            skipped.append({"pull": p, "problem": str(e)[:200]})
    catalog = tables_mod.write_datasets(run, tables)
    tables_mod.save(run, tables)
    write_json(run / "desk" / "provenance.json", {"calls": api.used, "skipped": skipped, "network_calls": api.calls})
    _done(run, "desk-data", note=f"{len(tables)} tables")
    log(run, f"data: tables {sorted(tables)}" + (f"; skipped {len(skipped)}" if skipped else ""))
    # --- analyst: the facts and the claim ledger
    stage(run, "desk-analyst", state="running", started=runlib.now())
    fact_list, analyst, claims = analyse(run, brief, lead, tables, cfg)
    facts_mod.save(run, fact_list)
    claims_mod.save(run, claims)
    write_json(run / "desk" / "analyst.json", analyst)
    _done(run, "desk-analyst", note=f"{len(fact_list)} facts, {len(claims)} claims")
    log(run, f"analyst: {len(fact_list)} facts, {len(claims)} claims ({len(analyst['claims_dropped'])} claim problems), "
             f"{len(analyst['dropped'])} dropped; verdict: {str(analyst['verdict'])[:140]}")
    # --- writer and reviewers
    rounds = max_rounds or cfg["loop"]["max_rounds"]
    answer, history = None, []
    stage(run, "desk-writer", state="running", started=runlib.now())

    def write(reviews=None, only: list[str] | None = None):
        """One draft: the writer's answer, built into the run's files; a build failure goes back once with what failed.
        `only` (a closing pass, R6): the new answer is taken only for those strings; the rest stays as it was."""
        nonlocal answer
        effort = (cfg["roles"]["writer"].get("revise_effort") if reviews else None) or None
        prev = answer
        w = roles.call(run, "writer", writer_packet(brief, analyst, fact_list, tables, research, catalog, previous=answer, reviews=reviews,
                                                    claims=claims), effort=effort)
        answer = _scoped(w["data"], prev, only) if only and prev else w["data"]
        for attempt in range(2):
            answer["_related"] = _related(answer.get("related_reading"), research)
            built = review.assemble(run, answer, brief, tables, fact_list, catalog)
            mech = (review.mechanical(run, built["draft"], built["charts"], fact_list, tables, catalog) if built["draft"]
                    else {"blocking": [], "advisory": [], "stats": {}})
            # what code can already see is wrong (a figure that cannot be drawn, a typed number, the length, a missing
            # section, a surface string with no claim or one that drops its comparison) goes back to the writer once,
            # before any reviewer is paid to read it
            problems = built["problems"] + mech["blocking"]
            if not problems:
                break
            log(run, f"writer: {len(problems)} problems found by code: {problems[:3]}")
            if attempt == 1 or _budget_left(run) <= 0:
                break
            w = roles.call(run, "writer", writer_packet(brief, analyst, fact_list, tables, research, catalog, previous=answer,
                                                        build_problems=problems, claims=claims), effort=cfg["roles"]["writer"].get("fix_effort") or None)
            answer = _scoped(w["data"], prev, only) if only and prev else w["data"]
        if not built["draft"]:
            raise roles.RoleError("writer: no usable draft")
        mech["blocking"] = [f"build: {p}" for p in built["problems"]] + mech["blocking"]
        return built, mech

    def more_facts(asks: list, rnd: int):
        """Numbers the next draft needs, asked for by the writer and the referee, computed before the revision."""
        if not asks:
            return
        try:
            more = roles.call(run, "analyst", analyst_packet(brief, lead, tables, have=fact_list, requests=asks, claims=claims), label="analyst")
            new, probs = facts_mod.compute(more["data"].get("facts") or [], tables, start=len(fact_list) + 1, existing=fact_list)
            fact_list.extend(new)
            facts_mod.save(run, fact_list)
            add, cp = claims_mod.resolve(more["data"].get("claims") or [], fact_list)
            add = [c for c in add if c.get("id") not in {x["id"] for x in claims}]
            add, cp2, _ = claims_mod.validate(claims + add, fact_list, tables)
            add = [c for c in add if c["id"] not in {x["id"] for x in claims}]
            claims.extend(add)
            claims_mod.save(run, claims)
            log(run, f"round {rnd}: {len(new)} more facts, {len(add)} more claims for {len(asks)} requests ({len(probs)} could not be computed)")
        except roles.RoleError as e:
            log(run, f"round {rnd}: more facts failed: {e}")

    def infer(draft, charts, stage_name):
        """The inference test on a draft (R4): its contradictions are blocking issues of kind framing."""
        if not ccfg.get("inference", True):
            return {"blocking": [], "advisory": [], "conclusions": []}
        try:
            res = inference_mod.run_test(run, draft, charts, {f["id"]: f for f in fact_list}, claims, claims_mod.load_map(run))
            inference_mod.record(run, res, stage_name)
            return res
        except roles.RoleError as e:
            log(run, f"inference: failed ({e})")
            return {"blocking": [], "advisory": [{"owner": "inference", "issue": f"the inference test failed: {e}"}], "conclusions": []}

    built, mech = write()
    earlier: list[dict] = []          # every blocking issue raised so far (R6 keys them by path and claim)
    prev_draft, prev_charts = None, {}
    for rnd in range(1, rounds + 1):
        draft, charts = built["draft"], built["charts"]
        cmap = claims_mod.load_map(run)
        fmap_ = {f["id"]: f for f in fact_list}
        stage(run, "desk-review", state="running", started=runlib.now())
        packets = review_packets(draft, fact_list, charts, tables, brief, mech, claims, cmap)
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = {r: ex.submit(roles.call, run, r, packets[r]) for r in ("referee", "checker")}
            inf_f = ex.submit(infer, draft, charts, f"round {rnd}")
            got = {}
            for r, f in futs.items():
                try:
                    got[r] = f.result().get("data") or {}
                except roles.RoleError as e:
                    got[r] = {"error": str(e)}
                    log(run, f"review round {rnd}: {r} failed: {e}")
            inf = inf_f.result()
        blocking = ([{"owner": "mechanical", "issue": b} for b in mech["blocking"]]
                    + [{"owner": "referee", **b} for b in got["referee"].get("blocking") or []]
                    + [{"owner": "checker", **b} for b in got["checker"].get("blocking") or []]
                    + inf["blocking"])
        demoted = []
        if rnd > 1 and cfg["loop"].get("converge", True):
            blocking, demoted = converge(blocking, earlier, _changed_paths(prev_draft, draft, prev_charts, charts), draft, charts, fmap_)
        else:
            for b in blocking:
                b["paths"] = _paths_of(b, draft, charts, fmap_)
        earlier += blocking
        advisory = ([{"owner": "mechanical", "issue": a} for a in mech["advisory"]]
                    + [{"owner": "referee", **a} for a in got["referee"].get("advisory") or []]
                    + [{"owner": "checker", **a} for a in got["checker"].get("advisory") or []]
                    + inf["advisory"] + demoted)
        record = {"round": rnd, "kind": "review", "blocking": blocking, "advisory": advisory, "stats": mech["stats"],
                  "referee_verdict": got["referee"].get("verdict"), "strongest": got["referee"].get("strongest"),
                  "inference": [{k: x.get(k) for k in ("says", "verdict", "claims", "why")} for x in inf.get("conclusions") or []],
                  "demoted": len(demoted), "cost_usd_so_far": roles.spent(run)}
        write_json(run / "reviews" / f"round-{rnd}.json", record)
        history.append({"round": rnd, "kind": "review", "blocking": len(blocking), "advisory": len(advisory), "words": mech["stats"]["words"],
                        "demoted": len(demoted)})
        log(run, f"round {rnd}: {len(blocking)} blocking ({len(inf['blocking'])} framing), {len(advisory)} advisory "
                 f"({len(demoted)} raised late on unchanged strings), {mech['stats']['words']} words, "
                 f"referee {got['referee'].get('verdict')}, USD {roles.spent(run):.2f}")
        if not blocking or _budget_left(run) <= 0.4:
            break
        more_facts((answer.get("need_facts") or []) + (got["referee"].get("need_facts") or []), rnd)
        reviews = {"must_fix": [{"n": i + 1, **{k: v for k, v in b.items() if k != "paths"}} for i, b in enumerate(blocking)],
                   "consider": advisory[:25], "keep": got["referee"].get("strongest"),
                   "skimming_reader": record["inference"]}
        prev_draft, prev_charts = json.loads(json.dumps(draft)), json.loads(json.dumps(charts))
        built, mech = write(reviews)
        if rnd < rounds:
            continue
        # The closing pass. Reviewers find new things in every draft, so a note could be revised for ever. After the
        # last full review the writer revises once more, and a verifier checks only whether each listed issue is
        # fixed (and reports a plain error of fact if the revision introduced one). What is not fixed stays blocking.
        # The writer's wording is taken only for the strings the list names (R6, the --only machinery of updates).
        listed = [b for b in reviews["must_fix"] if b["owner"] not in ("mechanical",)]
        for closing in range(1, cfg["loop"].get("closing_passes", 2) + 1):
            draft, charts = built["draft"], built["charts"]
            fmap_ = {f["id"]: f for f in fact_list}
            left = [{"owner": "mechanical", "issue": b} for b in mech["blocking"]]
            how = {}
            if listed:
                v = roles.call(run, "verifier", "## The must-fix list\n" + _j(listed) + "\n\n## The new draft\n"
                               + text.article(draft, fmap_, charts, "review") + "\n\n## Fact sheet\n" + facts_mod.sheet(fact_list)
                               + ("\n\n## Claim ledger\n" + claims_mod.sheet(claims, fmap_) if claims else ""))["data"]
                how = {it.get("n"): it for it in v.get("items") or []}
                left += [{**b, "not_fixed": (how.get(b["n"]) or {}).get("how")} for b in listed if not (how.get(b["n"]) or {}).get("fixed")]
                left += [{"owner": "verifier", "kind": "fact", **e} for e in v.get("new_errors") or []]
            inf = infer(draft, charts, f"closing {closing}")
            left += [b for b in inf["blocking"] if not any(x.get("owner") == "inference" and x.get("quote") == b.get("quote") for x in left)]
            n = len(history) + 1
            record = {"round": n, "kind": "closing", "blocking": left,
                      "advisory": [{"owner": "mechanical", "issue": a} for a in mech["advisory"]] + inf["advisory"], "stats": mech["stats"],
                      "fixed": [{"n": b["n"], "owner": b["owner"], "issue": b.get("issue"), "how": (how.get(b["n"]) or {}).get("how")}
                                for b in listed if (how.get(b["n"]) or {}).get("fixed")],
                      "inference": [{k: x.get(k) for k in ("says", "verdict", "claims", "why")} for x in inf.get("conclusions") or []],
                      "cost_usd_so_far": roles.spent(run)}
            write_json(run / "reviews" / f"round-{n}.json", record)
            history.append({"round": n, "kind": "closing", "blocking": len(left), "advisory": len(record["advisory"]),
                            "words": mech["stats"]["words"], "fixed": len(record["fixed"])})
            log(run, f"closing {closing}: {len(record['fixed'])} of {len(listed)} listed issues fixed, {len(left)} blocking left, "
                     f"{mech['stats']['words']} words, USD {roles.spent(run):.2f}")
            if not left or closing == cfg["loop"].get("closing_passes", 2) or _budget_left(run) <= 0.6:
                break
            # what the first closing pass left (an item not fixed, an error the last revision brought in) gets one more
            # revision, and the verifier then looks only at those
            listed = [{"n": i + 1, **{k: v for k, v in b.items() if k != "n"}} for i, b in enumerate(left) if b["owner"] != "mechanical"]
            only = None
            if cfg["loop"].get("scoped_closing", True):
                paths = [p for b in left for p in (b.get("paths") or _paths_of(b, draft, charts, fmap_))]
                located = all((b.get("paths") or _paths_of(b, draft, charts, fmap_)) for b in left if b["owner"] != "mechanical")
                only = sorted(set(paths)) if paths and located and not any(b["owner"] == "mechanical" for b in left) else None
            built, mech = write({"must_fix": [{"n": i + 1, **{k: v for k, v in b.items() if k not in ("n", "paths")}} for i, b in enumerate(left)],
                                 "note": "Only these remain. Change nothing else." + (f" Only these strings will be taken from your answer: {only}." if only else "")},
                                only=only)
    # --- the polish: Fable rewrites the English for plain reading, held to every check the note passed (desk/polish.py)
    stage(run, "desk-polish", state="running", started=runlib.now())
    answer, built, mech, prep = polish_mod.english(run, answer, brief, tables, fact_list, catalog, claims)
    _done(run, "desk-polish", note=f"English {prep['status']}")
    log(run, f"polish: English {prep['status']} after {prep['attempts']} call(s), {prep.get('words_before')} → {prep.get('words_after') or prep.get('words_before')} words"
             + (f"; {prep['problems'][:2]}" if prep.get("problems") else "") + f", USD {roles.spent(run):.2f}")
    draft, charts = built["draft"], built["charts"]
    placed = [b.get("chart") for sec in draft.get("sections", []) for b in sec.get("blocks", []) if b.get("type") == "figure"]
    cov = cover_mod.make(run, charts, placed)        # the list's picture: an echo of the first figure, drawn by code
    if not cov.get("ok"):
        log(run, f"cover left out: {cov.get('blocking')}")
    _done(run, "desk-writer", note=f"{len(history)} rounds")
    last = read_json(run / "reviews" / f"round-{len(history)}.json")
    # --- judge: once, a second time only near the bar (R7)
    stage(run, "desk-judge", state="running", started=runlib.now())
    fmap = {f["id"]: f for f in fact_list}
    con = mech["stats"]
    judged = text.article(draft, fmap, charts, "judged", sources=review.source_lines(catalog, con["cited"]), date=today)
    (run / "desk" / "judged.txt").write_text(judged, encoding="utf-8")
    bar = judge_mod.bar(cfg)
    score = judge_mod.score_note(run, judged, bar, cfg)
    verdict = judge_mod.decide(score, bar, last["blocking"], cfg)
    write_json(run / "desk" / "score.json", {"score": score, "bar": bar, "verdict": verdict})
    _done(run, "desk-judge", note=f"mean {score['mean']:.2f} against bar {bar['pass_mean']:.2f}: {verdict['status']} ({score['judges']} judge(s))")
    _done(run, "desk-review", note=f"{len(last['blocking'])} blocking left")
    # --- the pipeline's review file, the result and the memory
    write_json(run / "review.json", {
        "status": "pass" if verdict["status"] == "pass" else "changes_required", "rounds": len(history),
        "blocking": [{"where": b.get("where") or b["owner"], "issue": b.get("issue"), "owner": "draft-article", "fix": b.get("fix")} for b in last["blocking"]],
        "advisory": [{"where": a.get("where") or a["owner"], "issue": a.get("issue")} for a in last["advisory"]],
        "checks": {"mechanical": {"blocking": mech["blocking"], "advisory": mech["advisory"]}, "desk": con, "judge": score}})
    from ..usage import usage
    cost = usage(run)["total"]["cost_usd"]
    result = {"run": run.name, "status": "queued" if verdict["status"] == "pass" else "shelved", "slug": built["slug"],
              "title": text._plain(draft.get("title") or "", fmap), "lead": lead["key"], "screen": lead["screen"], "rounds": history, "score": score["mean"],
              "bar": bar["pass_mean"], "verdict": verdict, "cost_usd": cost, "words": con["words"], "apps": con["apps"],
              "publishers": con["publishers"], "facts": len(fact_list), "claims": len(claims), "network_calls": api.calls,
              **({"rewrite_of": brief["rewrite_of"]} if brief.get("rewrite_of") else {}),
              **({"idea": chosen["ref"]} if chosen else {})}
    write_json(run / "desk" / "result.json", result)
    # --- the Korean edition: every string drafted by qkr from the finished English (korean.py). It is written whenever
    # qkr answers; a string qkr could not draft to the checks shows its draft and waits beside the note for the editor.
    stage(run, "desk-korean", state="running", started=runlib.now())
    from . import korean, queue as queue_mod
    try:
        ko = korean.make(run)
        if ccfg.get("inference_korean", True) and ko.get("written"):
            ko = korean_inference(run, fact_list, claims) or ko
    except Exception as e:      # the English note is finished; a failure here is reported, and `desk daily` tries again
        ko = {"complete": False, "error": f"{type(e).__name__}: {e}", "open": []}
    try:      # the print proof: a note the editor approves must also print (queue.proof_pdf)
        queue_mod.proof_pdf(run)
    except Exception:
        pass
    placed_ = queue_mod.settle(run)
    _done(run, "desk-korean", note=("complete" if ko.get("complete") else ko.get("error") or "written with open points") + f", {len(ko.get('open') or [])} open")
    result = read_json(run / "desk" / "result.json")
    result["cost_usd"] = cost = usage(run)["total"]["cost_usd"]
    write_json(run / "desk" / "result.json", result)
    log(run, f"korean: {'complete' if ko.get('complete') else 'not complete'}, {len(ko.get('open') or [])} open, "
             f"{ko.get('seconds')}s; the note is {placed_.get('status')}")
    soft = cfg["budget"].get("soft_usd_first_queue")
    if soft and roles.spent(run) > soft:
        log(run, f"WARNING: the English cost USD {roles.spent(run):.2f} before its first queueing, over the soft target of USD {soft:.0f}")
    leads_mod.record({"key": lead["key"], "screen": lead["screen"], "run": run.name, "title": result["title"],
                      "outcome": result["status"], "score": score["mean"], "cost_usd": cost})
    if not offline and snap and not brief.get("rewrite_of"):
        watch.commit(snap)
    log(run, f"done: {result['status']}, score {score['mean']:.2f} (bar {bar['pass_mean']:.2f}), USD {cost:.2f}")
    return result


def _scoped(new: dict, prev: dict, only: list[str]) -> dict:
    """A closing pass's answer, taken only for the strings it was asked to fix (R6; queue._limit for the draft): the
    draft keeps every other string of the previous answer, the figures keep their previous specs unless one of their
    strings was named, and the claim map keeps the previous claims for the strings left alone."""
    from .queue import _limit
    if not isinstance(new.get("draft"), dict) or not isinstance(prev.get("draft"), dict):
        return new
    out = dict(new)
    dpaths = sorted({_surface_key(p) if p.startswith(("keyNumbers", "findings")) else p for p in only if not p.startswith("figure:")})
    out["draft"] = _limit(new["draft"], prev["draft"], dpaths)
    figs = {p.split(":", 1)[1].split(".")[0] for p in only if p.startswith("figure:")}
    newf = {f.get("id"): f for f in new.get("figures") or [] if isinstance(f, dict)}
    out["figures"] = [newf.get(f.get("id"), f) if f.get("id") in figs else f for f in prev.get("figures") or [] if isinstance(f, dict)]
    pm, nm = claims_mod.claim_map(prev), claims_mod.claim_map(new)
    out["claims"] = {k: (nm.get(k, v) if any(k == _surface_key(p) or k == p for p in only) else v) for k, v in pm.items()}
    out["need_facts"] = new.get("need_facts") or []
    out["related_reading"] = prev.get("related_reading")
    return out


def korean_inference(run: Path, fact_list: list[dict], claims: list[dict]) -> dict | None:
    """The inference test on the Korean edition's surface (R4, R8). A Korean reading the claims contradict goes back to
    the side-by-side reader as a point (kind framing), which answers with English for qkr to draft again; the test then
    reads the Korean once more. Every Korean word stays qkr's."""
    from . import korean
    fmap = {f["id"]: f for f in fact_list}
    cmap = claims_mod.load_map(run)
    surf = inference_mod.korean_surface(run, fmap)
    if not surf:
        return None
    res = inference_mod.run_test(run, {}, {}, fmap, claims, cmap, lang="ko", surf=surf, label="korean")
    inference_mod.record(run, res, "korean")
    ids = {"title": "d:title", "dek": "d:dek"}
    # a Korean reading the English claims do not support (the Korean says something the English does not: "fell from
    # 50% to 46%" for two groups compared, r6 on 18 Nov 2026) goes back as a point too
    extra = [{"where": ", ".join(x.get("from") or []), "issue": f"a reader of the Korean concludes “{x['says']}”, which the English and its claims do not say"}
             for x in res["conclusions"] if x["verdict"] == "unsupported" and x.get("from")]
    points = []
    for b in res["blocking"] + extra:
        for key in str(b.get("where") or "").split(", "):
            k = _surface_key(key)
            sid = ids.get(k) or (f"d:keyNumbers/{k.split('.')[1]}/label" if k.startswith("keyNumbers.") else
                                 f"d:findings/{k.split('.')[1]}" if k.startswith("findings.") else
                                 f"c:{k.split(':', 1)[1]}:headline" if k.startswith("figure:") else None)
            if sid:
                points.append({"id": sid, "problem": f"framing: {b['issue']}. The English states its claim with the comparison; "
                                                     "reword the English so qkr keeps the comparison and does not present a count as a result"})
    if not points:
        return None
    ko = korean.make(run, points=points)
    res2 = inference_mod.run_test(run, {}, {}, fmap, claims, cmap, lang="ko", surf=inference_mod.korean_surface(run, fmap), label="korean")
    inference_mod.record(run, res2, "korean, after the framing points")
    return ko
