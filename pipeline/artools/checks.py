"""Mechanical checks on a draft: numbers, style, licences, readability, charts, links; and on the cover."""
from __future__ import annotations

import csv
import re
import urllib.error
import urllib.request
from pathlib import Path

from .content import CITE, GLOSS, TOKEN, load_run, walk_text
from .paths import CONFIG, load_yaml, read_json, run_dir

DEFAULT_RULES = {
    "headline_max": {"en": 90, "ko": 50},
    "sentence_words_avg_max": 22, "sentence_words_max": 40, "paragraph_sentences_max": 4,
    "ko_sentence_chars_avg_max": 50, "ko_sentence_chars_max": 70,
    # Translation-style Korean (guides/voice-ko.md § 번역 투): pattern → what to write instead.
    "ko_translationese": {
        r"우리(?:는|가|의| 자료| 분석)": "'우리' 대신 출처를 밝히거나 주어를 생략",
        r"에 대한": "'~에 대한' 대신 동사로 풀기",
        r"[을를] 통해": "'~을 통해' 대신 '~로', '~하면서'",
        r"에 있어서?": "'~에 있어서' 대신 '~에서'",
        r"(?:으로|로) 인해": "'~로 인해' 대신 '~ 때문에'",
        r"에 의해": "능동으로",
        r"되어지|되어진|보여지|보여진": "이중 피동",
        r"할 필요가 있": "'~해야 한다'",
        r"것으로 나타났": "서술어를 바로",
        r"(?:아래|위) 그래프는": "그래프 제목에 맡기기",
    },
    "number_allow": [
        r"\b(1[89]|20)\d{2}(?:[–-](?:\d{2}|(?:1[89]|20)\d{2}))?\b",   # years and ranges: 2011, 2010–12, 2010–2012
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\b",
        r"\b\d{1,2}-(?:year|month|day)\b", r"\bQ[1-4]\b", r"\b[1-4]Q\d{2}\b",
        r"\d{4}년", r"\d{1,2}월", r"\d{1,2}일", r"[1-4]분기", r"\d{1,2}년물", r"\d{1,2}년 만기",
        r"\bG(?:7|20)\b", r"\bCOVID-19\b", r"\bBasel (?:II|III)\b", r"\bArticle \d+\b",
        r"\b0(?:–| to )100\b",                                         # a score's scale: "from 0 to 100", "0–100"
    ],
    "jargon": ["spread", "basis point", "bp", "yield", "TPI", "OMT", "CDS", "primary balance", "r − g", "TARGET"],
}


def rules() -> dict:
    p = CONFIG / "editorial.yaml"
    r = dict(DEFAULT_RULES)
    if p.exists():
        r.update(load_yaml(p) or {})
    return r


def _texts(draft: dict) -> list[tuple[str, str]]:
    """(where, text) for every reader-facing string; quotes are excluded (verbatim, numbers allowed)."""
    out = []
    for k in ("kicker", "title", "dek"):
        if draft.get(k):
            out.append((k, draft[k]))
    for i, f in enumerate(draft.get("findings", [])):
        out.append((f"findings[{i}]", f))
    q = draft.get("question") or {}
    for k in ("lookedAt", "premiseNote"):
        if q.get(k):
            out.append((f"question.{k}", q[k]))
    for kn in draft.get("keyNumbers", []):
        out.append(("keyNumbers.label", kn.get("label", "")))
    for s in draft.get("sections", []):
        out.append((f"{s['id']}.heading", s.get("heading", "")))
        for j, b in enumerate(s.get("blocks", [])):
            where = f"{s['id']}.{b.get('type')}[{j}]"
            if b.get("type") == "p":
                out.append((where, b.get("text", "")))
            elif b.get("type") == "list":
                out += [(where, t) for t in b.get("items", [])]
            elif b.get("type") == "table":
                out.append((where + ".caption", b.get("caption", "")))
                for r_i, row in enumerate(b.get("rows", [])):
                    out += [(f"{where}.rows[{r_i}].{k}", str(v)) for k, v in row.items() if isinstance(v, (str, int, float))]
    ins = draft.get("insight") or {}
    if ins.get("text"):
        out.append(("insight", ins["text"]))
    return out


