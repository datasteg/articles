"""The review queue: from a finished desk run to the editor's decision and back.

Out: every note waiting for the editor is written as a packet into the ledger folder
(/data/articles/ledger/desk/), which rides to the admin site in the private admin image like the Newsroom's run
ledger (never in git). The packet is what the editor needs to decide: the note as readers will see it, its figures as
data, its sources, the judge's scores beside the benchmark's, what the reviewers left, the cost.

Back: the admin site records a decision (approve, return with a note, reject) in its own database and writes one
line to its container log: `DESK-DECISION {json}`. The desk reads the line back
from that log, read-only (read_admin_log). A decision counts only when
its line comes from the admin app's container, names a note that is waiting, and carries the digest of exactly the
packet the editor saw; with DESK_SIGNING_KEY set on both sides it must also carry a valid signature.

Only an approval opens the publish gate, and only `artools ship` publishes: commit, push, deploy, as for any article.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import hmac
import json
import re
import shutil
import subprocess

from .. import runlib
from ..paths import DATA, RUNS, env_value, read_json, read_jsonl, write_json
from . import claims as claims_mod, config, facts as facts_mod, inference as inference_mod, judge as judge_mod, korean, leads as leads_mod, review, roles, text
from .api import DESK

LEDGER = DATA / "ledger" / "desk"
DECISIONS = DESK / "decisions.jsonl"          # every decision this machine has processed
LINE = re.compile(r"^admin-1\s*\|\s*(?:\S+\s+)?DESK-DECISION (\{.*\})\s*$")
WAITING = ("queued", "shelved", "returned")
REMOVED = DESK / "removed.json"               # records the editor removed on the admin site (20 Nov 2026)
IDEA_REF = re.compile(r"ideas:\d{4}-\d{2}-\d{2}(?::Q\d+)?")


def removed() -> set[str]:
    """What the editor removed on the admin site: desk runs, a day of ideas (ideas:<date>) or one question
    (ideas:<date>:<Q id>). A removed note leaves the queue (a waiting one is withdrawn); a removed idea leaves the preview."""
    return set((read_json(REMOVED, {}) or {}).get("refs") or [])


def remove(ref: str, decision: str | None = None) -> dict:
    refs = removed()
    if ref.startswith("ideas:"):
        out = {"removed": ref}
    else:
        run = RUNS / ref
        out = {"removed": ref, "was": state(run)}
        if state(run) in WAITING:
            out["withdrawn"] = withdraw(ref, f"removed by the editor on the admin site (decision {decision})").get("withdrawn")
    write_json(REMOVED, {"refs": sorted(refs | {ref}), "at": runlib.now()})
    return out


def _result(run) -> dict | None:
    return read_json(run / "desk" / "result.json", None)


def digest(run) -> str:
    """What the editor approves: both editions of the draft, its charts and its facts. Any change gives another digest."""
    h = hashlib.sha256()
    for p in [run / "draft" / "en.json", run / "draft" / "ko.json", run / "analysis" / "analysis.json", *sorted((run / "charts").glob("*.json"))]:
        if p.is_file():
            h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:20]


def state(run) -> str:
    """queued | shelved | returned | approved | published | rejected | failed"""
    r = _result(run) or {}
    if (read_json(run / "publish.json", {}) or {}).get("tag"):
        return "published"
    d = read_json(run / "desk" / "decision.json", {}) or {}
    if d.get("decision") == "reject":
        return "rejected"
    if d.get("decision") == "approve" and d.get("digest") == digest(run):
        return "approved"
    if d.get("decision") == "return" and d.get("digest") == digest(run):
        return "returned"
    return r.get("status") or "failed"


def busy(run) -> bool:
    """A desk stage of this note is still running in another process (`desk note` or `desk revise` in its Korean stage):
    the daily job leaves the note alone. On 19 Nov 2026 the 19:10 job drafted 20261114-desk-t4-r2's Korean while the
    note's own Korean stage was still at it; the two wrote the same ledger and the last write had no summary. A stage
    marked running for more than six hours is taken as a crashed process, not a busy one."""
    st = (read_json(run / "run.json", {}) or {}).get("stages") or {}
    now = dt.datetime.now(dt.timezone.utc)
    for v in st.values():
        if isinstance(v, dict) and v.get("state") == "running":
            try:
                started = dt.datetime.fromisoformat(str(v.get("started")).replace("Z", "+00:00"))
            except ValueError:
                return True
            if now - started < dt.timedelta(hours=6):
                return True
    return False


def proof_pdf(run) -> dict:
    """Print the note's PDF proof when there is none or it is older than the note (`artools render pdf`), and return
    pdf.check. A note the editor approves must also print: t8's approval (17 Nov 2026) stopped at the ship on a chart
    label the print drew outside its plot, because the desk had never printed the rewritten note."""
    from .. import pdf
    chk = pdf.check(run)
    if any("no proof" in b or "older than" in b or "no PDF" in b for b in chk["blocking"]):
        dg = digest(run)
        if (read_json(run / "desk" / "pdf-attempt.json", {}) or {}).get("digest") == dg:
            return chk       # already printed for this version and failed: not again every hour (17 Nov 2026: 50 minutes a run)
        try:
            res = pdf.proof(run.name)
            # the first print after a preview rebuild can answer 404 (a known make-pdf quirk): print once more
            if any("answered 404" in x for e in (res.get("editions") or {}).values() for x in e.get("problems") or []):
                res = pdf.proof(run.name)
            chk = res["check"]
        except (Exception, SystemExit) as e:      # artools' die() exits: a proof that cannot print is a held reason, not a crash
            chk = {"blocking": [f"the proof could not be printed: {type(e).__name__}: {str(e)[:300]}"], "advisory": []}
        write_json(run / "desk" / "pdf-attempt.json", {"digest": dg, "at": runlib.now(), "blocking": chk["blocking"]})
    return chk


def settle(run) -> dict:
    """The note's place in the queue, from what is on disk: the judge's verdict on the English and the state of the
    Korean edition. The desk holds a note back (shelved, still on the editor's list) when the English did not pass or
    when there is no Korean edition to read. Open points in a Korean edition do not hold it back: the edition shows
    qkr's draft for them and lists them beside the note, and the editor decides (16 Nov 2026)."""
    res = _result(run)
    if not res or res.get("status") in ("failed", "no-lead", "withdrawn"):
        return {"status": (res or {}).get("status")}
    verdict = (read_json(run / "desk" / "score.json", {}) or {}).get("verdict") or {}
    held = [] if verdict.get("status") == "pass" else [f"English: {r}" for r in verdict.get("reasons") or ["below the bar"]]
    # what the print proof found (a chart drawn outside its plot, a table wider than the column): the ship would stop
    # on it, so the note is held with the reason. A proof older than the note is printed again by proof_pdf, not here
    from .. import pdf
    if (run / "pdf" / "proof.json").is_file():
        held += [f"PDF: {b}" for b in pdf.check(run)["blocking"] if not ("older than" in b or "no proof" in b or "no PDF" in b)]
    if res.get("test"):          # a test edition is held whatever its scores: it is for comparison, never published
        held.insert(0, f"Test edition: {res['test']}")
    ko = korean.status(run)
    if config.load()["korean"]["required"]:
        if not ko.get("written"):
            held.append("Korean: " + (ko.get("error") or ("the edition is older than the English draft" if ko.get("stale") else "not made yet")))
    from ..usage import usage
    res.update(status="shelved" if held else "queued", held=held, cost_usd=usage(run)["total"]["cost_usd"],
               korean={k: ko.get(k) for k in ("complete", "written", "flagged", "strings", "reworded", "term_fixes", "seconds", "stale", "missing", "error", "at")}
               | {"open": len(ko.get("open") or []), "qkr_notes": len(ko.get("qkr_notes") or [])})
    write_json(run / "desk" / "result.json", res)
    return {"status": res["status"], "held": held}


def _plot(ch: dict, T) -> dict | None:
    """What the admin page needs to draw a scatter, a dumbbell or a line chart (bars travel as `bars`); a table has none."""
    ax = ch.get("axes") or {}
    axis = lambda a: {"label": T((a or {}).get("label")), "domain": (a or {}).get("domain"), "ticks": (a or {}).get("ticks")}  # noqa: E731
    if ch["form"] == "scatter":
        return {"x": axis(ax.get("x")), "y": axis(ax.get("y")),
                "points": [{"label": T(p.get("label")), "x": p["x"], "y": p["y"], "focus": p.get("group") == "focus"} for p in ch.get("points") or []]}
    if ch["form"] == "dumbbell":
        return {"x": axis(ax.get("x")), "fromLabel": T(ch.get("fromLabel")), "toLabel": T(ch.get("toLabel")),
                "rows": [{"label": T(r.get("label")), "from": r["from"], "to": r["to"], "highlight": bool(r.get("highlight"))} for r in ch.get("rows") or []]}
    if ch["form"] == "line":
        return {"y": axis(ax.get("y")), "x": ch.get("x") or [], "ticks": (ax.get("x") or {}).get("ticks") or [],
                "series": [{"label": T(s.get("label")), "values": s.get("values") or [], "focus": s.get("color") == "focus"} for s in ch.get("series") or []]}
    return None


def _view(draft: dict, fmap: dict, charts: dict, lang: str) -> dict:
    """One edition of the note as the editor reads it: text with its numbers, figures as words and data."""
    P = lambda s: text._plain(s or "", fmap, lang=lang)   # noqa: E731
    T = lambda v: text._tx(v, lang)                        # noqa: E731
    sections = []
    for s in draft.get("sections", []):
        blocks = []
        for b in s.get("blocks", []):
            if b.get("type") == "p":
                blocks.append({"type": "p", "text": P(b.get("text"))})
            elif b.get("type") == "list":
                blocks.append({"type": "list", "items": [P(i) for i in b.get("items", [])]})
            elif b.get("type") == "figure" and b.get("chart") in charts:
                ch = charts[b["chart"]]
                blocks.append({"type": "figure", "id": ch["id"], "form": ch["form"], "headline": T(ch.get("headline")),
                               "title": T(ch.get("title")), "subtitle": T(ch.get("subtitle")),
                               "howToRead": T(ch.get("howToRead")), "notes": [T(n) for n in ch.get("notes") or []],
                               "source": T((ch.get("meta") or {}).get("attribution")),
                               "columns": [{"key": c["key"], "label": T(c.get("label")), "align": c.get("align")} for c in ch["table"]["columns"]],
                               "rows": [{k: (T(v) if isinstance(v, dict) else v) for k, v in r.items()} for r in ch["table"]["rows"][:40]],
                               "bars": [{"label": T(c["label"]), "value": c["value"], "highlight": bool(c.get("highlight"))}
                                        for c in ch.get("categories") or []] or None,
                               "domain": ((ch.get("axes") or {}).get("x") or {}).get("domain"),
                               "plot": _plot(ch, T)})
        sections.append({"id": s.get("id"), "heading": P(s.get("heading")), "blocks": blocks})
    return {"title": P(draft.get("title")), "kicker": draft.get("kicker"), "dek": P(draft.get("dek")),
            "whyNow": P(draft.get("whyNow")) or None,
            "keyNumbers": [{"value": P(k.get("value")), "label": P(k.get("label"))} for k in draft.get("keyNumbers") or []],
            "findings": [P(f) for f in draft.get("findings") or []],
            "question": {k: P(v) for k, v in (draft.get("question") or {}).items() if v},
            "sections": sections, "insight": {"label": (draft.get("insight") or {}).get("label"), "text": P((draft.get("insight") or {}).get("text"))},
            "reproduce": draft.get("reproduce")}


def packet(run) -> dict:
    """The review packet of one note."""
    res = _result(run) or {}
    draft = read_json(run / "draft" / "en.json", {}) or {}
    fact_list = facts_mod.load(run)
    fmap = {f["id"]: f for f in fact_list}
    charts = {p.stem: read_json(p) for p in sorted((run / "charts").glob("*.json"))}
    ko_draft = read_json(run / "draft" / "ko.json", None)
    ko = korean.status(run)
    led = read_json(run / "desk" / "korean.json", {}) or {}
    en_of = {s["id"]: s for s in led.get("strings") or []}
    catalog = read_json(run / "data" / "datasteg" / "catalog.json", []) or []
    score = read_json(run / "desk" / "score.json", {}) or {}
    brief = read_json(run / "desk" / "brief.json", {}) or {}
    rounds = [read_json(p) for p in sorted((run / "reviews").glob("round-*.json"))]
    last = rounds[-1] if rounds else {}
    con = ((read_json(run / "review.json", {}) or {}).get("checks") or {}).get("desk") or {}
    from ..usage import usage
    u = usage(run)
    return {
        "run": run.name, "state": state(run), "digest": digest(run), "slug": res.get("slug"), "date": (res.get("run") or run.name)[:8],
        **_view(draft, fmap, charts, "en"),
        # the Korean edition as qkr drafted it, and where it stands: the editor reads both before approving
        "ko": _view(ko_draft, fmap, charts, "ko") if ko_draft else None,
        "korean": {**{k: ko.get(k) for k in ("complete", "written", "flagged", "strings", "reworded", "term_fixes", "stale", "missing", "error", "qkr", "at", "polish")},
                   "open": [{**x, "en": (en_of.get(x.get("id")) or {}).get("sent"),
                             "ko": (en_of.get(x.get("id")) or {}).get("ko") or (en_of.get(x.get("id")) or {}).get("shown")
                             or (en_of.get(x.get("id")) or {}).get("proposed")} for x in ko.get("open") or []],
                   "advisory": ko.get("advisory") or [], "required": config.load()["korean"]["required"],
                   # what qkr should learn from this note's refusals (desk/korean.py qkr_notes); its feedback endpoint got them too
                   "qkr_notes": ko.get("qkr_notes") or [], "feedback_sent": ko.get("feedback_sent"),
                   # the Korean title: qkr's, tuned among qkr's drafts, or the editor's own; the other drafts to pick from
                   "title": ko.get("title")},
        "held": res.get("held") or [],
        # the polish (Fable): what it did to the English (desk/polish.json); the Korean's is under korean.polish
        "polish": (read_json(run / "desk" / "polish.json", {}) or {}).get("en"),
        # a test edition (19 Nov 2026: Fable's edit of 20261118-desk-r6, at the owner's request): shown for comparison,
        # never approvable or published
        "test": res.get("test"),
        "compared_with": res.get("compared_with"),
        "sources": review.source_lines(catalog, con.get("cited") or []),
        "words": con.get("words"), "apps": con.get("apps"), "publishers": con.get("publishers"),
        "lead": {"key": res.get("lead"), "screen": res.get("screen")},
        "brief": {k: brief.get(k) for k in ("question", "thesis", "finding_type", "comparison", "hook", "why_now", "why_these", "conventional", "twist", "concept",
                                            "rival_readings", "rewrite_of")},
        # rule R9: the claims the note makes (with the strings that state each) and what a skimming reader takes
        # away (the inference test on both editions); for a regenerated note, what changed against the note it replaces
        "claims": claims_mod.card(claims_mod.load(run), fmap, claims_mod.load_map(run)) or None,
        "inference": inference_mod.card(run),
        "compared": read_json(run / "desk" / "compared.json", None),
        # the note's data as one ZIP of CSV files (desk/reproduce.py bundle), carried beside the packet for the admin page
        "download": ({"file": f"{run.name}.zip", "bytes": (run / "download" / "data.zip").stat().st_size}
                     if (run / "download" / "data.zip").is_file() else None),
        "score": {"mean": (score.get("score") or {}).get("mean"), "dims": (score.get("score") or {}).get("dims"),
                  "why": {k: (v or [None])[0] for k, v in ((score.get("score") or {}).get("why") or {}).items()},
                  "spread": (score.get("score") or {}).get("spread"), "bar": (score.get("bar") or {}).get("pass_mean"),
                  "bar_from": (score.get("bar") or {}).get("from"),
                  "benchmark": ((score.get("bar") or {}).get("benchmark") or {}), "names": judge_mod.NAMES},
        "verdict": score.get("verdict"),
        "rounds": [{"round": r.get("round"), "blocking": len(r.get("blocking") or []), "advisory": len(r.get("advisory") or [])} for r in rounds],
        "left": {"blocking": [{"owner": b.get("owner"), "issue": b.get("issue"), "fix": b.get("fix")} for b in last.get("blocking") or []],
                 "advisory": [{"owner": a.get("owner"), "issue": a.get("issue")} for a in (last.get("advisory") or [])[:15]]},
        "reader": last.get("reader"),
        "cost": {"usd": u["total"]["cost_usd"], "by_stage": {k: v["cost_usd"] for k, v in u["stages"].items()},
                 "by_model": {k: v["cost_usd"] for k, v in u["models"].items()}},
        "decision": read_json(run / "desk" / "decision.json", None),
        "published": read_json(run / "publish.json", None),
        "ship": read_json(run / "desk" / "ship.json", None),
    }


def withdraw(run_id: str, why: str) -> dict:
    """The desk takes a note back before the editor decides: a data or code error was found after it was queued.
    Not an editorial decision: the note leaves the queue and its lead may be written again."""
    run = RUNS / run_id
    res = _result(run)
    if not res or state(run) not in WAITING:
        return {"run": run_id, "withdrawn": False, "why": f"the note is {state(run) if res else 'not a desk run'}"}
    res.update(status="withdrawn", withdrawn={"at": runlib.now(), "why": why})
    write_json(run / "desk" / "result.json", res)
    leads_mod.record({"key": res.get("lead"), "screen": res.get("screen"), "run": run.name, "title": res.get("title"),
                      "outcome": "withdrawn", "note": why})
    return {"run": run_id, "withdrawn": True}


def desk_runs() -> list:
    return [p.parent.parent for p in sorted(RUNS.glob("*/desk/result.json"))]


def export(deploy: bool = False, keep_decided: int = 15) -> dict:
    """Write the queue into the ledger folder; with deploy, send it to the admin site."""
    (LEDGER / "notes").mkdir(parents=True, exist_ok=True)
    gone = removed()
    notes = []
    for run in desk_runs():
        r = _result(run) or {}
        if r.get("status") in ("failed", "no-lead", "withdrawn") or not (run / "draft" / "en.json").is_file() or run.name in gone:
            continue
        notes.append(packet(run))
    # a note the desk held back stays on the editor's list for two weeks, then drops off it (the run stays on disk)
    cutoff = (dt.date.today() - dt.timedelta(days=14)).strftime("%Y%m%d")
    notes = [n for n in notes if not (n["state"] == "shelved" and n["run"][:8] < cutoff)]
    waiting = [n for n in notes if n["state"] in WAITING]
    decided = [n for n in notes if n["state"] not in WAITING][-keep_decided:]
    keep = {n["run"] for n in waiting + decided}
    for f in [*(LEDGER / "notes").glob("*.json"), *(LEDGER / "notes").glob("*.zip")]:
        if f.stem not in keep:
            f.unlink()
    for n in waiting + decided:
        write_json(LEDGER / "notes" / f"{n['run']}.json", n)
        z = RUNS / n["run"] / "download" / "data.zip"
        if n.get("download") and z.is_file():
            shutil.copyfile(z, LEDGER / "notes" / f"{n['run']}.zip")
        else:
            (LEDGER / "notes" / f"{n['run']}.zip").unlink(missing_ok=True)
    acked = [d["id"] for d in read_jsonl(DECISIONS) if d.get("id")]
    q = {"acked": acked[-500:],
        "bar": judge_mod.bar(config.load()),
        "notes": [{k: n.get(k) for k in ("run", "state", "digest", "title", "date", "words", "apps", "held")}
                  | {"title_ko": (n.get("ko") or {}).get("title"), "korean": bool(n.get("ko")),
                     "korean_open": len((n.get("korean") or {}).get("open") or []),
                     "ship_error": (n.get("ship") or {}).get("error") if n["state"] == "approved" else None,
                     "score": n["score"]["mean"], "bar": n["score"]["bar"], "cost_usd": n["cost"]["usd"],
                     "verdict": (n.get("verdict") or {}).get("status"), "lead": n["lead"]["key"]} for n in waiting + decided]}
    # `desk daily` runs every hour: an unchanged queue keeps its build time, so the admin site is not redeployed for it
    q = json.loads(json.dumps(q, ensure_ascii=False))
    old = read_json(LEDGER / "queue.json", {}) or {}
    same = {k: v for k, v in old.items() if k != "built"} == q
    write_json(LEDGER / "queue.json", {"built": old.get("built") if same else runlib.now(), **q})
    # the ideas preview (desk/ideas.py, 20 Nov 2026): the last two weeks, shown on the admin site
    from . import ideas as ideas_mod
    (LEDGER / "ideas").mkdir(parents=True, exist_ok=True)
    keep_i = {p.name for p in ideas_mod.recent()}
    for f in (LEDGER / "ideas").glob("*.json"):
        if f.name not in keep_i:
            f.unlink()
    for p in ideas_mod.recent():
        d = read_json(p, {}) or {}
        if f"ideas:{d.get('date')}" in gone:
            (LEDGER / "ideas" / p.name).unlink(missing_ok=True)
            continue
        d["questions"] = [q for q in d.get("questions") or [] if f"ideas:{d.get('date')}:{q.get('id')}" not in gone]
        if (read_json(LEDGER / "ideas" / p.name, None) or None) != json.loads(json.dumps(d, ensure_ascii=False)):
            write_json(LEDGER / "ideas" / p.name, d)
    out = {"waiting": [n["run"] for n in waiting], "decided": len(decided), "dir": str(LEDGER)}
    if deploy:
        from ..ledger import deploy_admin
        out["admin"] = deploy_admin()
    return out


# ------------------------------------------------------------------ decisions

def _signature(d: dict, key: str) -> str:
    # the editor's Korean title is signed too when it is there (an older line without it signs as before)
    msg = "|".join(str(d.get(k) or "") for k in ("id", "run", "digest", "decision", "at", "note") + (("title_ko",) if d.get("title_ko") else ()))
    return hmac.new(key.encode(), msg.encode(), hashlib.sha256).hexdigest()


def read_admin_log(lines: int = 4000) -> list[dict]:
    """Decision lines from the admin app's container log, oldest first."""
    r = subprocess.run(["ds", "logs", "admin", str(lines)], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"ds logs admin failed: {(r.stdout + r.stderr)[-300:]}")
    return parse_log(r.stdout)


def parse_log(text_: str) -> list[dict]:
    out = []
    for line in text_.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        try:
            d = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("id") and d.get("run") and d.get("decision") in ("approve", "return", "reject", "retitle"):
            out.append(d)
    return out


def check_decision(d: dict) -> str | None:
    """Why a decision cannot be applied, or None."""
    if d.get("decision") == "remove":
        key = env_value("DESK_SIGNING_KEY")
        if key and not hmac.compare_digest(str(d.get("sig") or ""), _signature(d, key)):
            return "the signature does not match DESK_SIGNING_KEY"
        ref = str(d["run"])
        if IDEA_REF.fullmatch(ref):
            return None
        if not re.fullmatch(r"[A-Za-z0-9._-]+", ref) or not (RUNS / ref / "desk" / "result.json").is_file():
            return "no such desk run"
        return None
    run = RUNS / str(d["run"])
    if not re.fullmatch(r"[A-Za-z0-9._-]+", str(d["run"])) or not (run / "desk" / "result.json").is_file():
        return "no such desk run"
    key = env_value("DESK_SIGNING_KEY")
    if key and not hmac.compare_digest(str(d.get("sig") or ""), _signature(d, key)):
        return "the signature does not match DESK_SIGNING_KEY"
    if state(run) not in WAITING:
        return f"the note is {state(run)}, not waiting for a decision"
    if d.get("digest") != digest(run):
        return "the note changed after the editor saw it (digest differs); it must be reviewed again"
    if d.get("decision") in ("approve", "return") and (_result(run) or {}).get("test"):
        # a return revises the note (writer, polish, Korean: about USD 10); a test copy is never published, so it is
        # never revised (19 Nov 2026: a title note returned on 20261119-desk-ko3 rewrote the copy's English and Korean)
        return f"a test edition for comparison only ({(_result(run) or {}).get('test')}); it is never published"
    if (d.get("decision") == "approve" or d.get("title_ko")) and config.load()["korean"]["required"] and not korean.status(run).get("written"):
        return "there is no Korean edition for this version; a note is published in both languages"
    if d.get("decision") == "retitle" and not d.get("title_ko"):
        return "a retitle decision carries no Korean title"
    if d.get("title_ko"):
        t = str(d["title_ko"]).strip()
        if "\n" in t or not korean.HANGUL.search(t) or len(t) > 120:
            return "the Korean title must be one line of Korean, at most 120 characters"
    return None


def apply(d: dict, dry_run: bool = False) -> dict:
    """Apply one decision. An approval opens the publish gate and ships the note."""
    why = check_decision(d)
    out = {"id": d["id"], "run": d["run"], "decision": d["decision"]}
    if why:
        return {**out, "applied": False, "why": why}
    if dry_run:
        return {**out, "applied": False, "why": "dry run"}
    if d["decision"] == "remove":
        return {**out, "applied": True, **remove(str(d["run"]), d.get("id"))}
    run = RUNS / d["run"]
    cfg = config.load()
    if d.get("title_ko"):
        # the editor's own Korean title, used as written (never a model's), before the decision itself
        try:
            korean.set_editor(run, "d:title", str(d["title_ko"]), by=cfg["approval"]["by"], decision=d["id"])
            out["title_ko"] = "set"
        except ValueError as e:
            return {**out, "applied": False, "why": f"the Korean title was not set: {e}"}
    if d["decision"] == "retitle":
        # the note keeps waiting; the queue shows the new title, and its digest changes with it
        return {**out, "applied": True}
    write_json(run / "desk" / "decision.json", {"id": d["id"], "decision": d["decision"], "digest": d["digest"], "note": d.get("note"),
                                                "at": d.get("at"), "applied": runlib.now()})
    res = _result(run) or {}
    if d["decision"] == "approve":
        runlib.approve_gate(run, "publish", cfg["approval"]["by"], f"approved in the admin site (decision {d['id']})"
                            + (f": {d['note']}" if d.get("note") else ""))
        out.update(applied=True, **ship(run))
    else:
        leads_mod.record({"key": res.get("lead"), "screen": res.get("screen"), "run": run.name, "title": res.get("title"),
                          "outcome": "returned" if d["decision"] == "return" else "rejected", "note": d.get("note")})
        out.update(applied=True)
    return out


SHIP_TRIES = 6        # an approved note whose ship failed is tried again by every hourly daily, this many times


def ship(run) -> dict:
    """Publish an approved note (`artools ship`: commit, push, deploy). A failure is kept in desk/ship.json, shown to the
    editor in the admin site, and tried again by the next `desk daily` (16 Nov 2026: t8's first ship stopped on
    uncommitted desk code, and nothing said so or tried again)."""
    if (_result(run) or {}).get("test"):
        return {"shipped": None, "error": "a test edition for comparison only; it is never published"}
    before = (read_json(run / "publish.json", {}) or {}).get("deployed_at")
    r = subprocess.run(["artools", "ship", run.name], capture_output=True, text=True, timeout=5400)
    pub = read_json(run / "publish.json", {}) or {}
    # shipped means deployed now: an update's publish.json already holds the first publication's tag (17 Nov 2026: a
    # broken CLI never started, and the old tag read as a success)
    shipped = pub.get("tag") if r.returncode == 0 and pub.get("deployed_at") and pub.get("deployed_at") != before else None
    prev = read_json(run / "desk" / "ship.json", {}) or {}
    rec = {"at": runlib.now(), "tries": int(prev.get("tries") or 0) + 1, "tag": shipped,
           "error": None if shipped else _ship_error(r.stdout + r.stderr)}
    write_json(run / "desk" / "ship.json", rec)
    if shipped:
        res = _result(run) or {}
        leads_mod.record({"key": res.get("lead"), "screen": res.get("screen"), "run": run.name, "title": res.get("title"),
                          "outcome": "published"})
    return {"shipped": shipped, "ship_error": rec["error"], "ship_tries": rec["tries"]}


def _ship_error(out: str) -> str:
    """What stopped the ship, in a line or two: artools' `error` field when it printed one, else the end of its output."""
    try:
        j = json.loads(out[out.index("{"):])
        if isinstance(j, dict) and j.get("error"):
            more = j.get("changes") or j.get("blocking") or []
            return (str(j["error"]) + (f" ({len(more)}: {', '.join(str(x).strip() for x in more[:5])}…)" if more else ""))[:600]
    except ValueError:
        pass
    return out.strip()[-600:]


def _remember(d: dict, result: dict) -> None:
    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    with DECISIONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**d, "result": result, "processed": runlib.now()}, ensure_ascii=False) + "\n")


