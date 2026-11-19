"""The claim ledger (rule R2): what a note claims, as data, beside the facts.

The facts make every number safe: a model never types one, and each has a formula and a period. What a sentence
claims with those numbers was free text: its comparison, its base, the population a median is taken over, the
measure's name and whether the result is built into the measure. Note 20261118-desk showed the cost: a chart title
"three of six above the group median" was true and still read as a result, because half of any set sits above a
median and the inflow economies showed the same share.

So the analyst writes the claims the note may make (analysis/claims.json), each with its base, the population its
reference statistic is taken over, its comparator, its period, its reading and whether it is mechanical. Code checks
each claim here (`validate`); the writer then cites a claim for every string a skimming reader sees (title, dek, key
numbers, findings, chart headlines), and the lints (review.claim_lints), the inference test and the Korean checks
hold those strings to their claims.

The measures registry (family/measures.json, rule C1) gives each measure its name, the names it may
also go by (`aliases`), the names it must never carry (`never_call`) and, for a composite, the measures it is built
from (`inputs`); the joint stress signals and their inputs are listed under stress_count.signals.
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

from ..content import TOKEN
from ..paths import ARTICLES, read_json, write_json

REGISTRY = ARTICLES.parent / "family" / "measures.json"
KINDS = ("share_above", "count", "rank", "level", "change", "extreme", "correlation", "equal", "difference")
READINGS = ("difference", "no_difference", "extreme", "level", "mechanism")
FINDING_TYPES = READINGS          # the editor's finding_type is one of the readings (R1)
COUNTS = ("count", "countries", "rank")

# the panel's columns (and the stress view's) as registry measures; "signal:jN" is one of the joint stress signals
COLUMN_MEASURE = {
    "vulnerability": "vulnerability_v", "v": "vulnerability_v", "flow_pct": "flow_score_f", "flow": "flow_score_f",
    "a2_pct": "a2", "niip_gdp_pct": "niip_gdp", "b1_usd_bn": "bank_flow_lbs", "b2_usd_bn": "intl_debt_securities",
    "net_reserves_usd_bn": "net_reserves", "stress_count": "stress_count", "import_cover_months": "j1_import_cover",
    "financing_need_pct_exports": "j2", "lender_dest_overlap_pct": "overlap", "exports_12m_usd_bn": "goods_exports_partner",
    "imports_12m_usd_bn": "goods_imports_own", "exports_yoy_pct": "goods_trade_growth", "imports_yoy_pct": "goods_trade_growth",
    "export_market_hhi": "export_market_hhi", "bank_loans_usd_bn": "bank_loans_lbs", "top_lender_share_pct": "lender_share",
    "replay_vs_reserves_pct": "withdrawal_replay",
    "j1": "j1_import_cover", "j2": "j2", "j5": "overlap", "j3": "signal:j3", "j4": "signal:j4", "j6": "signal:j6", "j7": "signal:j7",
}

# a reference set a skimming reader cannot place: "the group", "group median", "the rest", "others", "the panel"
VAGUE_SET = re.compile(r"\b(?:the\s+)?group(?:'s)?\s+(?:median|mean|average)\b|\b(?:median|mean|average)\s+of\s+the\s+group\b|"
                       r"\bthe\s+group\b|\bthe\s+rest\b|\b(?:the\s+)?others\b|\bthe\s+other\s+economies\b|\bthe\s+panel\b", re.I)
DEFINED_SET = re.compile(r"\{\{F\d+[^}]*\}\}|\b\d+\b|\ball\b|\bwith (?:export |trade |funding )?data\b|\bthat (?:received|gained|lost)\b|"
                         r"\b(?:inflow|outflow|surplus|deficit) economies\b|\bof the \w+ economies\b", re.I)


class ClaimError(ValueError):
    pass


# ------------------------------------------------------------------ the registry

@functools.lru_cache(maxsize=1)
def registry() -> dict:
    return (read_json(REGISTRY, {}) or {}).get("measures") or {}


def measure_id(m: str | None) -> str | None:
    """A claim's `measure` as a registry id ("signal:j3" for a stress signal), or None when it is not one."""
    if not m:
        return None
    m = str(m).strip()
    reg = registry()
    if m in reg:
        return m
    if m.startswith("signal:") and m[7:] in ((reg.get("stress_count") or {}).get("signals") or {}):
        return m
    if m in COLUMN_MEASURE:
        return COLUMN_MEASURE[m]
    if re.fullmatch(r"[Jj][1-7]", m):
        return COLUMN_MEASURE.get(m.lower())
    return None


