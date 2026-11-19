"""From a run to the content format (contracts/content.md): fact tokens rendered per language, citation ids
mapped to numbered sources, charts and their CSVs copied, glossary terms written. Used by preview and publish."""
from __future__ import annotations

import csv
import json
import io
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

from . import pipelines, usage
from .locate import locate
from .paths import ARTICLES, CONFIG, CONTENT, PREVIEW, die, load_yaml, publish_anyway, read_json, read_jsonl, run_dir, write_json

TOKEN = re.compile(r"\{\{(F\d+)(?:\|([a-z,]+))?\}\}")
CITE = re.compile(r"\[\[([^\]]+)\]\]")
GLOSS = re.compile(r"\(\(([a-z0-9-]+)(?:\|[^)]*)?\)\)")
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December"]
MON_EN = [m[:3] for m in MONTHS_EN]
WORDS_EN = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
MINUS = "−"


# ------------------------------------------------------------------ facts → text

def fmt_number(v: float, decimals: int) -> str:
    s = f"{abs(v):,.{decimals}f}"
    return (MINUS if v < 0 and float(s.replace(",", "")) != 0 else "") + s


MONEY_UNIT = re.compile(r"^(USD|EUR|KRW|JPY|GBP|CNY) (bn|tn)$")
KO_CURRENCY = {"USD": "달러", "EUR": "유로", "KRW": "원", "JPY": "엔", "GBP": "파운드", "CNY": "위안"}
KO_EOK = re.compile(r"\{v\}0?억")


