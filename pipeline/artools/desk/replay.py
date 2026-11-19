"""Replay and compare.

`replay` runs the refined pipeline's review stages on a stored run's draft without writing anything into that run:
the text lints (with the run's claim ledger when it has one), the inference test on the English and on the Korean
surface, and the Korean code checks on the stored Korean. Its model calls are logged in a work folder of their own
(/data/articles/desk/replay/<run>-<time>/), so a note under the editor's review is never touched. `--against` matches
the old note's conclusions against another run's claims (the regenerated note's), which is how WP-G asks whether the
old note misled.

`compare` sets an old note beside the note that regenerates it: title, dek, key numbers, every chart headline in both
languages, the sentences that said "group median" or "the group", what a skimming reader takes from each, the claims
and the cost by stage. The new run keeps it as desk/compared.json, which the admin page shows as "Compared with …".
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ..paths import RUNS, read_json, write_json
from . import claims as claims_mod, facts as facts_mod, inference as inference_mod, korean, review, roles, text
from .api import DESK

REPLAY = DESK / "replay"
GROUPISH = re.compile(r"\bgroup(?:'s)? (?:median|mean|average)\b|\bthe group\b|\bthe rest\b|\bthe other economies\b", re.I)


def _load(run: Path) -> tuple[dict, dict, dict, list[dict], dict]:
    draft = read_json(run / "draft" / "en.json", {}) or {}
    charts = {p.stem: read_json(p) for p in sorted((run / "charts").glob("*.json"))}
    fmap = {f["id"]: f for f in facts_mod.load(run)}
    return draft, charts, fmap, claims_mod.load(run), claims_mod.load_map(run)


def korean_checks(run: Path) -> list[dict]:
    """The desk's code checks (comparison kept, service names, dates, numbers) on the stored Korean of the surface strings."""
    led = {s["id"]: s for s in (read_json(run / "desk" / "korean.json", {}) or {}).get("strings") or []}
    items, _ = korean.strings(run)
    out = []
    for it in items:
        st = led.get(it["id"]) or {}
        ko = st.get("ko") or st.get("shown")
        if not ko or not (it["id"] in ("d:title", "d:dek") or it["id"].startswith(("d:keyNumbers/", "d:findings/")) or it["id"].endswith(":headline")):
            continue
        if "compare" not in it:
            it["compare"] = {"numbers": []}       # no ledger: the comparison marker is still checked where the English compares
        p = korean.problems(it, ko, it["sent"])
        if p:
            out.append({"id": it["id"], "en": it["sent"], "ko": ko, "problems": p})
    return out


def replay(run_id: str, against: str | None = None, model: bool = True) -> dict:
    run = RUNS / run_id
    if not (run / "draft" / "en.json").is_file():
        raise SystemExit(f"{run_id}: no draft to replay")
    work = REPLAY / f"{run_id}-{dt.datetime.now():%Y%m%dT%H%M%S}"
    (work / "logs").mkdir(parents=True, exist_ok=True)
    draft, charts, fmap, claims, cmap = _load(run)
    out = {"run": run_id, "work": str(work), "claims": len(claims), "lints": review.claim_lints(draft, charts, claims, cmap, fmap),
           "korean_checks": korean_checks(run)}
    if model:
        en = inference_mod.run_test(work, draft, charts, fmap, claims, cmap)
        ko_surf = inference_mod.korean_surface(run, fmap)
        ko = inference_mod.run_test(work, {}, {}, fmap, claims, cmap, lang="ko", surf=ko_surf) if ko_surf else None
        if against:
            other = RUNS / against
            ofmap = {f["id"]: f for f in facts_mod.load(other)}
            oclaims = claims_mod.load(other)
            for res in [r for r in (en, ko) if r]:
                todo = res["conclusions"]
                ans = roles.call(work, "inference", inference_mod._match_packet(todo, oclaims, ofmap))["data"] or {}
                by = {int(a.get("n")): a for a in ans.get("matches") or [] if str(a.get("n") or "").isdigit()}
                for n, x in enumerate(todo, 1):
                    a = by.get(n) or {}
                    x["against"] = {"run": against, "verdict": a.get("verdict"), "claim": a.get("claim"), "why": a.get("why")}
        out["inference"] = {"en": en, "ko": ko}
    out["cost_usd"] = roles.spent(work, korean=True)
    write_json(work / "replay.json", out)
    return out


