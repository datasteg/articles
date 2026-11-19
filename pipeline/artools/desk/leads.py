"""Leads: readings of the panel that no single datasteg page shows, found by code, ranked, and remembered.

A lead is a claim the data supports today, with the numbers behind it and the tables a note would need. Every screen
here joins a funding measure (money-flow: BIS, IMF) with a trade measure (trade-flow: UN Comtrade), because that
join is what the desk adds: each app's own pages already show its own ranking. The screens are deliberately plain
statistics (counts, quartiles, rank correlations, changes): the editor role decides whether a lead is a story, and
the note's facts are recomputed from the tables, never copied from here.

Novelty is kept in /data/articles/desk/ledger.jsonl: a lead used for a note is not offered again for
`leads.cooldown_days`, a screen used recently is ranked lower, and a lead about an economy a recent note was about
(its brief's `focus`, within `leads.entity_cooldown_days`) loses `leads.entity_penalty` of its score, so the desk
does not write one note seven ways or about Canada every week.
"""
from __future__ import annotations

import datetime as dt
import json
import statistics

from ..paths import RUNS, read_json, read_jsonl
from . import config
from .api import DESK, Api, table_rows
from .facts import _ranks
from .panel import COLS, column

LEDGER = DESK / "ledger.jsonl"
FUNDING = ["vulnerability", "a2_pct", "a1_pct", "sov_count", "replay_vs_reserves_pct", "top_lender_share_pct", "bank_loans_pct_exports"]
TRADE = ["top_dest_share_pct", "export_market_hhi", "top_export_chapter_share_pct", "top_supplier_share_pct",
         "chokepoint_world_import_share_pct", "exports_yoy_pct"]


def _names(rows: dict, keys: list[str], n: int = 8) -> str:
    names = [rows[k]["name"] for k in keys[:n]]
    more = len(keys) - len(names)
    return ", ".join(names) + (f" and {more} more" if more > 0 else "")


def _spearman(a: dict, b: dict) -> tuple[float, int]:
    keys = [k for k in a if k in b]
    if len(keys) < 12:
        return 0.0, len(keys)
    return statistics.correlation(_ranks([a[k] for k in keys]), _ranks([b[k] for k in keys])), len(keys)


