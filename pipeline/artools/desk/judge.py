"""The judge and the bar.

One judge brief (guides/desk/roles/judge.md) scores every text, a desk note or an institution's article, on the
standard's eight dimensions. `calibrate` scores the benchmark set (/data/articles/desk/benchmarks/: short analytical
pieces from the BIS, central banks, the OECD and research institutes, kept on this machine as a private reference)
and writes scores.json; `bar` reads it. A note passes when no reviewer's blocking issue is left, no dimension is
below the floor, and its mean is at or above the benchmark set's median.

A model's score is noisy, so each text is scored `n` times and the scores are averaged; the spread is kept.
"""
from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..paths import read_json, write_json
from . import roles
from .api import DESK

BENCH = DESK / "benchmarks"
DIMS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8")
NAMES = {"D1": "Finding", "D2": "Consolidation", "D3": "Evidence", "D4": "Reasoning", "D5": "Limits", "D6": "Clarity",
         "D7": "Charts", "D8": "Use"}


def _one(run: Path, article: str) -> dict:
    d = roles.call(run, "judge", "## The article\n\n" + article)["data"]
    s = d.get("scores") or {}
    out = {}
    for k in DIMS:
        v = (s.get(k) or {}).get("score")
        if not isinstance(v, (int, float)) or not 1 <= v <= 5:
            raise roles.RoleError(f"judge: no usable score for {k}")
        out[k] = {"score": float(v), "why": (s.get(k) or {}).get("why")}
    return {"scores": out, "finding": d.get("finding"), "weakest": d.get("weakest"), "to_improve": d.get("to_improve") or []}


def score_text(run: Path, article: str, n: int = 2) -> dict:
    with ThreadPoolExecutor(max_workers=n) as ex:
        res = list(ex.map(lambda _: _one(run, article), range(n)))
    return _combine(res)


def score_note(run: Path, article: str, bar_: dict, cfg: dict) -> dict:
    """A note's score (rule R7): one judge, and a second only when the first is near the bar
    (quality.second_judge.near_bar) or a dimension is near the floor (near_floor); then the two are averaged."""
    q = cfg["quality"]
    n = int(q.get("judges") or 1)
    if n > 1:
        return score_text(run, article, n=n)
    res = [_one(run, article)]
    s = _combine(res)
    sj = q.get("second_judge") or {}
    why = []
    if sj and abs(s["mean"] - bar_["pass_mean"]) <= float(sj.get("near_bar", 0.15)):
        why.append(f"mean {s['mean']:.2f} within {sj.get('near_bar', 0.15)} of the bar {bar_['pass_mean']:.2f}")
    low = [k for k, v in s["dims"].items() if v - bar_["min_dimension"] < float(sj.get("near_floor", 0.25))] if sj else []
    if low:
        why.append(f"{', '.join(low)} within {sj.get('near_floor', 0.25)} of the floor {bar_['min_dimension']}")
    if why:
        res.append(_one(run, article))
        s = _combine(res)
    s["second_judge"] = "; ".join(why) or None
    return s


def _combine(res: list[dict]) -> dict:
    n = len(res)
    dims = {k: round(statistics.fmean(r["scores"][k]["score"] for r in res), 2) for k in DIMS}
    means = [statistics.fmean(r["scores"][k]["score"] for k in DIMS) for r in res]
    return {"dims": dims, "mean": round(statistics.fmean(dims.values()), 3), "judges": n,
            "spread": round(max(means) - min(means), 3) if n > 1 else 0.0,
            "why": {k: [r["scores"][k]["why"] for r in res] for k in DIMS},
            "finding": res[0]["finding"], "weakest": min(dims, key=dims.get),
            "to_improve": [x for r in res for x in r["to_improve"]][:6]}


def blind(path: Path) -> str:
    """A benchmark text as the judge reads it: title and date, the body, then its notes; the outlet, author and URL
    lines of the file's header are left out, so the publisher's name is not on the page (it may still be in the text)."""
    txt = path.read_text(encoding="utf-8")
    head, _, rest = txt.partition("\n\n")
    keep = {k.strip(): v.strip() for k, _, v in (l.partition(":") for l in head.splitlines()) if k.strip() in ("TITLE", "DATE")}
    body, _, notes = rest.partition("\n--- NOTES AND REFERENCES")
    notes = notes.partition("---\n")[2].strip() if notes else ""
    return (f"{keep.get('TITLE', '')}\n\n{keep.get('DATE', '')}\n\n{body.strip()}\n"
            + (f"\nNotes and references\n{notes}\n" if notes else ""))


def calibrate(n: int = 2, only: list[str] | None = None) -> dict:
    """Score the benchmark set. Kept: per piece, per dimension; the summary the bar reads."""
    manifest = read_json(BENCH / "manifest.json", []) or []
    run = BENCH / "judging"
    (run / "logs").mkdir(parents=True, exist_ok=True)
    prev = (read_json(BENCH / "scores.json", {}) or {}).get("pieces", {})
    pieces = dict(prev)
    for m in manifest:
        pid = m["id"]
        if only and pid not in only:
            continue
        pieces[pid] = {**score_text(run, blind(BENCH / f"{pid}.txt"), n), "outlet": m.get("outlet"), "words": m.get("words"),
                       "title": m.get("title")}
        write_json(BENCH / "scores.json", {"pieces": pieces, "summary": _summary(pieces), "cost_usd": roles.spent(run)})
    return read_json(BENCH / "scores.json")


def _summary(pieces: dict) -> dict:
    means = sorted(p["mean"] for p in pieces.values())
    if not means:
        return {}
    q = statistics.quantiles(means, n=4) if len(means) >= 4 else [means[0], statistics.median(means), means[-1]]
    return {"n": len(means), "median": round(statistics.median(means), 3), "q1": round(q[0], 3), "q3": round(q[2], 3),
            "min": means[0], "max": means[-1],
            "dims_median": {k: round(statistics.median(p["dims"][k] for p in pieces.values()), 2) for k in DIMS}}


def bar(cfg: dict) -> dict:
    """The pass mark: a quantile of the benchmark set's means (quality.benchmark: q1 | median | q3; q3 by default, the
    start of its best quarter) plus a margin, never below the configured floor."""
    q = cfg["quality"]
    s = (read_json(BENCH / "scores.json", {}) or {}).get("summary") or {}
    which = q.get("benchmark", "q3")
    ref = s.get(which)
    mark = (ref or 0) + q.get("benchmark_margin", 0.0)
    label = {"q1": "lower quartile", "median": "median", "q3": "upper quartile"}.get(which, which)
    return {"pass_mean": round(max(q["min_overall"], mark), 3), "min_dimension": q["min_dimension"], "benchmark": s or None,
            "from": f"the benchmark set's {label}" if ref and mark >= q["min_overall"] else "configured floor"}


def decide(score: dict, bar_: dict, blocking: list, cfg: dict) -> dict:
    reasons = []
    if blocking:
        reasons.append(f"{len(blocking)} blocking issues left after the last round")
    low = [f"{k} {NAMES[k]} {v}" for k, v in score["dims"].items() if v < bar_["min_dimension"]]
    if low:
        reasons.append("below the floor on " + ", ".join(low))
    if score["mean"] < bar_["pass_mean"]:
        reasons.append(f"mean {score['mean']:.2f} below the bar {bar_['pass_mean']:.2f} ({bar_['from']})")
    bench = (bar_.get("benchmark") or {}).get("dims_median") or {}
    return {"status": "pass" if not reasons else "shelve", "reasons": reasons,
            "against_benchmark": {k: round(score["dims"][k] - bench[k], 2) for k in DIMS} if bench else None}
