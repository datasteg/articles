"""The panel: one row per Signal Board economy, with what each app says about it side by side.

No datasteg page shows these columns together. money-flow knows who funds an economy and how exposed it is;
trade-flow knows what it sells, to whom, and where its imports depend on one supplier; global-network joins a few of
them per economy. The panel puts every economy's funding side beside its trade side so the lead screens can look
across the whole board at once. Each column records the app and view it came from, its unit and its period, so a
number taken from the panel can always be cited.
"""
from __future__ import annotations

from .api import Api, table_rows

# column id → (label, unit, app, view key, higher_is: "worse" | "more" | None)
COLS = {
    # money-flow · Signal Board (BIS LBS, DSS, CBS, TC; IMF IRFCL, IIP, BOP)
    "vulnerability": ("Funding vulnerability score (0–100)", "score", "money-flow", "board", "worse"),
    "exposure": ("Exposure half of the vulnerability score (0–100)", "score", "money-flow", "board", "worse"),
    "buffer_weakness": ("Buffer-weakness half of the vulnerability score (0–100)", "score", "money-flow", "board", "worse"),
    "flow_pct": ("Bank and bond funding flow, annualised % of the stock", "% per year", "money-flow", "board", None),
    "a1_pct": ("Foreign-currency credit to non-banks, % of GDP", "% of GDP", "money-flow", "board", "worse"),
    "a2_pct": ("A2: BIS banks' claims due within a year, % of A2's reserve base (net reserves, never under a tenth of gross)", "%", "money-flow", "board", "worse"),
    "niip_gdp_pct": ("Net international investment position, % of GDP", "% of GDP", "money-flow", "board", None),
    "ca_gdp_pct": ("Current account balance, % of GDP", "% of GDP", "money-flow", "board", None),
    "b1_usd_bn": ("Cross-border bank flow in the quarter, USD bn", "USD bn", "money-flow", "board", None),
    "b2_usd_bn": ("International bond net issuance in the quarter, USD bn", "USD bn", "money-flow", "board", None),
    "net_reserves_usd_bn": ("Net reserves (IMF reserve template section I less section II drains, not floored; may be negative), USD bn", "USD bn", "money-flow", "board", None),
    # money-flow · Sovereign (IMF WEO, BIS, OECD)
    "sov_count": ("Sovereign stress rules met (of up to seven)", "count", "money-flow", "sovereign", "worse"),
    # global-network · stress signals (money-flow quantity against trade-flow quantity)
    "stress_count": ("Joint funding-and-trade stress signals at threshold (of seven)", "count", "global-network", "stress", "worse"),
    "import_cover_months": ("Import cover: net reserves in months of goods imports (empty when net reserves are not positive)", "months", "global-network", "stress", None),
    "financing_need_pct_exports": ("Financing need (BIS banks' claims due within a year plus any current-account deficit), % of goods exports as partners record them", "% of exports", "global-network", "stress", "worse"),
    "lender_dest_overlap_pct": ("Lender and export market overlap (J5): the sum over partners of the smaller of lender share and export share, %", "%", "global-network", "stress", "more"),
    # global-network country sheet · trade side (UN Comtrade via trade-flow), on the window joined at the funding quarter:
    # the 12 months ending in the quarter's last month, or up to 6 months earlier (partial), as the stress signals use
    "exports_12m_usd_bn": ("Goods exports as partners record them, 12 months to the funding quarter's last month (goods_window_to), USD bn", "USD bn", "global-network", "country", None),
    "imports_12m_usd_bn": ("Goods imports as the economy records them, 12 months to the funding quarter's last month (goods_window_to), USD bn", "USD bn", "global-network", "country", None),
    "exports_yoy_pct": ("Goods exports over that window against the 12-month window ending 12 months earlier, %", "%", "global-network", "country", None),
    "imports_yoy_pct": ("Goods imports over that window against the 12-month window ending 12 months earlier, %", "%", "global-network", "country", None),
    "export_market_hhi": ("Concentration of export markets (Herfindahl index, 0–1)", "index", "global-network", "country", "more"),
    "top_dest_share_pct": ("Largest export destination, % of goods exports", "%", "global-network", "country", "more"),
    "top_supplier_share_pct": ("Largest import supplier, % of goods imports", "%", "global-network", "country", "more"),
    "top_export_chapter_share_pct": ("Largest export product group (HS chapter), % of goods exports", "%", "global-network", "country", "more"),
    "exports_unspecified_asia_pct": ("Goods exports recorded to 'Asia, destination not specified', % of goods exports (Gulf exporters)", "%", "global-network", "country", None),
    "chokepoint_world_import_share_pct": ("Its share of world imports at the chokepoint stage where it buys most, %", "%", "global-network", "country", "more"),
    "chokepoint_supplier_share_pct": ("At that stage, the largest supplier's share of the economy's imports, %", "%", "global-network", "country", "more"),
    # global-network country sheet · funding side detail (BIS LBS via money-flow)
    "bank_loans_usd_bn": ("Bank loans and deposits owed (BIS locational, all reporting banks), USD bn", "USD bn", "global-network", "country", None),
    "top_lender_share_pct": ("Largest lending banking system, % of those bank loans and deposits", "%", "global-network", "country", "more"),
    "replay_vs_reserves_pct": ("Bank and bond withdrawal replay: the worst past quarter on today's stock, % of net reserves (empty when net reserves are not positive)", "%", "global-network", "country", "worse"),
    # derived here from the above (datasteg desk calculation), on columns of the same period only (rule C2)
    "bank_loans_pct_exports": ("Bank loans and deposits owed, % of goods exports over the window joined at the funding quarter", "%", "desk", "calc", "more"),
}