def check_numbers(run: Path) -> dict:
    R = load_run(run)
    allow = [re.compile(p) for p in rules()["number_allow"]]
    blocking, advisory, tokens = [], [], {}
    # A desk run's Korean edition is drafted by qkr from the English with the numbers filled in (artools/desk/korean.py),
    # so its prose holds numbers, not tokens. It is checked string by string against its English instead.
    derived = (run / "desk" / "korean.json").is_file()
    for lang, d in R["drafts"].items():
        if not d:
            continue
        if lang == "ko" and derived:
            from .desk import korean
            blocking += korean.verify(run)
            for kn in d.get("keyNumbers", []):
                if not TOKEN.fullmatch((kn.get("value") or "").strip()):
                    blocking.append(f"ko.keyNumbers: value '{kn.get('value')}' must be a single fact token")
            continue
        tokens[lang] = set()
        for where, text in _texts(d):
            for m in TOKEN.finditer(text):
                tokens[lang].add(m.group(1))
                f = R["facts"].get(m.group(1))
                if not f:
                    blocking.append(f"{lang}.{where}: unknown fact {m.group(0)}")
                elif not f.get("publishable"):
                    blocking.append(f"{lang}.{where}: fact {m.group(1)} is not publishable")
            bare = TOKEN.sub(" ", text)
            bare = CITE.sub(" ", bare)
            bare = GLOSS.sub(" ", bare)
            bare = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", bare)       # links
            for a in allow:
                bare = a.sub(" ", bare)
            for m in re.finditer(r"\d[\d,.]*", bare):
                blocking.append(f"{lang}.{where}: typed number '{m.group(0)}' — use a fact token ({text[:80]}…)")
        for kn in d.get("keyNumbers", []):
            v = kn.get("value", "")
            if not TOKEN.fullmatch(v.strip()):
                blocking.append(f"{lang}.keyNumbers: value '{v}' must be a single fact token")
            else:
                tokens[lang].add(TOKEN.fullmatch(v.strip()).group(1))
        for cid in _cites(d):
            if cid not in R["evidence"] and cid not in R["datasets"] and cid not in R["facts"]:
                blocking.append(f"{lang}: citation [[{cid}]] matches no evidence or dataset")
            elif cid in R["evidence"] and R["evidence"][cid].get("quote") and not R["evidence"][cid].get("verified"):
                blocking.append(f"{lang}: citation {cid} carries an unverified quote")
    if "en" in tokens and "ko" in tokens and tokens["en"] != tokens["ko"]:
        blocking.append(f"EN and KO use different facts: only EN {sorted(tokens['en'] - tokens['ko'])}, "
                        f"only KO {sorted(tokens['ko'] - tokens['en'])}")
    return {"blocking": blocking, "advisory": advisory, "facts_used": {k: sorted(v) for k, v in tokens.items()}}


def _cites(d: dict) -> list[str]:
    from .content import cited_ids
    return cited_ids(d)