def sync(dry_run: bool = False, lines: list[dict] | None = None) -> dict:
    """Read the editor's decisions and apply the new ones, oldest first."""
    cfg = config.load()
    if lines is None:
        if cfg["approval"]["source"] != "ssh-logs":
            return {"error": f"approval.source {cfg['approval']['source']} is not implemented"}
        lines = read_admin_log()
    seen = {d.get("id") for d in read_jsonl(DECISIONS)}
    results = []
    for d in lines:
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        r = apply(d, dry_run)
        results.append(r)
        if not dry_run:
            _remember(d, r)
    return {"read": len(lines), "new": len(results), "results": results}


def decide_local(run_id: str, decision: str, by: str, note: str | None, title_ko: str | None = None) -> dict:
    """A decision made in the editor's own terminal, applied as the admin site's would be. `title_ko` is the editor's
    own Korean title, as the editor wrote it."""
    run = RUNS / run_id
    d = {"id": f"local-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}", "run": run_id, "digest": digest(run), "decision": decision,
         "note": note, "at": runlib.now(), "by": by, **({"title_ko": title_ko} if title_ko else {})}
    key = env_value("DESK_SIGNING_KEY")
    if key:
        d["sig"] = _signature(d, key)
    r = apply(d)
    _remember(d, r)
    return r


