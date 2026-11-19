"""The Korean edition of a data note, drafted by qkr.

Every Korean string on datasteg's sites comes from qkr, datasteg's own Korean model (the repository's rule; live guide
at $QKR_URL/llm.txt), never from the desk's own models and never from a person's hand. So the Korean edition is a
derived edition: code takes each English string of the finished note, fills in its numbers, and asks qkr to draft
the Korean (`POST /v1/refine` with an empty `ko`). Nothing else writes Korean here:

- economy names in figures come from the sites' own table (money-flow/config/economies.csv);
- the byline and the disclaimer come from config/editorial.yaml;
- two model roles help, and both write English only. `ko-source` rewords an English string that qkr's checks
  refused (qkr fails an answer whose Korean holds a number or loses a code the English does not explain: "June"
  becomes 6월, "US" becomes 미국). `ko-checker` reads the Korean beside the English and reports where the meaning
  differs, with an English rewording for qkr to draft from again, and where one term came out in two Korean forms
  (qkr then refines those strings with its own chosen form as a required term).

What code checks on every answer, beside qkr's own checks: the citation marks are the same, the Korean holds no
number the English lacks and loses none of two digits or more, a headline is one line and short enough, no particle
token is left. `verify` repeats these on the run's files and is what `artools check numbers` runs for this edition:
the Korean prose carries its numbers filled in (qkr chooses the particle and the counter from the number it sees),
so the rule "a model never types a number" is kept by comparing each string with its English, not by fact tokens.

Files: draft/ko.json, the `ko` entries of charts/*.json and cover/cover.json, and desk/korean.json, the ledger of
every string: the English sent, qkr's answer, its status, the model and style versions. The edition is written
whenever qkr has answered (16 Nov 2026: the editor reviews the Korean in the admin site, so it must be there to read).
A string without an accepted answer carries qkr's own refused draft (`shown`, never edited), or its English when qkr
gave no Korean at all, and is listed beside the note as an open point. `qkr_notes` says, for each refused answer,
what qkr itself should learn (a one-line headline split in two, a month counted as a new number), apart from what
was the English's fault.
"""
from __future__ import annotations

import copy
import csv
import functools
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import runlib
from ..content import CITE, MONEY_UNIT, TOKEN, render_fact
from ..paths import ARTICLES, CONFIG, CONTENT, load_yaml, read_json, read_jsonl, write_json
from . import config, facts as facts_mod, polish as polish_mod, roles
from .api import DESK

QKR_URL = os.environ.get("QKR_URL", "https://ko-refiner.example:8001").rstrip("/")
ECONOMIES = ARTICLES.parent / "money-flow" / "config" / "economies.csv"
HANGUL = re.compile(r"[가-힣]")
JOSA_TOKEN = re.compile(r"\{[^{}|]+\|[^{}]+\}")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
SERVICES = ("money-flow", "trade-flow", "global-network", "open-research", "datasteg")
# a comparison clause of the English kept in the Korean (rule R8): a fixed list in code, never a model's
# words. A string that states a claim with a comparator must keep one of these when its English compares.
EXPLICIT_CMP = re.compile(r"\b(?:vs\.?|versus|against|compared with|as did|as among|(?:just |much )?like|unlike|the same (?:share |proportion )?as|"
                          r"as (?:often|much|fast|many|common|likely) as|about as|no (?:more|different|better|worse) than|than (?:among|in|for))\b", re.I)
KO_MARKERS = ("대비", "비해", "처럼", "와 같은", "과 같은", "반면", "마찬가지", "동일", "같다", "같은 비율", "에서도", "보다")
TITLE_MAX = int(((load_yaml(CONFIG / "editorial.yaml") or {}).get("headline_max") or {}).get("ko", 50))   # the style check's limit
SETTLED = ("ok", "editor")     # an accepted qkr answer, or the editor's own words (set in the admin site, never by a model)
TITLES = DESK / "titles-ko.jsonl"   # every Korean title the editor wrote or chose: ko-title reads them for the form


class KoreanDown(RuntimeError):
    """qkr cannot be used now (unreachable, 409 style change, 502, a 503 that stays). The step stops; no Korean
    is written any other way."""


# ------------------------------------------------------------------ the English qkr drafts from

MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September",
                                          "October", "November", "December"])}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items()) if len(m) > 3})
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))
CARDINALS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
             "twelve": 12}
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9,
            "tenth": 10, "eleventh": 11, "twelfth": 12}
FRACTIONS = {"half": 2, "halve": 2, "third": 3, "quarter": 4, "fifth": 5, "sixth": 6, "eighth": 8, "tenth": 10}
SPELL = [(r"\bUS(?=[\s\-.,;:)']|$)(?!\$)", "United States"), (r"\bU\.S\.(?=\s)", "United States"), (r"\bUK\b", "United Kingdom"),
         (r"\bUAE\b", "United Arab Emirates"), (r"\bFX\b", "foreign-currency"), (r"\bper dollar\b", "per 1 dollar"),
         (r"\btwo-thirds\b", "2/3"), (r"\bone-third\b", "1/3"), (r"\bthree-quarters\b", "3/4")]


def _fill(text: str, facts: dict) -> str:
    """Fact tokens as the numbers a reader sees. Money in bn or tn goes in its Korean form (4,530억 달러: the
    pipeline's own conversion), so qkr keeps it; everything else as English digits."""
    def sub(m):
        f = facts.get(m.group(1))
        if not f:
            return m.group(0)
        opts = set((m.group(2) or "").split(",")) - {""}
        money = MONEY_UNIT.match((f.get("unit") or "").strip())
        return render_fact(f, "ko", opts) if money else render_fact(f, "en", opts | {"digits"})
    return TOKEN.sub(sub, text)