def check_style(run: Path) -> dict:
    R = load_run(run)
    rl = rules()
    blocking, advisory = [], []
    from .content import render_tokens
    for lang, d in R["drafts"].items():
        if not d:
            continue
        title = render_tokens(d.get("title", ""), R["facts"], lang)
        if len(title) > rl["headline_max"][lang]:
            blocking.append(f"{lang}.title: {len(title)} characters (max {rl['headline_max'][lang]})")
        if title.rstrip().endswith("?"):
            blocking.append(f"{lang}.title: no question headlines")
        if ":" in title and lang == "en":      # a Korean headline may be "A·B 비교: …, …" (the editor's form, 16 Nov 2026)
            advisory.append(f"{lang}.title: avoid colon subtitles")
        for k in ("kicker", "dek", "disclaimer"):
            if not d.get(k):
                blocking.append(f"{lang}: {k} missing")
        if len(d.get("findings", [])) not in range(3, 6):
            advisory.append(f"{lang}: {len(d.get('findings', []))} findings (3–5 expected)")
        for where, text in _texts(d):
            if re.search(r"(?<![\w])-\d", TOKEN.sub("", text)):
                advisory.append(f"{lang}.{where}: hyphen used as a minus sign")
            if re.search(r"!", text):
                advisory.append(f"{lang}.{where}: no exclamation marks")
    pl = read_json(run / "plan.json", {}) or {}
    figs = [b.get("chart") for s in (R["drafts"]["en"] or {}).get("sections", []) for b in s.get("blocks", []) if b.get("type") == "figure"]
    for f in pl.get("figures", []):
        if f["id"] not in figs and f["form"] != "stat-tiles":
            advisory.append(f"plan figure {f['id']} is not placed in the EN draft")
    return {"blocking": blocking, "advisory": advisory}


def check_licences(run: Path) -> dict:
    R = load_run(run)
    blocking = []
    for cid, ch in R["charts"].items():
        for s in (ch.get("meta") or {}).get("sources", []):
            d = R["datasets"].get(s)
            if d and not d.get("publishable"):
                blocking.append(f"chart {cid}: dataset {s} is not publishable")
    for f in R["facts"].values():
        for i in f.get("inputs", []):
            d = R["datasets"].get(i)
            if d and not d.get("publishable") and f.get("publishable"):
                blocking.append(f"fact {f['id']} marked publishable but {i} is not")
    return {"blocking": blocking, "advisory": []}


def check_readability(run: Path) -> dict:
    R = load_run(run)
    rl = rules()
    advisory, stats = [], {}
    from .content import render_tokens
    for lang, d in R["drafts"].items():
        if not d:
            continue
        paras = [render_tokens(CITE.sub("", GLOSS.sub(lambda m: m.group(0)[2:-2].split("|")[-1], t)), R["facts"], lang)
                 for w, t in _texts(d) if ".p[" in w or w == "insight"]
        sents = [s for p in paras for s in re.split(r"(?<=[.!?。])\s+", p.strip()) if s]
        if lang == "en":
            lens = [len(s.split()) for s in sents]
            avg = sum(lens) / max(1, len(lens))
            stats["en"] = {"sentences": len(sents), "avg_words": round(avg, 1), "max_words": max(lens or [0])}
            if avg > rl["sentence_words_avg_max"]:
                advisory.append(f"en: average sentence {avg:.1f} words (target ≤ {rl['sentence_words_avg_max']})")
            for s, n in zip(sents, lens):
                if n > rl["sentence_words_max"]:
                    advisory.append(f"en: {n}-word sentence: “{s[:90]}…”")
        else:
            lens = [len(s) for s in sents]
            avg = sum(lens) / max(1, len(lens))
            stats["ko"] = {"sentences": len(sents), "avg_chars": round(avg, 1)}
            if avg > rl["ko_sentence_chars_avg_max"]:
                advisory.append(f"ko: average sentence {avg:.0f} characters (target ≤ {rl['ko_sentence_chars_avg_max']})")
            long = [(s, n) for s, n in zip(sents, lens) if n > rl["ko_sentence_chars_max"]]
            stats["ko"]["over_max"] = len(long)
            for s, n in long[:8]:
                advisory.append(f"ko: {n}-character sentence: “{s[:60]}…”")
            for s in sents:
                if re.search(r"[:;](?=\s)", s):
                    advisory.append(f"ko: colon or semicolon joins two sentences: “{s[:60]}…”")
            blob = " ".join(paras)
            for pat, fix in rl["ko_translationese"].items():
                hits = [m.start() for m in re.finditer(pat, blob)]
                if hits:
                    i = hits[0]
                    advisory.append(f"ko: {len(hits)}× /{pat}/ ({fix}): “…{blob[max(0, i - 20):i + 25]}…”")
        for p in paras:
            n = len([s for s in re.split(r"(?<=[.!?。])\s+", p.strip()) if s])
            if n > rl["paragraph_sentences_max"]:
                advisory.append(f"{lang}: paragraph of {n} sentences: “{p[:70]}…”")
        if lang == "en":
            blob = " ".join(t for _, t in _texts(d))
            for term in rl["jargon"]:
                i = blob.find(term)
                if i >= 0 and "((" not in blob[max(0, i - 40):i + len(term) + 5] and term not in ("bp",):
                    advisory.append(f"en: '{term}' first appears without a glossary mark")
    return {"blocking": [], "advisory": advisory[:40], "stats": stats}