# ------------------------------------------------------------------ a returned note, and the day

def last_answer(run) -> dict | None:
    """The note's last full answer: Fable's polished one (desk/answer.json) when it is newer than the writer's last
    call, else the writer's. A rebuild (refresh) or a rewrite (revise) starts from what readers would see."""
    logs = sorted((run / "logs").glob("desk-writer.*.jsonl"), key=lambda p: int(p.name.split(".")[1]))
    f = run / "desk" / "answer.json"
    if f.is_file() and (not logs or f.stat().st_mtime >= logs[-1].stat().st_mtime):
        return read_json(f)
    return roles.extract_json((roles._result(logs[-1]) or {}).get("result") or "{}") if logs else None


def revise(run_id: str, decision: dict | None = None) -> dict:
    """One more round for a note the editor returned: the editor's note is the writer's must-fix list; the checks,
    the fact-checker and the judge run again; the note goes back in the queue with a new digest. `decision` is an
    update's note on a published note (`update`), in place of the admin site's decision."""
    from . import run as run_mod, tables as tables_mod
    run = RUNS / run_id
    d = decision or read_json(run / "desk" / "decision.json", {}) or {}
    if d.get("decision") != "return":
        return {"run": run_id, "revised": False, "why": "the note was not returned"}
    cfg = config.load()
    cap = cfg["budget"]["usd_per_note"]       # the note's whole English spend, earlier rounds included (Korean not counted)
    if roles.spent(run) >= cap - 1.0:
        res = _result(run) or {}
        res.update(status="shelved", held=(res.get("held") or []) + [f"Budget: USD {roles.spent(run):.2f} of USD {cap:.0f} spent; no rewrite"])
        write_json(run / "desk" / "result.json", res)
        return {"run": run_id, "revised": False, "why": f"the note's budget is spent (USD {roles.spent(run):.2f} of {cap})"}
    tables, fact_list = tables_mod.load(run), facts_mod.load(run)
    catalog = read_json(run / "data" / "datasteg" / "catalog.json", [])
    brief = read_json(run / "desk" / "brief.json", {})
    if cfg["note"].get("require_hook") and not brief.get("hook"):
        # a note written before a hook was required (16 Nov 2026) gets one from the editor, from what the run saw, or
        # is held back: no rewrite gives a note a reason to exist that its data do not
        brief, why = rehook(run, brief)
        if why:
            res = _result(run) or {}
            res.update(status="shelved", held=[f"No reason for today: {why}"])
            write_json(run / "desk" / "result.json", res)
            return {"run": run_id, "revised": False, "why": why}
    analyst = read_json(run / "desk" / "analyst.json", {})
    answer = {"draft": read_json(run / "draft" / "en.json"), "figures": []}
    # an update (a correction after publication) fixes only what the editor named: what the checker finds in strings
    # the rewrite did not touch was already live, and is listed, not rewritten (t8, 17 Nov 2026: a closing pass
    # rewrote a correct sentence of the limits section into a wrong-sign one)
    base = dict(_walk(answer["draft"])) if d.get("scope") else None
    outside: list[dict] = []
    published = copy.deepcopy(answer["draft"]) if d.get("only") else None

    def assemble(ans: dict) -> dict:
        """review.assemble, and for an update with `only` (17 Nov 2026: a correction of the dek also rewrote two other
        sentences) every string outside the named places is put back as published."""
        b = review.assemble(run, ans, brief, tables, fact_list, catalog)
        if published is not None and b.get("draft"):
            b["draft"] = _limit(b["draft"], published, d["only"])
            write_json(run / "draft" / "en.json", b["draft"])
        return b

    def scoped(found: list[dict], draft: dict) -> list[dict]:
        if base is None:
            return found
        changed = [v for k, v in _walk(draft) if isinstance(v, str) and base.get(k) != v]
        keep = []
        for b in found:
            ws = re.findall(r"[A-Za-z]{4,}", b.get("quote") or "")
            if b.get("owner") == "mechanical" or (ws and any(sum(w in c for w in ws) >= 0.7 * len(ws) for c in changed)):
                keep.append(b)
            elif b not in outside:
                outside.append({**b, "outside_correction": True})
        return keep
    prev = last_answer(run) or answer
    reviews = {"must_fix": [{"owner": "editor", "issue": d.get("note") or "the editor returned the note without a comment"}]}
    # a second rewrite for the same decision starts from what the last one left, not from the editor's note alone
    rounds = sorted((run / "reviews").glob("round-*.json"), key=lambda p: int(p.stem.split("-")[1]))
    last = read_json(rounds[-1], {}) if rounds else {}
    if last.get("after") == "returned by the editor" and last.get("decision") == d.get("id"):
        reviews["must_fix"] += [{k: v for k, v in b.items() if k in ("owner", "issue", "fix", "quote", "where")} for b in last.get("blocking") or []]
        reviews["note"] = "The editor's request was met in the last rewrite; keep it met and fix the issues listed after it. Change nothing else."
    if d.get("scope"):
        reviews["note"] = d["scope"]
    reviews["must_fix"] = [{"n": i + 1, **b} for i, b in enumerate(reviews["must_fix"])]
    claims = claims_mod.load(run)

    def inferred(draft_: dict, charts_: dict, stage_: str) -> list[dict]:
        """The inference test on the rewrite (R4): what it contradicts is blocking, kind framing."""
        if not claims or not (cfg.get("claims") or {}).get("inference", True):
            return []
        try:
            res_ = inference_mod.run_test(run, draft_, charts_, {f["id"]: f for f in fact_list}, claims, claims_mod.load_map(run))
            inference_mod.record(run, res_, stage_)
            return res_["blocking"]
        except roles.RoleError:
            return []
    w = roles.call(run, "writer", run_mod.writer_packet(brief, analyst, fact_list, tables, [], catalog, previous=prev, reviews=reviews, claims=claims))
    answer = w["data"]
    answer["_related"] = (read_json(run / "plan.json", {}) or {}).get("related") or []
    built = assemble(answer)
    # what code can see is wrong (a figure that cannot be built, the chart mix, the "Why this note" line, a typed
    # number) goes back to the writer once before the checker and the judge are paid to read it
    early = built["problems"] + (review.mechanical(run, built["draft"], built["charts"], fact_list, tables, catalog)["blocking"] if built["draft"] else [])
    if early:
        w = roles.call(run, "writer", run_mod.writer_packet(brief, analyst, fact_list, tables, [], catalog, previous=answer,
                                                            build_problems=early, claims=claims))
        answer = w["data"]
        answer["_related"] = (read_json(run / "plan.json", {}) or {}).get("related") or []
        built = assemble(answer)
    draft, charts = built["draft"], built["charts"]
    from . import cover as cover_mod
    cover_mod.make(run, charts, [b.get("chart") for sec in draft.get("sections", []) for b in sec.get("blocks", []) if b.get("type") == "figure"])
    mech = review.mechanical(run, draft, charts, fact_list, tables, catalog)
    packets = run_mod.review_packets(draft, fact_list, charts, tables, brief, mech, claims, claims_mod.load_map(run))
    chk = roles.call(run, "checker", packets["checker"])["data"]
    blocking = ([{"owner": "mechanical", "issue": b} for b in [f"build: {p}" for p in built["problems"]] + mech["blocking"]]
                + [{"owner": "checker", **b} for b in chk.get("blocking") or []] + inferred(draft, charts, "revise"))
    blocking = scoped(blocking, draft)
    # the closing passes a new note gets (run.py): what the checks still find goes back to the writer, who changes
    # only that, and the checks read the new draft; a rewrite that only adds what the editor asked for can bring in
    # errors of its own (t8 on 16 Nov: 1,277 words, quantity words without facts)
    for closing in range(cfg["loop"].get("closing_passes", 2)):
        # a closing pass (writer, checker) costs about USD 1; the judge after the loop about USD 0.8
        if not blocking or cap - roles.spent(run) < 2.0:
            break
        listed = [{"n": i + 1, **b} for i, b in enumerate(blocking)]
        w = roles.call(run, "writer", run_mod.writer_packet(brief, analyst, fact_list, tables, [], catalog, previous=answer,
                                                            reviews={"must_fix": listed, "note": "Only these remain. Change nothing else, "
                                                                     "and keep the editor's earlier request met."}, claims=claims),
                       effort=cfg["roles"]["writer"].get("fix_effort") or None)
        answer = w["data"]
        answer["_related"] = (read_json(run / "plan.json", {}) or {}).get("related") or []
        built = assemble(answer)
        if not built["draft"]:
            break
        draft, charts = built["draft"], built["charts"]
        mech = review.mechanical(run, draft, charts, fact_list, tables, catalog)
        packets = run_mod.review_packets(draft, fact_list, charts, tables, brief, mech, claims, claims_mod.load_map(run))
        chk = roles.call(run, "checker", packets["checker"])["data"]
        blocking = ([{"owner": "mechanical", "issue": b} for b in [f"build: {p}" for p in built["problems"]] + mech["blocking"]]
                    + [{"owner": "checker", **b} for b in chk.get("blocking") or []] + inferred(draft, charts, f"revise, closing {closing + 1}"))
        blocking = scoped(blocking, draft)
    # the polish (Fable) on the rewrite; a correction of a published note polishes only the places it may change
    from . import polish as polish_mod
    answer, built, mech, _ = polish_mod.english(run, answer, brief, tables, fact_list, catalog, claims, only=d.get("only"))
    draft, charts = built["draft"], built["charts"]
    blocking = scoped(blocking, draft)
    cover_mod.make(run, charts, [b.get("chart") for sec in draft.get("sections", []) for b in sec.get("blocks", []) if b.get("type") == "figure"])
    n = len(list((run / "reviews").glob("round-*.json"))) + 1
    write_json(run / "reviews" / f"round-{n}.json", {"round": n, "after": "returned by the editor", "decision": d.get("id"), "editor_note": d.get("note"),
                                                     "blocking": blocking, "outside_correction": outside, "advisory": [{"owner": "mechanical", "issue": a} for a in mech["advisory"]],
                                                     "stats": mech["stats"]})
    fmap = {f["id"]: f for f in fact_list}
    judged = text.article(draft, fmap, charts, "judged", sources=review.source_lines(catalog, mech["stats"]["cited"]),
                          date=dt.date.today().isoformat())
    (run / "desk" / "judged.txt").write_text(judged, encoding="utf-8")
    bar = judge_mod.bar(cfg)
    score = judge_mod.score_note(run, judged, bar, cfg)
    verdict = judge_mod.decide(score, bar, blocking, cfg)
    write_json(run / "desk" / "score.json", {"score": score, "bar": bar, "verdict": verdict})
    rv = read_json(run / "review.json", {}) or {}
    rv.update(status="pass" if verdict["status"] == "pass" else "changes_required", rounds=n,
              blocking=[{"where": b.get("where") or b["owner"], "issue": b.get("issue"), "owner": "draft-article",
                         **({"outside_correction": True} if b.get("outside_correction") else {})} for b in blocking + outside],
              checks={**(rv.get("checks") or {}), "desk": mech["stats"], "judge": score})
    write_json(run / "review.json", rv)
    from ..usage import usage
    res = _result(run) or {}
    res.update(status=("published" if decision else "queued") if verdict["status"] == "pass" else "shelved", score=score["mean"], bar=bar["pass_mean"], verdict=verdict,
               title=text._plain(draft.get("title") or "", fmap), words=mech["stats"]["words"], slug=built["slug"])
    write_json(run / "desk" / "result.json", res)
    # the Korean edition follows the English: qkr drafts the strings that changed (an update touches nothing else)
    ko = korean.make(run, only_changed=bool(decision), points=(decision or {}).get("ko_points"))
    proof_pdf(run)
    settle(run)
    res = _result(run) or {}
    res["cost_usd"] = usage(run)["total"]["cost_usd"]
    write_json(run / "desk" / "result.json", res)
    return {"run": run_id, "revised": True, "status": res["status"], "score": score["mean"], "digest": digest(run),
            "korean": {k: ko.get(k) for k in ("complete", "error")} | {"open": len(ko.get("open") or [])}}


