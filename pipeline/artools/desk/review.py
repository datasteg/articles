"""The desk's checks that need no model: what a draft must satisfy before a reviewer's time is spent on it.

`assemble` turns the writer's answer into the run's files (draft/en.json, charts/, plan.json, brief.json) and reports
what could not be built. `mechanical` then runs the pipeline's own checks (numbers, style, licences, charts,
readability) and the data note's hard rules from guides/desk/standard.md: length, figures, the limits and method
sections, at least two apps and two publishers, and at least one number that needs both sides of the join.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .. import checks as pipeline_checks
from ..content import CITE, GLOSS, TOKEN
from ..paths import CONFIG, CONTENT, load_yaml, read_json, write_json
from ..runlib import slugify
from ..validate import check as schema_check
from . import charts as charts_mod
from . import config, text
from .panel import SIDE
from .tables import dataset_id

CAUSAL = re.compile(r"\b(caus(?:e|es|ed|ing)|drove|driv(?:es|en|ing)|led to|leads to|because of|due to|triggered|result(?:s|ed)? in|thanks to)\b", re.I)
FORECAST = re.compile(r"\b(will (?:rise|fall|grow|shrink|increase|decline|hit|face|suffer|lose)|is (?:set|poised|likely|bound) to|"
                      r"investors should|should (?:buy|sell|hedge|avoid)|safe haven|is (?:safe|unsafe|risky)|are (?:safe|unsafe|risky))\b", re.I)
CODES = re.compile(r"(?<![\w{])(A[123]|B[12]|J[1-7]|R2[2-8]|G1[89]|V1[0-9])(?![\w}])|\b(?:score|flow) [VF]\b|\bV (?:score|of)\b")
INTERNAL = re.compile(r"\b(Signal Board|the board|board economies|country sheets?|money-flow|trade-flow|global-network|open-research|"
                      r"funding monitor|our (?:two )?(?:trade|funding) pages?)\b")
HISTORY_KEYS = ("quarter", "month", "period", "date", "year")
HYPE = re.compile(r"\b(unprecedented|striking(?:ly)?|dramatic(?:ally)?|alarming(?:ly)?|shocking|staggering|it is worth noting|notably,)\b", re.I)


def _editorial() -> dict:
    return load_yaml(CONFIG / "editorial.yaml") or {}


def new_slug(title: str, run: Path) -> str:
    base = slugify(re.sub(r"\{\{[^}]*\}\}", "", title), 6)
    slug, n = base, 2
    while (CONTENT / "articles" / slug).exists() and ((read_json(CONTENT / "articles" / slug / "meta.json", {}) or {}).get("run") or {}).get("id") != run.name:
        slug, n = f"{base}-{n}", n + 1
    return slug


def assemble(run: Path, answer: dict, brief: dict, tables: dict, facts: list[dict], catalog: list[dict]) -> dict:
    """Write the run's article files from the writer's answer. Returns {"problems": [...], "charts": {...}, "draft": …}:
    problems are things the writer must fix before any review (an invalid shape, a figure that cannot be drawn)."""
    problems = []
    draft = answer.get("draft")
    if not isinstance(draft, dict):
        return {"problems": ["the answer has no `draft` object"], "charts": {}, "draft": None}
    ed = _editorial()
    draft.setdefault("byline", (ed.get("byline") or {}).get("en", "datasteg desk · AI-assisted"))
    draft.setdefault("disclaimer", (ed.get("disclaimer") or {}).get("en"))
    draft.setdefault("citations", {})
    q = draft.get("question") or {}
    if isinstance(q, dict) and not q.get("premiseNote"):
        q["premiseNote"] = None
    problems += [p.replace("draft/en.json: ", "draft: ") for p in schema_check(draft, "draft", "draft/en.json")]
    fmap = {f["id"]: f for f in facts}
    cmap = {d["id"]: d for d in catalog}
    allow = [re.compile(p) for p in pipeline_checks.rules()["number_allow"]]
    built = {}
    figs = answer.get("figures") or []
    for spec in figs if isinstance(figs, list) else []:
        try:
            for m in TOKEN.finditer(" ".join(str(v) for v in spec.values() if isinstance(v, (str, list)))):
                if m.group(1) not in fmap:
                    raise charts_mod.ChartError(f"figure {spec.get('id')}: unknown fact {m.group(0)}")
            typed = charts_mod.typed_numbers(spec, allow)
            if typed:
                problems += typed
                continue
            ch = charts_mod.build(spec, tables, fmap, cmap)
            if ch["id"] in built:
                raise charts_mod.ChartError(f"two figures share the id {ch['id']}")
            built[ch["id"]] = ch
        except Exception as e:      # whatever a figure request breaks on goes back to the writer as a problem to fix
            problems.append(str(e) if isinstance(e, charts_mod.ChartError)
                            else f"figure {spec.get('id') if isinstance(spec, dict) else spec!r}: {type(e).__name__}: {e}")
    placed = [b.get("chart") for s in draft.get("sections", []) if isinstance(s, dict)
              for b in s.get("blocks", []) if isinstance(b, dict) and b.get("type") == "figure"]
    for c in placed:
        if c not in built:
            problems.append(f"the text places figure {c!r}, which was not built")
    for c in built:
        if c not in placed:
            problems.append(f"figure {c} is not placed in the text (add a block {{\"type\": \"figure\", \"chart\": \"{c}\"}})")
    # a count prints as a word ("four"), so a sentence or a headline that starts with a token starts in lower case
    starts = re.compile(r"(?:^|[.!?]\s+)\{\{F\d+")
    for where, t in [(k, draft.get(k)) for k in ("title", "dek")] + [("findings", f) for f in draft.get("findings") or []] \
            + [(sec.get("id"), b.get("text")) for sec in draft.get("sections", []) if isinstance(sec, dict)
               for b in sec.get("blocks", []) if isinstance(b, dict) and b.get("type") == "p"] \
            + [(f"figure {sp.get('id')}.{k}", sp.get(k)) for sp in (figs if isinstance(figs, list) else []) if isinstance(sp, dict)
               for k in ("headline", "title")]:
        if isinstance(t, str) and starts.search(t):
            problems.append(f"{where}: a sentence starts with a fact token, which prints in lower case; reword so a word comes first ({t[:70]}…)")
    # glossary marks are not used by the desk: terms are defined in the sentence
    marks = GLOSS.findall(str(draft))
    if marks:
        problems.append(f"glossary marks {sorted(set(marks))[:5]}: define the term in the sentence instead of (( ))")
    # "Get the data": where each table came from and how to fetch it again, built from the run's datasets by code
    # the label of the "Why this note" line is set by code, so qkr drafts its Korean with the rest of the note
    if isinstance(draft.get("whyNow"), str) and draft["whyNow"].strip():
        draft["whyNowLabel"] = "Why this note"
    else:
        draft.pop("whyNowLabel", None)
    from . import reproduce
    draft.pop("reproduce", None)
    rep = reproduce.build(draft, facts, built, catalog, tables, brief)
    dl = reproduce.bundle(run, draft, facts, built, catalog, tables, rep)      # the same data as one ZIP of CSV files
    if rep:
        if dl:
            rep["download"] = dl
        draft["reproduce"] = rep
    # the claim each surface string states (R3): the title, the dek, each key number, each finding and each chart
    # headline cite a claim of the ledger (analysis/claims.json); one without is sent back like a figure that fails
    from . import claims as claims_mod
    ledger = claims_mod.load(run)
    if ledger and (config.load().get("claims") or {}).get("required", True):
        problems += claims_mod.check_map(answer, ledger)
    claims_mod.save_map(run, claims_mod.claim_map(answer))
    write_json(run / "draft" / "en.json", draft)
    # a new English draft makes the Korean edition out of date: it is drafted again from this text (desk/korean.py)
    (run / "draft" / "ko.json").unlink(missing_ok=True)
    charts_mod.write(run, list(built.values()))
    slug = new_slug(str(draft.get("title") or brief.get("working_title") or run.name), run)
    known = {t["id"] for t in (load_yaml(CONFIG / "topics.yaml") or {}).get("topics", [])}
    write_json(run / "plan.json", {
        "run": run.name, "slug": slug, "type": "data-note", "date": dt.date.today().isoformat(),
        "headline": {"en": draft.get("title")}, "answer": brief.get("thesis"),
        "topics": [{"id": t} for t in (brief.get("topics") or []) if t in known][:3] or [{"id": "global-economy"}],
        "figures": [{"id": c["id"], "form": c["form"], "takeaway": c["headline"]["en"]} for c in built.values()],
        "related": answer.get("_related") or [], "sections": [{"id": s.get("id")} for s in draft.get("sections", []) if isinstance(s, dict)],
    })
    write_json(run / "brief.json", {"question": brief.get("question"), "jel": ["F3", "F1"],
                                    "entities": {"countries": [c for c in (brief.get("countries") or []) if re.fullmatch(r"[A-Z]{2}", str(c))][:6]}})
    return {"problems": problems, "charts": built, "draft": draft, "slug": slug}


# ------------------------------------------------------------------ hard rules

def _fact_sides(f: dict, tables: dict) -> set[str]:
    """Which sides of the join a fact reads: funding (BIS, IMF), trade (UN Comtrade), or joint (needs both)."""
    sides = set()
    expr = f.get("formula") or ""
    for name in f.get("tables") or []:
        t = tables.get(name) or {}
        if name == "panel":
            for col in re.findall(r"[a-z][a-z0-9_]{2,}", expr):
                if col in SIDE:
                    sides.add(SIDE[col])
        elif t.get("app") == "global-network":
            sides.add("joint")
        elif t.get("app") == "trade-flow":
            sides.add("trade")
        elif t.get("app") == "money-flow":
            sides.add("funding")
    if {"funding", "trade"} <= sides:
        sides.add("joint")
    return sides


def chart_sides(ch: dict, catalog: list[dict]) -> set[str]:
    """Which sides of the join a chart draws: from its columns (panel) or from the app of the tables it was drawn from."""
    sides = {SIDE[c["key"]] for c in (ch.get("table") or {}).get("columns", []) if c.get("key") in SIDE}
    apps = {d.get("app") for d in catalog if d["id"] in ((ch.get("meta") or {}).get("sources") or [])}
    if "global-network" in apps and not sides:
        sides.add("joint")
    sides |= {"funding" for a in apps if a == "money-flow"} | {"trade" for a in apps if a == "trade-flow"}
    return sides


def consolidation(draft: dict, facts: list[dict], tables: dict, catalog: list[dict]) -> dict:
    fmap = {f["id"]: f for f in facts}
    used = {m.group(1) for m in TOKEN.finditer(str(draft))}
    cmap = {d["id"]: d for d in catalog}

    def base(did, depth=0):
        d = cmap.get(did)
        if not d:
            return []
        if d.get("inputs") and depth < 4:
            return [x for i in d["inputs"] for x in base(i, depth + 1)]
        return [d]
    cited = {c.strip() for m in CITE.finditer(str(draft)) for c in m.group(1).split(",")}
    for k in draft.get("keyNumbers") or []:
        cited |= set(k.get("cite") or [])
    ds = [d for c in cited for d in base(c)] + [d for fid in used if fid in fmap for i in fmap[fid]["inputs"] for d in base(i)]
    apps = sorted({d.get("app") for d in ds if d.get("app") and d.get("app") != "desk"})
    pubs = sorted({p for d in ds for p in d.get("publishers") or []})
    joined = sorted(fid for fid in used if fid in fmap and "joint" in _fact_sides(fmap[fid], tables))
    sides = sorted({s for fid in used if fid in fmap for s in _fact_sides(fmap[fid], tables)})
    return {"apps": apps, "publishers": pubs, "joined_facts": joined, "sides": sides, "facts_used": len(used & set(fmap)),
            "facts_available": len(fmap), "cited": sorted(cited)}


def figure_rules(draft: dict, charts: dict, tables: dict, catalog: list[dict], cfg: dict) -> list[str]:
    """The note's rules for its figures and its "Why this note" line (config note: figures, forms, max_same,
    history_line): enough charts, in forms that fit their points, a line for any history the run pulled, one chart
    that shows the join, and a reason for today. Returns the blocking issues."""
    blocking = []
    drawn = [c for c in charts.values() if c["form"] != "table"]
    if not cfg["figures"][0] <= len(charts) <= cfg["figures"][1]:
        blocking.append(f"figures: {len(charts)}; a note has {cfg['figures'][0]}–{cfg['figures'][1]}")
    elif len(drawn) < cfg["figures"][0]:
        blocking.append(f"figures: {len(drawn)} chart(s) and {len(charts) - len(drawn)} table(s); a note needs at least "
                        f"{cfg['figures'][0]} charts (a table does not count): draw the comparison as bars, a dumbbell, a scatter or a line")
    else:
        drawn_forms = [c["form"] for c in drawn]
        if len(set(drawn_forms)) < cfg.get("forms", 2):
            blocking.append(f"figures: the charts are all {drawn_forms[0]}; use at least {cfg.get('forms', 2)} forms, each chosen for its point "
                            "(a line for an economy's own past, a dumbbell for two measures or then and now, bars for a ranking)")
        caps = cfg.get("max_same") or {}
        for f in sorted(set(drawn_forms)):
            cap = caps.get(f, caps.get("default", 99))
            if drawn_forms.count(f) > cap:
                blocking.append(f"figures: {drawn_forms.count(f)} {f} charts; a note takes at most {cap}: show the other points in the form that fits them")
    # a history the run pulled (a table keyed by period) is the reader's view of whether today is ordinary for that
    # economy: it is drawn as a line
    hist = sorted(n for n, t in tables.items() if (t.get("key") or [""])[0] in HISTORY_KEYS and len(t.get("rows") or []) >= 6)
    lined = {s for c in drawn if c["form"] == "line" for s in (c.get("meta") or {}).get("sources") or []}
    if cfg.get("history_line") and hist and not lined & {dataset_id(n) for n in hist}:
        blocking.append(f"figures: the run pulled a history ({', '.join(hist)}) but no line chart draws it; show where today sits in that economy's own past")
    # why this note exists today and why it is about these economies (guides/desk/roles/writer.md § Why this note)
    why = draft.get("whyNow")
    if not isinstance(why, str) or len(why.split()) < 8:
        blocking.append("whyNow: missing; one or two sentences under the dek on what is new today (with its period) and why these economies")
    elif len(TOKEN.sub("x", why).split()) > 60:
        blocking.append(f"whyNow: {len(why.split())} words; at most 55")
    elif re.search(r"\b(nothing (?:has )?changed|no new data|the (?:desk|screens?|leads?)\b|shelved|earlier notes?)", why, re.I):
        blocking.append("whyNow: says nothing is new or talks about the desk's process; give the reason a reader should look today")
    elif re.search(r"\b(?:read|retrieved|fetched|downloaded) (?:on|in)\b", why, re.I):
        blocking.append("whyNow: gives the day datasteg read the data, which is not the publisher's date; say the period the data reach "
                        "(\"BIS bank data to end-June 2026\") and leave the read date out")
    # a chart headline is read at a glance and drafted by qkr as a one-line Korean headline: short, with at most two
    # quantities (t8, 16 Nov 2026: the two headlines with three or more numbers, or over 110 characters, came back from
    # qkr too long or split over two lines)
    hl = cfg.get("chart_headline") or {}
    for cid, c in sorted(charts.items()):
        h = text._tx(c.get("headline"), "en") or ""
        qty = [m.group(0).rstrip(",") for m in re.finditer(r"(?<![Q\d.])\d[\d,]*(?:\.\d+)?%?", h)
               if not re.fullmatch(r"(?:19|20)\d{2}", m.group(0).rstrip(","))]
        if hl.get("max_chars") and len(h) > hl["max_chars"]:
            blocking.append(f"figure {cid}: the headline is {len(h)} characters; at most {hl['max_chars']} (one point, the rest in the subtitle)")
        if hl.get("max_numbers") and len(qty) > hl["max_numbers"]:
            blocking.append(f"figure {cid}: the headline carries {len(qty)} numbers ({', '.join(qty)}); at most {hl['max_numbers']}: "
                            "keep the one or two that make the point, the chart shows the others")
    if drawn and not any("joint" in chart_sides(c, catalog) or {"funding", "trade"} <= chart_sides(c, catalog) for c in drawn):
        blocking.append("figures: no chart shows the join; at least one must set a funding measure against a trade measure "
                        "(a scatter of one against the other, a dumbbell, or a joined ratio such as bank loans against exports)")
    return blocking


# ------------------------------------------------------------------ claim lints (rule R3)

_NUMW = r"(?:\{\{F\d+[^}]*\}\}|\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\w+teen|twenty[\w-]*|thirty[\w-]*)"
# a statistic a count or share is read against: a median, a mean, a top-N
BASE_STAT = re.compile(rf"\b(?:median|mean|average)\b|\btop {_NUMW}\b|\b{_NUMW} (?:highest|lowest|largest|smallest)\b|\b(?:highest|lowest) {_NUMW}\b", re.I)
# a count or a share of a set
COUNT_OF = re.compile(rf"\b(?:of|out of) (?:the )?{_NUMW}\b|\b{_NUMW} of {_NUMW}\b|\bhalf\b|\bmost\b|\bmajority\b|\bshare\b|%|"
                      r"\ball (?:belong|are|were|of)\b|\bevery one\b|\bonly\b", re.I)
# a comparison with the other set in the same string
COMPARATOR = re.compile(r"\b(?:vs\.?|versus|against|compared with|as did|as among|as for|the same (?:share|proportion|as)|whereas|"
                        r"than (?:among|in|for)|no (?:more|different|better|worse) than|as many as|just as|"
                        r"(?:un)?like (?:those|economies|inflow|outflow|the (?:N|\d+|economies|inflow|outflow|other))|unlike|"
                        r"as (?:much|fast|many|often|strongly|quickly|well|widely)\b(?:\W+\w+){0,8}?\W+as\b|as (?:much|fast|many|often|strongly|quickly|well|widely) (?:where|in|among|for)\b|as where|as (?:in|among|for) (?:all|those|the|economies|N|\d+)|"
                        r"those that (?:kept|received|gained|lost|did not|had)|(?:in )?both groups|either group|in each group|"
                        r"whether or not|whether (?:funding|money|it) (?:came|left|stayed)|in every economy|every economy with data|"
                        r"all (?:N|\d+|the) economies with|(?:economies|those|ones) without|without (?:one|an? (?:outflow|inflow)|outflows?)|"
                        r"that did not|did not lose|non-outflow|non-inflow)\b", re.I)
_TO_STAT = re.compile(r"\s+(?:the|a|its|their)?\s*(?:\w+\s+){0,3}?(?:median|mean|average|top)\b", re.I)


def has_comparator(t: str) -> bool:
    """Whether the string compares with another set (not merely with the median it is read against)."""
    return any(len(t[m.end():].strip(" .,;:)")) >= 3 and not _TO_STAT.match(t[m.end():]) for m in COMPARATOR.finditer(t))
VAGUE_CMP = re.compile(r"\b(?:much|very|just) like\b|\bsimilar(?:ly)? to\b|\bbroadly\b|\broughly the same\b|\bin line with\b|"
                       r"\bcomparable to\b|\babout the same\b|\blike the rest\b", re.I)
BUILT = re.compile(r"\bby construction\b|\bcounts? (?:the|its|their)\b|\bincludes? (?:the|its|their)\b|\bbuilt (?:from|on|in)\b|"
                   r"\bpart of the score\b|\bfollows from how\b|\bmechanical(?:ly)?\b|\bwhich (?:the|this) score (?:counts|includes)\b", re.I)
GROUP_MEDIAN = re.compile(r"\bgroup(?:'s)? (?:median|mean|average)\b|\b(?:median|mean|average) of the group\b", re.I)
# an input measure, as the words a headline would use for the set it selects
INPUT_WORDS = {"flow_score_f": r"funding|outflow|inflow|bank and bond|lost (?:net )?(?:foreign )?(?:funding|money)",
               "bank_flow_lbs": r"bank flow|funding", "intl_debt_securities": r"bond", "goods_trade_growth": r"export growth|exports? (?:grew|fell|rose|growth)",
               "goods_exports_partner": r"exports?", "vulnerability_v": r"vulnerab", "net_reserves": r"reserves", "lender_share": r"lender"}
SELF_CMP = re.compile(r"(?<![\w.])(?P<a>[-−]?\d[\d,]*(?:\.\d+)?%?)\s+(?:rather than|instead of|against|versus|vs\.?|compared with|up from|down from)\s+"
                      r"(?P=a)(?!\d|\.\d)|\bfrom (?P<b>[-−]?\d[\d,]*(?:\.\d+)?%?) to (?P=b)(?!\d|\.\d)")


def surface_texts(draft: dict, charts: dict) -> list[tuple[str, str]]:
    """(claim-map path, raw text) for what a skimming reader sees: title, dek, key numbers, findings, chart headlines
    and subtitles. Tokens stay tokens, so a lint can tell which facts a string shows."""
    out = [("title", draft.get("title") or ""), ("dek", draft.get("dek") or "")]
    out += [(f"keyNumbers.{i}", f"{k.get('value') or ''} {k.get('label') or ''}") for i, k in enumerate(draft.get("keyNumbers") or [])]
    out += [(f"findings.{i}", f) for i, f in enumerate(draft.get("findings") or []) if isinstance(f, str)]
    for cid, ch in sorted(charts.items()):
        out.append((f"figure:{cid}", text._tx(ch.get("headline")) or ""))
        if text._tx(ch.get("subtitle")):
            out.append((f"figure:{cid}.subtitle", text._tx(ch.get("subtitle"))))
    return [(p, t) for p, t in out if isinstance(t, str) and t.strip()]


def _vague_referent(t: str) -> str | None:
    """The first reference set the string does not define ("the group median", "the rest"), or None."""
    from . import claims as claims_mod
    for m in claims_mod.VAGUE_SET.finditer(t):
        after = t[m.end(): m.end() + 45]
        if GROUP_MEDIAN.search(m.group(0)) or not claims_mod.DEFINED_SET.match(after.lstrip(" ,(")) \
                and not re.match(r"\s*(?:of|,|\()\s*(?:all|the)?\s*(?:\{\{F\d+[^}]*\}\}|\d+)", after):
            return m.group(0)
    return None


def _plotted(ch: dict) -> list[str]:
    return [c.get("key") for c in (ch.get("table") or {}).get("columns") or [] if c.get("key") not in (None, "label")]


def claim_lints(draft: dict, charts: dict, claims: list[dict] | None = None, cmap: dict | None = None,
                fmap: dict | None = None) -> dict:
    """The text lints of rule R3, all code. Without a ledger (an old note, a replay) they read the text
    alone; with the claim ledger and the writer's claim map they check each string against the claim it states.
    Returns {"blocking": [...], "advisory": [...]} (strings, each starting with the lint's name)."""
    from . import claims as claims_mod
    blocking, advisory = [], []
    by = {c["id"]: c for c in claims or []}
    cmap = cmap or {}
    words = lambda t: TOKEN.sub("N", t or "")     # noqa: E731
    from ..content import render_fact
    fm = fmap or {}

    def shown(fid: str, raw: str) -> bool:
        """Whether a fact shows in a string: as its token (a draft string) or as its printed value (a built chart's
        headline holds the numbers already filled in)."""
        if re.search(r"\{\{" + re.escape(fid) + r"(?:\|[a-z,]+)?\}\}", raw):
            return True
        f = fm.get(fid)
        if not f:
            return False
        forms = set()
        for opts in (None, {"digits"}):
            try:
                forms.add(render_fact(f, "en", opts))
            except Exception:
                pass
        return any(v and re.search(r"(?<![\w.])" + re.escape(v) + r"(?![\w]|\.\d)", raw, re.I) for v in forms)
    surf = surface_texts(draft, charts)
    for path, raw in surf:
        t = words(raw)
        cited = [by[i] for i in cmap.get(path.split(".subtitle")[0].split(".title")[0], []) if i in by]
        # base-rate: a count or share against a median, a mean or a top-N must carry the comparison in the same string
        ctok_all = {m.group(1) for c in cited if isinstance(c.get("comparator"), dict) for m in TOKEN.finditer(json.dumps(c["comparator"]))}
        if not path.endswith(".subtitle") and BASE_STAT.search(t) and COUNT_OF.search(t) and not has_comparator(t) \
                and not any(shown(x, raw) for x in ctok_all):
            blocking.append(f"base-rate: `{path}` states a count or share against a {BASE_STAT.search(t).group(0)} with no comparison (half of "
                            f"any set sits above a median; a top-N says little until the rest are shown): say what the other economies show "
                            f"in the same string ({raw[:110]!r})")
        for c in cited:
            comp = c.get("comparator") if isinstance(c.get("comparator"), dict) else None
            toks = {m.group(1) for m in TOKEN.finditer(raw)}
            ctoks = {m.group(1) for m in TOKEN.finditer(json.dumps(comp or {}))}
            stat = c.get("statistic") or {}
            vtok = {m.group(1) for m in TOKEN.finditer(str(stat.get("value") or ""))}
            btok = {m.group(1) for m in TOKEN.finditer(str(stat.get("base") or ""))}
            if comp and ctoks and not any(shown(x, raw) for x in ctoks) and (c.get("kind") in ("share_above", "count", "rank") or c.get("reading") in ("no_difference", "difference")
                                                         or BASE_STAT.search(str(stat.get("against") or ""))) and not path.endswith(".subtitle"):
                if not path.startswith("keyNumbers.") and has_comparator(t):
                    pass        # a title, dek, finding or headline may give the comparison in words; a key number gives the count
                else:
                    blocking.append(f"base-rate: `{path}` states {c['id']} without its comparator ({comp.get('set')}: "
                                    f"{', '.join('{{' + x + '}}' for x in sorted(ctoks))}); put it in the same string")
            if c.get("kind") in ("count", "share_above") and vtok & toks and btok and not any(shown(x, raw) for x in btok):
                blocking.append(f"base-rate: `{path}` gives {c['id']}'s count without its base ({', '.join('{{' + x + '}}' for x in sorted(btok))}): "
                                "'three' needs 'of six'")
            if path.startswith("keyNumbers.") and c.get("kind") in ("count", "share_above") and comp \
                    and not (any(shown(x, raw) for x in ctoks) and any(shown(x, raw) for x in btok)):
                blocking.append(f"key number: `{path}` shows {c['id']}; its label must give the base and the comparator "
                                "(\"of 6 outflow economies; inflow economies: 14 of 28\")")
            if c.get("mechanical") and not BUILT.search(t) and not path.endswith(".subtitle"):
                blocking.append(f"mechanical: `{path}` states {c['id']}, which follows from how the measure is built; say so in the same "
                                "string (\"the score counts the funding loss itself\")")
            if comp and VAGUE_CMP.search(t):
                advisory.append(f"vague comparison: `{path}` says “{VAGUE_CMP.search(t).group(0)}” where {c['id']} has the number "
                                f"({', '.join('{{' + x + '}}' for x in sorted(ctoks))}); give it")
        if not cited and VAGUE_CMP.search(t) and not path.endswith(".subtitle"):
            advisory.append(f"vague comparison: `{path}` says “{VAGUE_CMP.search(t).group(0)}”; where a number exists, give the number")
        ref = _vague_referent(raw)
        if ref:
            blocking.append(f"referent: `{path}` says “{ref}” without naming the set; write the population (\"the median of all 34 economies "
                            f"with export data\", \"the 28 economies that received funding\") ({raw[:110]!r})")
    # a chart headline on a composite measure that selects its subject by one of the measure's inputs reads a result
    # the measure builds in (20261118: the five highest double-hit scores "belong to economies that lost net funding")
    for cid, ch in sorted(charts.items()):
        h = words(text._tx(ch.get("headline")) or "")
        if [i for i in cmap.get(f"figure:{cid}", []) if i in by]:
            continue        # held to its claims above: their mechanical flag is checked by code against the registry
        if ch.get("form") not in ("bars", "table", "dumbbell"):
            continue        # a ranking reads a selection as a result; a scatter or a line of the measure itself does not
        for col in _plotted(ch):
            mid = claims_mod.measure_id(col)
            if not (mid and (mid.startswith("signal:") or mid in ("vulnerability_v", "stress_count"))):
                continue    # a composite score, not a measure and its own components
            ins = claims_mod.inputs_of(mid) if mid else set()
            hit = [i for i in ins if INPUT_WORDS.get(i) and re.search(INPUT_WORDS[i], h, re.I)]
            if hit and (BASE_STAT.search(h) or COUNT_OF.search(h)) and not BUILT.search(h):
                blocking.append(f"mechanical: figure {cid} ranks {claims_mod.info(mid)['name']}, which is built from "
                                f"{', '.join(claims_mod.info(i)['name'] for i in hit)}; its headline reads that input as a finding. "
                                "Say that the score counts it, or make another point")
                break
    # the registry's names: a measure is never called by a name the registry rules out (F6, F9)
    argued = [("title", draft.get("title")), ("dek", draft.get("dek")), ("whyNow", draft.get("whyNow")),
              *[(f"findings.{i}", f) for i, f in enumerate(draft.get("findings") or [])],
              *[(f"keyNumbers.{i}", k.get("label")) for i, k in enumerate(draft.get("keyNumbers") or [])],
              ("insight", (draft.get("insight") or {}).get("text"))]
    for s in draft.get("sections") or []:
        argued += [(s.get("id"), b.get("text")) for b in s.get("blocks") or [] if b.get("type") == "p"]
        argued += [(s.get("id"), i) for b in s.get("blocks") or [] if b.get("type") == "list" for i in b.get("items") or []]
    for cid, ch in charts.items():
        argued += [(f"figure {cid}", text._tx(ch.get(k))) for k in ("headline", "title", "subtitle", "howToRead", "alt")]
        argued += [(f"figure {cid}", text._tx(n)) for n in ch.get("notes") or []]
        argued += [(f"figure {cid}", text._tx(c.get("label"))) for c in (ch.get("table") or {}).get("columns") or []]
    for where, t in argued:
        if not isinstance(t, str):
            continue
        for pat, wrong, m in claims_mod.never_call():
            hit = pat.search(t)
            if hit:
                blocking.append(f"registry name: {where} calls {m['name']} “{hit.group(0)}”, a name the registry rules out "
                                f"(family/measures.json never_call “{wrong}”); write “{m['name']}”"
                                + (f" or {', '.join('“' + a + '”' for a in m['aliases'][:3])}" if m["aliases"] else ""))
        if where not in ("title", "dek") and not where.startswith(("findings", "keyNumbers", "figure")) and GROUP_MEDIAN.search(words(t)):
            blocking.append(f"referent: {where} says “{GROUP_MEDIAN.search(words(t)).group(0)}”; name the population the median is taken over")
    # a sentence that compares a number with itself (20261114-t8 after a refresh: "114% rather than 114%")
    if fmap is not None:
        rendered = [(w, text._plain(t, fmap)) for w, t in argued if isinstance(t, str)]
        for w, t in rendered:
            m = SELF_CMP.search(t)
            if m:
                blocking.append(f"self-comparison: {w} compares {m.group('a') or m.group('b')} with itself ({t[max(0, m.start() - 40):m.end() + 20]!r}); "
                                "the numbers moved since the sentence was written: say what they show now")
    return {"blocking": list(dict.fromkeys(blocking)), "advisory": list(dict.fromkeys(advisory))}


def mechanical(run: Path, draft: dict, charts: dict, facts: list[dict], tables: dict, catalog: list[dict],
               claims: list[dict] | None = None, cmap: dict | None = None) -> dict:
    cfg = config.load()["note"]
    blocking, advisory = [], []
    if claims is None:
        from . import claims as claims_mod
        claims, cmap = claims_mod.load(run), claims_mod.load_map(run)
    res = pipeline_checks.run_checks(run.name, ["numbers", "style", "licences", "charts", "readability"])
    for name, r in res.items():
        blocking += [f"{name}: {x}" for x in r.get("blocking", [])]
        advisory += [f"{name}: {x}" for x in r.get("advisory", [])][:12]
    n = text.words(draft)
    lo, hi = cfg["words"]
    if n < lo * 0.85 or n > hi * 1.15:
        blocking.append(f"length: {n} words of prose; the note runs {lo}–{hi}")
    elif not lo <= n <= hi:
        advisory.append(f"length: {n} words of prose; the note runs {lo}–{hi}")
    forms = {c["form"] for c in charts.values()}
    blocking += figure_rules(draft, charts, tables, catalog, cfg)
    ids = [s.get("id") for s in draft.get("sections", [])]
    for need in ("limits", "method"):
        if need not in ids:
            blocking.append(f"sections: no section with id `{need}`")
    con = consolidation(draft, facts, tables, catalog)
    if len(con["apps"]) < cfg["min_apps"]:
        blocking.append(f"consolidation: the note cites {con['apps'] or 'no app'}; at least {cfg['min_apps']} apps are needed")
    if len(con["publishers"]) < cfg["min_publishers"]:
        blocking.append(f"consolidation: publishers behind the note are {con['publishers']}; at least {cfg['min_publishers']} are needed")
    if not con["joined_facts"]:
        blocking.append("consolidation: no number in the note needs both the funding side and the trade side; the join must be in the text")
    reader = text.article(draft, {f["id"]: f for f in facts}, charts, "reader")
    body = "\n".join(l for l in reader.splitlines() if not l.startswith(("  Data", "    ", "  Source")))
    for m in CODES.finditer(body):
        blocking.append(f"internal code “{m.group(0)}” in the text: readers do not know it; use the plain name ({body[max(0, m.start() - 50):m.end() + 30]!r})")
    # our apps and pages are not words readers know: the argument names the statistics (BIS, IMF, UN Comtrade); the
    # method section and the question box say which datasteg pages they were read from
    argued = [draft.get("title"), draft.get("dek"), *(draft.get("findings") or []), *[k.get("label") for k in draft.get("keyNumbers") or []],
              (draft.get("insight") or {}).get("text")]
    for sec in draft.get("sections", []):
        if sec.get("id") != "method":
            argued += [sec.get("heading")] + [b.get("text") for b in sec.get("blocks", []) if b.get("type") == "p"] \
                      + [i for b in sec.get("blocks", []) if b.get("type") == "list" for i in b.get("items", [])]
    for ch in charts.values():
        argued += [text._tx(ch.get(k)) for k in ("headline", "title", "subtitle")]
        # what a chart prints besides its title: series, the ends of a dumbbell, axes, its table's headers
        printed = [text._tx(ch.get(k)) for k in ("fromLabel", "toLabel", "howToRead")] + [text._tx(s.get("label")) for s in ch.get("series") or []] \
            + [text._tx(a.get("label")) for a in (ch.get("axes") or {}).values() if isinstance(a, dict)] \
            + [text._tx(c.get("label")) for c in (ch.get("table") or {}).get("columns") or []]
        for m in (CODES.search(x or "") for x in printed):
            if m:
                blocking.append(f"figure {ch['id']}: internal code “{m.group(0)}” in a label readers see; name the measure in plain words")
                break
    for t in argued:
        m = INTERNAL.search(t or "")
        if m:
            blocking.append(f"“{m.group(0)}” is our own page or app name, which readers do not know: name the statistics instead (BIS, IMF, "
                            f"UN Comtrade) and keep datasteg's page names for the method section ({(t or '')[max(0, m.start() - 50):m.end() + 30]!r})")
    if body.count("HHI") and "Herfindahl" not in body:
        blocking.append("“HHI” is used without its plain name (a Herfindahl index: the sum of squared shares)")
    for m in list(CAUSAL.finditer(body))[:6]:
        advisory.append(f"causal wording “{m.group(0)}”: allowed only for a mechanism stated as a condition, never for a pattern in the data "
                        f"({body[max(0, m.start() - 60):m.end() + 40]!r})")
    for m in list(FORECAST.finditer(body))[:4]:
        blocking.append(f"forecast or advice wording “{m.group(0)}” ({body[max(0, m.start() - 60):m.end() + 40]!r})")
    for m in list(HYPE.finditer(body))[:4]:
        advisory.append(f"hype or filler “{m.group(0)}”")
    cites = draft.get("citations") or {}
    for c in con["cited"]:
        if not (cites.get(c) or {}).get("used_for"):
            advisory.append(f"citations: no used_for line for {c}")
    for s in draft.get("sections", []):
        for b in s.get("blocks", []):
            if b.get("type") == "p" and TOKEN.search(b.get("text", "")) and not CITE.search(b.get("text", "")):
                advisory.append(f"{s.get('id')}: a paragraph with numbers carries no citation mark ({b['text'][:60]}…)")
                break
    lint = claim_lints(draft, charts, claims, cmap, {f["id"]: f for f in facts})
    blocking += lint["blocking"]
    advisory += lint["advisory"]
    if not 3 <= len(draft.get("keyNumbers") or []) <= 3:
        advisory.append(f"key numbers: {len(draft.get('keyNumbers') or [])}; the note has three")
    return {"blocking": list(dict.fromkeys(blocking)), "advisory": list(dict.fromkeys(advisory))[:30],
            "stats": {"words": n, "figures": len(charts), "forms": sorted(forms), **con,
                      "readability": (res.get("readability") or {}).get("stats")}}


def source_lines(catalog: list[dict], cited: list[str]) -> list[str]:
    """The sources a reader will see, for the judged text."""
    cmap = {d["id"]: d for d in catalog}
    seen, out = set(), []

    def add(did, depth=0):
        d = cmap.get(did)
        if not d or did in seen:
            return
        seen.add(did)
        if d.get("inputs") and depth < 4:
            for i in d["inputs"]:
                add(i, depth + 1)
            return
        out.append(f"{d['provider']}. {d['title']}. {d.get('url') or ''} (release {d.get('release')}; retrieved {str(d.get('retrieved'))[:10]})")
    for c in cited:
        add(c if c in cmap else dataset_id(c))
    return out