def ko_eok(v: float, decimals: int, signed: bool = False) -> str:
    """A billions amount in Korean 억/조, as the Bank of Korea writes it: 279.2 bn → '2,790억' (decimals 0),
    '2,792억' (decimals 1); 1,014 bn → '1조 140억'. The precision follows the fact's decimals (1 bn = 10억)."""
    p = decimals - 1
    e = round(abs(v) * 10, p)
    if e == 0:
        return "0억"
    p = max(p, 0)
    jo = int(e // 10000)
    rest = round(e - jo * 10000, p)
    body = " ".join(x for x in ((f"{jo:,}조" if jo else ""), (f"{rest:,.{p}f}억" if rest else "")) if x)
    return (MINUS if v < 0 else "+" if signed and v > 0 else "") + body


def render_fact(f: dict, lang: str, opts: set[str] | None = None) -> str:
    opts = opts or set()
    unit = (f.get("unit") or "").strip()
    disp = f.get("display") or {}
    v = f["value"]
    if unit in ("month", "date", "quarter", "year") or isinstance(v, str):
        s = str(v)
        if unit == "month" or re.fullmatch(r"\d{4}-\d{2}", s):
            y, m = int(s[:4]), int(s[5:7])
            return f"{MONTHS_EN[m - 1]} {y}" if lang == "en" else f"{y}년 {m}월"
        if unit == "date" or re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
            return f"{d} {MON_EN[m - 1]} {y}" if lang == "en" else f"{y}년 {m}월 {d}일"
        if unit == "quarter" or re.fullmatch(r"\d{4}-Q\d", s):
            return f"Q{s[-1]} {s[:4]}" if lang == "en" else f"{s[:4]}년 {s[-1]}분기"
        return s
    if "abs" in opts:
        v = abs(v)
    dec = int(disp.get("decimals", 0 if abs(v) >= 100 else 1))
    if unit in ("count", "months", "countries", "years", "times") and dec == 0 and lang == "en" and 0 <= v < 10 \
            and float(v).is_integer() and "digits" not in opts:
        word = WORDS_EN[int(v)]
        return {"months": f"{word} months", "years": f"{word} years", "countries": f"{word} countries",
                "times": f"{word} times"}.get(unit, word)
    num = fmt_number(v, dec)
    if "signed" in opts and v > 0:
        num = "+" + num
    tmpl = disp.get(lang)
    money = MONEY_UNIT.match(unit)
    if lang == "ko" and money and money.group(2) == "bn" and (not tmpl or KO_EOK.search(tmpl)):
        # Korean has no billion: bn amounts render in 억/조 ("2,790억 달러", "1조 140억 달러"), never "10억 달러" units
        # nor the old "{v}0억" text trick (no comma, wrong at decimals ≥ 1). Templates may say "{v}0억" or "{v}억".
        amount = ko_eok(v, dec, "signed" in opts)
        if not tmpl:
            return f"{amount} {KO_CURRENCY[money.group(1)]}"
        return KO_EOK.sub(lambda _: amount, tmpl, count=1)
    if lang == "ko" and money and money.group(2) == "tn" and not tmpl:
        return f"{num}조 {KO_CURRENCY[money.group(1)]}"
    if tmpl:
        return tmpl.replace("{v}", num)
    if unit == "bp":
        return f"{num}bp"
    if unit in ("%", "% of GDP", "% per year", "percent"):
        return f"{num}%"
    if unit == "pp":
        return f"{num} pp" if lang == "en" else f"{num}%p"
    if unit in ("x", "times"):
        return f"{num} times" if lang == "en" else f"{num}배"
    # a rank, a score or a ratio is a bare number in both editions (19 Nov 2026: "3 rank" in 20261119-desk's Korean
    # key numbers stopped its ship; the desk's English template was "{v}" and the Korean had none)
    if unit in ("months", "years", "count", "countries", "index", "rank", "score", "ratio"):
        suffix = {"months": (" months", "개월"), "years": (" years", "년"), "count": ("", ""),
                  "countries": (" countries", "개국"), "index": ("", ""), "rank": ("", ""), "score": ("", ""), "ratio": ("", "")}[unit]
        return num + (suffix[0] if lang == "en" else suffix[1])
    return f"{num} {unit}".strip()


def render_tokens(text: str, facts: dict, lang: str) -> str:
    def sub(m):
        f = facts.get(m.group(1))
        if not f:
            die(f"unknown fact token {m.group(0)}")
        return render_fact(f, lang, set((m.group(2) or "").split(",")) - {""})
    return TOKEN.sub(sub, text)


# ------------------------------------------------------------------ run loading

def load_run(run: Path) -> dict:
    facts = {f["id"]: f for f in (read_json(run / "analysis" / "analysis.json", {}) or {}).get("facts", [])}
    evidence = {}
    for p in list((run / "evidence").glob("*.jsonl")) + list((run / "scout").glob("evidence-*.jsonl")):
        for e in read_jsonl(p):
            evidence[e["id"]] = e
    datasets = {}
    for p in list((run / "data").glob("*/catalog.json")) + list((run / "scout" / "data").glob("*/catalog.json")):
        for d in read_json(p, []):
            datasets.setdefault(d["id"], d)
    return {"facts": facts, "evidence": evidence, "datasets": datasets,
            "plan": read_json(run / "plan.json", {}), "review": read_json(run / "question-review.json", {}),
            "brief": read_json(run / "brief.json", {}), "manifest": read_json(run / "run.json", {}),
            "drafts": {lang: read_json(run / "draft" / f"{lang}.json") for lang in ("en", "ko")},
            "glossary": read_json(run / "draft" / "glossary.json", []) or [],
            "charts": {p.stem: read_json(p) for p in sorted((run / "charts").glob("*.json"))
                       if not p.name.endswith(".log.json")}}  # charts.log.json is the stage log


def walk_text(obj, fn, key=None):
    """Apply fn to every reader-facing string in a draft."""
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [walk_text(x, fn, key) for x in obj]
    if isinstance(obj, dict):
        return {k: (v if k in ("id", "type", "chart", "key", "align", "cite", "citations") else walk_text(v, fn, k))
                for k, v in obj.items()}
    return obj


# ------------------------------------------------------------------ sources

def underlying(cid: str, R: dict, depth: int = 0) -> list[str]:
    """The records a citation id stands for: evidence and fetched datasets as themselves; a derived dataset
    (provider "datasteg calculation") or a fact by the datasets it was computed from."""
    if cid in R["evidence"]:
        return [cid]
    if cid in R["datasets"]:
        d = R["datasets"][cid]
        if "calculation" in (d.get("provider") or "").lower() and d.get("inputs") and depth < 5:
            return [x for i in d["inputs"] for x in underlying(i, R, depth + 1)]
        return [cid]
    if cid in R["facts"] and depth < 5:
        return [x for i in R["facts"][cid].get("inputs", []) for x in underlying(i, R, depth + 1)]
    die(f"citation {cid} matches no evidence, dataset or fact")


def source_key(cid: str, R: dict) -> tuple[str, dict]:
    """Grouping key: evidence by document; datasets by provider + series family (the provider's title), so a
    provider's series for ten countries is one source."""
    if cid in R["evidence"]:
        e = R["evidence"][cid]
        return "doc:" + e["doc"]["ref"], {"kind": "evidence", "rec": e}
    d = R["datasets"][cid]
    family = d.get("title") or d["indicator"]
    if d.get("provider", "").startswith("FRED"):
        family = d["key"]                       # FRED titles are per series; keep one source per series
    return f"data:{d['provider']}|{family}", {"kind": "dataset", "rec": d}


def doc_kind(e: dict) -> str:
    t = (e["doc"].get("type") or "").lower()
    series = (e["doc"].get("series") or "").lower()
    if "speech" in t or "speech" in series:
        return "speech"
    if "policy" in series or "brief" in series or "note" in series:
        return "policy-note"
    if e.get("source") == "official":
        return "web"
    return "paper"


def build_sources(R: dict, order: list[str]) -> tuple[list[dict], dict]:
    groups, under = {}, {}
    for cid in order:
        under[cid] = list(dict.fromkeys(underlying(cid, R)))
        for u in under[cid]:
            key, item = source_key(u, R)
            if (u, item) not in [(x, y) for x, y in groups.get(key, [])]:
                groups.setdefault(key, []).append((u, item))
    sources, sid_of = [], {}
    for n, (key, items) in enumerate(groups.items(), 1):
        sid = f"S{n}"
        for u, _ in items:
            sid_of[u] = sid
    mapping = {cid: list(dict.fromkeys(sid_of[u] for u in us)) for cid, us in under.items()}
    for n, (key, items) in enumerate(groups.items(), 1):
        sid = f"S{n}"
        first = items[0][1]
        cits = {lang: (R["drafts"][lang] or {}).get("citations", {}) for lang in ("en", "ko")}
        cids_here = [c for c, us in mapping.items() if sid in us]
        used = {lang: next((cits[lang].get(c, {}).get("used_for") for c in cids_here + [u for u, _ in items]
                            if cits[lang].get(c)), None) for lang in ("en", "ko")}
        if first["kind"] == "evidence":
            e = first["rec"]
            d = e["doc"]
            quote = next(({"text": it["rec"]["quote"], "lang": "en", "locator": _locator(it["rec"])}
                          for _, it in items if it["rec"].get("quote") and it["rec"].get("verified")), None)
            src = {"id": sid, "kind": doc_kind(e), "title": d["title"], "titleTranslated": d.get("title_ko") and {"ko": d["title_ko"]},
                   "authors": d.get("authors_text") or _authors(d.get("authors")), "institution": d.get("institution"),
                   "series": d.get("series"), "number": d.get("number"), "date": d.get("date"),
                   "url": d.get("url") or d.get("doc_url"), "pdfUrl": d.get("pdf_url"), "doi": d.get("doi"),
                   "quote": quote, "usedFor": used, "ref": d["ref"]}
            src["cite"] = {"en": _cite(src, "en"), "ko": _cite(src, "ko")}
        else:
            ds = [it["rec"] for _, it in items]
            d0 = ds[0]
            keys = list(dict.fromkeys(d["key"] for d in ds))
            geos = ", ".join(sorted({d.get("geo") or "" for d in ds} - {""}))
            inds = list(dict.fromkeys(d["indicator"] for d in ds))
            base = inds[0] if len(inds) == 1 else (d0.get("title") or inds[0])
            if len(inds) == 1 and len(ds) > 1:   # one indicator for several countries: drop the country from its name
                base = re.sub(r",\s*(France|Germany|Italy|Spain|Portugal|Greece|Belgium|Netherlands|Austria|Finland|Ireland|[A-Z]{2})$", "", base)
            title = base + (f" ({geos})" if len(ds) > 1 and geos else "")
            src = {"id": sid, "kind": "dataset", "title": title, "institution": d0["provider"],
                   "date": (d0.get("retrieved") or "")[:10], "url": d0.get("url"),
                   "dataset": {"provider": d0["provider"], "key": keys if len(keys) > 1 else keys[0],
                               "unit": d0.get("unit"), "frequency": d0.get("frequency"),
                               "lastObservation": (d0.get("span") or [None, None])[1],
                               "retrieved": (d0.get("retrieved") or "")[:10], "attribution": d0.get("attribution"),
                               "publishable": all(d.get("publishable") for d in ds), "locate": locate(ds)},
                   "usedFor": used}
            src["cite"] = {"en": f"{d0['provider']}. {title}. {', '.join(keys)}. Retrieved {_date_en(src['date'])}.",
                           "ko": f"{d0['provider']}. {title}. {', '.join(keys)}. {_date_ko(src['date'])} 조회."}
        sources.append({k: v for k, v in src.items() if v is not None})
    return sources, mapping


def _bases(cid: str, R: dict, depth: int = 0) -> list[str]:
    """underlying() without stopping on an id it doesn't know (a fact input that is neither a record nor a fact)."""
    if cid in R["evidence"] or (cid in R["datasets"] and not (
            "calculation" in (R["datasets"][cid].get("provider") or "").lower() and R["datasets"][cid].get("inputs") and depth < 5)):
        return [cid]
    if cid in R["datasets"]:
        return [x for i in R["datasets"][cid]["inputs"] for x in _bases(i, R, depth + 1)]
    if cid in R["facts"] and depth < 5:
        return [x for i in R["facts"][cid].get("inputs", []) for x in _bases(i, R, depth + 1)]
    return []


def fact_entries(R: dict, sources: list[dict]) -> list[dict]:
    """meta.json → facts: each fact's id, value, unit and period; `publishable`, false for a fact the analysis blocked
    or one computed from a series that may not be published (the site's API serves only publishable facts); and
    `sources`, the sources.json ids of the series and documents it was computed from. A fact none of whose series the
    article cites has `sources: []` and names them in `series` ({provider, key})."""
    by_series, by_doc = {}, {}
    for s in sources:
        if s.get("kind") == "dataset" and s.get("dataset"):
            keys = s["dataset"].get("key")
            for k in keys if isinstance(keys, list) else [keys]:
                by_series.setdefault((s["dataset"].get("provider"), k), s["id"])
        if s.get("ref"):
            by_doc.setdefault(s["ref"], s["id"])
    out = []
    for f in R["facts"].values():
        bases = list(dict.fromkeys(_bases(f["id"], R)))
        sids, series, ok = [], [], f.get("publishable") is not False and bool(bases)
        for u in bases:
            if u in R["evidence"]:
                sid = by_doc.get(R["evidence"][u]["doc"]["ref"])
            else:
                d = R["datasets"][u]
                ok = ok and d.get("publishable") is not False
                sid = by_series.get((d.get("provider"), d.get("key")))
                if not sid:
                    series.append({"provider": d.get("provider"), "key": d.get("key")})
            if sid and sid not in sids:
                sids.append(sid)
        e = {"id": f["id"], "value": f["value"], "unit": f.get("unit"), "period": f.get("period"), "publishable": ok, "sources": sids}
        if not sids and series:
            e["series"] = series
        out.append(e)
    return out


def _locator(e: dict) -> str | None:
    loc = e.get("locator") or {}
    if loc.get("page"):
        return f"p. {loc['page']}"
    return None


def _authors(a) -> str | None:
    if not a:
        return None
    if isinstance(a, list):
        names = [x.get("name") if isinstance(x, dict) else str(x) for x in a]
        names = [n for n in names if n]
        return ", ".join(names[:3]) + (" et al." if len(names) > 3 else "") if names else None
    return str(a)


def _date_en(s: str | None) -> str:
    if not s or len(s) < 10:
        return s or ""
    return f"{int(s[8:10])} {MON_EN[int(s[5:7]) - 1]} {s[:4]}"


def _date_ko(s: str | None) -> str:
    if not s or len(s) < 10:
        return s or ""
    return f"{s[:4]}년 {int(s[5:7])}월 {int(s[8:10])}일"


def _cite(s: dict, lang: str) -> str:
    who = s.get("authors") or s.get("institution") or ""
    year = (s.get("date") or "")[:4]
    series = " ".join(x for x in [s.get("series"), s.get("number")] if x)
    parts = [f"{who} ({year}).", f"{s['title']}.", f"{series}." if series else "", s.get("institution") if s.get("authors") else ""]
    return " ".join(p for p in parts if p).strip()


# ------------------------------------------------------------------ build

def plain(text: str) -> str:
    """A title as readers see it: without citation, glossary and emphasis marks."""
    text = CITE.sub("", text)
    text = re.sub(r"\(\(([^)|]+)(?:\|([^)]*))?\)\)", lambda m: m.group(2) or m.group(1), text)
    return re.sub(r"\*([^*]+)\*", r"\1", text).strip()


def citation(slug: str, date: str, titles: dict[str, str]) -> dict:
    """How readers should cite the article, from config/editorial.yaml → citation. Stamped into meta.json at publish,
    so an article keeps the author it was published under when the config changes (contracts/content.md § Citation)."""
    cfg = (load_yaml(CONFIG / "editorial.yaml") or {}).get("citation") or {}
    base = (cfg.get("base_url") or "https://articles.datasteg.com").rstrip("/")

    def per_lang(v, default: str) -> dict:
        return {lang: (v.get(lang) if isinstance(v, dict) else v) or default for lang in titles}

    return {"author": per_lang(cfg.get("author"), "datasteg"), "publisher": per_lang(cfg.get("publisher"), "datasteg articles"),
            "date": date, "title": {lang: plain(t) for lang, t in titles.items()},
            "url": {lang: f"{base}/{lang}/a/{slug}" for lang in titles}}


def cited_ids(draft: dict) -> list[str]:
    seen = []
    def grab(s):
        for m in CITE.finditer(s):
            for c in m.group(1).split(","):
                c = c.strip()
                if c and c not in seen:
                    seen.append(c)
        return s
    walk_text({k: v for k, v in draft.items() if k != "citations"}, grab)
    for kn in draft.get("keyNumbers", []):
        for c in kn.get("cite", []) or []:
            if c not in seen:
                seen.append(c)
    for blk in (b for s in draft.get("sections", []) for b in s.get("blocks", [])):
        for c in ([blk.get("cite")] if isinstance(blk.get("cite"), str) else blk.get("cite") or []):
            if c and c not in seen:
                seen.append(c)
    return seen


# ------------------------------------------------------------------ what the article drew on (meta.json)

APPS = ("money-flow", "trade-flow", "global-network", "open-research")   # the order of draws_on
ARCHIVE_REF = "jejualps:"      # a research-archive document: the store open-research is built from
FAMILY = ARTICLES.parent / "family" / "family.json"


def app_hosts() -> dict[str, str]:
    """Each app's host from family/family.json, as a lower-case netloc."""
    fam = read_json(FAMILY, None)
    if not fam:
        die(f"no {FAMILY}: draws_on needs the apps' hosts")
    return {s["id"]: urlparse(s["host"]).netloc.lower() for s in fam.get("sites", []) if s.get("id") in APPS and s.get("host")}


def draws_on(sources: list[dict], hosts: dict[str, str]) -> dict[str, int]:
    """The apps an article draws on, each with the number of distinct sources.json
    entries that put it there: open-research for a research-archive document (ref jejualps:<id>), another app for a
    page on its host. An app no source cites is left out."""
    cites = {a: set() for a in APPS}
    for s in sources:
        key = s.get("id") or s.get("ref") or s.get("url")
        if str(s.get("ref") or "").startswith(ARCHIVE_REF):
            cites["open-research"].add(key)
        for u in (s.get("url"), s.get("pdfUrl")):
            netloc = urlparse(u).netloc.lower() if isinstance(u, str) else ""
            for app, host in hosts.items():
                if netloc and netloc == host:
                    cites[app].add(key)
    return {a: len(cites[a]) for a in APPS if cites[a]}


def fetch_volume(run: Path) -> dict[str, dict]:
    """What the run fetched from statistics APIs, per provider folder data/<provider>/ (data/derived is computed and
    left out): series = catalog.json entries whose CSV the folder has, rows = their data rows (header excluded),
    bytes = their sizes. A folder with neither a catalog nor CSV files (data/public-data holds only its stage log) and
    a provider with no series are left out. Raises ValueError when a number cannot be read."""
    out = {}
    data = run / "data"
    for d in sorted(p for p in data.iterdir() if p.is_dir()) if data.is_dir() else []:
        if d.name == "derived":
            continue
        cat = d / "catalog.json"
        if not cat.is_file():
            if any(d.glob("*.csv")):
                raise ValueError(f"data/{d.name} has CSV files but no catalog.json")
            continue
        try:
            items = read_json(cat, []) or []
        except ValueError as e:
            raise ValueError(f"data/{d.name}/catalog.json: {e}") from e
        items = items.get("datasets", []) if isinstance(items, dict) else items
        files = {}
        for e in items:
            f = run / e["file"] if e.get("file") else d / f"{e.get('id')}.csv"
            if f.is_file():
                files.setdefault(f.resolve(), f)
        rows = 0
        for f in files.values():
            try:
                with f.open(encoding="utf-8", newline="") as fh:
                    rows += max(0, sum(1 for r in csv.reader(fh) if r) - 1)
            except (ValueError, csv.Error) as e:
                raise ValueError(f"{f.relative_to(run)}: {e}") from e
        if files:
            out[d.name] = {"series": len(files), "rows": rows, "bytes": sum(f.stat().st_size for f in files.values())}
    return out


def article_volume(run: Path | None, sources: list[dict], before: dict | None = None,
                   hosts: dict[str, str] | None = None) -> tuple[dict, str | None]:
    """meta.json → draws_on, draws_on_evidence and fetch (contracts/content.md § What the article drew on), and why
    fetch is left out, if it is. On an update, an app the editor added by hand (with draws_on_note) stays."""
    ev = draws_on(sources, app_hosts() if hosts is None else hosts)
    before = before or {}
    kept = list(before.get("draws_on") or []) if before.get("draws_on_note") else []
    out = {"draws_on": [a for a in APPS if a in ev or a in kept] + [a for a in kept if a not in APPS],
           "draws_on_evidence": ev}
    if before.get("draws_on_note"):
        out["draws_on_note"] = before["draws_on_note"]
    if run is None or not run.is_dir():
        return out, "no run folder"
    try:
        out["fetch"] = fetch_volume(run)
    except ValueError as e:
        return out, str(e)
    return out, None


def build(run_id: str, slug: str, dest_root: Path, approved_by: str | None = None, overwrite_glossary: bool = False) -> dict:
    run = run_dir(run_id)
    R = load_run(run)
    if not R["drafts"]["en"]:
        die("no draft/en.json")
    editions = [lang for lang in ("en", "ko") if R["drafts"][lang]]
    order = []
    for lang in editions:
        for c in cited_ids(R["drafts"][lang]):
            if c not in order:
                order.append(c)
    for ch in R["charts"].values():
        for c in (ch.get("meta") or {}).get("sources", []):
            if c not in order:
                order.append(c)
    sources, mapping = build_sources(R, order)
    hosts = app_hosts()     # before anything is written: a missing family.json stops here, not halfway

    def remap(s: str) -> str:
        s = CITE.sub(lambda m: "[[" + ",".join(dict.fromkeys(x for c in m.group(1).split(",")
                                                            for x in mapping.get(c.strip(), [c.strip()]))) + "]]", s)
        return s

    # the list's picture (guides/covers.md): published only when it passes its check; a preview leaves out a failing one
    from .cover import check as check_cover
    cover_svg = run / "cover" / "cover.svg"
    cover_check = check_cover(run) if cover_svg.is_file() else None
    if cover_check and cover_check["blocking"] and dest_root == CONTENT and not publish_anyway():
        die(f"the cover fails its check: artools check cover --run {run.name}", problems=cover_check["blocking"])

    dest = dest_root / "articles" / slug
    before = {}         # the published meta.json, when this is an update of a live article
    if dest.exists():   # several runs share .preview/ and content/: a slug belongs to the run that made it
        before = read_json(dest / "meta.json", {}) or {}
        owner = (before.get("run") or {}).get("id")
        if owner and owner != run.name:
            die(f"slug {slug} belongs to run {owner}; choose another slug in plan.json")
        shutil.rmtree(dest)
    before = before if dest_root == CONTENT and (before.get("review") or {}).get("approved") else {}
    (dest / "charts").mkdir(parents=True)
    (dest / "data").mkdir()
    for lang in editions:
        d = R["drafts"][lang]
        body = {k: v for k, v in d.items() if k not in ("citations", "methodNote")}   # older drafts carry a methodNote; the site shows none
        refined = ((R["review"] or {}).get("refined") or {}).get(lang)
        if refined and body.get("question"):   # the box shows the question approved at gate 1, not the raw wording
            body["question"] = {**body["question"], "asked": refined}
        body = walk_text(body, lambda s: remap(render_tokens(s, R["facts"], lang)))
        # an article that cites datasteg's data sites says that their figures follow datasteg's own aggregation rules
        note = ((load_yaml(CONFIG / "editorial.yaml") or {}).get("datasteg_data_note") or {}).get(lang)
        if note and uses_datasteg_data(sources) and note not in (body.get("disclaimer") or ""):
            body["disclaimer"] = ((body.get("disclaimer") or "").rstrip() + " " + note).strip()
        for kn in body.get("keyNumbers", []):
            kn["cite"] = list(dict.fromkeys(x for c in kn.get("cite", []) or [] for x in mapping.get(c, [c])))
        for blk in (b for s in body.get("sections", []) for b in s.get("blocks", [])):
            if isinstance(blk.get("cite"), str):
                blk["cite"] = mapping.get(blk["cite"], [blk["cite"]])[0]
            if isinstance(blk.get("source"), str):
                blk["source"] = mapping.get(blk["source"], [blk["source"]])[0]
        write_json(dest / f"{lang}.json", body)
    # where each source is cited (section ids)
    for s in sources:
        s["citedIn"] = []
    by_id = {s["id"]: s for s in sources}
    en = read_json(dest / "en.json")
    if en.get("keyNumbers"):
        for kn in en["keyNumbers"]:
            for c in kn.get("cite", []):
                if c in by_id and "key-numbers" not in by_id[c]["citedIn"]:
                    by_id[c]["citedIn"].append("key-numbers")
    for sec in en.get("sections", []):
        blob = str(sec)
        for m in CITE.finditer(blob):
            for c in m.group(1).split(","):
                if c in by_id and sec["id"] not in by_id[c]["citedIn"]:
                    by_id[c]["citedIn"].append(sec["id"])
    write_json(dest / "sources.json", sources)
    write_json(dest / "related.json", (R["plan"] or {}).get("related", []))
    chart_ids = []
    for cid, ch in R["charts"].items():
        ch = dict(ch)
        meta = dict(ch.get("meta") or {})
        meta["sources"] = list(dict.fromkeys(x for s in meta.get("sources", []) for x in mapping.get(s, [s])))
        ch["meta"] = meta
        if ch.get("form") == "stat-tiles":
            for t in ch.get("tiles", []):
                t["cite"] = list(dict.fromkeys(x for c in t.get("cite", []) or [] for x in mapping.get(c, [c])))
        ch = walk_text(ch, lambda s: remap(s))
        ch["csv"] = f"data/{cid}.csv" if ch.get("table") else None
        write_json(dest / "charts" / f"{cid}.json", ch)
        if ch.get("table"):
            _table_csv(ch["table"], dest / "data" / f"{cid}.csv")
        chart_ids.append(cid)
    cover = None
    if cover_check and not cover_check["blocking"]:
        shutil.copyfile(cover_svg, dest / "cover.svg")
        cover = {"file": "cover.svg", "alt": (read_json(run / "cover" / "cover.json", {}) or {}).get("alt")}
    # the PDF edition: a preview offers the make-pdf stage's proofs (<run>/pdf/); publishing leaves it empty, and
    # `artools ship` prints each edition again from content/ (pdf.publish), so content/ never takes a proof
    pdf = {}
    proof = (read_json(run / "pdf" / "proof.json", {}) or {}) if dest_root != CONTENT else {}
    for lang in editions:
        r = (proof.get("editions") or {}).get(lang) or {}
        if r.get("pages") and (run / "pdf" / f"{lang}.pdf").is_file():
            (dest / "pdf").mkdir(exist_ok=True)
            shutil.copyfile(run / "pdf" / f"{lang}.pdf", dest / "pdf" / f"{lang}.pdf")
            pdf[lang] = {"file": f"pdf/{lang}.pdf", "pages": r["pages"], "bytes": r["bytes"], "made": proof.get("made")}
    # a data note's data download (desk/reproduce.py bundle): one ZIP of CSV files, served next to the charts' CSVs
    download = None
    if (run / "download" / "data.zip").is_file():
        (dest / "data").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run / "download" / "data.zip", dest / "data" / "data.zip")
        download = {"file": "data/data.zip", "bytes": (dest / "data" / "data.zip").stat().st_size}
    plan, manifest = R["plan"] or {}, R["manifest"]
    words = {lang: _words(read_json(dest / f"{lang}.json"), lang) for lang in editions}
    stats = pipelines.run_stats(run, {lang: _body_words(read_json(dest / f"{lang}.json"), lang) for lang in editions})
    date = before.get("date") or plan.get("date") or manifest.get("created", "")[:10]
    # an update keeps the first date and every earlier correction, and adds the run's corrections.json entries
    corrections = list(before.get("corrections") or [])
    corrections += [c for c in read_json(run / "corrections.json", []) or [] if c not in corrections]
    meta = {
        "slug": slug, "type": stats["pipeline"]["id"], "pipeline": stats["pipeline"],
        "date": date,
        "updated": runlib_today() if before else None, "editions": editions, "topics": pipelines.topics(plan.get("topics", [])), "jel": (R["brief"] or {}).get("jel", []),
        "countries": ((R["brief"] or {}).get("entities") or {}).get("countries", []),
        "readTime": {lang: max(1, round(words[lang] / (230 if lang == "en" else 500))) for lang in editions},
        "charts": [f["id"] for f in plan.get("figures", []) if f["id"] in chart_ids] or chart_ids,
        "cover": cover,
        "facts": fact_entries(R, sources),
        "run": {"id": manifest.get("id"), "skills": {k: v.get("skill_version") for k, v in manifest.get("stages", {}).items()},
                "models": sorted(m for m in usage.usage(run.name)["models"] if "estimate" not in m),
                "runtime": {k: (manifest.get("runtime") or {}).get(k) for k in ("model", "effort")},
                "steps": stats["steps"], "gates": stats["gates"]},
        # the terms this article uses, with how it uses them; the shared definition (glossary/<id>.json) stays general
        "terms": [{"id": g["id"], "context": g.get("context")} for g in R["glossary"]],
        "review": {"editor": approved_by or (manifest.get("gates", {}).get("publish", {}) or {}).get("by"),
                   "approved": (stats["gates"].get("publish") or {}).get("at")},
        "citation": citation(slug, date, {lang: read_json(dest / f"{lang}.json").get("title", "") for lang in editions}),
        "pdf": pdf or None,
        "download": download,
        "corrections": corrections,
    }
    drew, fetch_problem = article_volume(run, sources, before, hosts)
    meta.update(drew)
    write_json(dest / "meta.json", meta)
    gl_dir = dest_root / "glossary"
    gl_dir.mkdir(parents=True, exist_ok=True)
    reused = []    # terms another article defined first, differently: the shared definition must fit this article too
    for g in R["glossary"]:
        p = gl_dir / f"{g['id']}.json"
        prev = read_json(p, None)
        mine = prev is not None and prev.get("_run") == run.name
        # published entries are the editor's: never overwritten; in preview a run only overwrites its own entries
        if prev is None or (overwrite_glossary and mine):
            entry = {"id": g["id"], "term": g["term"], "definition": g["definition"], "approvedBy": None}
            for k in ("topics", "see"):
                if g.get(k):
                    entry[k] = g[k]
            if overwrite_glossary:
                entry["_run"] = run.name
            write_json(p, entry)
        elif not mine and (prev.get("definition") != g["definition"]):
            reused.append(g["id"])
    return {"slug": slug, "dest": str(dest), "editions": editions, "sources": len(sources), "charts": chart_ids,
            "glossary_reused": reused, "cover": bool(cover), "draws_on": meta["draws_on"],
            **({"fetch_problem": fetch_problem} if fetch_problem else {}),
            **({"cover_problems": cover_check["blocking"]} if cover_check and cover_check["blocking"] else {}),
            "readTime": meta["readTime"]}