# the period each column is measured over (rule C2): a fact may combine two columns only when their
# periods agree, or when it compares one measure with itself at two periods (facts.py checks it)
PERIOD = {c: ("funding_quarter" if v[3] == "board" else "sovereign_year" if v[3] == "sovereign" else "stress_quarter" if v[3] == "stress"
              else "funding_quarter") for c, v in COLS.items()}
PERIOD.update({c: "goods_window" for c in ("exports_12m_usd_bn", "imports_12m_usd_bn", "exports_yoy_pct", "imports_yoy_pct", "bank_loans_pct_exports")})
PERIOD.update({c: "goods_window_newest" for c in ("export_market_hhi", "top_dest_share_pct", "top_supplier_share_pct",
                                                   "exports_unspecified_asia_pct")})
PERIOD.update({"top_export_chapter_share_pct": "products_window", "chokepoint_world_import_share_pct": "chokepoint_year",
               "chokepoint_supplier_share_pct": "chokepoint_year", "bank_loans_usd_bn": "lenders_quarter",
               "top_lender_share_pct": "lenders_quarter", "replay_vs_reserves_pct": "funding_quarter"})

# which side of the join a column measures: a note must use at least one number that needs both sides
SIDE = {c: ("joint" if v[2] == "desk" or v[3] == "stress" else
            "trade" if c in ("exports_12m_usd_bn", "imports_12m_usd_bn", "exports_yoy_pct", "imports_yoy_pct", "export_market_hhi",
                             "top_dest_share_pct", "top_supplier_share_pct", "top_export_chapter_share_pct",
                             "chokepoint_world_import_share_pct", "chokepoint_supplier_share_pct") else "funding")
        for c, v in COLS.items()}
SIDE.update({"top_dest": "trade", "top_dest_iso": "trade", "top_supplier": "trade", "top_export_chapter": "trade",
             "chokepoint_worst": "trade", "top_lender": "funding", "top_lender_iso": "funding"})