def _limit(new: dict, published: dict, only: list[str]) -> dict:  # noqa: D401
    """The published draft with only the named places (dotted paths: dek, insight, sections.2.blocks.5) taken from
    the new one."""
    out = copy.deepcopy(published)
    for path in only:
        keys = [int(k) if k.isdigit() else k for k in path.split(".")]
        src, dst = new, out
        try:
            for k in keys[:-1]:
                src, dst = src[k], dst[k]
            dst[keys[-1]] = copy.deepcopy(src[keys[-1]])
        except (KeyError, IndexError, TypeError):
            continue
    return out


def refresh(run_id: str, write: bool = False) -> dict:
    """A note's numbers again from today's views: the panel and every table the run pulled are
    read again from the API, and each fact is recomputed by its own formula. Returns what changed and what can no
    longer be computed (a column that left the panel, a join the period rule now refuses). With write=True the tables,
    the facts and the charts are rewritten; the text keeps its fact tokens, so its numbers follow."""
    from .api import Api
    from . import panel as panel_mod, run as run_mod, tables as tables_mod
    run = RUNS / run_id
    old_tables = tables_mod.load(run)
    old_facts = facts_mod.load(run)
    api = Api()
    panel = panel_mod.build(api)
    tables = {"panel": tables_mod.from_panel(panel), **tables_mod.panel_inputs(api, panel)}
    skipped = []
    for name, t in old_tables.items():
        if name in tables or not t.get("path"):
            continue
        try:
            tables[name] = tables_mod.pull(api, name, t["path"], t.get("params") or {})
        except Exception as e:
            skipped.append({"table": name, "problem": str(e)[:200]})
    changed, failed, new_facts = [], [], []
    for f in old_facts:
        try:
            v, used = facts_mod.evaluate(f["formula"], tables)
        except facts_mod.FactError as e:
            failed.append({"id": f["id"], "label": f["label"], "old": f["value"], "problem": str(e)[:400]})
            new_facts.append(f)
            continue
        g = dict(f, value=v, period=facts_mod._period({}, used, tables, f["formula"]))
        dec = (f.get("display") or {}).get("decimals", 1)
        if isinstance(v, (int, float)) and isinstance(f["value"], (int, float)):
            if round(v, dec) != round(f["value"], dec):
                changed.append({"id": f["id"], "label": f["label"], "old": f["value"], "new": v, "decimals": dec})
        elif v != f["value"]:
            changed.append({"id": f["id"], "label": f["label"], "old": f["value"], "new": v})
        new_facts.append(g)
    out = {"run": run_id, "changed": changed, "failed": failed, "skipped_tables": skipped, "facts": len(old_facts)}
    if write and not failed:
        tables_mod.write_datasets(run, tables)
        tables_mod.save(run, tables)
        facts_mod.save(run, new_facts)
        # the charts are drawn again from the new tables with the last writer answer's figure specs; the text is the same
        brief = read_json(run / "desk" / "brief.json", {})
        ans = last_answer(run)
        if ans and isinstance(ans.get("figures"), list):
            ans["draft"] = read_json(run / "draft" / "en.json")
            ans["_related"] = (read_json(run / "plan.json", {}) or {}).get("related") or []
            catalog = read_json(run / "data" / "datasteg" / "catalog.json", [])
            built = review.assemble(run, ans, brief, tables, new_facts, catalog)
            out["chart_problems"] = built["problems"]
        out["written"] = True
        if changed:
            out["reread"] = reread(run, {c["id"] for c in changed})
    return out