def _top_quarter(vals: dict) -> set[str]:
    if len(vals) < 12:
        return set()
    cut = sorted(vals.values(), reverse=True)[max(0, len(vals) // 4 - 1)]
    return {k for k, v in vals.items() if v >= cut}


def _lab(col: str) -> str:
    return COLS[col][0]


# ------------------------------------------------------------------ screens

def same_partner(p: dict, api: Api) -> list[dict]:
    rows = p["rows"]
    same = [e for e, r in rows.items() if r.get("top_lender_iso") and r.get("top_lender_iso") == r.get("top_dest_iso")]
    if len(same) < 3:
        return []
    same.sort(key=lambda e: -(rows[e].get("top_lender_share_pct") or 0) - (rows[e].get("top_dest_share_pct") or 0))
    return [{
        "key": "same-partner", "screen": "same_partner", "apps": ["money-flow", "trade-flow"],
        "claim": f"In {len(same)} of {len(rows)} economies the largest foreign banking system lending to them and their "
                 f"largest export market are the same economy: {_names(rows, same)}.",
        "why": "One partner's trouble would then reach an economy through its bank funding and its sales at once. Bank "
               "lenders come from BIS locational banking statistics, export markets from UN Comtrade: neither page shows the overlap.",
        "economies": same, "cols": ["top_lender", "top_lender_share_pct", "top_dest", "top_dest_share_pct", "lender_dest_overlap_pct",
                                    "bank_loans_pct_exports", "a2_pct"],
        "numbers": {e: {"lender": rows[e]["top_lender"], "lender_share_pct": rows[e]["top_lender_share_pct"],
                        "market_share_pct": rows[e]["top_dest_share_pct"]} for e in same},
        "strength": min(1.0, len(same) / 10 + 0.3),
        "pulls": [{"name": f"pair_{e.lower()}", "path": f"global-network/pairs/{e}/{rows[e]['top_lender_iso']}"} for e in same[:3]]
                 + [{"name": f"cut_{same[0].lower()}", "path": "money-flow/markets/bank/lender-cut",
                     "params": {"debtor": same[0], "lender": rows[same[0]]["top_lender_iso"], "cut_pct": 25}}],
    }]


def joint_top(p: dict, api: Api) -> list[dict]:
    """Economies in the top quarter of the board on a funding measure and on a trade measure at once."""
    rows, out = p["rows"], []
    for f in FUNDING[:5]:
        tf = _top_quarter(column(p, f))
        for t in TRADE[:5]:
            tt = _top_quarter(column(p, t))
            both = sorted(tf & tt, key=lambda e: -(rows[e].get(f) or 0))
            n = len([e for e in rows if isinstance(rows[e].get(f), (int, float)) and isinstance(rows[e].get(t), (int, float))])
            if n < 20 or len(both) < 4:
                continue
            expected = len(tf) * len(tt) / n
            out.append({
                "key": f"joint-{f}-{t}", "screen": "joint_top", "apps": ["money-flow", "trade-flow"],
                "claim": f"{len(both)} economies are in the top quarter of the board on both “{_lab(f)}” and “{_lab(t)}”: "
                         f"{_names(rows, both)} (about {expected:.1f} would be expected if the two were unrelated).",
                "why": "A weak funding position and a concentrated trade position in the same economy is the case where one "
                       "shock has two ways in. The funding measure is from BIS and IMF statistics, the trade measure from UN Comtrade.",
                "economies": both, "cols": [f, t, "flow_pct", "import_cover_months", "top_dest", "top_export_chapter"],
                "numbers": {e: {f: rows[e].get(f), t: rows[e].get(t)} for e in both},
                "strength": min(1.0, 0.25 + 0.2 * (len(both) - expected)),
                "pulls": [{"name": f"stress_{both[0].lower()}", "path": "global-network/stress", "params": {"economy": both[0]}}],
            })
    return sorted(out, key=lambda x: -x["strength"])[:3]


def relation(p: dict, api: Api) -> list[dict]:
    """Rank correlations across the board between a funding measure and a trade measure: the strong ones, and the
    absent one where a reader would expect a link."""
    out = []
    for f in FUNDING:
        for t in TRADE:
            rho, n = _spearman(column(p, f), column(p, t))
            if n >= 24 and abs(rho) >= 0.4:
                way = "higher" if rho > 0 else "lower"
                out.append({
                    "key": f"relation-{f}-{t}", "screen": "relation", "apps": ["money-flow", "trade-flow"],
                    "claim": f"Across {n} economies, a higher “{_lab(f)}” goes with a {way} “{_lab(t)}” (rank correlation {rho:+.2f}).",
                    "why": "A pattern across the board that links how economies are funded to how they trade; it needs both sides' data.",
                    "economies": [], "cols": [f, t], "numbers": {"rho": round(rho, 3), "n": n},
                    "strength": min(1.0, abs(rho) + 0.1), "pulls": [],
                })
    rho, n = _spearman(column(p, "vulnerability"), column(p, "export_market_hhi"))
    if n >= 24 and abs(rho) < 0.15:
        out.append({
            "key": "relation-none-vulnerability-export_market_hhi", "screen": "relation", "apps": ["money-flow", "trade-flow"],
            "claim": f"Across {n} economies, funding vulnerability and the concentration of export markets are unrelated "
                     f"(rank correlation {rho:+.2f}): the economies most exposed in funding are not the ones most tied to one buyer.",
            "why": "The two risks are often discussed together; the data say they sit in different economies.",
            "economies": [], "cols": ["vulnerability", "export_market_hhi", "top_dest", "top_dest_share_pct"],
            "numbers": {"rho": round(rho, 3), "n": n}, "strength": 0.45, "pulls": [],
        })
    return sorted(out, key=lambda x: -x["strength"])[:3]


def funding_against_exports(p: dict, api: Api) -> list[dict]:
    rows = p["rows"]
    left = [e for e, r in rows.items() if isinstance(r.get("flow_pct"), (int, float)) and r["flow_pct"] < 0]
    if len(left) < 3:
        return []
    grew = [e for e in left if (rows[e].get("exports_yoy_pct") or 0) > 0]
    fell = [e for e in left if (rows[e].get("exports_yoy_pct") or 0) < 0]
    left.sort(key=lambda e: rows[e]["flow_pct"])
    return [{
        "key": f"funding-left-{p['quarter']}", "screen": "funding_against_exports", "apps": ["money-flow", "trade-flow"],
        "claim": f"Bank and bond funding left {len(left)} of {len(rows)} economies in the latest quarter ({_names(rows, left)}); "
                 f"goods exports grew over the year in {len(grew)} of them and fell in {len(fell)}.",
        "why": "Whether money leaves an economy whose sales are also falling (a double hit) or one that is selling more "
               "(a portfolio move) changes what the outflow means. Flows are from BIS statistics, exports from UN Comtrade.",
        "economies": left, "cols": ["flow_pct", "b1_usd_bn", "b2_usd_bn", "exports_yoy_pct", "imports_yoy_pct", "vulnerability",
                                    "niip_gdp_pct", "ca_gdp_pct"],
        "numbers": {e: {"flow_pct": rows[e]["flow_pct"], "exports_yoy_pct": rows[e].get("exports_yoy_pct")} for e in left},
        "strength": 0.55 + (0.2 if fell else 0.0) + 0.05 * min(4, len(left) - 3),
        "pulls": [{"name": "board_prev", "path": "money-flow/board", "params": {"quarter": _prev_quarter(p["quarter"])}}],
    }]


def movers(p: dict, api: Api) -> list[dict]:
    """The board against the quarter before: whose vulnerability moved most, and what they sell."""
    rows = p["rows"]
    prev = {r["economy"]: r for r in table_rows(api.get("money-flow/board", quarter=_prev_quarter(p["quarter"])))}
    d = {e: rows[e]["vulnerability"] - prev[e]["vulnerability"] for e in rows
         if e in prev and isinstance(rows[e].get("vulnerability"), (int, float)) and isinstance(prev[e].get("vulnerability"), (int, float))}
    if len(d) < 20:
        return []
    up = sorted(d, key=lambda e: -d[e])[:5]
    turned = [e for e in rows if e in prev and isinstance(prev[e].get("flow_pct"), (int, float))
              and isinstance(rows[e].get("flow_pct"), (int, float)) and prev[e]["flow_pct"] >= 0 > rows[e]["flow_pct"]]
    out = [{
        "key": f"movers-{p['quarter']}", "screen": "movers", "apps": ["money-flow", "trade-flow"],
        "claim": f"Funding vulnerability rose most over the quarter in {_names(rows, up)} "
                 f"({', '.join(f'{d[e]:+.1f}' for e in up)} points on a 0–100 score); funding flows turned from inflow to outflow in "
                 f"{len(turned)} economies" + (f" ({_names(rows, turned)})" if turned else "") + ".",
        "why": "A new quarter of BIS and IMF data moved the board; reading the movers beside what each sells and to whom "
               "(UN Comtrade) shows whether the funding change meets a trade exposure.",
        "economies": up + [e for e in turned if e not in up], "cols": ["vulnerability", "flow_pct", "a2_pct", "exports_yoy_pct",
                                                                       "top_dest", "top_dest_share_pct", "top_export_chapter"],
        "numbers": {e: {"change_in_vulnerability": round(d[e], 2), "flow_pct": rows[e]["flow_pct"],
                        "flow_pct_before": prev[e].get("flow_pct")} for e in up},
        "strength": min(1.0, 0.35 + max(d.values()) / 12 + 0.08 * len(turned)),
        "pulls": [{"name": "board_prev", "path": "money-flow/board", "params": {"quarter": _prev_quarter(p["quarter"])}}],
    }]
    return out


def shock(p: dict, api: Api) -> list[dict]:
    out = []
    for s in api.get("global-network/shocks")["data"].get("replays", []):
        if not s.get("ongoing"):
            continue
        d = api.get(f"global-network/shocks/{s['id']}")["data"]
        hit = (d.get("who_was_hit") or {}).get("economies") or []
        falls = [h for h in hit if isinstance(h.get("worst_3m_export_change_pct"), (int, float)) and h["worst_3m_export_change_pct"] < 0]
        if len(falls) < 3:
            continue
        sig = d.get("signals_before") or {}
        last = (d.get("months") or {}).get("last_with_data")
        if not last or (dt.date.today() - dt.date(int(last[:4]), int(last[5:7]), 1)).days > 400:
            continue                    # a replay whose data ended more than a year ago is history, not a lead
        out.append({
            "key": f"shock-{s['id']}-{last}", "screen": "shock", "apps": ["global-network", "money-flow", "trade-flow"],
            "claim": f"{d.get('label')}: to {last}, exports fell over three months against a year earlier in {len(falls)} of the "
                     f"board economies, most in {', '.join(h['name'] for h in falls[:4])}; the stress count a quarter before "
                     f"the shock ranks with the later export falls at rho {sig.get('spearman_rho')} over {sig.get('economies')} economies.",
            "why": "An ongoing shock replayed month by month through trade links, read beside each economy's funding flows "
                   "before and after: who was hit, and whether funding cushioned it. Observed, not causal.",
            "economies": [h["economy"] for h in falls[:8] if h["economy"] in p["rows"]],
            "cols": ["exports_yoy_pct", "flow_pct", "vulnerability", "import_cover_months", "top_supplier", "top_supplier_share_pct"],
            "numbers": {h["economy"]: {"worst_3m_export_change_pct": h["worst_3m_export_change_pct"],
                                       "flow_score_before": h.get("flow_score_before")} for h in falls[:8]},
            "strength": 0.6 + 0.05 * min(6, len(falls) - 3),
            "pulls": [{"name": f"shock_{s['id'].replace('-', '_')}", "path": f"global-network/shocks/{s['id']}"}],
        })
    return out


def chokepoint(p: dict, api: Api) -> list[dict]:
    """The largest buyers at chokepoint stages, against how many months of imports their reserves cover."""
    rows = p["rows"]
    big = [(e, c) for e, r in rows.items() for c in r.get("chokepoints") or []
           if (c.get("world_import_share_pct") or 0) >= 15 and (c.get("supplier_share_pct") or 0) >= 50]
    if len(big) < 3:
        return []
    big.sort(key=lambda x: -(x[1]["world_import_share_pct"] * x[1]["supplier_share_pct"]))
    ecos = list(dict.fromkeys(e for e, _ in big))
    return [{
        "key": "chokepoint-buyers", "screen": "chokepoint", "apps": ["trade-flow", "money-flow"],
        "claim": "Where one exporter dominates a product-chain stage, a few economies do most of the buying from it: "
                 + "; ".join(f"{rows[e]['name']} takes {c['world_import_share_pct']:.0f}% of world imports of {c['stage'].lower()}, "
                             f"{c['supplier_share_pct']:.0f}% of it from {c['supplier']}" for e, c in big[:4]) + ".",
        "why": "Chokepoints are usually described from the seller's side (exporter concentration). The buyer's side shows who "
               "would have to pay or wait, and the funding side (reserves against imports, vulnerability) shows who could.",
        "economies": ecos[:8], "cols": ["chokepoint_world_import_share_pct", "chokepoint_supplier_share_pct", "chokepoint_worst",
                                        "import_cover_months", "vulnerability", "net_reserves_usd_bn", "top_supplier", "top_supplier_share_pct"],
        "numbers": {f"{e}:{c['stage']}": {"world_import_share_pct": c["world_import_share_pct"], "supplier": c["supplier"],
                                          "supplier_share_pct": c["supplier_share_pct"]} for e, c in big[:8]},
        "strength": min(1.0, 0.4 + 0.05 * len(big)),
        "pulls": [{"name": f"chain_{big[0][1]['chain']}", "path": f"trade-flow/chains/{big[0][1]['chain']}", "params": {"economy": big[0][0]}}],
    }]


def scale(p: dict, api: Api) -> list[dict]:
    """Bank borrowing against goods exports: which economies run on finance and which on trade."""
    vals = column(p, "bank_loans_pct_exports")
    if len(vals) < 20:
        return []
    rows = p["rows"]
    hi = sorted(vals, key=lambda e: -vals[e])[:5]
    lo = sorted(vals, key=lambda e: vals[e])[:5]
    med = statistics.median(vals.values())
    return [{
        "key": "scale-bank-loans-exports", "screen": "scale", "apps": ["money-flow", "trade-flow"],
        "claim": f"Cross-border bank loans owed range from {vals[lo[0]]:.0f}% of a year's goods exports in {rows[lo[0]]['name']} to "
                 f"{vals[hi[0]]:.0f}% in {rows[hi[0]]['name']} (median {med:.0f}%): {_names(rows, hi)} at the top, {_names(rows, lo)} at the bottom.",
        "why": "The ratio sets one economy's bank borrowing (BIS) against what it earns from selling goods (UN Comtrade): a "
               "rough gauge of whether its ties to the world run through finance or through trade.",
        "economies": hi + lo, "cols": ["bank_loans_usd_bn", "exports_12m_usd_bn", "bank_loans_pct_exports", "top_lender",
                                       "top_lender_share_pct", "a2_pct", "vulnerability"],
        "numbers": {e: round(vals[e], 1) for e in hi + lo}, "strength": 0.5, "pulls": [],
    }]


def spotlight(p: dict, api: Api) -> list[dict]:
    """One economy that stands in the board's top five on several measures from both sides."""
    rows, out = p["rows"], []
    tops = {}
    for c in FUNDING + TRADE[:5]:
        vals = column(p, c)
        for e in sorted(vals, key=lambda k: -vals[k])[:5]:
            tops.setdefault(e, []).append(c)
    for e, cs in tops.items():
        f, t = [c for c in cs if c in FUNDING], [c for c in cs if c in TRADE]
        if len(f) >= 2 and len(t) >= 1 and len(cs) >= 4:
            out.append({
                "key": f"spotlight-{e}", "screen": "spotlight", "apps": ["money-flow", "trade-flow", "global-network"],
                "claim": f"{rows[e]['name']} is in the board's top five on {len(cs)} measures at once: "
                         + "; ".join(f"{_lab(c)} ({rows[e][c]:.1f})" for c in cs) + ".",
                "why": "A single economy where funding exposure and trade concentration meet, read through its lenders, "
                       "its markets and its past withdrawal episodes.",
                "economies": [e], "cols": cs + ["top_lender", "top_dest", "top_export_chapter", "flow_pct", "import_cover_months"],
                "numbers": {c: rows[e][c] for c in cs}, "strength": min(1.0, 0.3 + 0.1 * len(cs)),
                "pulls": [{"name": f"stress_{e.lower()}", "path": "global-network/stress", "params": {"economy": e}},
                          {"name": f"pair_{e.lower()}", "path": f"global-network/pairs/{e}/{rows[e].get('top_lender_iso') or 'USA'}"}],
            })
    return sorted(out, key=lambda x: -x["strength"])[:3]


# ------------------------------------------------------------------ change and departure (added 15 Nov 2026)
# The screens above compare economies at one date, and their leads tend to restate a ranking geography or size
# already explains. These read each economy against its own past and against what size alone would predict.

# joint signals with a quarterly history since 2005 (global-network/stress?economy=…): a funding quantity over a
# trade quantity, so a move in one needs both sides; `worse` is the direction a reader would worry about
HISTORY = {"j1": ("import cover (net reserves in months of goods imports)", "months", "low", "import_cover_months"),
           "j2": ("external financing need as a share of goods exports", "% of exports", "high", "financing_need_pct_exports")}
WINDOW = 20         # quarters of an economy's own past a reading is set against (five years)


def _histories(p: dict, api: Api) -> dict[str, list[dict]]:
    """Each economy's joint signals by quarter, oldest first (one call per economy, cached per release)."""
    if "_hist" not in p:
        out = {}
        for e in p["rows"]:
            try:
                rows = table_rows(api.get("global-network/stress", economy=e))
            except Exception:
                continue
            out[e] = sorted((r for r in rows if r.get("quarter")), key=lambda r: r["quarter"])
        p["_hist"] = out
    return p["_hist"]


def _series(rows: list[dict], key: str) -> list[float]:
    return [r[key] for r in rows if isinstance(r.get(key), (int, float)) and not isinstance(r.get(key), bool)]


def own_extremes(p: dict, api: Api) -> list[dict]:
    """Economies where a joint funding-over-trade ratio is at the edge of its own past five years."""
    rows, out = p["rows"], []
    for key, (label, unit, worse, col) in HISTORY.items():
        hits = {}
        for e, h in _histories(p, api).items():
            if e not in rows:
                continue
            v = _series(h[-(WINDOW + 1):], key)
            if len(v) < WINDOW - 4 or h[-1].get(key) is None:
                continue
            cur, past = v[-1], v[:-1]
            sd = statistics.pstdev(past) or None
            if (worse == "high" and cur >= max(past)) or (worse == "low" and cur <= min(past)):
                hits[e] = {"now": cur, "own_median": round(statistics.median(past), 2),
                           "own_z": round((cur - statistics.mean(past)) / sd, 2) if sd else None, "quarters": len(past),
                           "quarter": h[-1]["quarter"]}
        if not hits:
            continue
        order = sorted(hits, key=lambda e: -abs(hits[e]["own_z"] or 0))
        word = "highest" if worse == "high" else "lowest"
        q = hits[order[0]]["quarter"]
        out.append({
            "key": f"history-{key}-{word}-{q}", "screen": "own_extremes", "apps": ["global-network", "money-flow", "trade-flow"],
            "claim": f"At {q}, {label} was at its {word} in the past five years in {len(hits)} of {len(rows)} economies: "
                     + ", ".join(f"{rows[e]['name']} ({hits[e]['now']:.1f} against an own median of {hits[e]['own_median']:.1f})" for e in order[:6]) + ".",
            "why": "The ratio sets a funding quantity (reserves or financing need, BIS and IMF) against a trade quantity "
                   "(UN Comtrade), so it moves when either side does. The stress page shows each economy's line; no page "
                   "asks which economies are at the edge of their own range at once, or whether the move came with a "
                   "change in funding vulnerability.",
            "economies": order[:8], "cols": [col, "vulnerability", "flow_pct", "exports_yoy_pct", "imports_yoy_pct", "net_reserves_usd_bn"],
            "numbers": {e: hits[e] for e in order[:8]},
            "strength": min(1.0, 0.5 + 0.08 * len(hits) + 0.05 * min(3, max(abs(hits[e]["own_z"] or 0) for e in hits))),
            "pulls": [{"name": f"stress_{e.lower()}", "path": "global-network/stress", "params": {"economy": e}} for e in order[:2]],
        })
    return out


def decoupled(p: dict, api: Api) -> list[dict]:
    """A joint ratio that moved sharply over the year, against the economy's own past, while the funding
    vulnerability score (which reads the funding side only) hardly moved: a change only the join shows."""
    rows, out = p["rows"], []
    for key, (label, unit, worse, col) in HISTORY.items():
        hits = {}
        for e, h in _histories(p, api).items():
            if e not in rows or len(h) < 24:
                continue
            j = [r.get(key) for r in h]
            v = [r.get("v") for r in h]
            ok = lambda s, i: isinstance(s[i], (int, float)) and isinstance(s[i - 4], (int, float))  # noqa: E731
            dj = [j[i] - j[i - 4] for i in range(4, len(h) - 1) if ok(j, i)]
            dv = [v[i] - v[i - 4] for i in range(4, len(h) - 1) if ok(v, i)]
            if len(dj) < 16 or len(dv) < 16 or not ok(j, len(h) - 1) or not ok(v, len(h) - 1):
                continue
            sj, sv = statistics.pstdev(dj) or None, statistics.pstdev(dv) or None
            if not sj or not sv:
                continue
            zj = (j[-1] - j[-5] - statistics.mean(dj)) / sj
            zv = (v[-1] - v[-5] - statistics.mean(dv)) / sv
            bad = zj >= 2 if worse == "high" else zj <= -2
            if bad and abs(zv) < 1:
                hits[e] = {"change_over_year": round(j[-1] - j[-5], 2), "own_z_of_change": round(zj, 2),
                           "vulnerability_change": round(v[-1] - v[-5], 2), "vulnerability_z": round(zv, 2),
                           "from": h[-5]["quarter"], "to": h[-1]["quarter"]}
        if not hits:
            continue
        order = sorted(hits, key=lambda e: -abs(hits[e]["own_z_of_change"]))
        way = "rose" if worse == "high" else "fell"
        out.append({
            "key": f"decoupled-{key}-{hits[order[0]]['to']}", "screen": "decoupled", "apps": ["global-network", "money-flow", "trade-flow"],
            "claim": f"Over the year to {hits[order[0]]['to']}, {label} {way} more than in all but a few of their own years since 2005 in "
                     + ", ".join(f"{rows[e]['name']} ({hits[e]['change_over_year']:+.1f}, {hits[e]['own_z_of_change']:+.1f} standard deviations)" for e in order[:5])
                     + "; the funding vulnerability score, which reads the funding side only, changed little in each.",
            "why": "A joined ratio that moves while the funding-only score does not points to the trade side (exports or "
                   "imports, UN Comtrade) or to a part of funding the score leaves out. Neither app's page alone shows the gap; "
                   "the note must say which side moved, from the tables.",
            "economies": order[:6], "cols": [col, "vulnerability", "exports_yoy_pct", "imports_yoy_pct", "net_reserves_usd_bn", "flow_pct"],
            "numbers": {e: hits[e] for e in order[:6]},
            "strength": min(1.0, 0.6 + 0.05 * len(hits) + 0.05 * min(3, abs(hits[order[0]]["own_z_of_change"]) - 2)),
            "pulls": [{"name": f"stress_{e.lower()}", "path": "global-network/stress", "params": {"economy": e}} for e in order[:2]],
        })
    return out


def beyond_size(p: dict, api: Api) -> list[dict]:
    """The largest export market against that market's weight in world imports (what size alone predicts), beside
    whether banks located in the same economy are also the largest lender."""
    rows = p["rows"]
    weight = {}
    for d in {r.get("top_dest_iso") for r in rows.values() if r.get("top_dest_iso")}:
        try:
            w = ((api.get(f"trade-flow/economies/{d}", direction="imports")["data"].get("imports") or {}).get("share_of_world_pct"))
        except Exception:
            continue
        if isinstance(w, (int, float)) and w > 0:
            weight[d] = w
    lift = {e: r["top_dest_share_pct"] / weight[r["top_dest_iso"]] for e, r in rows.items()
            if isinstance(r.get("top_dest_share_pct"), (int, float)) and r.get("top_dest_iso") in weight
            and (r.get("exports_unspecified_asia_pct") or 0) < 10}
    if len(lift) < 20:
        return []
    med = statistics.median(lift.values())
    # within a region, size and proximity are shared: a lift far above the region's own median is what neither explains
    by_region = {}
    for e in lift:
        by_region.setdefault(rows[e].get("region"), []).append(lift[e])
    rel = {e: lift[e] / statistics.median(by_region[rows[e].get("region")]) for e in lift if len(by_region[rows[e].get("region")]) >= 4}
    top = [e for e in sorted(rel, key=lambda e: -rel[e]) if rel[e] >= 1.5][:6]
    if len(top) < 2:
        return []
    same = [e for e in top if rows[e].get("top_lender_iso") == rows[e].get("top_dest_iso")]
    return [{
        "key": "beyond-size-" + "-".join(sorted(top)[:3]).lower(), "screen": "beyond_size", "apps": ["trade-flow", "money-flow", "global-network"],
        "claim": "Set against the market's weight in world imports, the largest export market takes far more than size predicts, and more "
                 "than for the region's other economies, in " + ", ".join(
                     f"{rows[e]['name']} ({rows[e]['top_dest']}: {rows[e]['top_dest_share_pct']:.0f}% of exports against "
                     f"{weight[rows[e]['top_dest_iso']]:.1f}% of world imports, {lift[e]:.1f} times; region median {lift[e] / rel[e]:.1f})" for e in top)
                 + f". The median across {len(lift)} economies is {med:.1f} times. In {len(same)} of them banks located in the same economy are also the largest lender.",
        "why": "A large share for a large market is what size predicts, and the region's median takes out part of proximity. "
               "A neighbour can still top this list (no distance data are used): the editor must ask whether a border or a "
               "currency union explains the tie before calling it new. Read beside the bank funding (BIS) from the same economy.",
        "economies": top, "cols": ["top_dest", "top_dest_share_pct", "top_lender", "top_lender_share_pct",
                                   "lender_dest_overlap_pct", "bank_loans_pct_exports"],
        "numbers": {e: {"top_dest": rows[e]["top_dest"], "share_pct": rows[e]["top_dest_share_pct"],
                        "market_world_import_share_pct": weight[rows[e]["top_dest_iso"]], "lift": round(lift[e], 2),
                        "lift_over_region_median": round(rel[e], 2)} for e in top},
        "strength": min(1.0, 0.45 + 0.05 * len(top) + 0.05 * len(same)),
        "pulls": [{"name": f"exports_{top[0].lower()}", "path": f"trade-flow/economies/{top[0]}", "params": {"direction": "exports"}},
                  {"name": f"imports_{rows[top[0]]['top_dest_iso'].lower()}", "path": f"trade-flow/economies/{rows[top[0]]['top_dest_iso']}",
                   "params": {"direction": "imports"}}],
    }]


CHANGE_SCREENS = {"own_extremes", "decoupled", "beyond_size", "movers", "shock"}
SCREENS = (same_partner, joint_top, relation, funding_against_exports, movers, shock, chokepoint, scale, spotlight,
           own_extremes, decoupled, beyond_size)


def _prev_quarter(q: str) -> str:
    y, m = int(q[:4]), int(q[5:7])
    m -= 3
    if m <= 0:
        y, m = y - 1, m + 12
    last = {3: 31, 6: 30, 9: 30, 12: 31}[m]
    return f"{y}-{m:02d}-{last}"


# ------------------------------------------------------------------ ranking and memory

def history() -> list[dict]:
    return read_jsonl(LEDGER)


def record(entry: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **entry}, ensure_ascii=False) + "\n")


