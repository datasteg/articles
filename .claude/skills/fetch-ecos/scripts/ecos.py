#!/usr/bin/env python3
"""Bank of Korea ECOS Open API: find, validate and fetch a statistic for an articles run.

ECOS is not a REST/Swagger API. Every call is one GET whose parameters are PATH SEGMENTS in a fixed order:
  https://ecos.bok.or.kr/api/{service}/{key}/{json|xml}/{kr|en}/{first row}/{last row}/{service arguments...}
Errors arrive as HTTP 200 with {"RESULT": {"CODE": "INFO-200" | "ERROR-101" ..., "MESSAGE": ...}}.
A series is (table STAT_CODE, cycle, ITEM_CODE1 .. ITEM_CODE4); a table with two item groups needs both codes.
Full grammar, services and error codes: ../reference/api.md.

Standard library only. The key is read from BOK_API_KEY (or ECOS_API_KEY) in the environment or the first
.env file found in the working folder, articles/ or the repository root. It sits in every URL, so it is
redacted from every error and never written to disk.

  ecos.py tables 시장금리                         tables whose name contains every word (searchable tables only)
  ecos.py tables "interest rate" --lang en       the same in English
  ecos.py items 817Y002 국고채                    the items of one table, optionally filtered
  ecos.py index                                  build the local index of every item of every table (cached a week)
  ecos.py find 국고채 10년 --cycle D               search the index: table names + item names + groups
  ecos.py keystats 금리                           the 100 key statistics with their latest values (good anchors)
  ecos.py word 기준금리                            the statistics glossary (definitions for readers)
  ecos.py meta 경제심리지수                        methodology notes for the 15 BOK statistics
  ecos.py obs 817Y002 D 20260901 20261016 010210000
  ecos.py validate 817Y002 D 010210000 --unit % --range 0,20 --anchor 20261016=3.0:0.5
  ecos.py fetch 817Y002 D 010210000 --from 20070101 --run /data/articles/runs/<id> --indicator "..."

Every command prints JSON. `validate` and `fetch` exit 2 when the verdict is "fail".
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://ecos.bok.or.kr/api"
PACE_S = 0.35            # stay well under the per-key limits (ERROR-602 means "too many calls, wait")
PAGE = 10000             # rows per call; the loop pages through list_total_count
INDEX_TTL_DAYS = 7
CYCLES = {"A": "YYYY", "S": "YYYYS1|S2", "Q": "YYYYQ1..Q4", "M": "YYYYMM", "SM": "YYYYMMS1|S2", "D": "YYYYMMDD"}
STALE_DAYS = {"D": 10, "SM": 40, "M": 75, "Q": 200, "S": 300, "A": 730}
ERRORS = {
    "INFO-100": "invalid key", "INFO-200": "no data for this request",
    "ERROR-100": "a required value is missing", "ERROR-101": "date format doesn't match the cycle",
    "ERROR-200": "file type missing or invalid", "ERROR-300": "row range missing",
    "ERROR-301": "row range must be integers", "ERROR-400": "range too large: 60-second timeout, split the request",
    "ERROR-500": "server error or unknown service", "ERROR-600": "database connection error",
    "ERROR-601": "SQL error", "ERROR-602": "too many calls: access limited for a while",
}

_key = None
_last = 0.0


# ---------------------------------------------------------------- key, cache, HTTP

def api_key() -> str:
    global _key
    if _key:
        return _key
    _key = (os.environ.get("BOK_API_KEY") or os.environ.get("ECOS_API_KEY")
            or _from_env_files(("BOK_API_KEY", "ECOS_API_KEY")))
    if not _key:
        sys.exit(json.dumps({"error": "BOK_API_KEY not found in the environment or in an .env file "
                                      "(articles/.env or the repository root)"}))
    return _key


def _from_env_files(names) -> str | None:
    here = Path(__file__).resolve()
    seen = []
    for base in [Path.cwd(), *Path.cwd().parents, *here.parents]:
        f = base / ".env"
        if f in seen or not f.is_file():
            continue
        seen.append(f)
        for line in f.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.strip().partition("=")
            v = v.split(" #")[0].strip().strip('"').strip("'")   # allow "KEY=value  # comment"
            if sep and k.strip() in names and v and not v.startswith("#"):
                return v
    return None


def redact(text: str) -> str:
    return text.replace(_key, "***") if _key else text


def cache_dir() -> Path:
    for d in (os.environ.get("ARTICLES_CACHE"), "/data/articles/cache"):
        if d and Path(d).is_dir() and os.access(d, os.W_OK):
            p = Path(d) / "ecos"
            p.mkdir(exist_ok=True)
            return p
    p = Path.home() / ".cache" / "datasteg-articles" / "ecos"
    p.mkdir(parents=True, exist_ok=True)
    return p


class EcosError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code} {message}")
        self.code, self.message = code, message


def call(service: str, args: list[str], lang="kr", first=1, last=PAGE) -> tuple[dict, bytes]:
    """One ECOS call. Returns (payload under the service name, raw bytes). Raises EcosError on RESULT."""
    global _last
    segs = [service, api_key(), "json", lang, str(first), str(last)] + [urllib.parse.quote(str(a), safe="") for a in args]
    url = BASE + "/" + "/".join(segs)
    for attempt in range(4):
        wait = PACE_S - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            with urllib.request.urlopen(url, timeout=70) as r:
                raw = r.read()
            body = json.loads(raw)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            if attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            raise SystemExit(json.dumps({"error": f"ECOS {service}: {redact(str(e))}"}))
        if "RESULT" in body:
            code, msg = body["RESULT"].get("CODE", ""), body["RESULT"].get("MESSAGE", "")
            if code in ("ERROR-602", "ERROR-500", "ERROR-600") and attempt < 3:
                time.sleep(10 * (attempt + 1))
                continue
            raise EcosError(code, f"{ERRORS.get(code, '')} ({msg})")
        return body.get(service, {}), raw
    raise SystemExit(json.dumps({"error": f"ECOS {service}: no answer"}))


def call_all(service: str, args: list[str], lang="kr") -> tuple[list[dict], list[bytes]]:
    rows, raws, first = [], [], 1
    while True:
        try:
            payload, raw = call(service, args, lang, first, first + PAGE - 1)
        except EcosError as e:
            if e.code == "INFO-200":
                return rows, raws
            raise
        page = payload.get("row", [])
        rows.extend(page)
        raws.append(raw)
        if not page or len(rows) >= int(payload.get("list_total_count", 0)):
            return rows, raws
        first += PAGE


def out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def fail(e: EcosError):
    sys.exit(json.dumps({"error": e.code, "meaning": redact(e.message)}, ensure_ascii=False))


# ---------------------------------------------------------------- tables, items, index

def table_list(lang="kr", refresh=False) -> list[dict]:
    path = cache_dir() / f"tables.{lang}.json"
    if path.exists() and not refresh and time.time() - path.stat().st_mtime < INDEX_TTL_DAYS * 86400:
        return json.loads(path.read_text(encoding="utf-8"))
    rows, _ = call_all("StatisticTableList", [], lang)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def table_path(code: str, tables: list[dict]) -> str:
    by = {t["STAT_CODE"]: t for t in tables}
    names, t, guard = [], by.get(code), 0
    while t and guard < 10:
        names.append(t["STAT_NAME"])
        t, guard = by.get(t.get("P_STAT_CODE")), guard + 1
    return " > ".join(reversed(names))


def item_list(code: str, lang="kr") -> list[dict]:
    rows, _ = call_all("StatisticItemList", [code], lang)
    return rows


def index_path(lang) -> Path:
    return cache_dir() / f"items.{lang}.jsonl"


def build_index(lang="kr", refresh=False) -> dict:
    path = index_path(lang)
    if path.exists() and not refresh and time.time() - path.stat().st_mtime < INDEX_TTL_DAYS * 86400:
        return {"index": str(path), "status": "fresh", "age_days": round((time.time() - path.stat().st_mtime) / 86400, 1)}
    all_tables = table_list(lang, refresh)
    tables = [t for t in all_tables if t.get("SRCH_YN") == "Y"]
    tmp = path.with_suffix(".tmp")
    n_items, errors = 0, []
    with tmp.open("w", encoding="utf-8") as f:
        for i, t in enumerate(tables, 1):
            try:
                items = item_list(t["STAT_CODE"], lang)
            except EcosError as e:
                errors.append({"table": t["STAT_CODE"], "error": e.code})
                continue
            tpath = table_path(t["STAT_CODE"], all_tables)
            for it in items:
                it["ORG_NAME"] = producer(t)[0]
                it["TABLE_PATH"] = tpath
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
                n_items += 1
            if i % 100 == 0:
                print(f"indexed {i}/{len(tables)} tables", file=sys.stderr)
    tmp.replace(path)
    return {"index": str(path), "status": "built", "tables": len(tables), "items": n_items, "errors": errors[:20]}


BOK_NAMES = ("한국은행", "Bank of Korea", "The Bank of Korea", "BOK")


def producer(table: dict) -> tuple[str, bool]:
    """(clean producer name, is the Bank of Korea). ECOS leaves ORG_NAME empty on the Bank of Korea's own tables
    (265 of 617 searchable ones on 20 Oct 2026, e.g. 722Y001 base rate, 161Y… money) and appends phone numbers to
    other producers ("국가데이터처(☎ 042-481-6943)")."""
    raw = (table.get("ORG_NAME") or "").strip()
    name = re.sub(r"\s*\((?:☎\s*)?[0-9][0-9\-\s]*\)\s*$", "", raw).strip()
    if not name:
        return "한국은행", True
    return name, name in BOK_NAMES


def words_match(text: str, words: list[str]) -> bool:
    text = text.lower()
    return all(w.lower() in text for w in words)


# ---------------------------------------------------------------- dates and values

def to_iso(time_str: str, cycle: str) -> str:
    c = cycle.upper()
    if c == "D":
        return f"{time_str[:4]}-{time_str[4:6]}-{time_str[6:8]}"
    if c == "M":
        return f"{time_str[:4]}-{time_str[4:6]}"
    if c == "Q":
        return f"{time_str[:4]}-Q{time_str[-1]}"
    if c == "S":
        return f"{time_str[:4]}-H{time_str[-1]}"
    if c == "SM":
        return f"{time_str[:4]}-{time_str[4:6]}-S{time_str[-1]}"
    return time_str


def period_end(time_str: str, cycle: str) -> dt.date:
    c = cycle.upper()
    y = int(time_str[:4])
    if c == "D":
        return dt.date(y, int(time_str[4:6]), int(time_str[6:8]))
    if c in ("M", "SM"):
        m = int(time_str[4:6])
        return (dt.date(y + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1))
    if c == "Q":
        q = int(time_str[-1])
        return dt.date(y + (q * 3) // 12, (q * 3) % 12 + 1, 1) - dt.timedelta(days=1)
    if c == "S":
        return dt.date(y, 6, 30) if time_str.endswith("1") else dt.date(y, 12, 31)
    return dt.date(y, 12, 31)


def default_from(cycle: str) -> str:
    return {"A": "1990", "S": "1990S1", "Q": "1990Q1", "M": "199001", "SM": "199001S1", "D": "20000101"}[cycle.upper()]


def default_to(cycle: str) -> str:
    t = dt.date.today()
    return {"A": f"{t.year}", "S": f"{t.year}S2", "Q": f"{t.year}Q4", "M": f"{t.year}12",
            "SM": f"{t.year}12S2", "D": t.strftime("%Y%m%d")}[cycle.upper()]


def to_float(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def series(code: str, cycle: str, start: str, end: str, items: list[str], lang="kr") -> tuple[list[dict], list[bytes]]:
    """StatisticSearch. Unused item positions are sent as '?', as the ECOS specification's sample URL does."""
    cycle = cycle.upper()
    args = [code, cycle, start, end] + list(items) + ["?"] * (4 - len(items))
    if cycle == "D" and int(end[:4]) - int(start[:4]) > 8:
        rows, raws, y = [], [], int(start[:4])     # daily ranges are split by year to avoid ERROR-400
        while y <= int(end[:4]):
            s = start if y == int(start[:4]) else f"{y}0101"
            e = end if y == int(end[:4]) else f"{y}1231"
            r, rw = call_all("StatisticSearch", [code, cycle, s, e] + args[4:], lang)
            rows += r
            raws += rw
            y += 1
        return rows, raws
    return call_all("StatisticSearch", args, lang)