def check_charts(run: Path) -> dict:
    R = load_run(run)
    blocking, advisory = [], []
    editions = [lang for lang, d in R["drafts"].items() if d] or ["en"]
    for cid, ch in R["charts"].items():
        form = ch.get("form")
        for fld in ("headline", "title", "alt"):
            for lang in editions:
                if not (ch.get(fld) or {}).get(lang):
                    blocking.append(f"{cid}: {fld}.{lang} missing")
        if form not in ("stat-tiles", "table"):
            axes = ch.get("axes") or {}
            need = ["x", "y"] if form in ("line", "scatter") else ["x"]
            for ax in need:
                a = axes.get(ax) or {}
                lab = a.get("label") or {}
                for lang in editions:
                    if not lab.get(lang):
                        blocking.append(f"{cid}: axes.{ax}.label.{lang} missing")
                if not a.get("unit") and not any(u in (lab.get("en") or "") for u in ("%", "bp", "index", "USD", "won")):
                    advisory.append(f"{cid}: axes.{ax} has no unit")
            if form == "bars":
                dom = (axes.get("x") or {}).get("domain")
                if dom and dom[0] != 0:
                    blocking.append(f"{cid}: bars must start at zero (domain {dom})")
            if not (ch.get("meta") or {}).get("lastObservation"):
                advisory.append(f"{cid}: meta.lastObservation missing")
        if not ch.get("table") and form != "stat-tiles":
            blocking.append(f"{cid}: no table view")
        # values must match their datasets where the chart says which dataset a series comes from
        for s in ch.get("series", []) or []:
            ds = s.get("dataset")
            if ds and ds in R["datasets"] and ch.get("x"):
                vals = _csv_values(run, R["datasets"][ds])
                for x, v in zip(ch["x"], s.get("values", [])):
                    if v is None or x not in vals or vals[x] is None:
                        continue
                    if abs(vals[x] - v) > max(1e-6, abs(vals[x]) * 1e-6) + 0.051:
                        blocking.append(f"{cid}: series {s['id']} at {x} is {v}, dataset {ds} has {vals[x]}")
                        break
        for s in (ch.get("meta") or {}).get("sources", []):
            if s not in R["datasets"] and s not in R["evidence"] and s not in R["facts"]:
                blocking.append(f"{cid}: meta.sources has unknown id {s}")
    pl = read_json(run / "plan.json", {}) or {}
    for f in pl.get("figures", []):
        if f["id"] not in R["charts"]:
            blocking.append(f"plan figure {f['id']} has no chart file")
    return {"blocking": blocking, "advisory": advisory}


def _csv_values(run: Path, ds: dict) -> dict:
    p = run / ds["file"]
    out = {}
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[r["date"]] = float(r["value"]) if r["value"] else None
    return out