def _words(d: dict, lang: str) -> int:
    texts = []
    walk_text(d, lambda s: texts.append(s) or s)
    blob = " ".join(texts)
    return len(blob.split()) if lang == "en" else len(re.sub(r"\s", "", blob))


def _body_words(d: dict, lang: str) -> int:
    """Words a reader reads as prose: findings, paragraphs, lists, quotes and the insight (not tables or citations)."""
    texts = list(d.get("findings", []))
    for sec in d.get("sections", []):
        for b in sec.get("blocks", []):
            texts += [b["text"]] if b.get("type") in ("p", "quote") else b.get("items", []) if b.get("type") == "list" else []
    texts.append((d.get("insight") or {}).get("text", ""))
    blob = re.sub(r"\[\[[^\]]*\]\]|\{\{[^}]*\}\}", "0", " ".join(texts))
    return len(blob.split()) if lang == "en" else len(re.sub(r"\s", "", blob))


def _table_csv(table: dict, path: Path):
    cols = table.get("columns", [])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([(c.get("label") or {}).get("en", c["key"]) if isinstance(c.get("label"), dict) else c.get("label", c["key"]) for c in cols])
    for r in table.get("rows", []):
        # a cell may be {"en": …, "ko": …} (a country name, a month): the CSV carries the English
        w.writerow([(v.get("en", "") if isinstance(v := r.get(c["key"], ""), dict) else v) for c in cols])
    path.write_text("﻿" + buf.getvalue(), encoding="utf-8")


def runlib_today() -> str:
    import datetime as dt
    return dt.date.today().isoformat()


def preview(run_id: str, slug: str) -> dict:
    r = build(run_id, slug, PREVIEW, overwrite_glossary=True)
    return {**r, "content_dir": str(PREVIEW)}


DATASTEG_DATA = re.compile(r"https?://(?:money-flow|trade-flow|global-network|api|mcp)\.datasteg\.com", re.I)


def uses_datasteg_data(sources: list[dict]) -> bool:
    """Whether an article cites data from datasteg's data sites (or their API)."""
    return any(DATASTEG_DATA.search(json.dumps(s, ensure_ascii=False)) for s in sources or [])


def publish(run_id: str, slug: str) -> dict:
    run = run_dir(run_id)
    m = read_json(run / "run.json")
    g = m["gates"]["publish"]
    if not g.get("approved"):
        die("gate 3 (publish) is not approved: artools run gate <run> publish --approve --by <editor>")
    return build(run_id, slug, CONTENT, approved_by=g.get("by"))
