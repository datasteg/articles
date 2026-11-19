#!/usr/bin/env python3
"""FRED (Federal Reserve Bank of St. Louis): find, validate and fetch a series for an articles run.

Standard library only. The key is read from FRED_API_KEY (environment, or the first .env file found in
the working folder, articles/ or the repository root) and is never printed: errors are redacted.

  fred.py search "france long-term government bond yield" --freq M          full-text search
  fred.py search --id "IRLTLT01*M156N"                                      series-id pattern search
  fred.py tags "france;interest rate;monthly"                               tag search (FRED's own tags)
  fred.py info IRLTLT01FRM156N                                              metadata, source, licence tags, notes
  fred.py obs IRLTLT01FRM156N --start 2025-01-01                            observations
  fred.py validate IRLTLT01FRM156N --freq M --units percent --range 0,20 --anchor 2011-11-01=3.4:0.3
  fred.py fetch IRLTLT01FRM156N --run /data/articles/runs/<id> --indicator "France 10-year yield" [validate options]

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
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.stlouisfed.org/fred"
PACE_S = 0.6  # FRED allows 120 requests a minute
STALE_DAYS = {"D": 10, "W": 21, "BW": 35, "M": 75, "Q": 200, "SA": 400, "A": 730}
# The search filter wants FRED's long frequency names; "M" silently matches nothing.
FREQ_NAME = {"D": "Daily", "W": "Weekly", "BW": "Biweekly", "M": "Monthly", "Q": "Quarterly",
             "SA": "Semiannual", "A": "Annual"}
# FRED's "cc" tag group says how a series may be reused.
LICENCE = {
    "public domain: citation requested": (True, "public domain, citation requested"),
    "copyrighted: citation required": (True, "copyrighted, citation required"),
    "copyrighted: pre-approval required": (False, "copyrighted, pre-approval required before reuse"),
}

_key = None
_last = 0.0


# ---------------------------------------------------------------- key and HTTP

def api_key() -> str:
    global _key
    if _key:
        return _key
    _key = os.environ.get("FRED_API_KEY") or _from_env_files("FRED_API_KEY")
    if not _key:
        sys.exit(json.dumps({"error": "FRED_API_KEY not found in the environment or in an .env file "
                                      "(articles/.env or the repository root)"}))
    return _key


def _from_env_files(name: str) -> str | None:
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
            if sep and k.strip() == name and v and not v.startswith("#"):
                return v
    return None


def redact(text: str) -> str:
    return text.replace(_key, "***") if _key else text


def get(endpoint: str, **params) -> dict:
    global _last
    params = {k: v for k, v in params.items() if v is not None}
    params.update(api_key=api_key(), file_type="json")
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    for attempt in range(4):
        wait = PACE_S - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read()
            data = json.loads(body)
            data["_raw"] = body
            return data
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            raise SystemExit(json.dumps({"error": f"FRED {endpoint}: HTTP {e.code}", "detail": redact(detail)[:500]}))
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            raise SystemExit(json.dumps({"error": f"FRED {endpoint}: {redact(str(e.reason))}"}))
    raise SystemExit(json.dumps({"error": f"FRED {endpoint}: no answer"}))


def out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


# ---------------------------------------------------------------- lookups

def brief(s: dict) -> dict:
    return {
        "id": s["id"], "title": s["title"], "freq": s.get("frequency_short"), "units": s.get("units"),
        "sa": s.get("seasonal_adjustment_short"), "start": s.get("observation_start"),
        "end": s.get("observation_end"), "updated": (s.get("last_updated") or "")[:10],
        "popularity": s.get("popularity"), "discontinued": "DISCONTINUED" in s["title"].upper(),
    }


def series_meta(sid: str) -> dict:
    data = get("series", series_id=sid)
    if not data.get("seriess"):
        raise SystemExit(json.dumps({"error": f"no FRED series {sid}"}))
    return data["seriess"][0]


def series_tags(sid: str) -> dict:
    tags = get("series/tags", series_id=sid).get("tags", [])
    by = {}
    for t in tags:
        by.setdefault(t["group_id"], []).append(t["name"])
    return by


def licence_of(tags: dict) -> dict:
    for name in tags.get("cc", []):
        if name in LICENCE:
            ok, text = LICENCE[name]
            return {"tag": name, "publishable": ok, "licence": text}
    return {"tag": None, "publishable": None, "licence": "unknown: FRED shows no citation/copyright tag; read the notes"}


def observations(sid: str, start=None, end=None, units=None, frequency=None, aggregation=None) -> tuple[list, bytes]:
    data = get("series/observations", series_id=sid, observation_start=start, observation_end=end,
               units=units, frequency=frequency, aggregation_method=aggregation, limit=100000)
    obs = [(o["date"], None if o["value"] in (".", "") else float(o["value"])) for o in data.get("observations", [])]
    return obs, data["_raw"]


# ---------------------------------------------------------------- validation

def parse_anchor(text: str) -> tuple[str, float, float | None]:
    date, _, rest = text.partition("=")
    value, _, tol = rest.partition(":")
    return date.strip(), float(value), float(tol) if tol else None


def read_csv(path: str) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        rows = csv.reader(f)
        next(rows, None)
        return {r[0]: float(r[1]) for r in rows if len(r) > 1 and r[1] not in ("", ".")}


def validate(sid: str, a) -> dict:
    meta = series_meta(sid)
    tags = series_tags(sid)
    lic = licence_of(tags)
    obs, _ = observations(sid, start=a.start, end=a.end, units=a.transform, frequency=a.to_freq,
                          aggregation=a.aggregation)
    values = [v for _, v in obs if v is not None]
    checks = []

    def check(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    title = meta["title"]
    check("exists", "pass", f"{sid}: {title}")
    check("not discontinued", "fail" if "DISCONTINUED" in title.upper() else "pass",
          f"observations {meta['observation_start']} to {meta['observation_end']}")
    freq = a.to_freq.upper() if a.to_freq else meta.get("frequency_short")
    if a.freq:
        check("frequency", "pass" if freq.upper() == a.freq.upper() else "fail",
              f"expected {a.freq}, series is {freq} ({meta.get('frequency')})")
    if a.units:
        units = meta.get("units", "")
        check("units", "pass" if a.units.lower() in units.lower() else "fail",
              f"expected '{a.units}', series is '{units}'" + (f", transformed by '{a.transform}'" if a.transform else ""))
    if a.sa:
        check("seasonal adjustment", "pass" if a.sa.upper() == meta.get("seasonal_adjustment_short", "").upper() else "fail",
              f"expected {a.sa}, series is {meta.get('seasonal_adjustment_short')}")
    last_date = next((d for d, v in reversed(obs) if v is not None), None)
    if last_date and not a.end:
        age = (dt.date.today() - dt.date.fromisoformat(last_date)).days
        limit = a.max_stale_days or STALE_DAYS.get((freq or "M").upper(), 75)
        check("fresh", "pass" if age <= limit else "warn",
              f"last observation {last_date}, {age} days ago (limit {limit} for frequency {freq})")
    if a.start and obs:
        gap = (dt.date.fromisoformat(obs[0][0]) - dt.date.fromisoformat(a.start)).days
        ok = gap <= 0 or ((freq or "").upper() == "D" and gap <= 7)   # daily data start on a business day
        check("coverage", "pass" if ok else "warn", f"asked from {a.start}, first observation {obs[0][0]}")
    if obs:
        missing = sum(1 for _, v in obs if v is None)
        share = missing / len(obs)
        limit = 0.10 if (freq or "").upper() == "D" else 0.02
        check("missing values", "pass" if share <= limit else "warn",
              f"{missing} of {len(obs)} observations missing ({share:.1%})"
              + ("; daily series miss market holidays" if (freq or "").upper() == "D" else ""))
    else:
        check("observations", "fail", "no observations in the requested window")
    if a.range and values:
        lo, hi = (float(x) for x in a.range.split(","))
        bad = [(d, v) for d, v in obs if v is not None and not lo <= v <= hi]
        check("range", "pass" if not bad else "fail",
              f"values {min(values):g} to {max(values):g}; expected {lo:g} to {hi:g}" + (f"; first outside: {bad[0]}" if bad else ""))
    lookup = dict(obs)
    for text in a.anchor or []:
        date, value, tol = parse_anchor(text)
        got = lookup.get(date)
        tol = tol if tol is not None else max(abs(value) * 0.01, 1e-9)
        if got is None:
            check(f"anchor {date}", "fail", f"no observation on {date} (FRED dates are period starts: 2026-09-01 for Sep 2026)")
        else:
            check(f"anchor {date}", "pass" if abs(got - value) <= tol else "fail",
                  f"expected {value:g} ± {tol:g}, series has {got:g}")
    if a.compare:
        # accept 2026-09 for 2026-09-01: FRED dates monthly and quarterly data by the first day of the period
        other = {(d + "-01" if len(d) == 7 else d): v for d, v in read_csv(a.compare).items()}
        pairs = [(lookup[d], other[d]) for d in other if lookup.get(d) is not None]
        if not pairs:
            check("compare", "warn", f"no overlapping dates with {a.compare}")
        else:
            diffs = [abs(x - y) for x, y in pairs]
            tol = a.compare_tol if a.compare_tol is not None else 0.05
            check("compare", "pass" if max(diffs) <= tol else "warn",
                  f"{len(pairs)} overlapping dates with {a.compare}: mean abs diff {sum(diffs)/len(diffs):.4g}, "
                  f"max {max(diffs):.4g} (tolerance {tol:g})")
    if lic["publishable"] is False:
        check("licence", "warn", f"{lic['tag']}: usable for analysis, not for publication without permission")
    elif lic["publishable"] is None:
        check("licence", "warn", lic["licence"])
    else:
        check("licence", "pass", lic["tag"])
    statuses = [c["status"] for c in checks]
    verdict = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    return {"series": brief(meta), "source": tags.get("src", []), "geo": tags.get("geo", []), "licence": lic,
            "notes": (meta.get("notes") or "")[:800], "verdict": verdict, "checks": checks,
            "_meta": meta, "_tags": tags}


# ---------------------------------------------------------------- commands

def cmd_search(a):
    if a.id:
        data = get("series/search", search_text=a.id, search_type="series_id", limit=a.limit,
                   order_by="popularity", sort_order="desc")
    else:
        if not a.text:
            raise SystemExit(json.dumps({"error": "give search text, or --id with a series-id pattern"}))
        data = get("series/search", search_text=" ".join(a.text), search_type="full_text", limit=a.limit,
                   order_by=a.order, sort_order="desc",
                   filter_variable="frequency" if a.freq else None,
                   filter_value=FREQ_NAME.get(a.freq.upper(), a.freq) if a.freq else None)
    rows = [brief(s) for s in data.get("seriess", [])]
    if not a.include_discontinued:
        rows = [r for r in rows if not r["discontinued"]]
    if a.units:
        rows = [r for r in rows if a.units.lower() in (r["units"] or "").lower()]
    out({"total": data.get("count"), "shown": len(rows), "results": rows})


def cmd_tags(a):
    data = get("tags/series", tag_names=a.tags, limit=a.limit, order_by="popularity", sort_order="desc")
    rows = [brief(s) for s in data.get("seriess", [])]
    if a.freq:
        rows = [r for r in rows if (r["freq"] or "").upper() == a.freq.upper()]
    out({"total": data.get("count"), "shown": len(rows), "results": rows})


def cmd_info(a):
    meta = series_meta(a.id)
    tags = series_tags(a.id)
    rel = get("series/release", series_id=a.id).get("releases", [{}])
    out({"series": brief(meta), "units_short": meta.get("units_short"), "release": rel[0].get("name") if rel else None,
         "release_link": rel[0].get("link") if rel else None, "source": tags.get("src", []), "geo": tags.get("geo", []),
         "licence": licence_of(tags), "tags": tags, "notes": meta.get("notes"),
         "url": f"https://fred.stlouisfed.org/series/{meta['id']}"})


def cmd_obs(a):
    obs, _ = observations(a.id, start=a.start, end=a.end, units=a.transform, frequency=a.to_freq, aggregation=a.aggregation)
    rows = obs if a.all else obs[-a.tail:]
    out({"id": a.id, "count": len(obs), "first": obs[0] if obs else None, "last": obs[-1] if obs else None,
         "rows": [{"date": d, "value": v} for d, v in rows]})


def cmd_validate(a):
    r = validate(a.id, a)
    r.pop("_meta"), r.pop("_tags")
    out(r)
    sys.exit(2 if r["verdict"] == "fail" else 0)


def cmd_fetch(a):
    r = validate(a.id, a)
    meta, tags = r.pop("_meta"), r.pop("_tags")
    if r["verdict"] == "fail" and not a.force:
        out({"fetched": False, "reason": "validation failed; fix the choice or pass --force with a reason", **r})
        sys.exit(2)
    obs, raw = observations(a.id, start=a.start, end=a.end, units=a.transform, frequency=a.to_freq, aggregation=a.aggregation)
    base = Path(a.run) / "data" / "fred" if a.run else Path(a.out)
    (base / "raw").mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(raw).hexdigest()
    (base / "raw" / f"{a.id}.{sha[:12]}.json").write_bytes(raw)
    (base / "raw" / f"{a.id}.meta.json").write_text(json.dumps({"series": meta, "tags": tags}, ensure_ascii=False, indent=1))
    did = a.dataset_id or f"fred-{a.id.lower()}"
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["date", "value"])
    w.writerows([d, "" if v is None else repr(v)] for d, v in obs)
    (base / f"{did}.csv").write_text(buf.getvalue(), encoding="utf-8")
    lic = r["licence"]
    src = ", ".join(tags.get("src", [])) or "FRED"
    entry = {
        "id": did, "indicator": a.indicator, "provider": "FRED, Federal Reserve Bank of St. Louis", "source": src,
        "key": a.id, "url": f"https://fred.stlouisfed.org/series/{a.id}", "title": meta["title"],
        "definition": a.definition or meta["title"], "geo": a.geo or ", ".join(tags.get("geo", [])),
        "unit": meta.get("units") + (f" ({a.transform})" if a.transform else ""),
        "frequency": (a.to_freq or meta.get("frequency_short")).upper(),
        "aggregation": a.aggregation if a.to_freq else None, "seasonal_adjustment": meta.get("seasonal_adjustment_short"),
        "span": [obs[0][0], obs[-1][0]] if obs else None, "missing": [] if (a.to_freq or meta.get("frequency_short", "")).upper() in ("D", "W") else [d for d, v in obs if v is None][:200],
        "missing_count": sum(1 for _, v in obs if v is None),
        "retrieved": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sha256": sha,
        "last_updated": meta.get("last_updated"), "licence": lic["licence"],
        "attribution": f"Source: {src}, via FRED, Federal Reserve Bank of St. Louis",
        "publishable": bool(lic["publishable"]), "file": f"data/fred/{did}.csv" if a.run else str(base / f"{did}.csv"),
        "validation": {"verdict": r["verdict"], "checks": r["checks"], "forced": bool(a.force and r["verdict"] == "fail")},
    }
    cat_path = base / "catalog.json"
    catalog = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else []
    catalog = [c for c in catalog if c["id"] != did] + [entry]
    tmp = cat_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(cat_path)
    out({"fetched": True, "dataset": entry["id"], "file": entry["file"], "observations": len(obs),
         "span": entry["span"], "publishable": entry["publishable"], "verdict": r["verdict"],
         "warnings": [c for c in r["checks"] if c["status"] != "pass"]})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="full-text or series-id search")
    s.add_argument("text", nargs="*")
    s.add_argument("--id", help="series-id pattern, * as wildcard (IRLTLT01*M156N)")
    s.add_argument("--freq", help="D, W, BW, M, Q, SA, A")
    s.add_argument("--units", help="keep results whose units contain this text")
    s.add_argument("--order", default="search_rank", choices=["search_rank", "popularity"])
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--include-discontinued", action="store_true")
    s.set_defaults(fn=cmd_search)

    t = sub.add_parser("tags", help="series carrying all the given FRED tags, ';'-separated")
    t.add_argument("tags")
    t.add_argument("--freq")
    t.add_argument("--limit", type=int, default=25)
    t.set_defaults(fn=cmd_tags)

    i = sub.add_parser("info", help="metadata, release, source, licence tags, notes")
    i.add_argument("id")
    i.set_defaults(fn=cmd_info)

    def window(x):
        x.add_argument("--start", help="YYYY-MM-DD")
        x.add_argument("--end", help="YYYY-MM-DD")
        x.add_argument("--transform", help="FRED units transform: lin, chg, ch1, pch, pc1, pca, cch, cca, log")
        x.add_argument("--to-freq", help="aggregate to a lower frequency: w, m, q, a")
        x.add_argument("--aggregation", choices=["avg", "sum", "eop"], help="with --to-freq")

    o = sub.add_parser("obs", help="observations")
    o.add_argument("id")
    window(o)
    o.add_argument("--tail", type=int, default=12)
    o.add_argument("--all", action="store_true")
    o.set_defaults(fn=cmd_obs)

    def checks(x):
        x.add_argument("id")
        window(x)
        x.add_argument("--freq", help="expected frequency (D, W, M, Q, A)")
        x.add_argument("--units", help="expected text in units, e.g. percent")
        x.add_argument("--sa", help="expected seasonal adjustment: SA, NSA, SAAR")
        x.add_argument("--range", help="lo,hi plausible values")
        x.add_argument("--anchor", action="append", help="DATE=VALUE[:TOL], a known published value; repeatable")
        x.add_argument("--max-stale-days", type=int)
        x.add_argument("--compare", help="CSV (date,value) of the same concept from another source")
        x.add_argument("--compare-tol", type=float)

    v = sub.add_parser("validate", help="check a candidate before using it")
    checks(v)
    v.set_defaults(fn=cmd_validate)

    f = sub.add_parser("fetch", help="validate, then write CSV, raw response and catalog entry")
    checks(f)
    f.add_argument("--run", help="run folder; writes data/fred/ inside it")
    f.add_argument("--out", help="folder to write to when there is no run")
    f.add_argument("--indicator", required=True, help="what the series measures, in plain words")
    f.add_argument("--dataset-id")
    f.add_argument("--definition")
    f.add_argument("--geo")
    f.add_argument("--force", action="store_true", help="fetch despite a failed validation (record why)")
    f.set_defaults(fn=cmd_fetch)

    a = p.parse_args()
    if a.cmd == "fetch" and not (a.run or a.out):
        p.error("fetch needs --run or --out")
    try:
        a.fn(a)
    except SystemExit:
        raise
    except Exception as e:  # never leak the key in a traceback
        sys.exit(json.dumps({"error": redact(f"{type(e).__name__}: {e}")}))


if __name__ == "__main__":
    main()