def reread(run, ids: set[str]) -> dict:
    """After refresh() recomputed a note's numbers (R6, F10: t8's "114% rather than 114%"): every string whose facts
    changed, and the claims they cite, are read again before anything ships. Code's lints (a number compared with
    itself, a claim's comparison) and the verifier, who reports what the fact sheet now contradicts. Errors hold the
    note back with the reason."""
    draft = read_json(run / "draft" / "en.json", {}) or {}
    charts = {p.stem: read_json(p) for p in sorted((run / "charts").glob("*.json"))}
    fact_list = facts_mod.load(run)
    fmap = {f["id"]: f for f in fact_list}
    tok = lambda v: {m.group(1) for m in review.TOKEN.finditer(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))}   # noqa: E731
    touched = [(".".join(map(str, p)), v) for p, v in _walk(draft) if isinstance(v, str) and tok(v) & ids]
    touched += [(f"figure:{cid}.{k}", text._tx(ch.get(k))) for cid, ch in charts.items() for k in ("headline", "subtitle", "alt")
                if isinstance(ch.get(k), dict) and tok(ch[k].get("en") or "") & ids]
    claims = [c for c in claims_mod.load(run) if tok(c) & ids]
    lint = review.claim_lints(draft, charts, claims_mod.load(run), claims_mod.load_map(run), fmap)
    errors = [{"owner": "mechanical", "issue": b} for b in lint["blocking"] if b.startswith(("self-comparison", "base-rate", "mechanical"))]
    if touched:
        try:
            v = roles.call(run, "verifier", "## The must-fix list\n[]\n\n## After a refresh\nThe note's numbers were recomputed from today's "
                           "data. Read each string below, whose numbers changed, against the fact sheet: is it still true, and does a "
                           "comparison still hold (a sentence may now compare a number with itself, or call a gap that closed)? Report "
                           "only errors, under `new_errors`.\n\n## The strings whose numbers changed\n"
                           + "\n".join(f"- {p}: {text._plain(t, fmap, ids=True)}" for p, t in touched)
                           + "\n\n## Fact sheet\n" + facts_mod.sheet(fact_list)
                           + ("\n\n## The claims they cite\n" + claims_mod.sheet(claims, fmap) if claims else ""))["data"] or {}
            errors += [{"owner": "verifier", "kind": "fact", **e} for e in v.get("new_errors") or []]
        except roles.RoleError as e:
            errors.append({"owner": "verifier", "issue": f"the reread after the refresh failed: {e}"})
    out = {"strings": len(touched), "claims": [c["id"] for c in claims], "errors": errors, "at": runlib.now()}
    write_json(run / "desk" / "reread.json", out)
    if errors:
        res = _result(run) or {}
        if res.get("status") in WAITING:
            res.update(status="shelved", held=(res.get("held") or []) + [f"Refresh: {len(errors)} string(s) no longer true after the numbers "
                                                                          f"changed ({(errors[0].get('issue') or '')[:120]})"])
            write_json(run / "desk" / "result.json", res)
    return out