def check_links(run: Path) -> dict:
    """Every cited URL answers. A 404/410 or a page that says it isn't found blocks; a timeout or a refusal of
    automated requests is advisory (some sites, FRED among them, drop browser-like user agents)."""
    R = load_run(run)
    urls = set()
    for lang in ("en", "ko"):
        for cid in set(_cites(R["drafts"][lang] or {})):
            if cid in R["evidence"]:
                urls.add(R["evidence"][cid]["doc"].get("url"))
            elif cid in R["datasets"]:
                urls.add(R["datasets"][cid].get("url"))
    blocking, advisory, ok = [], [], 0
    agents = ["datasteg-articles-linkcheck/0.1 (+https://articles.datasteg.com)", "Python-urllib/3.12"]
    for u in sorted(x for x in urls if x):
        last = None
        for ua in agents:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": ua}, method="GET")
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read(20000).decode("utf-8", "replace").lower()
                    head = body[:6000]
                    if ("page not found" in head or "404 not found" in head) and "<title" in head:
                        last = ("block", f"{u}: answers but looks like a not-found page")
                    else:
                        last = ("ok", None)
                break
            except urllib.error.HTTPError as e:
                last = ("block", f"{u}: HTTP {e.code}") if e.code in (404, 410) else ("advise", f"{u}: HTTP {e.code}")
                if e.code in (404, 410):
                    break
            except Exception as e:
                last = ("advise", f"{u}: {type(e).__name__} (check by hand)")
        kind, msg = last
        if kind == "ok":
            ok += 1
        elif kind == "block":
            blocking.append(msg)
        else:
            advisory.append(msg)
    return {"blocking": blocking, "advisory": advisory, "ok": ok}


def check_glossary(run: Path) -> dict:
    """Glossary terms are shared by every article: definitions stay general, and a term another article already
    defines keeps that definition (this article adds a context sentence instead). Topics come from config/topics.yaml."""
    import yaml
    from .paths import CONFIG, CONTENT
    blocking, advisory = [], []
    gl = read_json(run / "draft" / "glossary.json", []) or []
    for g in gl:
        prev = read_json(CONTENT / "glossary" / f"{g['id']}.json", None)
        for lang in ("en", "ko"):
            d = (g.get("definition") or {}).get(lang) or ""
            if re.search(r"\bhere\b|this article|in this piece|이 글", d, re.I):
                # blocking only when this definition would become the shared one (publishing keeps an existing entry)
                (advisory if prev else blocking).append(
                    f"glossary {g['id']} ({lang}): the definition mentions this article; keep it general and move the "
                    f"article-specific part to `context`")
        if prev and prev.get("definition") != g.get("definition"):
            advisory.append(f"glossary {g['id']}: already defined by another article (\"{(prev['definition'] or {}).get('en', '')[:90]}…\"); "
                            f"publishing keeps that definition. If it doesn't fit here, add a `context` sentence or use another id")
    known = {t["id"] for t in yaml.safe_load((CONFIG / "topics.yaml").read_text(encoding="utf-8"))["topics"]}
    for t in (read_json(run / "plan.json", {}) or {}).get("topics", []):
        if t.get("id") not in known and not t.get("new"):
            advisory.append(f"topic {t.get('id')} is not in config/topics.yaml; choose a listed topic or mark it \"new\" for the editor")
    return {"blocking": blocking, "advisory": advisory, "terms": len(gl)}


ALL = {"numbers": check_numbers, "style": check_style, "licences": check_licences, "readability": check_readability,
       "charts": check_charts, "links": check_links, "glossary": check_glossary}


def check_cover(run: Path) -> dict:
    from .cover import check
    return check(run)


def check_pdf(run: Path) -> dict:
    from .pdf import check
    return check(run)


# the cover and the PDF are made after the review, so `check all` (the review's) leaves them out
def check_video_script(run: Path) -> dict:
    from .video.script import check
    return check(run)


OTHER = {"cover": check_cover, "pdf": check_pdf, "video-script": check_video_script}


def run_checks(run_id: str, names: list[str]) -> dict:
    run = run_dir(run_id)
    return {n: {**ALL, **OTHER}[n](run) for n in names}