def info(mid: str) -> dict:
    """{id, name, aliases, never_call, inputs} of a registry measure or a stress signal."""
    reg = registry()
    if mid.startswith("signal:"):
        s = ((reg.get("stress_count") or {}).get("signals") or {}).get(mid[7:]) or {}
        if s.get("measure"):
            return info(s["measure"])
        return {"id": mid, "name": s.get("name") or mid, "aliases": s.get("aliases") or [], "never_call": s.get("never_call") or [],
                "inputs": s.get("inputs") or [], "definition": s.get("definition")}
    m = reg.get(mid) or {}
    return {"id": mid, "name": (m.get("name") or {}).get("en") or mid, "name_ko": (m.get("name") or {}).get("ko"),
            "aliases": m.get("aliases") or [], "never_call": m.get("never_call") or [], "inputs": m.get("inputs") or [],
            "definition": (m.get("definition") or {}).get("en")}


def inputs_of(mid: str, depth: int = 0) -> set[str]:
    """Every measure a composite is built from, at any depth."""
    out: set[str] = set()
    for i in info(mid)["inputs"] if depth < 5 else []:
        out.add(i)
        out |= inputs_of(i, depth + 1)
    return out


def columns_of(mids: set[str]) -> set[str]:
    return {c for c, m in COLUMN_MEASURE.items() if m in mids}


def never_call() -> list[tuple[re.Pattern, str, dict]]:
    """(pattern, the wrong name, the measure) for every registry name a text must not use."""
    out = []
    reg = registry()
    ids = list(reg) + [f"signal:{k}" for k in ((reg.get("stress_count") or {}).get("signals") or {})]
    for mid in ids:
        m = info(mid)
        for wrong in m["never_call"]:
            pat = re.escape(wrong).replace(re.escape("{economy}"), r"(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)?|its)")
            out.append((re.compile(r"\b" + pat + r"\b", re.I if "{economy}" not in wrong else 0), wrong, m))
    return out


# ------------------------------------------------------------------ the ledger

def _tokens(x) -> list[str]:
    return [m.group(1) for m in TOKEN.finditer(json.dumps(x, ensure_ascii=False))]


def resolve(specs: list, facts: list[dict]) -> tuple[list[dict], list[dict]]:
    """The analyst's claims with fact keys ({{n_out}}) turned into fact ids ({{F12}}). Returns (claims, problems)."""
    keys = {f["key"]: f["id"] for f in facts if f.get("key")}
    ids = {f["id"] for f in facts}
    out, problems = [], []
    for c in specs if isinstance(specs, list) else []:
        if not isinstance(c, dict):
            problems.append({"claim": None, "problem": "a claim must be an object"})
            continue
        bad = []

        def sub(m):
            k = m.group(1)
            if k in ids:
                return m.group(0)
            if k in keys:
                return "{{" + keys[k] + (m.group(2) or "") + "}}"
            bad.append(k)
            return m.group(0)
        txt = re.sub(r"\{\{([A-Za-z_][\w]*)(\|[a-z,]+)?\}\}", sub, json.dumps(c, ensure_ascii=False))
        if bad:
            problems.append({"claim": c.get("id"), "problem": f"names facts that do not exist or could not be computed: {sorted(set(bad))}; "
                                                              "use the `key` of a fact you asked for, or drop the claim"})
            continue
        out.append(json.loads(txt))
    return out, problems