# ---------------------------------------------------------------- validation

def parse_anchor(text: str):
    date, _, rest = text.partition("=")
    value, _, tol = rest.partition(":")
    return date.strip(), float(value), float(tol) if tol else None


def read_csv(path: str) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        return {row[0]: float(row[1]) for row in r if len(row) > 1 and row[1] not in ("", ".")}


def validate(a) -> dict:
    cycle = a.cycle.upper()
    checks = []

    def check(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    tables = table_list(a.lang)
    table = next((t for t in tables if t["STAT_CODE"] == a.table), None)
    if not table:
        check("table", "fail", f"{a.table} is not in StatisticTableList")
        return {"verdict": "fail", "checks": checks}
    check("table", "pass" if table.get("SRCH_YN") == "Y" else "fail",
          f"{a.table}: {table_path(a.table, tables)} (searchable: {table.get('SRCH_YN')})")
    org, bok = producer(table)
    stated = "" if (table.get("ORG_NAME") or "").strip() else " (ECOS leaves the producer empty on its own tables)"
    check("licence", "pass" if bok else "warn",
          f"producer: {org}{stated}. " + ("Bank of Korea statistic: reuse allowed with attribution." if bok else
                                         "Copyright stays with the producer; commercial reuse may need its approval (ECOS terms, art. 5)."))
    items = item_list(a.table, a.lang)
    groups = sorted({it["GRP_CODE"] for it in items})
    picked = []
    for pos, code in enumerate(a.items):
        grp = groups[pos] if pos < len(groups) else None
        match = [it for it in items if it["ITEM_CODE"] == code and it["CYCLE"] == cycle and (grp is None or it["GRP_CODE"] == grp)]
        if not match:
            other = sorted({it["CYCLE"] for it in items if it["ITEM_CODE"] == code})
            check(f"item {pos + 1}", "fail", f"{code} not found in {grp or 'the table'} for cycle {cycle}"
                  + (f"; it exists for cycles {other}" if other else ""))
        else:
            it = match[0]
            picked.append(it)
            parent = f" (under {it['P_ITEM_NAME']})" if it.get("P_ITEM_NAME") else ""
            check(f"item {pos + 1}", "pass", f"{it['GRP_NAME']}: {code} {it['ITEM_NAME']}{parent}, "
                  f"{it['START_TIME']}..{it['END_TIME']}, {it['DATA_CNT']} points, unit {it['UNIT_NAME']}")
    if len(a.items) < len(groups):
        check("all dimensions set", "fail",
              f"the table has {len(groups)} item groups ({', '.join(groups)}) but {len(a.items)} item code(s) were given; "
              "the answer would mix several series")
    unit = (picked[-1]["UNIT_NAME"] if picked else "") or ""
    if a.unit:
        check("unit", "pass" if a.unit.lower() in unit.lower() else "fail", f"expected '{a.unit}', item unit is '{unit}'")
    start = a.from_ or default_from(cycle)
    end = a.to or default_to(cycle)
    try:
        rows, _ = series(a.table, cycle, start, end, a.items, a.lang)
    except EcosError as e:
        check("observations", "fail", f"{e.code}: {e.message}")
        rows = []
    obs = [(r["TIME"], to_float(r.get("DATA_VALUE"))) for r in rows]
    times = [t for t, _ in obs]
    if rows:
        dup = len(times) - len(set(times))
        check("one series", "pass" if dup == 0 else "fail",
              f"{len(times)} rows, {dup} duplicated periods" + ("; set every item group" if dup else ""))
        missing = sum(1 for _, v in obs if v is None)
        check("missing values", "pass" if missing <= len(obs) * 0.02 else "warn", f"{missing} of {len(obs)} values empty")
        if not a.to:
            last = max(t for t, v in obs if v is not None) if any(v is not None for _, v in obs) else None
            if last:
                age = (dt.date.today() - period_end(last, cycle)).days
                limit = a.max_stale_days or STALE_DAYS.get(cycle, 75)
                check("fresh", "pass" if age <= limit else "warn",
                      f"last value {last}, {max(age, 0)} days after its period ended (limit {limit} for cycle {cycle})")
        if a.from_:
            first = min(times)   # a daily series may start on the first business day after the date asked
            ok = first <= a.from_ or (cycle == "D" and (period_end(first, cycle) - period_end(a.from_, cycle)).days <= 7)
            check("coverage", "pass" if ok else "warn", f"asked from {a.from_}, first value {first}")
        vals = [v for _, v in obs if v is not None]
        if a.range and vals:
            lo, hi = (float(x) for x in a.range.split(","))
            bad = [(t, v) for t, v in obs if v is not None and not lo <= v <= hi]
            check("range", "pass" if not bad else "fail", f"values {min(vals):g} to {max(vals):g}; expected {lo:g} to {hi:g}"
                  + (f"; first outside: {bad[0]}" if bad else ""))
        lookup = dict(obs)
        for text in a.anchor or []:
            t, value, tol = parse_anchor(text)
            got = lookup.get(t)
            tol = tol if tol is not None else max(abs(value) * 0.01, 1e-9)
            if got is None:
                check(f"anchor {t}", "fail", f"no value for {t} (use the cycle's format: {CYCLES[cycle]})")
            else:
                check(f"anchor {t}", "pass" if abs(got - value) <= tol else "fail", f"expected {value:g} ± {tol:g}, series has {got:g}")
        if a.compare:
            other = read_csv(a.compare)
            if cycle == "M":   # accept 2026-09 and 2026-09-01 alike
                other = {d[:7]: v for d, v in other.items()}
            iso = {to_iso(t, cycle): v for t, v in obs if v is not None}
            pairs = [(iso[d], other[d]) for d in other if d in iso]
            if not pairs:
                check("compare", "warn", f"no overlapping dates with {a.compare} (dates must be {to_iso(times[0], cycle)}-style)")
            else:
                diffs = [abs(x - y) for x, y in pairs]
                tol = a.compare_tol if a.compare_tol is not None else 0.05
                check("compare", "pass" if max(diffs) <= tol else "warn",
                      f"{len(pairs)} overlapping dates: mean abs diff {sum(diffs) / len(diffs):.4g}, max {max(diffs):.4g} (tolerance {tol:g})")
    else:
        check("observations", "fail", f"no values for {start}..{end}")
    statuses = [c["status"] for c in checks]
    verdict = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {"table": a.table, "table_name": table["STAT_NAME"], "org": org, "cycle": cycle, "items": a.items,
            "item_names": [p["ITEM_NAME"] for p in picked], "unit": unit, "verdict": verdict, "checks": checks,
            "_obs": obs, "_table": table, "_picked": picked}


# ---------------------------------------------------------------- commands

def cmd_tables(a):
    tables = table_list(a.lang, a.refresh)
    rows = [t for t in tables if words_match(t["STAT_NAME"], a.words) and (a.all or t.get("SRCH_YN") == "Y")]
    out({"total": len(tables), "shown": len(rows[:a.limit]),
         "results": [{"code": t["STAT_CODE"], "name": t["STAT_NAME"], "path": table_path(t["STAT_CODE"], tables),
                      "cycle": t.get("CYCLE"), "org": producer(t)[0], "searchable": t.get("SRCH_YN")} for t in rows[:a.limit]]})


def cmd_items(a):
    items = item_list(a.table, a.lang)
    rows = [it for it in items if words_match(" ".join(str(it.get(k) or "") for k in ("ITEM_NAME", "P_ITEM_NAME", "GRP_NAME")), a.words)
            and (not a.cycle or it["CYCLE"] == a.cycle.upper())]
    groups = {}
    for it in items:
        groups.setdefault(it["GRP_CODE"], it["GRP_NAME"])
    out({"table": a.table, "table_name": items[0]["STAT_NAME"] if items else None, "groups": groups,
         "cycles": sorted({it["CYCLE"] for it in items}), "total": len(items), "shown": len(rows[:a.limit]),
         "results": [{"group": it["GRP_CODE"], "item": it["ITEM_CODE"], "name": it["ITEM_NAME"], "parent": it.get("P_ITEM_NAME"),
                      "cycle": it["CYCLE"], "span": f"{it['START_TIME']}..{it['END_TIME']}", "points": it["DATA_CNT"],
                      "unit": it["UNIT_NAME"]} for it in rows[:a.limit]]})


def cmd_index(a):
    out(build_index(a.lang, a.refresh))


def cmd_find(a):
    path = index_path(a.lang)
    if not path.exists():
        out({"error": "no item index yet: run `ecos.py index` once (one call per table, a few minutes), "
                      "or use `tables` and `items`"})
        sys.exit(1)
    hits = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            it = json.loads(line)
            text = " ".join(str(it.get(k) or "") for k in ("TABLE_PATH", "STAT_NAME", "GRP_NAME", "ITEM_NAME", "P_ITEM_NAME"))
            if words_match(text, a.words) and (not a.cycle or it["CYCLE"] == a.cycle.upper()):
                in_item = sum(w.lower() in (it.get("ITEM_NAME") or "").lower() for w in a.words)
                hits.append((-in_item, -int(it.get("DATA_CNT") or 0), it))
    hits.sort(key=lambda h: (h[0], h[1]))
    out({"index_age_days": round((time.time() - path.stat().st_mtime) / 86400, 1), "matches": len(hits),
         "results": [{"table": it["STAT_CODE"], "table_name": it["STAT_NAME"], "group": f"{it['GRP_CODE']} {it['GRP_NAME']}",
                      "item": it["ITEM_CODE"], "name": it["ITEM_NAME"], "parent": it.get("P_ITEM_NAME"), "cycle": it["CYCLE"],
                      "span": f"{it['START_TIME']}..{it['END_TIME']}", "unit": it["UNIT_NAME"],
                      "org": producer({"ORG_NAME": it.get("ORG_NAME")})[0]}
                     for _, _, it in hits[:a.limit]]})


def cmd_keystats(a):
    rows, _ = call_all("KeyStatisticList", [], a.lang)
    rows = [r for r in rows if words_match(f"{r.get('CLASS_NAME')} {r.get('KEYSTAT_NAME')}", a.words)]
    out({"shown": len(rows), "results": [{"group": r.get("CLASS_NAME"), "name": r.get("KEYSTAT_NAME"), "value": r.get("DATA_VALUE"),
                                          "unit": r.get("UNIT_NAME"), "as_of": r.get("CYCLE")} for r in rows]})


def cmd_word(a):
    rows, _ = call_all("StatisticWord", [a.term], a.lang)
    out({"results": [{"word": r.get("WORD"), "definition": r.get("CONTENT")} for r in rows]})


def cmd_meta(a):
    rows, _ = call_all("StatisticMeta", [a.name], a.lang)
    out({"results": [{"level": r.get("LVL"), "name": r.get("CONT_NAME"), "meta": r.get("META_DATA")} for r in rows]})


def cmd_obs(a):
    rows, _ = series(a.table, a.cycle, a.start, a.end, a.items, a.lang)
    shown = rows if a.all else rows[-a.tail:]
    if not rows:
        out({"count": 0, "hint": f"no rows: check that the items exist for cycle {a.cycle.upper()} "
                                  f"(`ecos.py items {a.table}`), that every item group has a code, and that the dates "
                                  f"use the cycle's format ({CYCLES.get(a.cycle.upper(), '?')})"})
        return
    out({"count": len(rows), "unit": rows[0].get("UNIT_NAME") if rows else None,
         "names": [rows[0].get(f"ITEM_NAME{i}") for i in range(1, 5) if rows and rows[0].get(f"ITEM_NAME{i}")],
         "rows": [{"time": r["TIME"], "value": r.get("DATA_VALUE")} for r in shown]})


def cmd_validate(a):
    r = validate(a)
    for k in ("_obs", "_table", "_picked"):
        r.pop(k, None)
    out(r)
    sys.exit(2 if r["verdict"] == "fail" else 0)


def cmd_fetch(a):
    r = validate(a)
    obs, table, picked = r.pop("_obs", []), r.pop("_table", {}), r.pop("_picked", [])
    if r["verdict"] == "fail" and not a.force:
        out({"fetched": False, "reason": "validation failed; fix the choice or pass --force with a reason", **r})
        sys.exit(2)
    cycle = a.cycle.upper()
    start, end = a.from_ or default_from(cycle), a.to or default_to(cycle)
    rows, raws = series(a.table, cycle, start, end, a.items, a.lang)
    base = Path(a.run) / "data" / "ecos" if a.run else Path(a.out)
    (base / "raw").mkdir(parents=True, exist_ok=True)
    raw = b"\n".join(raws)
    sha = hashlib.sha256(raw).hexdigest()
    key = "_".join([a.table, cycle, *a.items])
    (base / "raw" / f"{key}.{sha[:12]}.jsonl").write_bytes(raw)
    (base / "raw" / f"{key}.request.json").write_text(json.dumps(
        {"service": "StatisticSearch", "table": a.table, "cycle": cycle, "from": start, "to": end, "items": a.items,
         "lang": a.lang, "key": "redacted"}, ensure_ascii=False, indent=1), encoding="utf-8")
    did = a.dataset_id or ("ecos-" + "-".join([a.table, *a.items, cycle])).lower()
    obs = [(to_iso(row["TIME"], cycle), to_float(row.get("DATA_VALUE"))) for row in rows]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["date", "value"])
    w.writerows([d, "" if v is None else repr(v)] for d, v in obs)
    (base / f"{did}.csv").write_text(buf.getvalue(), encoding="utf-8")
    org, bok = producer(table)
    names = " > ".join(p["ITEM_NAME"] for p in picked)
    entry = {
        "id": did, "indicator": a.indicator, "provider": "Bank of Korea, ECOS", "source": org,
        "key": f"{a.table}/{cycle}/{'/'.join(a.items)}", "url": "https://ecos.bok.or.kr/",
        "title": f"{table.get('STAT_NAME')}: {names}", "definition": a.definition or f"{table.get('STAT_NAME')}: {names}",
        "geo": a.geo or "KR", "unit": r.get("unit"), "frequency": cycle, "aggregation": None,
        "span": [obs[0][0], obs[-1][0]] if obs else None, "missing": [] if cycle == "D" else [d for d, v in obs if v is None][:200],
        "missing_count": sum(1 for _, v in obs if v is None),
        "retrieved": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sha256": sha,
        "licence": "ECOS Open API terms: reuse allowed with attribution" if bok else
                   f"ECOS Open API terms: copyright held by {org}; commercial reuse may need its approval",
        "attribution": "Source: Bank of Korea, ECOS" if bok else f"Source: {org}, via Bank of Korea ECOS",
        "publishable": bool(bok or a.publishable),
        "file": f"data/ecos/{did}.csv" if a.run else str(base / f"{did}.csv"),
        "validation": {"verdict": r["verdict"], "checks": r["checks"], "forced": bool(a.force and r["verdict"] == "fail")},
    }
    cat_path = base / "catalog.json"
    catalog = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else []
    catalog = [c for c in catalog if c["id"] != did] + [entry]
    tmp = cat_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(cat_path)
    out({"fetched": True, "dataset": did, "file": entry["file"], "observations": len(obs), "span": entry["span"],
         "unit": entry["unit"], "publishable": entry["publishable"], "verdict": r["verdict"],
         "warnings": [c for c in r["checks"] if c["status"] != "pass"]})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lang", default="kr", choices=["kr", "en"], help="names in Korean (default) or English")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("tables", help="search table names (StatisticTableList, cached a week)")
    t.add_argument("words", nargs="*")
    t.add_argument("--all", action="store_true", help="include non-searchable category rows")
    t.add_argument("--refresh", action="store_true")
    t.add_argument("--limit", type=int, default=40)
    t.set_defaults(fn=cmd_tables)

    i = sub.add_parser("items", help="items of one table (StatisticItemList)")
    i.add_argument("table")
    i.add_argument("words", nargs="*")
    i.add_argument("--cycle")
    i.add_argument("--limit", type=int, default=60)
    i.set_defaults(fn=cmd_items)

    x = sub.add_parser("index", help="build the local index of all items (one call per table)")
    x.add_argument("--refresh", action="store_true")
    x.set_defaults(fn=cmd_index)

    f = sub.add_parser("find", help="search the item index by words in table, group and item names")
    f.add_argument("words", nargs="+")
    f.add_argument("--cycle")
    f.add_argument("--limit", type=int, default=30)
    f.set_defaults(fn=cmd_find)

    k = sub.add_parser("keystats", help="the 100 key statistics with latest values")
    k.add_argument("words", nargs="*")
    k.set_defaults(fn=cmd_keystats)

    w = sub.add_parser("word", help="statistics glossary")
    w.add_argument("term")
    w.set_defaults(fn=cmd_word)

    m = sub.add_parser("meta", help="methodology notes (StatisticMeta)")
    m.add_argument("name")
    m.set_defaults(fn=cmd_meta)

    o = sub.add_parser("obs", help="values (StatisticSearch)")
    o.add_argument("table")
    o.add_argument("cycle", help="A, S, Q, M, SM, D")
    o.add_argument("start", help="in the cycle's format: 2020, 2020S1, 2020Q1, 202001, 202001S1, 20200101")
    o.add_argument("end")
    o.add_argument("items", nargs="*", help="item codes, one per item group, in group order")
    o.add_argument("--tail", type=int, default=12)
    o.add_argument("--all", action="store_true")
    o.set_defaults(fn=cmd_obs)

    def checks(c):
        c.add_argument("table")
        c.add_argument("cycle")
        c.add_argument("items", nargs="+", help="item codes, one per item group, in group order")
        c.add_argument("--from", dest="from_", help="start in the cycle's format")
        c.add_argument("--to", help="end in the cycle's format")
        c.add_argument("--unit", help="expected text in the unit, e.g. % or 원")
        c.add_argument("--range", help="lo,hi plausible values (use --range=-5,5 for negatives)")
        c.add_argument("--anchor", action="append", help="TIME=VALUE[:TOL] in the cycle's format; repeatable")
        c.add_argument("--max-stale-days", type=int)
        c.add_argument("--compare", help="CSV (date,value) of the same concept from another source, ISO dates")
        c.add_argument("--compare-tol", type=float)

    v = sub.add_parser("validate", help="check a candidate before using it")
    checks(v)
    v.set_defaults(fn=cmd_validate)

    fe = sub.add_parser("fetch", help="validate, then write CSV, raw response and catalog entry")
    checks(fe)
    fe.add_argument("--run")
    fe.add_argument("--out")
    fe.add_argument("--indicator", required=True)
    fe.add_argument("--dataset-id")
    fe.add_argument("--definition")
    fe.add_argument("--geo")
    fe.add_argument("--publishable", action="store_true", help="the producer's terms were checked and allow publication")
    fe.add_argument("--force", action="store_true")
    fe.set_defaults(fn=cmd_fetch)

    a = p.parse_args()
    if a.cmd == "fetch" and not (a.run or a.out):
        p.error("fetch needs --run or --out")
    try:
        a.fn(a)
    except EcosError as e:
        fail(e)
    except SystemExit:
        raise
    except Exception as e:  # never leak the key in a traceback
        sys.exit(json.dumps({"error": redact(f"{type(e).__name__}: {e}")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