def _walk(x, p=()):
    """(path, value) for every leaf of a draft."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from _walk(v, p + (k,))
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from _walk(v, p + (i,))
    else:
        yield p, x


def correction_ko(run, en: str) -> dict:
    """The Korean of a correction line, drafted like any string of the note and held to the same checks; once more with
    what failed when the first answer fails."""
    korean._RUN[:] = [run]
    item = {"id": "correction", "kind": "draft", "path": ["correction"], "profile": "article", "en": en, "sent": korean.normalise(en)}
    a = {}
    for _ in range(2):
        a = korean._refine([{"req": {"id": "correction", "profile": "article", "ko": "", "en": item["sent"]}, "mode": "careful"}],
                           config.load()["korean"])["correction"]
        if a.get("status") == "refined" and a.get("ko") and not korean.problems(item, a["ko"]):
            return a
        item["sent"] = korean.normalise(en) + " (Write every date in Korean form, 2026년 11월 17일, never 2026-11-17.)"
    return {**a, "status": "fallback"}


def update(run_id: str, note: str, correction: str | None = None, only: list[str] | None = None,
           ko_points: list[dict] | None = None) -> dict:
    """The editor's note on a published note (update-article for the desk; `artools drive` does not run desk runs):
    one rewrite with the note as the writer's only must-fix, the checker's closing passes, the judge, the Korean of
    what changed (qkr; the editor's own Korean title stays while the English title is the same), the PDF proof, then
    `artools ship`, which republishes the same slug with its first date, an `updated` date and `previous`. A change of
    substance carries `correction`, one English sentence (what the note said, what is right); qkr drafts its Korean,
    and readers see it under "Corrections". A wording fix carries none."""
    run = RUNS / run_id
    if state(run) != "published":
        return {"run": run_id, "updated": False, "why": f"the note is {state(run)}, not published"}
    today = dt.date.today().isoformat()
    (run / "update").mkdir(exist_ok=True)
    write_json(run / "update" / f"review-{today}.json", read_json(run / "review.json", {}) or {})
    d = {"id": f"update-{today}", "decision": "return", "note": note, **({"only": only} if only else {}),
         **({"ko_points": ko_points} if ko_points else {}),
         "scope": "A correction after publication. Change only what the editor's note names, wherever the note names it. "
                  "Keep the title, every other sentence, the numbers, the figures and the sources word for word."}
    r = revise(run_id, decision=d)
    if not r.get("revised"):
        return {**r, "updated": False}
    if correction:
        ko = correction_ko(run, correction)
        if ko.get("status") != "refined" or not ko.get("ko"):
            return {**r, "updated": False, "why": f"qkr gave no Korean for the correction ({ko.get('status')}); nothing was republished"}
        cs = read_json(run / "corrections.json", []) or []
        cs.append({"date": today, "text": {"en": correction, "ko": ko["ko"]}})
        write_json(run / "corrections.json", cs)
    s = ship(run)
    out = {**r, **s, "updated": bool(s.get("shipped")), "note": note, "correction": correction}
    write_json(run / "update" / f"{today}.json", {**out, "at": runlib.now()})
    out["queue"] = export(deploy=True)
    return out


def rehook(run, brief: dict) -> tuple[dict, str | None]:
    """The editor names the hook, why_now and why_these of a note already written, from the packet its run saw (its
    leads, its changes, the releases of the 45 days before it, this month's research). Returns the brief with them
    and None, or the brief unchanged and why no hook could be found."""
    from . import run as run_mod, watch
    from .api import Api
    w = read_json(run / "desk" / "watch.json", {}) or {}
    snap, changed = w.get("snapshot") or {}, w.get("changed") or []
    found = read_json(run / "desk" / "leads.json", []) or []
    shortlist = found[: config.load()["leads"]["shortlist"]]
    if brief.get("lead") and not any(l["key"] == brief["lead"] for l in shortlist):
        shortlist = [l for l in found if l["key"] == brief["lead"]] + shortlist
    research = run_mod._research(Api())
    releases = watch.recent(snap, str(snap.get("at") or runlib.now())[:10])
    packet = (run_mod.editor_packet(shortlist, changed, {}, str(snap.get("at") or "")[:10], research, releases)
              + "\n\n## The note already written for the lead " + str(brief.get("lead")) + "\n```json\n"
              + json.dumps({k: brief.get(k) for k in ("working_title", "question", "thesis", "why_now", "focus", "economies")}, ensure_ascii=False, indent=1)
              + "\n```\nThis note was written before a hook was required. Do not choose another lead. Answer only "
                "`{\"hook\": {...}, \"why_now\": \"…\", \"why_these\": \"…\"}` for this note, from the packet above, or "
                "`{\"hook\": null, \"why\": \"…\"}` when nothing in the packet gives it a reason to be read now.")
    ans = roles.call(run, "editor", packet, label="editor")["data"]
    if not ans.get("hook"):
        return brief, ans.get("why") or "the editor found no hook"
    new = {**brief, **{k: ans.get(k) for k in ("hook", "why_now", "why_these") if ans.get(k)}}
    problems = run_mod.check_hook(new, changed, research, shortlist, releases)
    if problems:
        return brief, "; ".join(problems[:2])
    write_json(run / "desk" / "brief.json", new)
    return new, None


def spent_today() -> float:
    today = dt.date.today().strftime("%Y%m%d")
    return round(sum(roles.spent(r) for r in desk_runs() if r.name.startswith(today)), 2)


def daily(force: bool = False, deploy: bool = True) -> dict:
    """The cron entry, run every hour: one at a time, it applies the editor's
    decisions, revises what was returned, writes the day's note (once a day, from config schedule.note_from_hour) when
    the data changed and no note is waiting, and sends the queue to the admin site when it changed."""
    import fcntl
    DESK.mkdir(parents=True, exist_ok=True)
    lock = (DESK / "daily.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"at": runlib.now(), "skipped": "another `desk daily` is still running"}
    try:
        return _daily(force, deploy)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _daily(force: bool, deploy: bool) -> dict:
    from . import run as run_mod, watch
    from .api import Api
    cfg = config.load()
    out = {"at": runlib.now()}
    try:
        out["sync"] = sync()
    except Exception as e:
        out["sync"] = {"error": f"{type(e).__name__}: {e}"}
    # an approval whose ship failed (a dirty tree, a deploy error): tried again every hour, a few times
    out["shipped"] = []
    for r in desk_runs():
        if state(r) == "approved" and int((read_json(r / "desk" / "ship.json", {}) or {}).get("tries") or 0) < SHIP_TRIES:
            try:
                out["shipped"].append({"run": r.name, **ship(r)})
            except Exception as e:
                out["shipped"].append({"run": r.name, "error": f"{type(e).__name__}: {e}"})
    out["revised"] = []
    for r in desk_runs():
        if state(r) == "returned" and spent_today() < cfg["budget"]["usd_per_day"]:
            try:
                out["revised"].append(revise(r.name))
            except Exception as e:
                out["revised"].append({"run": r.name, "error": f"{type(e).__name__}: {e}"})
    # a waiting note whose Korean edition is missing or out of date (qkr was down, the English changed) gets it now
    out["korean"] = []
    for r in desk_runs():
        if state(r) in ("queued", "shelved") and not busy(r) and cfg["korean"]["required"] and r.name[:8] >= (dt.date.today() - dt.timedelta(days=14)).strftime("%Y%m%d"):
            ko = korean.status(r)
            if ko.get("missing") or ko.get("stale") or not ko.get("written"):
                try:
                    k = korean.make(r)
                    out["korean"].append({"run": r.name, "complete": k.get("complete"), "open": len(k.get("open") or []), "error": k.get("error"), **settle(r)})
                except Exception as e:
                    out["korean"].append({"run": r.name, "error": f"{type(e).__name__}: {e}"})
    # a waiting note changed since its proof (a Korean title set, a Korean redraft): printed again and settled
    out["pdf"] = []
    for r in desk_runs():
        if state(r) in ("queued", "shelved") and not busy(r) and r.name[:8] >= (dt.date.today() - dt.timedelta(days=14)).strftime("%Y%m%d"):
            from .. import pdf
            if any("older than" in b or "no proof" in b or "no PDF" in b for b in pdf.check(r)["blocking"]):
                out["pdf"].append({"run": r.name, "blocking": proof_pdf(r)["blocking"], **settle(r)})
    waiting = [r.name for r in desk_runs() if state(r) == "queued"]
    sch = cfg.get("schedule") or {}
    now = dt.datetime.now()
    today_runs = [r.name for r in desk_runs() if r.name.startswith(now.strftime("%Y%m%d"))]
    if not force and now.hour < int(sch.get("note_from_hour", 0)):
        out["note"] = {"skipped": f"a new note is written from {sch['note_from_hour']}:00, after the apps' morning data"}
    elif not force and len(today_runs) >= int(sch.get("notes_per_day", 1)):
        out["note"] = {"skipped": f"today's note was already tried: {today_runs}"}
    elif waiting and not force:
        out["note"] = {"skipped": f"{len(waiting)} note(s) wait for the editor: {waiting}"}
    else:
        out["note"] = _today_note(cfg, force, run_mod, watch, Api)
    # the ideas preview, once a day after the morning data (it writes no note; shown on the admin site)
    if (cfg.get("ideas") or {}).get("daily", True) and (force or now.hour >= int(sch.get("note_from_hour", 0))):
        try:
            from . import ideas as ideas_mod
            out["ideas"] = ideas_mod.make()
        except Exception as e:
            out["ideas"] = {"error": f"{type(e).__name__}: {e}"}
    out["queue"] = export(deploy=deploy)      # deploy_admin redeploys only when a ledger file changed
    return out


def _today_note(cfg: dict, force: bool, run_mod, watch, Api) -> dict:
    changed = watch.changes(watch.snapshot(Api()), watch.load())
    fresh = [c for c in changed if c["kind"] in ("period", "dataset", "vintage")]
    if not fresh and not force and any(r.name.startswith(dt.date.today().strftime("%Y%m")) for r in desk_runs()) and dt.date.today().weekday() != 0:
        return {"skipped": "no new data since the last note (a note is still written each Monday from a new join)"}
    if spent_today() >= cfg["budget"]["usd_per_day"]:
        return {"skipped": f"today's budget is spent (USD {spent_today()})"}
    try:
        return run_mod.note()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