def _fact(fmap: dict, v) -> dict | None:
    m = TOKEN.search(str(v or ""))
    return fmap.get(m.group(1)) if m else None


def _where_columns(where: str | None, tables: dict, table: str) -> set[str]:
    t = tables.get(table) or {}
    cols = {c.get("id") for c in t.get("columns") or []} | set(COLUMN_MEASURE)
    return {w for w in re.findall(r"[a-z][a-z0-9_]*", where or "") if w in cols}


def expected_mechanical(c: dict, tables: dict) -> tuple[bool, str]:
    """Whether the claim's subject set is selected by an input of its measure (or by the measure itself): then a
    ranking or a count of that set on the measure follows from how the measure is built. Returns (mechanical, why)."""
    mid = measure_id(c.get("measure"))
    if not mid:
        return False, ""
    subj = c.get("subject") or {}
    used = _where_columns(subj.get("where"), tables, subj.get("table") or "panel")
    ins = inputs_of(mid)
    hit = used & columns_of(ins)
    if hit:
        names = sorted({info(COLUMN_MEASURE[h])["name"] for h in hit})
        return True, f"the subject set is selected on {', '.join(sorted(hit))} ({'; '.join(names)}), an input of {info(mid)['name']}"
    return False, ""


def validate(claims: list[dict], facts: list[dict], tables: dict, brief: dict | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """Code's checks on each claim. Returns (claims that pass, problems for the analyst,
    cautions). A claim that fails is not used; the analyst gets the problem back, as for a fact that failed."""
    fmap = {f["id"]: f for f in facts}
    ok, problems, cautions = [], [], []
    seen = set()
    for c in claims:
        cid = str(c.get("id") or "")
        why = []
        if not re.fullmatch(r"C\d+", cid) or cid in seen:
            why.append("`id` must be C1, C2 … and unique")
        kind, reading = c.get("kind"), c.get("reading")
        if kind not in KINDS:
            why.append(f"`kind` {kind!r} is not one of {list(KINDS)}")
        if reading not in READINGS:
            why.append(f"`reading` {reading!r} is not one of {list(READINGS)}")
        if not measure_id(c.get("measure")):
            why.append(f"`measure` {c.get('measure')!r} is not a registry id (family/measures.json) nor a column the registry maps; "
                       "use the measure's registry id, or the table column it is read from")
        unknown = [t for t in _tokens(c) if t not in fmap]
        if unknown:
            why.append(f"names facts that are not on the sheet: {unknown}")
        subj, stat, comp = c.get("subject") or {}, c.get("statistic") or {}, c.get("comparator")
        if not str(subj.get("set") or "").strip():
            why.append("`subject.set` must name the economies the claim is about, in words")
        if not TOKEN.search(str(stat.get("value") or "")):
            why.append("`statistic.value` must be a fact token")
        against = str(stat.get("against") or "").strip()
        if kind in ("count", "share_above"):
            if not TOKEN.search(str(stat.get("base") or "")):
                why.append(f"a {kind} needs `statistic.base`: the fact that counts the set it is out of ('3 of 6' needs the 6)")
        if kind == "share_above" or re.search(r"\b(median|mean|average|top|highest|lowest)\b", against, re.I):
            if not against:
                why.append("`statistic.against` must say what the count is above or below")
            elif VAGUE_SET.search(against) and not DEFINED_SET.search(VAGUE_SET.sub("", against)):
                why.append(f"`statistic.against` {against!r} does not name its population: write 'median of all economies with export data', never 'the group'")
            if not TOKEN.search(str(stat.get("ref") or "")) and re.search(r"\b(median|mean|average)\b", against, re.I):
                why.append("`statistic.ref` must be the fact of the median or mean the count is read against")
            no_comp = str(c.get("no_comparator") or "").strip()
            if not (isinstance(comp, dict) and TOKEN.search(str(comp.get("value") or ""))) and len(no_comp.split()) < 6:
                why.append("a share against a median, a mean or a top-N needs a `comparator` (the same statistic for the other economies: "
                           "half of any set sits above a median), or `no_comparator` saying why none applies")
        if reading in ("no_difference", "difference") and not (isinstance(comp, dict) and TOKEN.search(str(comp.get("value") or ""))):
            why.append(f"a `{reading}` reading needs a `comparator` with its value: no difference from what?")
        if isinstance(comp, dict) and comp:
            if not str(comp.get("set") or "").strip():
                why.append("`comparator.set` must name the other economies, in words")
            elif VAGUE_SET.search(str(comp["set"])) and not DEFINED_SET.search(VAGUE_SET.sub("", str(comp["set"]))):
                why.append(f"`comparator.set` {comp['set']!r} does not name its population")
            if kind in ("count", "share_above") and not TOKEN.search(str(comp.get("base") or "")):
                why.append("`comparator.base` must be the fact that counts the comparator's set")
        if not str(c.get("period") or "").strip():
            why.append("`period` must give the period of the claim's numbers, for each side if they differ")
        if not isinstance(c.get("mechanical"), bool):
            why.append("`mechanical` must be true or false")
        # the periods of the values compared must agree (rule C2, check K9); a change compares a measure with itself
        if kind != "change" and not unknown:
            vals = [_fact(fmap, x) for x in (stat.get("value"), stat.get("ref"), (comp or {}).get("value") if isinstance(comp, dict) else None)]
            pers = {str(f.get("period")) for f in vals if f and f.get("unit") not in COUNTS and f.get("period")}
            if len(pers) > 1:
                why.append(f"its values are of different periods {sorted(pers)}: compare like with like (rule C2), or make it a `change`")
        mech, mwhy = expected_mechanical(c, tables)
        if mech and c.get("mechanical") is False:
            why.append(f"`mechanical` must be true: {mwhy}. A ranking or count of that set on the measure follows from how it is built")
        if why:
            problems.append({"claim": cid or None, "problem": "; ".join(why)})
            continue
        seen.add(cid)
        ok.append(c)
    if claims and not any(c.get("finding") for c in ok):
        problems.append({"claim": None, "problem": "no claim is marked `finding: true`: mark the one claim the note's title states"})
    ft = (brief or {}).get("finding_type")
    lead = next((c for c in ok if c.get("finding")), None)
    if ft and lead and lead.get("reading") != ft:
        cautions.append(f"The editor expected a {ft} finding; the finding claim {lead['id']} reads {lead.get('reading')}. "
                        "The writer frames the note by the claim, not by the brief.")
    return ok, problems, cautions


def save(run: Path, claims: list[dict]) -> None:
    write_json(run / "analysis" / "claims.json", {"claims": claims, "rules": "artools/desk/claims.py"})


def load(run: Path) -> list[dict]:
    return (read_json(run / "analysis" / "claims.json", {}) or {}).get("claims") or []


def _r(v, fmap, lang="en") -> str:
    from ..content import render_fact
    def sub(m):
        f = fmap.get(m.group(1))
        return render_fact(f, lang) if f else m.group(0)
    return TOKEN.sub(sub, str(v)) if v is not None else ""


def render(c: dict, fmap: dict, ids: bool = True) -> str:
    """One claim as a line a writer, a reviewer or the editor reads (values filled in, with their fact ids)."""
    def v(x):
        s = _r(x, fmap)
        return s + (" {" + ",".join(_tokens(x)) + "}" if ids and _tokens(x) else "")
    stat, comp = c.get("statistic") or {}, c.get("comparator")
    subj = c.get("subject") or {}
    s = f"{c.get('id')} [{c.get('kind')}; reading {c.get('reading')}{'; MECHANICAL' if c.get('mechanical') else ''}{'; THE FINDING' if c.get('finding') else ''}] "
    s += f"{subj.get('set')}" + (f" (n {v(subj.get('n'))})" if subj.get("n") else "") + f": {v(stat.get('value'))}"
    if stat.get("base"):
        s += f" of {v(stat.get('base'))}"
    if stat.get("against"):
        s += f", against {stat['against']}" + (f" ({v(stat.get('ref'))})" if stat.get("ref") else "")
    if isinstance(comp, dict) and comp:
        s += f" · comparator {comp.get('set')}: {v(comp.get('value'))}" + (f" of {v(comp.get('base'))}" if comp.get("base") else "")
    elif c.get("no_comparator"):
        s += f" · no comparator: {c['no_comparator']}"
    mid = measure_id(c.get("measure"))
    s += f" · measure {info(mid)['name'] if mid else c.get('measure')} · period {c.get('period')}"
    if c.get("says"):
        s += f" · says: {_r(c['says'], fmap)}"
    return s


def sheet(claims: list[dict], fmap: dict, ids: bool = True) -> str:
    return "\n".join("- " + render(c, fmap, ids) for c in claims) or "(no claims)"


def card(claims: list[dict], fmap: dict, cmap: dict, lang: str = "en") -> list[dict]:
    """The claims as the admin page shows them: each with its base, comparator and period, and the strings that state it."""
    by = {}
    for path, ids in cmap.items():
        for i in ids:
            by.setdefault(i, []).append(path)
    out = []
    for c in claims:
        stat, comp = c.get("statistic") or {}, c.get("comparator") if isinstance(c.get("comparator"), dict) else {}
        mid = measure_id(c.get("measure"))
        out.append({"id": c.get("id"), "kind": c.get("kind"), "reading": c.get("reading"), "finding": bool(c.get("finding")),
                    "mechanical": bool(c.get("mechanical")), "measure": info(mid)["name"] if mid else c.get("measure"),
                    "subject": (c.get("subject") or {}).get("set"), "value": _r(stat.get("value"), fmap, lang),
                    "base": _r(stat.get("base"), fmap, lang) or None, "against": stat.get("against"),
                    "ref": _r(stat.get("ref"), fmap, lang) or None,
                    "comparator": ({"set": comp.get("set"), "value": _r(comp.get("value"), fmap, lang), "base": _r(comp.get("base"), fmap, lang) or None}
                                   if comp else None),
                    "no_comparator": c.get("no_comparator"), "period": c.get("period"), "says": _r(c.get("says"), fmap, lang) or None,
                    "stated_in": sorted(by.get(c.get("id"), []))})
    return out


# ------------------------------------------------------------------ the writer's claim map (R3)

def surface_paths(draft: dict, figures: list[dict] | dict) -> list[str]:
    """The strings a skimming reader sees, each of which must state a claim: title, dek, key numbers, findings and
    every chart headline."""
    out = ["title", "dek"]
    out += [f"keyNumbers.{i}" for i, _ in enumerate(draft.get("keyNumbers") or [])]
    out += [f"findings.{i}" for i, _ in enumerate(draft.get("findings") or [])]
    ids = list(figures) if isinstance(figures, dict) else [f.get("id") for f in figures or [] if isinstance(f, dict)]
    out += [f"figure:{i}" for i in ids if i]
    return out


def claim_map(answer: dict) -> dict[str, list[str]]:
    """The writer's `claims` map, normalised to {path: [claim ids]}. A figure's id may also be given on its spec."""
    raw = answer.get("claims") if isinstance(answer.get("claims"), dict) else {}
    out = {}
    for k, v in raw.items():
        ids = v if isinstance(v, list) else re.findall(r"C\d+", str(v or ""))
        out[str(k)] = [str(x) for x in ids if re.fullmatch(r"C\d+", str(x))]
    for f in answer.get("figures") or []:
        if isinstance(f, dict) and f.get("id") and f.get("claim") and f"figure:{f['id']}" not in out:
            out[f"figure:{f['id']}"] = re.findall(r"C\d+", str(f["claim"]))
    return out


def check_map(answer: dict, claims: list[dict]) -> list[str]:
    """Build problems: a surface string with no claim, or a claim id that is not in the ledger."""
    if not claims:
        return []
    draft = answer.get("draft") if isinstance(answer.get("draft"), dict) else {}
    known = {c["id"] for c in claims}
    cm = claim_map(answer)
    out = []
    for p in surface_paths(draft, answer.get("figures") or []):
        ids = cm.get(p) or []
        if not ids:
            out.append(f"claims: `{p}` cites no claim; give the claim id it states in the answer's `claims` map ({{\"{p}\": \"C1\"}}), "
                       "or rewrite it to state one of the ledger's claims")
        elif any(i not in known for i in ids):
            out.append(f"claims: `{p}` cites {', '.join(i for i in ids if i not in known)}, which the ledger does not have")
    return out


def save_map(run: Path, cmap: dict) -> None:
    write_json(run / "draft" / "claims-map.json", cmap)


def load_map(run: Path) -> dict:
    return read_json(run / "draft" / "claims-map.json", {}) or {}


# ------------------------------------------------------------------ what a skimming reader sees (R4)

def surface(draft: dict, charts: dict, fmap: dict, lang: str = "en") -> list[dict]:
    """[{key, text}]: the title, the dek, each key number (value and label) and each chart's headline, title and
    subtitle, as a reader sees them on a list page or when skimming the charts. Keys match the claim map's paths
    (a chart's subtitle is `figure:<id>.subtitle`)."""
    from . import text as text_mod
    P = lambda s: text_mod._plain(s or "", fmap, lang=lang)     # noqa: E731
    T = lambda v: text_mod._tx(v, lang) if isinstance(v, dict) else (v or "")   # noqa: E731
    out = [{"key": "title", "text": P(draft.get("title"))}, {"key": "dek", "text": P(draft.get("dek"))}]
    for i, k in enumerate(draft.get("keyNumbers") or []):
        out.append({"key": f"keyNumbers.{i}", "text": f"{P(k.get('value'))} — {P(k.get('label'))}"})
    placed = [b.get("chart") for s in draft.get("sections", []) for b in s.get("blocks", []) if b.get("type") == "figure"]
    for cid in placed + [c for c in charts if c not in placed]:
        ch = charts.get(cid)
        if not ch:
            continue
        out.append({"key": f"figure:{cid}", "text": T(ch.get("headline"))})
        for part in ("title", "subtitle"):
            if T(ch.get(part)):
                out.append({"key": f"figure:{cid}.{part}", "text": T(ch.get(part))})
    return [x for x in out if x["text"].strip()]


DIRECTIONAL = {"better", "worse", "higher", "lower", "more", "fewer", "larger", "smaller", "outperformed", "underperformed"}
SAME = {"same", "like", "similar", "no_difference", "equal"}
# a conclusion that already speaks of both sets ("outflow or not", "in every economy", "whether funding came in or left")
BOTH_SIDES = re.compile(r"\bor not\b|\bwhether\b|\bboth\b|\beither\b|\bevery (?:economy|one)\b|\ball (?:the )?economies\b|\bas well as\b|"
                        r"\bthe same\b|\bas (?:in|among|for|often|much|fast)\b|\b(?:vs\.?|versus|against|compared with)\b|\blike\b", re.I)
# a conclusion that itself says the two are alike ("about as common", "essentially the same") reads no difference,
# whatever relation the reader tagged it with
ALIKE = re.compile(r"\babout as\b|\bas (?:common|likely|often|much|fast) as\b|\b(?:roughly|essentially|about|much|nearly) the same\b|"
                   r"\bjust as\b|\bno different\b|\bsimilar\b|\bsmall gap\b|\bgap is (?:small|tiny)\b", re.I)
_STOP = {"the", "economies", "economy", "with", "data", "export", "exports", "of", "and", "that", "in", "all", "group", "a", "an",
         "their", "its", "to", "for", "on", "at", "by", "from", "those", "other", "others", "were", "was", "had", "have"}


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", str(s or "").lower()) if w not in _STOP}


def match(conclusions: list[dict], claims: list[dict], cmap: dict) -> list[dict]:
    """Each conclusion of the inference test against the claims its strings cite (code, R4). verdict: supported |
    contradicted | unresolved (no claim cited, or code cannot tell: the role's match task decides those)."""
    by = {c["id"]: c for c in claims}
    out = []
    for x in conclusions or []:
        keys = [str(k).split(".")[0] if str(k).startswith("figure:") else str(k) for k in x.get("from") or []]
        ids = sorted({i for k in keys for i in cmap.get(k) or []})
        cited = [by[i] for i in ids if i in by]
        rel = str(x.get("relation") or "none").lower()
        words = _words(x.get("subject")) | _words(x.get("comparator")) | _words(x.get("says"))
        both = bool(BOTH_SIDES.search(str(x.get("says") or "")))
        per = []
        for c in cited:
            sw = _words((c.get("subject") or {}).get("set")) | _words(((c.get("comparator") or {}) if isinstance(c.get("comparator"), dict) else {}).get("set"))
            about = bool(words & sw)
            about_cmp = bool(_words(x.get("comparator")) & sw) and bool(_words(x.get("subject")) & sw)
            rd = c.get("reading")
            if c.get("mechanical") and not x.get("by_construction") and rel in DIRECTIONAL | {"finding"}:
                per.append(("contradicted", f"{c['id']} is mechanical (the subject was selected by an input of the measure), "
                                            "but a reader takes it as a finding"))
            elif rd == "no_difference":
                if rel in SAME or (both and rel not in DIRECTIONAL) or rel == "none" or ALIKE.search(str(x.get("says") or "")):
                    per.append(("supported", ""))
                elif rel in DIRECTIONAL and about_cmp and not ALIKE.search(str(x.get("says") or "")):
                    per.append(("contradicted", f"{c['id']} reads no difference, but a reader concludes one side did {rel}"))
                elif rel == "finding" and about and not str(x.get("comparator") or "").strip() and not both:
                    # a count taken as a result, or a plain description of another fact: code cannot tell (r5 on 18 Nov
                    # 2026: "eight of 36 economies lost funding" is the latter); the match task decides with the ledger
                    per.append(("unresolved", f"a reader takes a result from a string citing {c['id']} (no difference) with no "
                                              "comparison; is it the claim's count read as a result?"))
                else:
                    per.append(("unresolved", f"code could not tell whether the conclusion reads a difference into {c['id']}"))
            elif rd == "difference":
                if rel in SAME and about_cmp:
                    per.append(("contradicted", f"{c['id']} reads a difference, but a reader concludes the two are the same"))
                elif rel in SAME:
                    per.append(("unresolved", f"code could not tell whether the conclusion denies {c['id']}'s difference"))
                else:
                    per.append(("supported", ""))
            elif rel in ("none",) and not about:
                per.append(("supported", ""))
            else:
                # a level, an extreme, a mechanism: whether the conclusion says what the claim says is for the match task
                per.append(("unresolved", f"code cannot check a {rd} claim's content; the match task reads {c['id']}"))
        if not cited:
            verdict, why = "unresolved", "the strings it comes from cite no claim"
        elif any(v == "contradicted" for v, _ in per):
            verdict, why = next((v, w) for v, w in per if v == "contradicted")
        elif any(v == "supported" for v, _ in per) and not any(v == "unresolved" and "content" in w for v, w in per):
            verdict, why = "supported", ""
        else:
            verdict, why = per[0]
        out.append({**{k: x.get(k) for k in ("says", "from", "relation", "subject", "comparator", "by_construction")},
                    "claims": ids, "verdict": verdict, "why": why})
    return out