def subjects(run_name: str | None) -> list[str]:
    """The economies a note was about: its brief's `focus` (one or two ISO3 codes), else the first two it names."""
    b = (read_json(RUNS / run_name / "desk" / "brief.json", {}) or {}) if run_name else {}
    focus = b.get("focus") or (b.get("economies") or [])[:2]
    return [e for e in focus if isinstance(e, str) and len(e) == 3][:2]


def recent_subjects(today: dt.date | None = None) -> dict[str, str]:
    """Economy → date of the latest note about it within the entity cooldown (queued, approved or published notes)."""
    cfg = config.load()["leads"]
    today = today or dt.date.today()
    withdrawn = {h.get("run") for h in history() if h.get("outcome") == "withdrawn"}
    out = {}
    for h in history():
        if h.get("outcome") not in ("queued", "published", "approved") or h.get("run") in withdrawn:
            continue
        if (today - dt.date.fromisoformat(h["at"][:10])).days < cfg["entity_cooldown_days"]:
            for e in subjects(h.get("run")):
                out[e] = h["at"][:10]
    return out


def find(p: dict, api: Api, changed: list[dict] | None = None, today: dt.date | None = None, keep: str | None = None) -> list[dict]:
    """Every screen's leads, scored: strength of the pattern, freshness (the lead reads a view whose data changed),
    variety (its screen was not used lately); a lead used within the cooldown is dropped."""
    cfg = config.load()["leads"]
    today = today or dt.date.today()
    withdrawn = {h.get("run") for h in history() if h.get("outcome") == "withdrawn"}
    used = [h for h in history() if h.get("outcome") in ("queued", "published", "approved") and h.get("run") not in withdrawn]
    recent_keys = {h["key"] for h in used if (today - dt.date.fromisoformat(h["at"][:10])).days < cfg["cooldown_days"]}
    recent_screens = [h.get("screen") for h in used[-6:]]
    covered = recent_subjects(today)
    fresh_views = {v for c in changed or [] for v in c.get("views", [])}
    fresh_apps = {c["app"] for c in changed or [] if c["kind"] in ("period", "dataset")}
    out = []
    for screen in SCREENS:
        try:
            found = screen(p, api)
        except Exception as e:          # one broken screen must not cost the morning's note
            out.append({"key": f"error-{screen.__name__}", "screen": screen.__name__, "error": f"{type(e).__name__}: {e}", "score": -1})
            continue
        for lead in found:
            if lead["key"] in recent_keys and lead["key"] != keep:      # `keep`: a lead asked for by name is not on cooldown
                continue
            views = {COLS[c][3] for c in lead["cols"] if c in COLS}
            fresh = 1.0 if views & fresh_views else 0.5 if set(lead["apps"]) & fresh_apps else 0.0
            variety = 1.0 - 0.25 * recent_screens.count(lead["screen"])
            # a reading against an economy's own past or against what size predicts is preferred to a ranking at one date
            if lead["screen"] in CHANGE_SCREENS:
                variety += 0.4
            lead["fresh"] = fresh
            subj = lead["economies"][:2]
            seen = [e for e in subj if e in covered]
            lead["covered_recently"] = {e: covered[e] for e in seen}
            lead["score"] = round(0.55 * lead["strength"] + 0.2 * fresh + 0.25 * max(0.0, variety)
                                  - cfg["entity_penalty"] * len(seen) / max(1, len(subj)), 3)
            out.append(lead)
    return sorted(out, key=lambda x: -x["score"])