TEXT = ("name", "region", "advanced", "top_dest", "top_supplier", "top_export_chapter", "top_lender",
        "stress_firing", "sov_signals", "how_it_earns", "chokepoint_worst")


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def build(api: Api) -> dict:
    """{"rows": {iso3: {...}}, "views": {view key: {app, cite, release, period, sources}}, "economies": [...]}."""
    views = {}

    def keep(key: str, ans: dict, app: str):
        m = ans.get("meta") or {}
        views[key] = {"app": app, "cite": m.get("cite"), "release": m.get("release"), "built": m.get("built"),
                      "period": m.get("period"), "summary": m.get("summary"),
                      "sources": [{k: s.get(k) for k in ("publisher", "dataset", "url", "vintage", "licence")}
                                  for s in m.get("sources") or []]}

    board = api.get("money-flow/board")
    keep("board", board, "money-flow")
    rows = {}
    for r in table_rows(board):
        e = r["economy"]
        rows[e] = {"economy": e, "name": r["name"], **{c: _num(r.get(c)) for c in COLS if COLS[c][3] == "board"}}
    quarter = board["data"]["quarter"]

    sov = api.get("money-flow/sovereign")
    keep("sovereign", sov, "money-flow")
    for x in sov["data"]["economies"]:
        if x["economy"] in rows:
            rows[x["economy"]].update(sov_count=x.get("count"), sov_of=x.get("of"), sov_signals=x.get("signals") or [])

    st = api.get("global-network/stress")
    keep("stress", st, "global-network")
    for x in st["data"]["economies"]:
        if x["economy"] in rows:
            v = x.get("values") or {}
            rows[x["economy"]].update(stress_count=x.get("signals_at_threshold"), stress_scored=x.get("signals_scored"),
                                      stress_firing=x.get("firing") or [], import_cover_months=_num(v.get("J1")),
                                      financing_need_pct_exports=_num(v.get("J2")), lender_dest_overlap_pct=_num(v.get("J5")),
                                      stress_trade_window_to=x.get("trade_window_to"), stress_partial=x.get("partial"),
                                      j1_not_meaningful=x.get("j1_not_meaningful"))
    stress_quarter = (st["data"].get("period") or {}).get("shown") or st["data"].get("quarter")

    for e, row in rows.items():
        ans = api.get(f"global-network/countries/{e}")
        if "country" not in views:
            keep("country", ans, "global-network")
            views["country"]["cite"] = "https://global-network.datasteg.com/en"      # the sheet family, not one economy
        d = ans["data"]
        row.update(region=d.get("region"), advanced=d.get("advanced"), sheet=(ans.get("meta") or {}).get("cite"))
        t = d.get("trade") or {}
        dests, sups = t.get("destinations") or [], t.get("suppliers") or []
        # a partner that is not an economy (UN Comtrade 490, "Asia, not elsewhere specified", since 17 Nov 2026 its own
        # node in trade-flow) is not a buyer: it is taken out of the markets and kept as its own column
        unspecified = [x for x in dests if x.get("economy") is False]
        dests = [x for x in dests if x.get("economy") is not False]
        sups = [x for x in sups if x.get("economy") is not False]
        if unspecified:
            row["exports_unspecified_asia_pct"] = _num(unspecified[0].get("share_pct"))
        per = d.get("periods") or {}
        aq = per.get("goods_window_at_quarter") or {}
        ex_top = ((t.get("products") or {}).get("exports") or {}).get("top") or []
        chk = t.get("chokepoints") or []
        row.update(exports_12m_usd_bn=_num(t.get("exports_12m_at_quarter_usd_bn")), imports_12m_usd_bn=_num(t.get("imports_12m_at_quarter_usd_bn")),
                   exports_yoy_pct=_num(t.get("exports_yoy_at_quarter_pct")), imports_yoy_pct=_num(t.get("imports_yoy_at_quarter_pct")),
                   goods_window_from=aq.get("from"), goods_window_to=aq.get("to"), goods_window_partial=aq.get("partial"),
                   goods_window_quarter=aq.get("quarter"), goods_window_newest_to=(per.get("goods_window") or {}).get("to"),
                   products_window_to=(per.get("products_window") or {}).get("to"), lenders_quarter=per.get("bank_lenders_quarter"),
                   chokepoint_year=per.get("chokepoint_year"),
                   export_market_hhi=_num(t.get("export_market_hhi")),
                   top_dest=dests[0]["name"] if dests else None, top_dest_iso=dests[0]["partner"] if dests else None,
                   top_dest_share_pct=_num(dests[0].get("share_pct")) if dests else None,
                   top_supplier=sups[0]["name"] if sups else None, top_supplier_iso=sups[0]["partner"] if sups else None,
                   top_supplier_share_pct=_num(sups[0].get("share_pct")) if sups else None,
                   top_export_chapter=ex_top[0]["name"] if ex_top else None,
                   top_export_chapter_share_pct=_num(ex_top[0].get("share_pct")) if ex_top else None,
                   goods_window={"from": aq.get("from"), "to": aq.get("to"), "partial": aq.get("partial")} if aq else None,
                   chokepoints=[{"chain": c.get("chain"), "stage": c.get("stage"), "hhi": _num(c.get("hhi")),
                                 "world_import_share_pct": _num(c.get("import_share_pct")),
                                 "supplier": (c.get("top_supplier") or {}).get("name"),
                                 "supplier_iso": (c.get("top_supplier") or {}).get("economy"),
                                 "supplier_share_pct": _num((c.get("top_supplier") or {}).get("share_pct"))} for c in chk])
        # the chokepoint stage (exporter HHI above 0.25) where the economy is the largest buyer in the world's imports
        big = max(row["chokepoints"], key=lambda c: c["world_import_share_pct"] or 0, default=None)
        if big and big["world_import_share_pct"] is not None:
            row.update(chokepoint_world_import_share_pct=big["world_import_share_pct"],
                       chokepoint_supplier_share_pct=big["supplier_share_pct"],
                       chokepoint_worst=f"{big['stage']} (largest supplier {big['supplier']})")
        f = d.get("funding") or {}
        bl = f.get("bank_lenders") or {}
        top = bl.get("top") or []
        rep = d.get("withdrawal_replay") or {}
        row.update(bank_loans_usd_bn=_num(bl.get("all_reporters_total_usd_bn") or bl.get("total_loans_usd_bn")),
                   top_lender=top[0]["name"] if top else None, top_lender_iso=top[0]["lender"] if top else None,
                   top_lender_share_pct=_num(top[0].get("share_of_loans_pct")) if top else None,
                   replay_vs_reserves_pct=_num(rep.get("against_net_reserves_pct")),
                   lenders=[{"iso": x["lender"], "name": x["name"], "share": _num(x.get("share_of_loans_pct"))} for x in top],
                   dests=[{"iso": x["partner"], "name": x["name"], "share": _num(x.get("share_pct"))} for x in dests])
        # the desk's own join: loans at the lenders' quarter over exports on the window joined at the funding quarter;
        # only when the lenders' quarter is that quarter (rule C2); the overlap is J5 from the stress board
        if row.get("bank_loans_usd_bn") and row.get("exports_12m_usd_bn") and row.get("lenders_quarter") == row.get("goods_window_quarter"):
            row["bank_loans_pct_exports"] = round(100 * row["bank_loans_usd_bn"] / row["exports_12m_usd_bn"], 2)

    views["calc"] = {"app": "desk", "cite": None, "release": None, "period": None, "sources": [],
                     "summary": "datasteg desk calculation from the money-flow and trade-flow views above"}
    # the funding quarter of the board, the stress board and the country sheets must be the same quarter (rule C2)
    quarters = {"board": quarter, "stress": stress_quarter,
                "country": sorted({r.get("goods_window_quarter") for r in rows.values() if r.get("goods_window_quarter")})}
    return {"quarter": quarter, "quarters": quarters, "rows": rows, "views": views, "economies": sorted(rows),
            "releases": {a: api.release(a) for a in ("money-flow", "trade-flow", "global-network", "open-research")}}


def views_of(cols: list[str]) -> list[str]:
    """The input views a set of panel columns came from (board, sovereign, stress, country), in that order. The
    desk's own joins read the country sheets (lenders and markets) and, for the loans ratio, nothing else."""
    out = []
    for c in cols:
        v = COLS[c][3] if c in COLS else ("country" if c in SIDE else None)
        v = "country" if v == "calc" else v
        if v and v not in out:
            out.append(v)
    return [v for v in ("board", "sovereign", "stress", "country") if v in out]


def column(panel: dict, col: str) -> dict[str, float]:
    return {e: r[col] for e, r in panel["rows"].items() if isinstance(r.get(col), (int, float))}