def _view(run: Path) -> dict:
    draft, charts, fmap, claims, cmap = _load(run)
    ko = read_json(run / "draft" / "ko.json", {}) or {}
    P = lambda s, lang="en": text._plain(s or "", fmap, lang=lang)    # noqa: E731
    placed = [b.get("chart") for s in draft.get("sections", []) for b in s.get("blocks", []) if b.get("type") == "figure"]
    groupish = []
    for p, v in _walk(draft):
        if isinstance(v, str) and p and p[0] not in ("reproduce", "citations") and GROUPISH.search(v):
            groupish.append({"where": ".".join(map(str, p)), "text": P(v)})
    for cid, ch in charts.items():
        for k in ("headline", "subtitle", "title"):
            t = text._tx(ch.get(k))
            if t and GROUPISH.search(t):
                groupish.append({"where": f"figure:{cid}.{k}", "text": t})
    from ..usage import usage
    u = usage(run)
    by_stage = {k: round(v["cost_usd"], 2) for k, v in u["stages"].items()}
    return {
        "run": run.name, "title": {"en": P(draft.get("title")), "ko": P(ko.get("title"), "ko") or None},
        "dek": {"en": P(draft.get("dek")), "ko": P(ko.get("dek"), "ko") or None},
        "keyNumbers": [{"en": f"{P(k.get('value'))} — {P(k.get('label'))}",
                        "ko": (f"{P(k2.get('value'), 'ko')} — {P(k2.get('label'), 'ko')}" if (k2 := (ko.get("keyNumbers") or [{}] * 9)[i] if i < len(ko.get("keyNumbers") or []) else None) else None)}
                       for i, k in enumerate(draft.get("keyNumbers") or [])],
        "charts": [{"id": cid, "en": text._tx((charts.get(cid) or {}).get("headline")), "ko": text._tx((charts.get(cid) or {}).get("headline"), "ko") or None}
                   for cid in placed if cid in charts],
        "groupish": groupish,
        "claims": [claims_mod.render(c, fmap, ids=False) for c in claims],
        "cost": {"english_usd": round(roles.spent(run), 2), "korean_usd": round(roles.spent(run, korean=True) - roles.spent(run), 2),
                 "by_stage": by_stage},
    }


def _walk(x, p=()):
    from .queue import _walk as w
    yield from w(x, p)


def compare(old_id: str, new_id: str, old_replay: dict | None = None) -> dict:
    """The old note beside the new; written to the new run's desk/compared.json (the admin card) and returned."""
    old, new = RUNS / old_id, RUNS / new_id
    a, b = _view(old), _view(new)
    inf_new = read_json(new / "desk" / "inference.json", {}) or {}
    pick = lambda r: [{k: x.get(k) for k in ("says", "verdict", "why")} | ({"against": x["against"]} if x.get("against") else {})  # noqa: E731
                      for x in (r or {}).get("conclusions") or []]
    out = {"old": old_id, "new": new_id, "at": dt.datetime.now().isoformat(timespec="seconds"),
           "data_moved": _data_moved(old, new),
           "rows": {"old": a, "new": b},
           "inference": {"old": {"en": pick(((old_replay or {}).get("inference") or {}).get("en")),
                                 "ko": pick(((old_replay or {}).get("inference") or {}).get("ko"))},
                         "new": {"en": pick(inf_new.get("en")), "ko": pick(inf_new.get("ko"))}}}
    write_json(new / "desk" / "compared.json", out)
    return out


def _data_moved(old: Path, new: Path) -> list[str]:
    """What moved in the views between the two runs (a new quarter, a new release), from their watch snapshots."""
    a = ((read_json(old / "desk" / "watch.json", {}) or {}).get("snapshot") or {})
    b = ((read_json(new / "desk" / "watch.json", {}) or {}).get("snapshot") or {})
    out = []
    for k in sorted(set(a.get("apps") or {}) | set(b.get("apps") or {})):
        ra, rb = (a.get("apps") or {}).get(k), (b.get("apps") or {}).get(k)
        if ra != rb:
            out.append(f"{k}: release {ra} → {rb}")
    for k in sorted(set(a.get("periods") or {}) | set(b.get("periods") or {})):
        pa, pb = (a.get("periods") or {}).get(k), (b.get("periods") or {}).get(k)
        if pa != pb:
            out.append(f"{k}: period {pa} → {pb}")
    return out


def cost_estimate(run: Path) -> dict:
    """What a stored note's English would cost through the refined stages (WP-F's cost test): its own logged cost per
    stage, the analyst +30% (the claim ledger), the checker +25% (the ledger in its packet), the reader dropped, one judge
    instead of two, and the inference test at its logged cost or USD 0.30."""
    from ..usage import usage
    st = {k: v["cost_usd"] for k, v in usage(run)["stages"].items() if not k.startswith("desk-korean")}
    est = dict(st)
    est.pop("desk-reader", None)
    if "desk-analyst" in est:
        est["desk-analyst"] *= 1.3
    if "desk-checker" in est:
        est["desk-checker"] *= 1.25
    if "desk-judge" in est and ((read_json(run / "desk" / "score.json", {}) or {}).get("score") or {}).get("judges", 2) >= 2:
        est["desk-judge"] /= 2
    est.setdefault("desk-inference", 0.30)
    return {"by_stage": {k: round(v, 3) for k, v in est.items()}, "total": round(sum(est.values()), 2),
            "was": round(sum(st.values()), 2)}
