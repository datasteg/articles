"""Series from public providers without a key (ECB Data Portal, Eurostat), pass-through to the FRED and ECOS
skills' own scripts, and read-only SQL over a run's CSVs."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .paths import SKILLS, die, read_json, run_dir, write_json

UA = "datasteg-articles/0.1 (+https://datasteg.com)"
STALE_DAYS = {"D": 10, "W": 21, "M": 75, "Q": 200, "A": 730}
LICENCE = {
    "ecb": ("ECB: reuse with attribution (ECB statistics reuse policy)", "Source: ECB Data Portal", True),
    "eurostat": ("Eurostat: CC BY 4.0", "Source: Eurostat", True),
}
EUROSTAT_GEO = {"EL": "GR", "UK": "GB"}


def _get(url: str) -> bytes:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            if attempt == 3:
                die(f"fetch failed: {type(e).__name__}: {e}", url=url)
            time.sleep(2 ** attempt * 2)
    raise RuntimeError


def _base(run: str, provider: str, scout: bool) -> Path:
    r = run_dir(run)
    base = (r / "scout" / "data" / provider) if scout else (r / "data" / provider)
    (base / "raw").mkdir(parents=True, exist_ok=True)
    return base


def _catalog_put(base: Path, entry: dict) -> None:
    cat = read_json(base / "catalog.json", [])
    cat = [c for c in cat if c["id"] != entry["id"]] + [entry]
    write_json(base / "catalog.json", cat)


def _write_csv(path: Path, rows: list[tuple[str, float | None]]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["date", "value"])
    w.writerows([d, "" if v is None else repr(v)] for d, v in rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _checks(rows, freq: str, start: str | None, rng: str | None, anchors: list[str] | None) -> list[dict]:
    checks = []
    vals = [v for _, v in rows if v is not None]
    if not rows:
        return [{"check": "observations", "status": "fail", "detail": "no observations"}]
    last = max(d for d, v in rows if v is not None)
    # period end of the last observation
    y = int(last[:4])
    if freq == "A":
        end = dt.date(y, 12, 31)
    elif freq == "Q":
        qn = int(last[-1])
        end = dt.date(y + (qn * 3) // 12, (qn * 3) % 12 + 1, 1) - dt.timedelta(days=1)
    elif freq == "M":
        m = int(last[5:7])
        end = dt.date(y + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1)
    else:
        end = dt.date.fromisoformat(last[:10])
    age = (dt.date.today() - end).days
    lim = STALE_DAYS.get(freq, 75)
    checks.append({"check": "fresh", "status": "pass" if age <= lim else "warn",
                   "detail": f"last observation {last}, {max(age, 0)} days after its period ended (limit {lim})"})
    if start:
        checks.append({"check": "coverage", "status": "pass" if rows[0][0] <= start else "warn",
                       "detail": f"asked from {start}, first {rows[0][0]}"})
    miss = sum(1 for _, v in rows if v is None)
    checks.append({"check": "missing values", "status": "pass" if miss <= max(1, len(rows) * 0.02) else "warn",
                   "detail": f"{miss} of {len(rows)} empty"})
    if rng and vals:
        lo, hi = (float(x) for x in rng.split(","))
        bad = [(d, v) for d, v in rows if v is not None and not lo <= v <= hi]
        checks.append({"check": "range", "status": "fail" if bad else "pass",
                       "detail": f"values {min(vals):g} to {max(vals):g}; expected {lo:g} to {hi:g}"})
    look = dict(rows)
    for a in anchors or []:
        d, _, rest = a.partition("=")
        val, _, tol = rest.partition(":")
        got, val = look.get(d), float(val)
        tol = float(tol) if tol else abs(val) * 0.01
        checks.append({"check": f"anchor {d}", "status": "fail" if got is None or abs(got - val) > tol else "pass",
                       "detail": f"expected {val:g} ± {tol:g}, series has {got}"})
    return checks


def _verdict(checks):
    s = [c["status"] for c in checks]
    return "fail" if "fail" in s else "warn" if "warn" in s else "pass"


def ecb_get(key: str, run: str, indicator: str, start: str | None = None, dataset_id: str | None = None,
            scout: bool = False, rng: str | None = None, anchors: list[str] | None = None, geo: str | None = None) -> dict:
    flow, _, series = key.partition(".")
    params = {"format": "csvdata"}
    if start:
        params["startPeriod"] = start
    url = f"https://data-api.ecb.europa.eu/service/data/{flow}/{series}?{urllib.parse.urlencode(params)}"
    raw = _get(url)
    rows_in = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    if not rows_in:
        die(f"ECB returned no rows for {key}")
    first = rows_in[0]
    freq = first.get("FREQ", "M")
    rows = [(r["TIME_PERIOD"], float(r["OBS_VALUE"]) if r.get("OBS_VALUE") else None) for r in rows_in]
    if freq == "M":   # fill the calendar so gaps are explicit
        have = dict(rows)
        y, m = int(rows[0][0][:4]), int(rows[0][0][5:7])
        ly, lm = int(rows[-1][0][:4]), int(rows[-1][0][5:7])
        rows = []
        while (y, m) <= (ly, lm):
            k = f"{y}-{m:02d}"
            rows.append((k, have.get(k)))
            m += 1
            if m == 13:
                y, m = y + 1, 1
    base = _base(run, "ecb", scout)
    sha = hashlib.sha256(raw).hexdigest()
    (base / "raw" / f"{key}.{sha[:12]}.csv").write_bytes(raw)
    did = dataset_id or "ecb-" + key.lower().replace(".", "-")
    _write_csv(base / f"{did}.csv", rows)
    checks = _checks(rows, freq, start, rng, anchors)
    lic, attr, pub = LICENCE["ecb"]
    unit = {"PC": "% per year" if "interest" in first.get("TITLE", "").lower() else "%"}.get(first.get("UNIT", ""), first.get("UNIT"))
    entry = {
        "id": did, "indicator": indicator, "provider": "ECB Data Portal", "source": first.get("SOURCE_AGENCY") or "ECB",
        "key": key, "url": f"https://data.ecb.europa.eu/data/datasets/{flow}/{key}",
        "title": first.get("TITLE"), "definition": first.get("TITLE_COMPL") or first.get("TITLE"),
        "geo": geo or first.get("REF_AREA"), "unit": unit, "frequency": freq,
        "aggregation": "monthly average" if flow == "IRS" else None,
        "span": [rows[0][0], rows[-1][0]], "missing": [d for d, v in rows if v is None],
        "missing_count": sum(1 for _, v in rows if v is None),
        "retrieved": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sha256": sha,
        "licence": lic, "attribution": attr, "publishable": pub,
        "file": str((base / f"{did}.csv").relative_to(run_dir(run))),
        "validation": {"verdict": _verdict(checks), "checks": checks, "forced": False},
    }
    _catalog_put(base, entry)
    return {"fetched": True, "dataset": did, "observations": len(rows), "span": entry["span"],
            "last": next((f"{d}={v}" for d, v in reversed(rows) if v is not None), None),
            "verdict": entry["validation"]["verdict"], "warnings": [c for c in checks if c["status"] != "pass"]}


def eurostat_get(dataset: str, params: str, geos: list[str], run: str, indicator: str, id_prefix: str,
                 scout: bool = False, since: str | None = None, rng: str | None = None) -> dict:
    q = urllib.parse.parse_qsl(params) + [("format", "JSON")] + [("geo", g) for g in geos]
    if since:
        q.append(("sinceTimePeriod", since))
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?{urllib.parse.urlencode(q)}"
    raw = _get(url)
    j = json.loads(raw)
    dims, sizes = j["id"], j["size"]
    stride = [1] * len(sizes)
    for k in range(len(sizes) - 2, -1, -1):
        stride[k] = stride[k + 1] * sizes[k + 1]
    cat = {d: j["dimension"][d]["category"]["index"] for d in dims}
    labels = {d: j["dimension"][d]["category"].get("label", {}) for d in dims}
    gi, ti = dims.index("geo"), dims.index("time")
    times = sorted(cat["time"].items(), key=lambda kv: kv[1])
    base = _base(run, "eurostat", scout)
    sha = hashlib.sha256(raw).hexdigest()
    (base / "raw" / f"{dataset}.{sha[:12]}.json").write_bytes(raw)
    lic, attr, pub = LICENCE["eurostat"]
    results = []
    unit_label = "; ".join(v for d in dims if d not in ("geo", "time", "freq") for v in labels[d].values())
    for g, gx in cat["geo"].items():
        rows = []
        for t, tx in times:
            ix = gx * stride[gi] + tx * stride[ti]
            v = j["value"].get(str(ix))
            rows.append((t, float(v) if v is not None else None))
        code = EUROSTAT_GEO.get(g, g)
        did = f"{id_prefix}-{code.lower()}"
        _write_csv(base / f"{did}.csv", rows)
        freq = "A" if all(len(t) == 4 for t, _ in times) else "Q" if any("Q" in t for t, _ in times) else "M"
        checks = _checks([r for r in rows if r[1] is not None] or rows, freq, None, rng, None)
        entry = {
            "id": did, "indicator": indicator, "provider": "Eurostat", "source": "Eurostat", "key": f"{dataset}?{params}&geo={g}",
            "url": f"https://ec.europa.eu/eurostat/databrowser/view/{dataset}/default/table",
            "title": j.get("label"), "definition": unit_label, "geo": code, "unit": unit_label.split(";")[0],
            "frequency": freq, "aggregation": None, "span": [times[0][0], times[-1][0]],
            "missing": [t for t, v in rows if v is None], "missing_count": sum(1 for _, v in rows if v is None),
            "retrieved": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated": j.get("updated"), "sha256": sha, "licence": lic, "attribution": attr, "publishable": pub,
            "file": str((base / f"{did}.csv").relative_to(run_dir(run))),
            "validation": {"verdict": _verdict(checks), "checks": checks, "forced": False},
        }
        _catalog_put(base, entry)
        last = next(((t, v) for t, v in reversed(rows) if v is not None), None)
        results.append({"dataset": did, "geo": code, "last": last, "verdict": entry["validation"]["verdict"]})
    return {"fetched": True, "dataset": dataset, "updated": j.get("updated"), "series": results}


def passthrough(provider: str, args: list[str]) -> int:
    script = {"fred": SKILLS / "fetch-fred" / "scripts" / "fred.py", "ecos": SKILLS / "fetch-ecos" / "scripts" / "ecos.py"}[provider]
    return subprocess.call([sys.executable, str(script), *args])


def load_run_tables(run: str) -> tuple[sqlite3.Connection, list[str]]:
    r = run_dir(run)
    db = sqlite3.connect(":memory:")
    names = []
    for p in sorted(list((r / "data").rglob("*.csv")) + list((r / "scout" / "data").rglob("*.csv"))):
        if "raw" in p.parts:
            continue
        name = ("scout_" if "scout" in p.parts else "") + p.stem.replace("-", "_").replace(".", "_")
        with p.open(encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if not rows:
            continue
        cols = [c.replace("-", "_") for c in rows[0]]
        db.execute(f'create table "{name}" ({", ".join(chr(34) + c + chr(34) for c in cols)})')
        conv = [[(float(x) if x not in ("",) and _isnum(x) else (None if x == "" else x)) for x in row] for row in rows[1:]]
        db.executemany(f'insert into "{name}" values ({",".join("?" * len(cols))})', conv)
        names.append(name)
    return db, names


def _isnum(x: str) -> bool:
    try:
        float(x)
        return True
    except ValueError:
        return False


def query(run: str, sql: str | None, limit: int = 200) -> dict:
    db, names = load_run_tables(run)
    if not sql:
        return {"tables": names}
    if not sql.lstrip().lower().startswith(("select", "with")):
        die("read-only: SELECT or WITH only")
    cur = db.execute(sql)
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchmany(limit)]
    return {"columns": cols, "rows": rows, "shown": len(rows)}