def normalise(text: str) -> str:
    """English written so that qkr's checks can pass: a month as a number, a count as a digit, a country code
    spelled out. The meaning does not change; what the Korean will need is already in the English."""
    t = re.sub(r"\*([^*]+)\*", r"\1", text)
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", t))
    t = re.sub(rf"\b(\d{{1,2}}) ({_MON})\.? ((?:19|20)\d{{2}})\b", lambda m: f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}", t)
    t = re.sub(rf"\b[Ee]nd-({_MON})\.? ((?:19|20)\d{{2}})\b", lambda m: f"the end of {m.group(2)}-{MONTHS[m.group(1)]:02d}", t)
    t = re.sub(rf"\b({_MON})\.? ((?:19|20)\d{{2}})\b", lambda m: f"{m.group(2)}-{MONTHS[m.group(1)]:02d}", t)
    # a month without its year: the year of the string when it names only one, otherwise "month 6"
    # (not again on English already normalised: a rewording passes through here a second time)
    lone = rf"\b(to|in|of|since|from|until|by|through|and|early|late|the|on) ({_MON})\b(?!-| \(month)"
    if len(years) == 1:
        y = next(iter(years))
        t = re.sub(lone, lambda m: f"{m.group(1)} {y}-{MONTHS[m.group(2)]:02d}", t)
        t = re.sub(rf"\b[Ee]nd-({_MON})\b", lambda m: f"the end of {y}-{MONTHS[m.group(1)]:02d}", t)
    else:
        # no year to go by: the month keeps its name and gets its number ("month 7" alone was read as seven months)
        t = re.sub(lone, lambda m: f"{m.group(1)} {m.group(2)} (month {MONTHS[m.group(2)]})", t)
    # "the quarter to June 2026" is 2분기 in Korean, and "the year to June" is 12개월: say so in the English
    qtr = lambda y, m: f"quarter {int(m) // 3} of {y}"      # noqa: E731
    t = re.sub(r"\b(?:the )?quarters to ((?:19|20)\d{2})-(0[369]|12) and ((?:19|20)\d{2})-(0[369]|12)\b",
               lambda m: f"{qtr(m.group(1), m.group(2))} and {qtr(m.group(3), m.group(4))}", t, flags=re.I)
    t = re.sub(r"\b(?:the )?quarter to ((?:19|20)\d{2})-(0[369]|12)\b", lambda m: qtr(m.group(1), m.group(2)), t, flags=re.I)
    t = re.sub(r"\b(?:the|a) year to (?=(?:19|20)\d{2}-\d{2}\b)", "the 12 months to ", t, flags=re.I)
    # money in the pipeline's Korean form (the site writes a billion-dollar unit as 10억 달러, an amount in 억 and 조)
    def money(m):
        v = float(m.group(2).replace(",", "")) * (-1 if m.group(1) else 1)
        dec = len(m.group(2).partition(".")[2])
        return render_fact({"value": v, "unit": f"USD {m.group(3)}", "display": {"decimals": dec}}, "ko")
    t = re.sub(r"\bUSD (−|-)?(\d[\d,]*(?:\.\d+)?) (bn|tn)\b", money, t)
    t = re.sub(r"\bUSD (bn|tn)\b", lambda m: render_fact({"value": 1, "unit": f"USD {m.group(1)}", "display": {"decimals": 0}}, "ko"), t)
    t = re.sub(r"\b((?:19|20)\d{2})[- ]Q([1-4])\b", r"quarter \2 of \1", t)
    t = re.sub(r"\bQ([1-4]) ((?:19|20)\d{2})\b", r"quarter \1 of \2", t)
    t = re.sub(rf"\b(?:the )?({'|'.join(ORDINALS)}) quarter of ((?:19|20)\d{{2}})\b", lambda m: f"quarter {ORDINALS[m.group(1).lower()]} of {m.group(2)}", t, flags=re.I)
    t = re.sub(r"\bQ([1-4])\b", r"quarter \1", t)
    for pat, rep in SPELL:
        t = re.sub(pat, rep, t)
    # fractions: Korean writes 5분의 1, so the English carries both digits
    t = re.sub(rf"\b(one|{'|'.join(CARDINALS)})-({'|'.join(FRACTIONS)})s?\b",
               lambda m: f"{1 if m.group(1).lower() == 'one' else CARDINALS[m.group(1).lower()]}/{FRACTIONS[m.group(2).lower()]}", t, flags=re.I)
    t = re.sub(r"\b(?:a|one) (third|fifth|tenth)\b(?! (?:highest|lowest|largest|smallest|biggest|of all|in a row))", lambda m: f"1/{FRACTIONS[m.group(1).lower()]}", t)
    t = re.sub(r"\b(?:a|one) quarter of\b", "1/4 of", t)
    t = re.sub(rf"\b({'|'.join(CARDINALS)})(?=[ -][A-Za-z])", lambda m: str(CARDINALS[m.group(1).lower()]), t, flags=re.I)
    # ranks: Korean writes 5위, 1차; "first" and "second" only where they are plainly a rank or a round
    t = re.sub(rf"\b({'|'.join(o for o in ORDINALS if o not in ('first', 'second'))})\b(?=[ -](?:highest|lowest|largest|smallest|biggest|most|least|of|among|in)\b)",
               lambda m: _nth(ORDINALS[m.group(1).lower()]), t, flags=re.I)
    t = re.sub(r"\b(first|second)(?=-round\b|[ -](?:highest|lowest|largest|smallest|biggest)\b)", lambda m: _nth(ORDINALS[m.group(1).lower()]), t, flags=re.I)
    t = re.sub(r"\bzero\b", "0", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def _nth(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _nums(text: str) -> set[str]:
    out = set()
    for m in NUM.finditer(CITE.sub(" ", text)):
        s = m.group(0).replace(",", "").rstrip(".")
        whole, _, frac = s.partition(".")
        out.add((whole.lstrip("0") or "0") + ("." + frac if frac else ""))
    return out


def _word_numbers(text: str) -> set[str]:
    """Numbers an English text holds as words, which its Korean may write as digits."""
    low = text.lower()
    out = {str(v) for w, v in {**CARDINALS, **ORDINALS}.items() if re.search(rf"\b{w}\b", low)}
    out |= {str(int(m) // 3) for m in re.findall(r"\b(?:19|20)\d{2}-(0[369]|12)\b", text)}       # a quarter-end month names its quarter
    out |= {str(int(m)) for m in re.findall(r"\b(?:19|20)\d{2}-(\d{2})\b", text)}
    # a month named in words is a number in Korean ("end-March" is 3월말, "the June quarter" 6월 분기: 20261119-desk)
    out |= {str(i) for m, i in MONTHS.items() if len(m) > 3 and re.search(rf"\b{m}\b", text)}
    for a, b in re.findall(r"\b(\d{1,2})/(\d{1,2})\b", text):           # a fraction may be said as a percentage
        if int(b):
            out |= {a, b, f"{100 * int(a) / int(b):g}", str(round(100 * int(a) / int(b)))}
    for pat, vals in [(r"\bfifth", "5 20"), (r"\btenth", "10"), (r"\bthird", "3 33"),
                      (r"\bone\b|\bper\b|\ban?\b|\bsingle\b", "1"), (r"\btwice\b|\bdoubl|\bboth\b|\bhalf\b|\bhalves\b", "2"), (r"\bhalf\b", "50"),
                      (r"\bquarter\b", "4 25"), (r"\b(?:leads?|led|highest|largest|biggest|top)\b", "1"), (r"\bthird\b", "3"), (r"\bzero\b|\bnone\b|\bno\b", "0"), (r"\bdozen\b|\byear\b|\bannual", "12"), (r"\bbillion|\bbn\b", "10"), (r"\bhundred", "100"), (r"\bthousand", "1000")]:
        if re.search(pat, low):
            out |= set(vals.split())
    return out


def _cites(text: str) -> list[str]:
    """The sources a string cites. A mark repeated after a sentence was split is the same citation."""
    return sorted({c.strip() for m in CITE.finditer(text) for c in m.group(1).split(",")})


def problems(item: dict, ko: str, sent: str | None = None) -> list[str]:
    """What code finds wrong with a Korean answer for one string, beside qkr's own checks."""
    sent = sent if sent is not None else item["sent"]
    out = []
    if not ko or not ko.strip():
        return ["no Korean came back"]
    if "\n" in ko.strip():
        out.append("the answer has a line break; this field is one line")
    if _cites(sent) != _cites(ko):
        out.append(f"citation marks differ: English {_cites(sent)}, Korean {_cites(ko)}")
    have, got = _nums(sent), _nums(ko)
    new = sorted(got - have - (_word_numbers(sent) if item.get("words_ok", True) else set()))
    if new:
        out.append(f"the Korean has numbers the English does not: {new}")
    lost = sorted(n for n in have - got if "." in n or len(n) >= 2)
    if lost:
        out.append(f"the Korean lost numbers: {lost}")
    if JOSA_TOKEN.search(ko):
        out.append("a particle token is left in the answer")
    # code writes months as 2026-06 for the number checks; the Korean writes 2026년 6월 (the claude engine copied the
    # code form into t8's Korean dek on 17 Nov 2026: "2026-06 말")
    if re.search(r"(?<![\d-])(?:19|20)\d{2}-\d{2}(?:-\d{2})?(?![\d-])", ko):
        out.append("a date is written as YYYY-MM in the Korean; write it as 2026년 6월 (or 2026년 6월말, 2026년 11월 17일)")
    # datasteg's service names are kept as written (qks-v2 translated them on 18 Nov 2026)
    for n in SERVICES:
        if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", sent) and n not in ko:
            out.append(f"the service name {n} was not kept as written")
    # the comparison of a claim's string is kept: its base and comparator numbers, and a comparison marker (R8)
    cmp_ = item.get("compare") or {}
    if cmp_:
        need = sorted(set(cmp_.get("numbers") or []) & _nums(sent))
        miss = [n for n in need if n not in _nums(ko)]
        if miss:
            out.append(f"comparison: the Korean dropped the base or the comparator {miss} that the English gives")
        # only an explicit comparison word asks for a Korean marker; two groups set side by side ("8.9% in A and 8.6% in B")
        # or "in all 34 economies" carry no marker in either language
        if EXPLICIT_CMP.search(sent) and not any(m in ko for m in KO_MARKERS):
            out.append("comparison: the English compares with the other economies and the Korean has no comparison marker "
                       "(korean.KO_MARKERS); it reads as a result on its own")
    if item["path"][-1] == "title" and item["kind"] == "draft" and len(ko.strip()) > TITLE_MAX:
        out.append(f"the Korean headline is {len(ko.strip())} characters; the site allows {TITLE_MAX}")
    if not HANGUL.search(ko) and len(re.findall(r"\b[a-z]{3,}\b", sent)) >= 2:
        out.append("the answer holds no Korean")
    # an economy's name cut short: qkr sometimes takes the last syllable of a name for a particle (벨기에 → 벨기은)
    for en, name in names().items():
        if len(name) >= 3 and name not in ko and name[:-1] in ko and re.search(rf"\b{re.escape(en)}\b", sent):
            out.append(f"the economy name {en} is misspelt in the Korean; the sites write it {name}")
    return out


# ------------------------------------------------------------------ the strings of a note

@functools.lru_cache(maxsize=1)
def names() -> dict[str, str]:
    """English name → Korean name, as the sites write economies (money-flow's economy table)."""
    out = {}
    if ECONOMIES.is_file():
        with ECONOMIES.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("name_en") and r.get("name_ko"):
                    out[r["name_en"]] = r["name_ko"]
    return out


def published_labels() -> dict[tuple[str, str], list[str]]:
    """(field, English) → the Korean that published articles carry for the same short label (the insight box's
    "Our read", a kicker). qkr gets them as `context`, so a note's label reads like the site's, not like a new coinage."""
    out: dict[tuple[str, str], list[str]] = {}
    for f in sorted((CONTENT / "articles").glob("*/ko.json")):
        ko, en = read_json(f, {}) or {}, read_json(f.parent / "en.json", {}) or {}
        for field, a, b in (("kicker", en.get("kicker"), ko.get("kicker")),
                            ("insight/label", (en.get("insight") or {}).get("label"), (ko.get("insight") or {}).get("label"))):
            if a and b and b not in out.setdefault((field, a), []):
                out[(field, a)].append(b)
    return out


def _sentence(s: str) -> bool:
    return bool(re.search(r"[.!?]\s*$", s.strip()) or re.search(r"[a-z]\. [A-Z]", s))


def _get(obj, path):
    for k in path:
        obj = obj[k]
    return obj


def _set(obj, path, value):
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = value


def strings(run: Path) -> tuple[list[dict], list[dict]]:
    """(strings for qkr, labels that are names). Each string: id, kind (draft | chart | cover), path, profile, en
    (as written, with fact tokens), sent (what qkr drafts from)."""
    draft = read_json(run / "draft" / "en.json", {}) or {}
    fmap = {f["id"]: f for f in facts_mod.load(run)}
    out, named = [], []
    seen = published_labels()
    from . import claims as claims_mod
    ledger = {c["id"]: c for c in claims_mod.load(run)}
    cmap = claims_mod.load_map(run)

    def surface_key(kind, path, chart):
        if chart:
            return f"figure:{chart}" if path == ["headline"] else None
        if path in (["title"], ["dek"]):
            return path[0]
        if len(path) == 3 and path[0] == "keyNumbers" and path[2] == "label":
            return f"keyNumbers.{path[1]}"
        if len(path) == 2 and path[0] == "findings":
            return f"findings.{path[1]}"
        return None

    def claim_info(key):
        """The numbers a claim's string must keep in Korean (base, comparator), and the claim as context for qkr."""
        cs = [ledger[i] for i in cmap.get(key) or [] if i in ledger] if key else []
        nums, ctx = set(), []
        for c in cs:
            comp = c.get("comparator") if isinstance(c.get("comparator"), dict) else {}
            stat = c.get("statistic") or {}
            for v in (stat.get("base"), comp.get("value"), comp.get("base")):
                if v:
                    nums |= _nums(normalise(_fill(str(v), fmap)))
            if c.get("reading") in ("no_difference", "difference") or c.get("kind") == "share_above" or c.get("mechanical"):
                ctx.append(normalise(_fill("The claim this headline states (keep its comparison, do not present the count as a result): "
                                           + claims_mod.render(c, fmap, ids=False), fmap))[:400])
        return ({"numbers": sorted(nums)} if cs else None), ctx

    def terms_for(sent):
        """The registry's Korean names for the measures the English names by their registry name (R8), as qkr terms."""
        out_ = {}
        for mid, m in claims_mod.registry().items():
            en_, ko_ = (m.get("name") or {}).get("en"), (m.get("name") or {}).get("ko")
            if en_ and ko_ and len(en_) >= 12 and re.search(rf"(?<!\w){re.escape(en_)}(?!\w)", sent, re.I):
                out_[en_] = ko_
        return out_

    def add(kind, path, profile, en, chart=None):
        if isinstance(en, str) and en.strip():
            sid = (f"c:{chart}:" if chart else "d:" if kind == "draft" else "v:") + "/".join(str(p) for p in path)
            sent = normalise(_fill(en, fmap))
            cmp_, cctx = claim_info(surface_key(kind, list(path), chart))
            ctx = ((seen.get(("/".join(str(p) for p in path), en)) or [])[:16] if kind == "draft" else []) + (cctx if chart else [])
            out.append({"id": sid, "kind": kind, "chart": chart, "path": list(path), "profile": profile, "en": en,
                        "sent": sent, "context": ctx[:16], **({"compare": cmp_} if cmp_ else {}),
                        **({"terms": t} if (t := terms_for(sent)) else {})})

    add("draft", ["kicker"], "label", draft.get("kicker"))
    add("draft", ["title"], "headline", draft.get("title"))
    add("draft", ["dek"], "article", draft.get("dek"))
    add("draft", ["whyNowLabel"], "label", draft.get("whyNowLabel"))
    add("draft", ["whyNow"], "article", draft.get("whyNow"))
    for i, k in enumerate(draft.get("keyNumbers") or []):
        add("draft", ["keyNumbers", i, "label"], "note", k.get("label"))
    for i, f in enumerate(draft.get("findings") or []):
        add("draft", ["findings", i], "article", f)
    for k in ("asked", "lookedAt", "premiseNote"):
        add("draft", ["question", k], "article", (draft.get("question") or {}).get(k))
    for i, s in enumerate(draft.get("sections") or []):
        add("draft", ["sections", i, "heading"], "headline", s.get("heading"))
        add("draft", ["sections", i, "summary"], "article", s.get("summary"))
        for j, b in enumerate(s.get("blocks") or []):
            if b.get("type") == "p":
                add("draft", ["sections", i, "blocks", j, "text"], "article", b.get("text"))
            elif b.get("type") == "list":
                for n, it in enumerate(b.get("items") or []):
                    add("draft", ["sections", i, "blocks", j, "items", n], "article", it)
    ins = draft.get("insight") or {}
    add("draft", ["insight", "label"], "label", ins.get("label"))
    add("draft", ["insight", "text"], "article", ins.get("text"))
    for cid, c in (draft.get("citations") or {}).items():
        add("draft", ["citations", cid, "used_for"], "note", (c or {}).get("used_for"))
    rep = draft.get("reproduce") or {}          # "Get the data": words go to qkr; URLs and code are copied unchanged
    add("draft", ["reproduce", "heading"], "headline", rep.get("heading"))
    add("draft", ["reproduce", "intro"], "article", rep.get("intro"))
    add("draft", ["reproduce", "note"], "note", rep.get("note"))
    add("draft", ["reproduce", "download", "label"], "label", (rep.get("download") or {}).get("label"))
    for i, it in enumerate(rep.get("items") or []):
        add("draft", ["reproduce", "items", i, "label"], "label", it.get("label"))
    for p in sorted((run / "charts").glob("*.json")):
        ch = read_json(p)
        cid = ch["id"]

        def en_of(path):
            try:
                v = _get(ch, path)
            except (KeyError, IndexError, TypeError):
                return None
            return v.get("en") if isinstance(v, dict) else None

        for key, prof in (("headline", "headline"), ("title", "label"), ("subtitle", "note"), ("alt", "article"), ("howToRead", "article"),
                          ("fromLabel", "label"), ("toLabel", "label")):
            add("chart", [key], prof, en_of([key]), cid)
        for i, n in enumerate(ch.get("notes") or []):
            add("chart", ["notes", i], "article" if _sentence(en_of(["notes", i]) or "") else "note", en_of(["notes", i]), cid)
        for ax in (ch.get("axes") or {}):
            add("chart", ["axes", ax, "label"], "label", en_of(["axes", ax, "label"]), cid)
        for i, _ in enumerate(ch.get("series") or []):
            add("chart", ["series", i, "label"], "label", en_of(["series", i, "label"]), cid)
        for i, _ in enumerate(ch.get("referenceLines") or []):
            add("chart", ["referenceLines", i, "label"], "label", en_of(["referenceLines", i, "label"]), cid)
        for i, _ in enumerate((ch.get("table") or {}).get("columns") or []):
            add("chart", ["table", "columns", i, "label"], "label", en_of(["table", "columns", i, "label"]), cid)
        add("chart", ["meta", "attribution"], "note", en_of(["meta", "attribution"]), cid)
        # labels that name a row: an economy, a banking system, a period
        for group in ("categories", "rows", "points"):
            for i, r in enumerate(ch.get(group) or []):
                if en_of([group, i, "label"]):
                    named.append({"chart": cid, "path": [group, i, "label"], "en": en_of([group, i, "label"])})
        for i, r in enumerate((ch.get("table") or {}).get("rows") or []):
            lab = r.get("label")
            lab = lab.get("en") if isinstance(lab, dict) else lab
            if isinstance(lab, str) and lab:
                named.append({"chart": cid, "path": ["table", "rows", i, "label"], "en": lab, "cell": True})
    cov = read_json(run / "cover" / "cover.json", None)
    if cov and isinstance(cov.get("alt"), dict):
        add("cover", ["alt"], "article", cov["alt"].get("en"))
    return out, named


def source_digest(items: list[dict], named: list[dict]) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(f"{it['id']}\0{it['profile']}\0{it['en']}\0".encode())
    for n in named:
        h.update(f"{n['chart']}\0{'/'.join(map(str, n['path']))}\0{n['en']}\0".encode())
    return h.hexdigest()[:20]


# ------------------------------------------------------------------ qkr

def _http(path: str, body: dict | None = None, timeout: int = 900):
    req = urllib.request.Request(QKR_URL + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    waits = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 503 and waits < int(os.environ.get("QKR_RETRIES", "3")):
                waits += 1
                time.sleep(int(e.headers.get("Retry-After") or 60))     # the GPU is busy (OCR, a swap): wait it out
                continue
            if e.code == 409:
                raise KoreanDown("qkr answered 409: its style version is not the one this code was written for; the owner must look") from e
            raise KoreanDown(f"qkr answered {e.code}: {e.read()[:200]!r}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise KoreanDown(f"qkr cannot be reached at {QKR_URL}: {e}") from e


CLAUDE_VERSIONS = {"model_version": "claude-p", "style_version": "claude-brief-1", "checks_version": "desk"}


def _engine() -> str:
    """qkr, or claude: `claude -p` through the ko-writer role while qkr is training (config korean.engine). The desk's own checks and the side-by-side reader run either way."""
    return (os.environ.get("DESK_KO_ENGINE") or config.load()["korean"].get("engine") or "qkr").lower()


_RUN: list[Path] = []      # the run being drafted, for the ko-writer role's logs


def health() -> dict:
    if _engine() == "claude":
        model = config.role("ko-writer")["model"]
        return {**CLAUDE_VERSIONS, "model_version": f"claude-p:{model}"}
    h = _http("/v1/health", timeout=60)
    if not h.get("ok", True) and h.get("llama") not in ("up", "swapped_out"):
        raise KoreanDown(f"qkr is not healthy: {h}")
    return h


def _claude_refine(items: list[dict], cfg: dict) -> dict[str, dict]:
    """qkr's refine through the ko-writer role (`claude -p`), in batches; answers shaped like qkr's."""
    out = {}
    batch = 12
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]
        reqs = [{"id": it["req"]["id"], "profile": it["req"]["profile"], "service": cfg["service"], "en": it["req"].get("en") or "",
                 "ko_now": it["req"].get("ko") or None, **{k: it["req"][k] for k in ("context", "locked", "terms") if it["req"].get(k)}}
                for it in chunk]
        try:
            data = roles.call(_RUN[-1], "ko-writer", json.dumps({"items": reqs}, ensure_ascii=False), label="korean")["data"] or {}
            got = {str(x.get("id")): x.get("ko") for x in data.get("items") or []}
        except (roles.RoleError, IndexError) as e:
            got, err = {}, str(e)
        model = config.role("ko-writer")["model"]
        for it in chunk:
            ko = got.get(it["req"]["id"])
            out[it["req"]["id"]] = ({"status": "refined", "ko": ko, "checks": {}} if ko else
                                    {"status": "fallback", "ko": "", "proposed": None, "checks": {"engine": "fail: no answer"}}) \
                | {"_versions": {**CLAUDE_VERSIONS, "model_version": f"claude-p:{model}"}}
    return out


def _refine(items: list[dict], cfg: dict) -> dict[str, dict]:
    """One request per string, a few at a time (the server works on four): {id: qkr's answer}."""
    if _engine() == "claude":
        return _claude_refine(items, cfg)
    def one(it):
        r = _http("/v1/refine", {"service": cfg["service"], "mode": it.get("mode", "fast"), "expect_style_version": cfg["style"], "items": [it["req"]]})
        a = (r.get("items") or [{}])[0]
        a["_versions"] = {k: r.get(k) for k in ("model_version", "style_version", "checks_version")}
        return it["req"]["id"], a
    with ThreadPoolExecutor(max_workers=cfg["workers"]) as ex:
        return dict(ex.map(one, items))


def _draft(todo: list[dict], cfg: dict) -> dict[str, dict]:
    """Draft mode (an empty `ko`): one call per distinct (profile, English), shared by the strings that carry it."""
    uniq = {}
    for it in todo:
        uniq.setdefault((it["profile"], it["sent"], tuple(it.get("context") or ()), json.dumps(it.get("terms") or {}, sort_keys=True)), []).append(it)
    # datasteg's service names are locked: qkr puts them back as written (its `names` check fails an answer that lost one)
    reqs = [{"req": {"id": hashlib.sha1(f"{p}\0{s}\0{c}\0{t}".encode()).hexdigest()[:12], "profile": p, "ko": "", "en": s, **({"context": list(c)} if c else {}),
                     **({"terms": json.loads(t)} if t != "{}" else {}),
                     **({"locked": lk} if (lk := [n for n in SERVICES if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", s)]) else {})}}
            for p, s, c, t in uniq]
    got = _refine(reqs, cfg)
    out = {}
    for r, ((p, s, c, t), its) in zip(reqs, uniq.items()):
        for it in its:
            out[it["id"]] = got[r["req"]["id"]]
    return out


def _take(it: dict, ans: dict, st: dict, how: str) -> None:
    """Record qkr's answer for a string: accepted when qkr's checks and the desk's pass."""
    failed = {k: v for k, v in (ans.get("checks") or {}).items() if v != "pass"}
    ko = ans.get("ko") if ans.get("status") == "refined" else None
    why = [f"qkr {k}: {v}" for k, v in failed.items()] if ans.get("status") != "refined" else []
    if ans.get("status") not in ("refined", "fallback"):
        why.append(f"qkr status {ans.get('status')}")
    if ko:
        why += problems(it, ko)
    for key in ("polished", "ko_qkr", "polish_reported", "polish_undone", "polish_refused"):
        st.pop(key, None)          # a new draft of qkr's is refined by Fable again
    st.update(sent=it["sent"], context=it.get("context") or None, attempts=st.get("attempts", 0) + 1, how=how, status="ok" if ko and not why else "failed", why=why,
              proposed=ans.get("proposed") if not ko else None, edits=ans.get("edits"), warnings=ans.get("warnings"),
              versions=ans.get("_versions"))
    if ko and not why:
        st["ko"] = ko
    elif ko:
        st["proposed"] = ko          # qkr passed it, the desk did not: kept for the record, never applied
        _reject(st, ko, "; ".join(why))


def _reject(st: dict, ko: str, why: str) -> None:
    """An answer of qkr's that was not used, kept for its feedback endpoint (the next training round reads them)."""
    st.setdefault("rejected", []).append({"ko": ko, "why": why[:400]})


def send_feedback(cfg: dict, items: list[dict], state: dict) -> int:
    """Tell qkr which of its answers the desk's checks or the side-by-side reader refused, with the answer that
    was kept (qkr's own). Best effort: a failure here never stops the edition."""
    if _engine() == "claude":
        return 0          # the answers are Claude's, not qkr's: nothing for qkr's training set
    n = 0
    for it in items:
        st = state[it["id"]]
        for r in st.get("rejected") or []:
            if r.get("reported"):
                continue
            try:
                _http("/v1/feedback", {"service": cfg["service"], "id": f"desk:{it['id']}", "profile": it["profile"], "ko_src": "",
                                       "ko_model": r["ko"], "ko_final": st.get("ko") or "", "verdict": "rejected",
                                       "note": f"data note, drafted from English: {st.get('sent') or it['sent']!r}. Refused because: {r['why']}"[:1500]}, timeout=60)
                r["reported"] = True
                n += 1
            except Exception:
                return n
    return n


# ------------------------------------------------------------------ the two English-only roles

def _reword(run: Path, failed: list[dict], state: dict) -> dict[str, str]:
    packet = ["## Strings qkr could not draft\n"]
    for it in failed:
        st = state[it["id"]]
        packet.append(f"### {it['id']}  (profile: {it['profile']}{', the note headline: at most 40 Korean characters' if it['path'][-1] == 'title' and it['kind'] == 'draft' else ''})\n"
                      f"English as written: {_FILLED[it['id']]}\nEnglish sent: {st.get('sent') or it['sent']}\n"
                      f"Why it failed: {'; '.join(st.get('why') or ['unknown'])}\n"
                      + (f"qkr's refused Korean (to see what went wrong; do not correct it): {st['proposed']}\n" if st.get("proposed") else ""))
    data = roles.call(run, "ko-source", "\n".join(packet), label="korean")["data"]
    return {str(x.get("id")): str(x.get("en")) for x in (data.get("items") or []) if x.get("id") and x.get("en")}


_FILLED: dict[str, str] = {}       # id → the string's English with its numbers filled in, as first sent


def _usable(it: dict, en: str) -> str | None:
    """A rewording is used only when it keeps the string's numbers and citation marks."""
    new = normalise(en)
    base = _FILLED.get(it["id"], it["sent"])
    extra = _nums(new) - _nums(base) - _word_numbers(base)
    lost = {n for n in _nums(base) - _nums(new) if "." in n or len(n) >= 2}
    if extra or lost or _cites(new) != _cites(base):
        return None
    # nor adds a statement: a rewording says the same thing (20261119-desk: the side-by-side reader's rewording of the
    # dek added "This is not the whole decline: …", which qkr then drafted)
    sentences = lambda t: len([x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"])", t.strip()) if x.strip()])     # noqa: E731
    if sentences(new) > max(sentences(base), 1) + (1 if sentences(base) >= 3 else 0) or len(new.split()) > 1.3 * len(base.split()) + 6:
        return None
    return new


def _check(run: Path, items: list[dict], state: dict, name_map: dict, points: list[dict] | None = None) -> dict:
    used = sorted({en for en in name_map if any(re.search(rf"\b{re.escape(en)}\b", it["sent"]) for it in items)})
    packet = ["## Economy names as the sites write them\n" + "\n".join(f"- {en} = {name_map[en]}" for en in used) + "\n",
              "## The strings (English as written; Korean as qkr drafted it)\n"]
    for it in items:
        st = state[it["id"]]
        if st.get("status") != "ok":
            continue
        base = _FILLED[it["id"]]
        packet.append(f"### {it['id']}  (profile: {it['profile']})\nEN: {base}\n"
                      + (f"EN sent to qkr (a rewording): {st['sent']}\n" if st.get("sent") and st["sent"] != base else "")
                      + f"KO: {st['ko']}\n")
    if points:
        packet.append("## The editor's points\n\nThe editor read the published Korean and found these. Answer each one: an "
                      "issue on its string with `en`, or a term with the variants and `use`, as below.\n"
                      + "\n".join(f"- {x['id']}: {x['problem']}" for x in points) + "\n")
    return roles.call(run, "ko-checker", "\n".join(packet), label="korean")["data"] or {}


# ------------------------------------------------------------------ the step

def make(run: Path, redo: bool = False, only_changed: bool = False, points: list[dict] | None = None) -> dict:
    """Draft, check and write the Korean edition of a run. Returns the summary kept in desk/result.json."""
    cfg = config.load()["korean"]
    t0 = time.time()
    _RUN[:] = [run]
    items, named = strings(run)
    fmap = {f["id"]: f for f in facts_mod.load(run)}
    _FILLED.clear()
    _FILLED.update({it["id"]: normalise(_fill(it["en"], fmap)) for it in items})
    src = source_digest(items, named)
    old = read_json(run / "desk" / "korean.json", {}) or {}
    state: dict[str, dict] = {}
    stale_editor: dict[str, dict] = {}       # the editor's words for an English that has changed since: shown, not used
    prev = {s["id"]: s for s in old.get("strings") or []}
    if not redo:
        # an answer is kept while its English is the same, so a rewrite of the note drafts only what changed
        for it in items:
            p = prev.get(it["id"])
            # (a first draft is kept only while code would still send the same English for it)
            if p and p.get("status") == "ok" and p.get("en") == it["en"] and not problems(it, p.get("ko") or "", p.get("sent")) \
                    and (p.get("how") != "draft" or (p.get("sent") == it["sent"] and (p.get("context") or []) == (it.get("context") or []))):
                state[it["id"]] = {k: p.get(k) for k in ("sent", "ko", "status", "attempts", "how", "edits", "warnings", "versions", "ko_before", "no_terms", "terms", "context", "rejected", "tuning",
                                                         "polished", "ko_qkr", "polish_reported", "polish_undone", "polish_refused")
                                   if p.get(k) is not None}
                state[it["id"]]["why"] = []
    for it in items:
        p = prev.get(it["id"])
        # the editor's own words stay while the English they were written for is the same (a redo keeps them too)
        if p and p.get("status") == "editor" and (p.get("editor") or {}).get("en") == it["en"]:
            state[it["id"]] = {k: p.get(k) for k in ("sent", "ko", "status", "how", "editor", "rejected", "versions", "tuning") if p.get(k) is not None}
            state[it["id"]]["why"] = []
        elif p and (p.get("editor") or p.get("editor_stale")):
            stale_editor[it["id"]] = p.get("editor") or p["editor_stale"]
    for it in items:
        state.setdefault(it["id"], {"status": "new", "attempts": 0})
    # an update of a published note (only_changed): the checker's findings are acted on only in strings whose English
    # changed; the rest stays as published, and what the checker says about it is listed (17 Nov 2026: t8's dek fix
    # also redrafted five unchanged strings, two of them worse)
    fresh = {it["id"] for it in items if state[it["id"]]["status"] == "new"}
    # the editor's points on the published Korean (`desk update --ko`): those strings are open to change too
    points = [x for x in points or [] if x.get("id") in {it["id"] for it in items}]
    fresh |= {x["id"] for x in points}
    # a string sent back (a point) starts again from qkr's own draft, and Fable rewrites what qkr drafts again
    # (20 Nov 2026: on 20261120-desk the framing points left the title qkr's redraft, never polished, as it kept
    # Fable's flag from the first pass)
    for x in points:
        st = state[x["id"]]
        if st.get("how") == "refined by Fable" and st.get("ko_qkr"):
            st["ko"], st["how"] = st.pop("ko_qkr"), "draft"
        for k in ("polished", "polish_reported", "polish_undone", "polish_refused"):
            st.pop(k, None)
    for k, v in stale_editor.items():
        state[k]["editor_stale"] = v

    def save(extra: dict | None = None):
        write_json(run / "desk" / "korean.json", {
            "made": runlib.now(), "source": src, "qkr": versions, "seconds": round(time.time() - t0),
            "strings": [{"id": it["id"], "kind": it["kind"], "chart": it["chart"], "path": it["path"], "profile": it["profile"],
                         "en": it["en"], **state[it["id"]]} for it in items],
            "names": name_rows, **(extra or {})})

    try:
        h = health()
    except KoreanDown as e:
        # qkr is down: stop. An edition made earlier for the same English stays; nothing is written another way.
        return {**status(run), "error": str(e), "strings": len(items), "at": runlib.now()}
    versions = {k: h.get(k) for k in ("model_version", "style_version", "checks_version", "glossary_rows")}
    name_map = names()
    name_rows = []
    # 1. draft what has no accepted answer
    todo = [it for it in items if state[it["id"]]["status"] not in SETTLED]
    if todo:
        got = _draft(todo, cfg)
        for it in todo:
            _take(it, got[it["id"]], state[it["id"]], "draft")
        save()
    # 2. reword what qkr's checks or the desk's refused, and draft again
    for _ in range(cfg["rewrites"]):
        failed = [it for it in items if state[it["id"]]["status"] not in SETTLED]
        if not failed:
            break
        try:
            new = _reword(run, failed, state)
        except roles.RoleError:
            break
        again = []
        for it in failed:
            en = _usable(it, new.get(it["id"]) or "")
            if en and en != state[it["id"]].get("sent"):
                it["sent"] = en
                again.append(it)
            elif new.get(it["id"]):
                state[it["id"]]["why"] = (state[it["id"]].get("why") or []) + ["the rewording changed a number or a citation mark and was not used"]
        if not again:
            break
        got = _draft(again, cfg)
        for it in again:
            _take(it, got[it["id"]], state[it["id"]], "reworded")
        save()
    # 2b. a paragraph qkr still cannot draft whole (an empty answer, a slip it repeats) goes sentence by sentence
    for it in [i for i in items if state[i["id"]]["status"] not in SETTLED and i["profile"] == "article"]:
        parts = [x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"−])", _FILLED[it["id"]]) if x.strip()]
        if len(parts) < 2:
            continue
        subs = [{"id": f"{it['id']}#{n}", "kind": "part", "chart": None, "path": ["part"], "profile": "article", "en": x, "sent": x}
                for n, x in enumerate(parts)]
        got = _draft(subs, cfg)
        sts = []
        for sub in subs:
            st = {}
            _take(sub, got[sub["id"]], st, "draft")
            sts.append(st)
        ko = " ".join(st.get("ko") or "" for st in sts)
        if all(st.get("status") == "ok" for st in sts) and not problems(it, ko, _FILLED[it["id"]]):
            state[it["id"]].update(status="ok", ko=ko, sent=_FILLED[it["id"]], how="drafted sentence by sentence", why=[], proposed=None,
                                   versions=sts[0].get("versions"))
            it["sent"] = _FILLED[it["id"]]
    save()
    # 3. meaning and terms: the checker reads, qkr drafts again or refines with its own chosen form as a term
    open_issues, term_fixes = [], 0
    for rnd in range(cfg["check_rounds"] + 1):
        if not any(state[it["id"]]["status"] == "ok" for it in items):
            break
        try:
            res = _check(run, items, state, name_map, points if rnd == 0 else None)
        except roles.RoleError as e:
            open_issues = [{"id": None, "kind": "unchecked", "problem": f"the Korean was not read against the English: {e}"}]
            break
        by_id = {it["id"]: it for it in items}
        issues = [x for x in res.get("issues") or [] if x.get("id") in by_id and x.get("kind") != "style"]
        # one term in two forms: Fable's refinement makes the wording consistent, so the term rounds run only without it
        terms = [t for t in res.get("terms") or [] if t.get("use") and t.get("variants")] if not polish_mod.on("ko") else []
        open_issues = [{k: x.get(k) for k in ("id", "kind", "quote_ko", "problem")} for x in issues]
        if only_changed:
            issues = [x for x in issues if x["id"] in fresh]
        if rnd == cfg["check_rounds"] or not (issues or terms):
            break
        again, polish, touched = [], [], set()
        for x in issues:
            it = by_id[x["id"]]
            st = state[it["id"]]
            if it["id"] in touched or st.get("status") != "ok":
                continue
            touched.add(it["id"])
            en = _usable(it, x.get("en") or "")
            _reject(st, st["ko"], f"{x.get('kind')}: {x.get('problem')}" + (f" (the words: {x['quote_ko']})" if x.get("quote_ko") else ""))
            if st.get("how") == "term made the same" and st.get("ko_before"):
                # the slip came in with a term fix: qkr's earlier answer is put back, and the string takes no more term fixes
                st.update(ko=st.pop("ko_before"), how="draft (a term fix was undone)", no_terms=True)
            elif en and en != st.get("sent"):
                it["sent"] = en
                again.append(it)
            else:
                # the English is not the cause (a garbled word, a misspelt name): qkr refines its own answer, in careful
                # mode, with the sites' name for an economy as a required term when a name is wrong
                need = {}
                if x.get("kind") == "name" and x.get("quote_ko"):
                    lacking = [name_map[e] for e in name_map if re.search(rf"\b{re.escape(e)}\b", st["sent"]) and name_map[e] not in st["ko"]]
                    if len(lacking) == 1 and x["quote_ko"] in st["ko"]:
                        need = {x["quote_ko"]: lacking[0]}
                polish.append({"it": it, "mode": "careful",
                               "req": {"id": it["id"], "profile": it["profile"], "ko": st["ko"], "en": st["sent"], **({"terms": need} if need else {})}})
        if again:
            got = _draft(again, cfg)
            for it in again:
                before = dict(state[it["id"]])
                _take(it, got[it["id"]], state[it["id"]], "reworded after the check")
                if state[it["id"]]["status"] != "ok":      # the new draft failed: the earlier answer stands, the issue stays open
                    state[it["id"]] = before
        if polish:
            got = _refine(polish, cfg)
            for r in polish:
                a, it = got[r["req"]["id"]], r["it"]
                if a.get("status") == "refined" and a.get("ko") and a["ko"] != state[it["id"]]["ko"] and not problems(it, a["ko"]):
                    state[it["id"]].update(ko=a["ko"], how="refined after the check", versions=a.get("_versions"))
        # a term in two forms: qkr refines the strings that hold the other form, with the chosen form required
        all_ko = " ".join(state[i["id"]].get("ko") or "" for i in items)
        reqs = []
        for it in items:
            st = state[it["id"]]
            # a variant is replaced only as a whole word of its own: never one that is part of the chosen form or of
            # another variant (a short stem would be cut out of a longer word)
            want = {v: t["use"] for t in terms if t["use"] in all_ko for v in t["variants"]
                    if v != t["use"] and len(v) >= 3 and v in (st.get("ko") or "") and v not in t["use"] and t["use"] not in v
                    and not any(v in o for o in t["variants"] if o != v)}
            if st.get("status") == "ok" and want and it not in again and it["id"] not in touched and not st.get("no_terms") \
                    and (not only_changed or it["id"] in fresh):
                reqs.append({"it": it, "req": {"id": it["id"], "profile": it["profile"], "ko": st["ko"], "en": st["sent"], "terms": want}})
        if reqs:
            got = _refine(reqs, cfg)
            for r in reqs:
                a, it = got[r["req"]["id"]], r["it"]
                if a.get("status") == "refined" and a.get("ko") and not problems(it, a["ko"]):
                    state[it["id"]].update(ko_before=state[it["id"]]["ko"], ko=a["ko"], how="term made the same", terms=r["req"]["terms"],
                                           versions=a.get("_versions"))
                    term_fixes += 1
        save()
        if not again and not reqs and not polish and not touched:
            break
    # 3b. Fable refines the expression of every string (19 Nov 2026, the owner's decision; desk/polish.py). It replaces the
    # title tuning: Fable rewrites the title with the rest. Without the polish, the title is tuned as before
    title, polished = None, None
    if polish_mod.on("ko"):
        polished = polish_mod.korean(run, items, state, name_map, _FILLED, fresh if only_changed or points else None)
        changed_ids = {i["id"] for i in items if state[i["id"]].get("ko_qkr") and state[i["id"]].get("how") == "refined by Fable"}
        open_issues = [x for x in open_issues if x.get("id") not in changed_ids]
    else:
        try:
            title = tune_title(run, items, state, cfg, open_issues)
        except (roles.RoleError, KoreanDown, OSError) as e:
            title = {"error": f"{type(e).__name__}: {e}"}
    save()
    # 4. names in figures
    for n in named:
        ko = name_map.get(n["en"])
        if ko is None and (re.fullmatch(r"[\d\-–Q ./]+", n["en"]) or not re.search(r"[A-Za-z]{2}", n["en"])):
            ko = n["en"]                    # a period or a number: the same in both editions
        name_rows.append({**{k: n[k] for k in ("chart", "path", "en")}, "ko": ko, "from": "economies.csv" if n["en"] in name_map else "same"})
    unnamed = sorted({n["en"] for n in name_rows if n["ko"] is None})
    if unnamed:       # a label the economy table does not have (a banking system, a product): qkr drafts it as a label
        fake = [{"id": f"n:{e}", "kind": "name", "chart": None, "path": ["label"], "profile": "label", "en": e, "sent": normalise(e)} for e in unnamed]
        got = _draft(fake, cfg)
        for f in fake:
            st = {}
            _take(f, got[f["id"]], st, "draft")
            for n in name_rows:
                if n["en"] == f["en"] and st.get("status") == "ok":
                    n.update(ko=st["ko"], **{"from": "qkr"})
    failed = [{"id": it["id"], "kind": "no-answer", "problem": "; ".join(state[it["id"]].get("why") or ["no answer"])}
              for it in items if state[it["id"]]["status"] not in SETTLED]
    failed += [{"id": f"name:{n['en']}", "kind": "no-answer", "problem": "no Korean name for this label"} for n in name_rows if n["ko"] is None]
    complete = not failed
    blocking = failed + [x for x in open_issues if x.get("kind") in ("meaning", "missing", "added", "name", "untranslated", "framing", "unchecked")]
    summary = {"complete": complete, "strings": len(items), "open": blocking,
               "advisory": [x for x in open_issues if x not in blocking],
               "reworded": sum(1 for it in items if "reworded" in (state[it["id"]].get("how") or "")), "term_fixes": term_fixes,
               "seconds": round(time.time() - t0), "qkr": versions, "source": src, "at": runlib.now()}
    # what is shown for a string without an accepted answer: qkr's last draft for it, as qkr wrote it, or the English
    for it in items:
        st = state[it["id"]]
        if st["status"] in SETTLED:
            st.pop("shown", None)
            st.pop("shown_from", None)
            continue
        drafts = [st.get("proposed")] + [r.get("ko") for r in reversed(st.get("rejected") or [])]
        ko = next((k for k in drafts if k and HANGUL.search(k)), None)
        st["shown"], st["shown_from"] = (ko, "qkr") if ko else (_fill(it["en"], fmap), "english")
    for n in name_rows:
        if n["ko"] is None:
            n.update(ko=n["en"], **{"from": "english"})
    for x in failed:
        st = state.get(x["id"]) or {}
        if st.get("shown_from"):
            x["shown_from"] = st["shown_from"]
    summary["written"] = True
    summary["title"] = _title_view(state, title, stale_editor)
    summary["flagged"] = len(failed)
    summary["qkr_notes"] = qkr_notes(items, state, open_issues)
    summary["feedback_sent"] = send_feedback(cfg, items, state) + polish_mod.feedback(cfg, items, state)
    if polished is not None:      # what Fable's refinement stands at over every pass, not only this one
        polished = {**polished, "this_pass": polished.get("changed"),
                    "changed": sum(1 for i in items if state[i["id"]].get("how") == "refined by Fable" and state[i["id"]].get("ko_qkr"))}
    summary["polish"] = polished
    save({"summary": summary})
    _write(run, items, state, name_rows)
    # the pipeline's own checks on the edition as written: a headline over the limit, a figure text without Korean
    from .. import checks as pipeline_checks
    every = {**pipeline_checks.ALL, **pipeline_checks.OTHER}
    res = {n: every[n](run) for n in ("numbers", "style", "charts")}
    found = [f"{name}: {b}" for name, r in res.items() for b in r.get("blocking", [])
             if b.startswith("ko") or ".ko " in b or b.endswith(".ko missing") or "KO" in b]
    if found:
        summary["open"] = summary["open"] + [{"id": None, "kind": "check", "problem": b} for b in found]
        save({"summary": summary})
    return summary


# ------------------------------------------------------------------ the title

def _examples(n: int) -> list[dict]:
    """The Korean titles the editor wrote or chose, newest first (TITLES)."""
    rows = [r for r in read_jsonl(TITLES) if r.get("ko") and r.get("en")] if TITLES.is_file() else []
    return list(reversed(rows))[:n]


def _locked(en: str) -> dict:
    lk = [n for n in SERVICES if re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", en)]
    return {"locked": lk} if lk else {}


def tune_title(run: Path, items: list[dict], state: dict, cfg: dict, open_issues: list[dict]) -> dict | None:
    """The Korean title, tuned (config korean.title). ko-title writes English headlines shaped for a Korean news
    headline; qkr drafts each in each mode; ko-title ranks qkr's drafts and the first one, and the best faithful
    draft that passes the desk's checks becomes the title. Every Korean word is still qkr's. A title the editor wrote
    is never tuned, and a tuned title is kept while its English is the same (no new calls)."""
    tcfg = cfg.get("title") or {}
    it = next((i for i in items if i["id"] == "d:title"), None)
    if not it or not tcfg.get("angles"):
        return None
    st = state[it["id"]]
    if st.get("status") == "editor" or (st.get("how") == "tuned title" and st.get("tuning")):
        return st.get("tuning")
    draft = read_json(run / "draft" / "en.json", {}) or {}
    fmap = {f["id"]: f for f in facts_mod.load(run)}
    title_en = _FILLED.get(it["id"]) or it["sent"]
    dek = normalise(_fill(draft.get("dek") or "", fmap))
    why = normalise(_fill(draft.get("whyNow") or "", fmap))
    first = st.get("ko") if st.get("status") == "ok" else (st.get("proposed") or None)
    ex = _examples(int(tcfg.get("examples", 12)))
    exs = "\n".join(f"- EN: {e['en']}\n  the editor's Korean title: {e['ko']}" for e in ex) or "(none yet)"
    allowed = _nums(title_en) | _nums(dek) | _word_numbers(title_en)
    cands, seen = [], set()
    if first and HANGUL.search(first):
        cands.append({"id": "c0", "ko": first.strip(), "en": st.get("sent") or it["sent"], "mode": "first draft",
                      "problems": problems(it, first, st.get("sent") or it["sent"]) + ([] if st.get("status") == "ok" else st.get("why") or [])})
        seen.add(first.strip())
    out = {"candidates": cands, "chosen": None, "rounds": 0, "at": runlib.now()}
    best = None
    # a round: angles in English, qkr's drafts, a ranking of every draft so far. Another round (with what was wrong
    # with each draft) while the best faithful draft is not yet a headline in form (t8, 16 Nov 2026: qkr dropped
    # Mexico from two drafts and split one over two lines, and the first draft stood at form 2)
    for rnd in range(int(tcfg.get("rounds", 2))):
        so_far = "\n".join(f"- {c['ko']!r} (from: {c['en']}): " + ("; ".join(c["problems"]) if c["problems"] else
                            f"faithful {c.get('faithful')}, form {c.get('form')}, pull {c.get('pull')}: {c.get('why')}") for c in cands[1:])
        data = roles.call(run, "ko-title", f"## Task: angles\n\nWrite {tcfg['angles']} angles.\n\nEnglish title: {title_en}\n"
                          f"Dek: {dek}\nWhy this note: {why}\nqkr's current Korean title: {first or '(none)'}"
                          + (f" ({cands[0].get('why')})" if cands and cands[0].get("why") else "") + "\n\n"
                          + (f"## qkr's drafts of your earlier angles, and what was wrong with them\n{so_far}\n\n" if so_far else "")
                          + f"## Titles the editor chose\n{exs}\n", label="korean")["data"] or {}
        angles = []
        for a in data.get("angles") or []:
            en = normalise(str(a.get("en") or "")).strip()
            if en and en not in angles and not (_nums(en) - allowed) and _cites(en) == []:
                angles.append(en)
        angles = angles[: int(tcfg["angles"])]
        reqs = [{"mode": mode, "en": en, "req": {"id": f"t{rnd}.{k}{mode[0]}", "profile": "headline", "ko": "", "en": en, **_locked(en)}}
                for k, en in enumerate(angles) for mode in (tcfg.get("modes") or ["fast"])]
        got = _refine(reqs, cfg) if reqs else {}
        for r in reqs:
            a = got[r["req"]["id"]]
            ko = (a.get("ko") or "").strip() if a.get("status") == "refined" else ""
            if not ko or ko in seen:
                continue
            seen.add(ko)
            cands.append({"id": f"c{len(cands)}", "ko": ko, "en": r["en"], "mode": r["mode"] + (f", round {rnd + 1}" if rnd else ""),
                          "problems": problems(it, ko, r["en"]), "versions": a.get("_versions")})
        out["rounds"] = rnd + 1
        ok = [c for c in cands if not c["problems"]]
        # every candidate is read by the skimming reader too (R8): a title from which a reader concludes what the claims
        # contradict (a count as a result, a difference where the note finds none) is dropped before the pick
        untested = [c for c in ok if "inference" not in c]
        if untested and (config.load().get("claims") or {}).get("inference_korean", True):
            from . import claims as claims_mod, inference as inference_mod
            ledger, cm = claims_mod.load(run), claims_mod.load_map(run)
            if ledger and cm.get("title"):
                try:
                    res = inference_mod.run_test(run, {}, {}, fmap, ledger, {f"title#{c['id']}": cm["title"] for c in untested}, lang="ko",
                                                 surf=[{"key": f"title#{c['id']}", "text": c["ko"]} for c in untested], label="korean")
                    bad = {}
                    for x in res["conclusions"]:
                        if x["verdict"] == "contradicted":
                            for k in x.get("from") or []:
                                bad.setdefault(str(k).split("#")[-1], x)
                    for c in untested:
                        x = bad.get(c["id"])
                        c["inference"] = "contradicted" if x else "ok"
                        if x:
                            c["problems"].append(f"inference: a reader of this title concludes “{x['says']}”; {x['why']}")
                except roles.RoleError as e:
                    out["inference_error"] = str(e)
            ok = [c for c in cands if not c["problems"]]
        if not ok:
            continue
        packet = (f"## Task: pick\n\nEnglish title: {title_en}\nDek: {dek}\n\n## Candidates\n"
                  + "\n".join(f"### {c['id']}\nKO: {c['ko']}\n(qkr drafted it from: {c['en']})" for c in ok)
                  + f"\n\n## Titles the editor chose\n{exs}\n")
        pick = roles.call(run, "ko-title", packet, label="korean")["data"] or {}
        rank = {str(r.get("id")): r for r in pick.get("ranking") or [] if isinstance(r, dict)}
        for c in ok:
            c.update({k: (rank.get(c["id"]) or {}).get(k) for k in ("faithful", "form", "pull", "why")})
        best = next((c for c in ok if c["id"] == str(pick.get("best")) and (rank.get(c["id"]) or {}).get("faithful") is True), None)
        if best and (best.get("form") or 0) >= 4:
            break
    if best:
        out["chosen"] = best["id"]
        if best["ko"] != (first or "").strip() or st.get("status") != "ok":
            if st.get("status") == "ok":
                _reject(st, st["ko"], "title: ko-title chose another of qkr's drafts, from a reshaped English headline: "
                        f"{best['ko']} (form {best.get('form')}, pull {best.get('pull')}): {best.get('why')}")
            st.update(status="ok", ko=best["ko"], sent=best["en"], how="tuned title", why=[], proposed=None,
                      versions=best.get("versions") or st.get("versions"))
            it["sent"] = best["en"]
            # what the side-by-side reader said about the old title no longer applies
            open_issues[:] = [x for x in open_issues if x.get("id") != it["id"]]
        else:
            st["how"] = "tuned title"
        if (best.get("form") or 0) < 4:
            out["why"] = "no draft of qkr's reached a headline's form (4 of 5); the best faithful one stands. Pick or write the title"
    else:
        out["why"] = "no faithful draft passed the desk's checks; the first draft stands. Pick or write the title"
    st["tuning"] = out
    return out


def _title_view(state: dict, tuning: dict | None, stale_editor: dict) -> dict:
    """The title as the admin site shows it: where it came from, the other drafts, the editor's earlier words."""
    st = state.get("d:title") or {}
    return {"ko": st.get("ko") if st.get("status") in SETTLED else st.get("shown"),
            "from": "editor" if st.get("status") == "editor" else "tuned" if st.get("how") == "tuned title" else "polished" if st.get("how") == "refined by Fable" else "qkr",
            "qkr": st.get("ko_qkr"),
            "candidates": (st.get("tuning") or tuning or {}).get("candidates") or [],
            "chosen": (st.get("tuning") or tuning or {}).get("chosen"),
            "editor": st.get("editor"), "editor_stale": st.get("editor_stale") or stale_editor.get("d:title"),
            "error": (tuning or {}).get("error")}


def set_editor(run: Path, sid: str, ko: str, *, by: str, decision: str | None = None) -> dict:
    """The editor's own Korean for one string (the title, from the admin site): used exactly as written, never by a
    model's hand, sent to qkr's feedback as an edit of its draft, and kept while the English is the same."""
    ko = (ko or "").strip()
    if not ko or "\n" in ko or not HANGUL.search(ko) or len(ko) > 120:
        raise ValueError("the Korean must be one line of Korean, at most 120 characters")
    led = read_json(run / "desk" / "korean.json", None)
    if not led or not led.get("summary"):
        raise ValueError("this note has no Korean edition yet")
    items, named = strings(run)
    if source_digest(items, named) != led.get("source"):
        raise ValueError("the Korean edition is older than the English; it is drafted again first")
    it = next((i for i in items if i["id"] == sid), None)
    recs = {s["id"]: s for s in led.get("strings") or []}
    if not it or sid not in recs:
        raise ValueError(f"no string {sid}")
    st = recs[sid]
    before = (st.get("editor") or {}).get("qkr") if st.get("status") == "editor" else \
        (st.get("ko") if st.get("status") == "ok" else st.get("shown") if st.get("shown_from") == "qkr" else None)
    st["editor"] = {"ko": ko, "en": it["en"], "qkr": before, "at": runlib.now(), "by": by, "decision": decision}
    st.update(status="editor", ko=ko, how="the editor's wording", why=[])
    for k in ("shown", "shown_from", "proposed", "editor_stale"):
        st.pop(k, None)
    cfg = config.load()["korean"]
    if before and before != ko:
        try:
            _http("/v1/feedback", {"service": cfg["service"], "id": f"desk:{sid}", "profile": it["profile"], "ko_src": "",
                                   "ko_model": before, "ko_final": ko, "verdict": "edited",
                                   "note": (f"data note, drafted from English: {st.get('sent') or it['sent']!r}. The editor rewrote the draft "
                                            "in their own words" + (" as a Korean news headline (topic first, a two-part contrast, a firm "
                                            "noun ending)" if it["profile"] == "headline" else "") + ".")[:1500]}, timeout=60)
            st["editor"]["reported"] = True
        except Exception:
            pass
    state = {i["id"]: recs.get(i["id"]) or {"status": "new"} for i in items}
    s = led["summary"]
    s["open"] = [x for x in s.get("open") or [] if x.get("id") != sid]
    s["flagged"] = sum(1 for x in s["open"] if x.get("kind") == "no-answer")
    s["complete"] = s["flagged"] == 0
    s["qkr_notes"] = [x for x in s.get("qkr_notes") or [] if not (x.get("id") == sid and x.get("check") == "editor")] \
        + [x for x in qkr_notes(items, state, []) if x.get("id") == sid and x.get("check") == "editor"]
    s["title"] = _title_view(state, None, {})
    s["at"] = runlib.now()
    write_json(run / "desk" / "korean.json", led)
    _write(run, items, state, led.get("names") or [])
    if sid == "d:title":
        TITLES.parent.mkdir(parents=True, exist_ok=True)
        with TITLES.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"run": run.name, "en": it["sent"], "qkr": before, "ko": ko, "at": runlib.now(), "by": by}, ensure_ascii=False) + "\n")
    return status(run)


# ------------------------------------------------------------------ what qkr should learn

_QKR_LESSONS = [
    # (pattern in the reason an answer was refused, who is at fault, the lesson for qkr or for the desk)
    (r"line break", "qkr", "a one-line field (headline profile) came back on two lines; a headline answer must be one line"),
    (r"qkr ending: fail: headline (\d+) chars", "qkr", "the headline profile drafted a headline longer than its own limit and then failed it; "
     "it should shorten (keep the point, drop the second number or the period) instead of failing"),
    (r"qkr figures: fail: new or changed number", "qkr", "the figures check counted a number qkr wrote itself as new"),
    (r"misspelt in the Korean", "qkr", "an economy name lost its last syllable before a particle (벨기에 → 벨기은 type)"),
    (r"holds no Korean", "qkr", "the answer came back in English"),
    (r"citation marks differ", "qkr", "a citation mark [[...]] was dropped or changed"),
    (r"particle token", "qkr", "a particle token {..|..} was left in the answer"),
    (r"the Korean has numbers the English does not", "qkr", "the Korean added a number the English does not have"),
    (r"the Korean lost numbers", "qkr", "the Korean dropped a number the English has"),
    (r"^(meaning|missing|added|name|untranslated)", "qkr", "the side-by-side reader found the Korean does not say what the English says"),
    (r"^framing", "qkr", "the Korean presented a neutral count as a result or dropped the comparison the English makes (news-headline "
     "compression of “three of six exceed the median” into a result); keep the comparison clause and do not turn a base-rate count into an achievement"),
    (r"comparison: the Korean dropped", "qkr", "the Korean dropped the base or the comparator number of a comparison the English gives"),
    (r"comparison: the English compares", "qkr", "the Korean lost the comparison clause (none of the comparison markers in korean.KO_MARKERS): the count reads as a result"),
    (r"service name", "qkr", "a datasteg service name was translated into Korean; service names are kept as written"),
    (r"^term", "qkr", "one English term came out in two Korean forms"),
    (r"rewording changed a number", "desk", "the English rewording for qkr changed a number and was not used (ko-source)"),
    (r"qkr status", "qkr", "qkr returned no draft (server status)"),
    (r"^title: ko-title chose", "qkr", "qkr's headline from the plain English title lost to its own draft of a reshaped English headline: "
     "from a plain title the headline profile should give a Korean news headline (topic first, a two-part contrast, a firm noun "
     "ending), not carry the English sentence across"),
]


def qkr_notes(items: list[dict], state: dict, open_issues: list[dict]) -> list[dict]:
    """For every answer of qkr's that was refused in this run (and every open meaning point), who was at fault and
    what qkr should learn: the editor reads them beside the note, and qkr's feedback endpoint gets the same refusals."""
    out, seen = [], set()
    by_id = {it["id"]: it for it in items}
    for it in items:
        st = state[it["id"]]
        reasons = [(r.get("why") or "", r.get("ko")) for r in st.get("rejected") or []]
        if st["status"] != "ok":
            reasons += [(w, st.get("proposed")) for w in st.get("why") or []]
        for why, ko in reasons:
            for part in [p.strip() for p in re.split(r";\s*", why) if p.strip()]:
                for pat, who, lesson in _QKR_LESSONS:
                    if re.search(pat, part, re.I):
                        detail = lesson
                        if who == "qkr" and pat.startswith("^("):
                            # the side-by-side reader's own words say what went wrong, in this string
                            detail, part = part, "ko-checker"
                        if "figures" in pat:
                            mon = re.search(rf"\b({_MON})\b", st.get("sent") or it["sent"])
                            if mon:
                                detail = (f"the figures check refused its own answer for writing the month '{mon.group(1)}' as "
                                          f"{MONTHS[mon.group(1)]}월; a month name rendered as N월 is not a new number")
                        key = (it["id"], detail)
                        if key in seen:
                            break
                        seen.add(key)
                        out.append({"id": it["id"], "who": who, "lesson": detail, "check": part[:300], "en": st.get("sent") or it["sent"],
                                    "ko": ko, "accepted": st["status"] == "ok"})
                        break
    for it in items:
        st = state[it["id"]]
        ed = st.get("editor") or {}
        if st.get("status") == "editor" and ed.get("qkr") and ed.get("qkr") != ed.get("ko"):
            lesson = "the editor rewrote qkr's draft in their own words"
            if it["profile"] == "headline":
                lesson += ("; the editor's headline names the topic first, sets a two-part contrast and ends on a firm noun"
                           + ("; it uses the colon the headline profile forbids" if ":" in ed["ko"] else ""))
            out.append({"id": it["id"], "who": "qkr", "lesson": lesson, "check": "editor", "en": st.get("sent") or it["sent"],
                        "ko": f"qkr: {ed['qkr']} → editor: {ed['ko']}", "accepted": True})
    for c in ((state.get("d:title") or {}).get("tuning") or {}).get("candidates") or []:
        if c.get("mode") == "first draft" or not (c.get("faithful") is False or c.get("problems")):
            continue
        out.append({"id": "d:title", "who": "qkr", "check": "ko-title", "en": c.get("en"), "ko": c.get("ko"), "accepted": True,
                    "lesson": "a headline draft from a reshaped English " + ("; ".join(c["problems"]) if c.get("problems") else f"was not faithful: {c.get('why')}")})
    for x in open_issues:
        if x.get("id") in by_id and (x["id"], x.get("problem")) not in seen:
            seen.add((x["id"], x.get("problem")))
            out.append({"id": x["id"], "who": "qkr", "lesson": f"{x.get('kind')}: {x.get('problem')}", "check": "ko-checker",
                        "en": state[x["id"]].get("sent"), "ko": x.get("quote_ko") or state[x["id"]].get("ko"), "accepted": True})
    return out


# ------------------------------------------------------------------ the files

def _write(run: Path, items: list[dict], state: dict, name_rows: list[dict]) -> None:
    ed = load_yaml(CONFIG / "editorial.yaml") or {}
    en = read_json(run / "draft" / "en.json")
    ko = copy.deepcopy(en)
    shown = lambda st: st.get("ko") if st.get("status") in SETTLED else st.get("shown")     # noqa: E731
    for it in items:
        if it["kind"] == "draft":
            _set(ko, it["path"], shown(state[it["id"]]))
    if ko.get("reproduce"):
        from .reproduce import localise
        ko["reproduce"] = localise(ko["reproduce"], "ko")
    ko["byline"] = (ed.get("byline") or {}).get("ko") or en.get("byline")
    ko["disclaimer"] = (ed.get("disclaimer") or {}).get("ko") or en.get("disclaimer")
    write_json(run / "draft" / "ko.json", ko)
    for p in sorted((run / "charts").glob("*.json")):
        ch = read_json(p)
        for it in items:
            if it["kind"] == "chart" and it["chart"] == ch["id"]:
                _get(ch, it["path"])["ko"] = shown(state[it["id"]])
        for n in name_rows:
            if n["chart"] != ch["id"]:
                continue
            if n["path"][0] == "table":
                _set(ch, n["path"], {"en": n["en"], "ko": n["ko"]})
            else:
                _get(ch, n["path"])["ko"] = n["ko"] if n["en"] else ""
        for group in ("categories", "rows", "points"):       # a label left empty on purpose (an unnamed point) is empty in both
            for r in ch.get(group) or []:
                if isinstance(r.get("label"), dict) and not r["label"].get("en"):
                    r["label"]["ko"] = ""
        cols = [c["label"].get("ko") for c in (ch.get("table") or {}).get("columns", [])[1:] if isinstance(c.get("label"), dict)]
        if isinstance((ch.get("meta") or {}).get("definition"), dict) and cols and all(cols):
            ch["meta"]["definition"]["ko"] = "; ".join(cols)
        write_json(p, ch)
    cov = read_json(run / "cover" / "cover.json", None)
    alt = next((shown(state[it["id"]]) for it in items if it["kind"] == "cover"), None)
    if cov and alt:
        cov["alt"]["ko"] = alt
        write_json(run / "cover" / "cover.json", cov)
    plan = read_json(run / "plan.json", None)
    if plan and isinstance(plan.get("headline"), dict):
        plan["headline"]["ko"] = ko.get("title")
        for f in plan.get("figures") or []:
            ch = read_json(run / "charts" / f"{f.get('id')}.json", {}) or {}
            if isinstance(f.get("takeaway"), str) and (ch.get("headline") or {}).get("ko"):
                f["takeaway_ko"] = ch["headline"]["ko"]
        write_json(run / "plan.json", plan)


def status(run: Path) -> dict:
    """Where the Korean edition of a run stands, for the queue and the approval."""
    led = read_json(run / "desk" / "korean.json", None)
    if not led or not led.get("summary"):
        return {"complete": False, "open": [], "missing": True}
    items, named = strings(run)
    s = dict(led["summary"])
    s["stale"] = source_digest(items, named) != led.get("source")
    on_disk = (run / "draft" / "ko.json").is_file()
    s["complete"] = bool(s.get("complete")) and not s["stale"] and on_disk
    # an edition the editor can read: written for the English that is there now (it may carry open points)
    s["written"] = on_disk and not s["stale"]
    return s


def verify(run: Path) -> list[str]:
    """Blocking problems of the Korean edition as it is on disk (`artools check numbers` runs this for a desk run):
    every Korean string is the ledger's qkr answer for the English that is there now, and passes the number and
    citation checks against that English."""
    led = read_json(run / "desk" / "korean.json", None)
    ko = read_json(run / "draft" / "ko.json", None)
    if not ko:
        return []
    if not led:
        return ["ko: draft/ko.json has no ledger (desk/korean.json): the Korean edition must be drafted by `artools desk korean`"]
    items, named = strings(run)
    out = []
    if source_digest(items, named) != led.get("source"):
        out.append("ko: the Korean edition is older than the English draft; run `artools desk korean` again")
    rec = {s["id"]: s for s in led.get("strings") or []}
    charts = {p.stem: read_json(p) for p in sorted((run / "charts").glob("*.json"))}
    for it in items:
        r = rec.get(it["id"])
        flagged = bool(r) and r.get("status") not in SETTLED and r.get("shown")
        if not r or (r.get("status") not in SETTLED and not flagged):
            out.append(f"ko.{it['id']}: no accepted qkr answer")
            continue
        try:
            on_disk = _get(ko, it["path"]) if it["kind"] == "draft" else _get(charts[it["chart"]], it["path"]).get("ko") if it["kind"] == "chart" \
                else ((read_json(run / "cover" / "cover.json", {}) or {}).get("alt") or {}).get("ko")
        except (KeyError, IndexError, TypeError):
            on_disk = None
        if on_disk != (r.get("shown") if flagged else r.get("ko")):
            out.append(f"ko.{it['id']}: the text on disk is not qkr's answer in the ledger")
        if r.get("status") == "editor":
            if (r.get("editor") or {}).get("en") != it["en"]:
                out.append(f"ko.{it['id']}: the editor's Korean was written for another English; the desk must draft it again")
            continue
        if not flagged:
            # a flagged string is qkr's refused draft (or the English), shown to the editor with its failed check
            # beside the note; approving the note accepts it as it is. The checks of 18 Nov 2026 (comparison kept,
            # service names) hold notes written with a claim ledger; a note published before keeps its earlier checks.
            # A string Fable rewrote (19 Nov 2026, from the Korean alone) is also held to qkr's draft
            new = (run / "analysis" / "claims.json").is_file()
            polished = r.get("how") == "refined by Fable" and r.get("ko_qkr")
            if polished and it["id"] == "d:title":
                # Fable's title is written anew from the whole Korean note (20 Nov 2026): it keeps no number of the
                # English title, uses only numbers the note has, and its facts were read by polish-ko-title
                note_nums = set().union(*(_nums(s.get("ko_qkr") or s.get("ko") or s.get("shown") or "") for s in rec.values()))
                out += [f"ko.{it['id']}: Fable's title: {p}" for p in polish_mod.ko_problems(it, r.get("ko") or "", r["ko_qkr"], note_nums)]
                continue
            # the explicit comparison word is not asked of Fable's rewrite: it keeps the comparison in its own words, and
            # the fact editor (polish-ko-facts) compared it with qkr's draft, which had the word
            out += [f"ko.{it['id']}: {p}" for p in problems(it, r.get("ko") or "", r.get("sent"))
                    if (new or not p.startswith(("comparison:", "the service name")))
                    and not (polished and p.startswith("comparison: the English compares"))]
            if polished:
                out += [f"ko.{it['id']}: Fable's rewrite: {p}" for p in polish_mod.ko_problems(it, r.get("ko") or "", r["ko_qkr"])]
    return out
