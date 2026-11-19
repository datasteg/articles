"""The data desk, offline: no network, no model calls. A small panel of six economies stands in for the API."""
import os
os.environ.setdefault("DESK_KO_ENGINE", "qkr")   # the tests fake qkr; the live config may say claude
import json

import pytest

from artools import pipelines
from artools.desk import charts, config, facts, judge, korean, leads, queue, review, roles, tables, text, watch
from artools.desk import panel as panel_mod
from artools.desk import polish as polish_mod

ECON = {
    # economy: (name, vulnerability, flow, top lender, lender share, top market, market share, exports yoy, loans, exports)
    "CAN": ("Canada", 58.0, 13.8, "USA", 50.0, "USA", 60.8, 7.5, 913.0, 651.0),
    "MEX": ("Mexico", 59.1, 11.9, "USA", 50.0, "USA", 74.9, 13.0, 86.0, 656.0),
    "KOR": ("Korea", 42.4, 9.8, "HKG", 23.0, "CHN", 24.7, 28.3, 162.5, 1020.7),
    "JPN": ("Japan", 39.2, -7.7, "GBR", 26.0, "CHN", 18.9, 5.5, 1100.0, 704.0),
    "RUS": ("Russia", 22.2, -16.1, "GBR", 17.0, "CHN", 34.9, -10.0, 28.0, 390.0),
    "PRT": ("Portugal", 39.8, 6.8, "ESP", 37.0, "ESP", 20.5, 5.7, 62.0, 99.0),
}


def _panel():
    rows = {}
    for e, (name, v, flow, lender, ls, dest, dshare, yoy, loans, exports) in ECON.items():
        rows[e] = {"economy": e, "name": name, "vulnerability": v, "flow_pct": flow, "top_lender_iso": lender, "top_lender": lender,
                   "top_lender_share_pct": ls, "top_dest_iso": dest, "top_dest": dest, "top_dest_share_pct": dshare,
                   "exports_yoy_pct": yoy, "bank_loans_usd_bn": loans, "exports_12m_usd_bn": exports,
                   "bank_loans_pct_exports": round(100 * loans / exports, 2), "chokepoints": []}
    views = {k: {"app": a, "cite": f"https://{a}.datasteg.com/en/x?utm_source=datasteg-api", "release": "20261114.1", "period": {"shown": "2026-06-30"},
                 "sources": [{"publisher": p}]} for k, a, p in (("board", "money-flow", "Bank for International Settlements"),
                                                               ("sovereign", "money-flow", "International Monetary Fund"),
                                                               ("stress", "global-network", "UN Comtrade"),
                                                               ("country", "global-network", "UN Comtrade"))}
    return {"quarter": "2026-06-30", "rows": rows, "views": views, "economies": sorted(rows)}


def _tables():
    p = _panel()
    t = {"panel": tables.from_panel(p)}
    for key, app, pubs in (("board", "money-flow", ["BIS", "IMF"]), ("country", "global-network", ["UN Comtrade", "BIS"])):
        t[key] = {"name": key, "app": app, "path": f"{app}/{key}", "params": {}, "key": ["economy"],
                  "columns": [{"id": "economy"}, {"id": "name"}], "rows": [{"economy": e, "name": r["name"], "_key": e} for e, r in p["rows"].items()],
                  "title": key, "summary": key, "cite": f"https://{app}.datasteg.com/en/x", "release": "20261114.1",
                  "period": {"shown": "2026-06-30"}, "sources": [], "publishers": pubs, "notes": []}
    t["panel"]["inputs"] = ["board", "country"]
    return t


# ------------------------------------------------------------------ facts

def test_a_fact_is_an_expression_over_the_tables_and_nothing_else():
    t = _tables()
    v, used = facts.evaluate("count('panel', 'top_lender_iso == top_dest_iso')", t)
    assert (v, used) == (3, ["panel"])
    assert facts.evaluate("cell('panel','CAN','top_dest_share_pct') - cell('panel','MEX','top_dest_share_pct')", t)[0] == pytest.approx(-14.1)
    assert facts.evaluate("rank('panel','vulnerability','MEX')", t)[0] == 1
    assert facts.evaluate("where_max('panel','bank_loans_pct_exports')", t)[0] == "Japan"
    assert facts.evaluate("share('panel','flow_pct < 0')", t)[0] == pytest.approx(100 * 2 / 6)
    for bad in ("__import__('os').system('true')", "cell.__class__", "open('/etc/passwd')", "[x for x in (1,)]", "panel",
                "cell('panel','CAN','vulnerability') if 1 else 0", "(lambda: 1)()"):
        with pytest.raises(facts.FactError):
            facts.evaluate(bad, t)
    with pytest.raises(facts.FactError, match="no row"):
        facts.evaluate("cell('panel','XXX','vulnerability')", t)
    with pytest.raises(facts.FactError, match="no column"):
        facts.evaluate("median('panel','nope')", t)


def test_a_condition_cannot_call_anything():
    t = _tables()
    with pytest.raises(facts.FactError):
        facts.evaluate("count('panel', \"__import__('os').system('true')\")", t)
    with pytest.raises(facts.FactError):
        facts.evaluate("count('panel', 'name.upper() == 1')", t)
    with pytest.raises(facts.FactError, match="not an expression"):      # a malformed filter is the model's error to fix, not a crash
        facts.evaluate("count('panel', 'flow_pct <')", t)


def test_compute_reports_what_it_could_not_compute_and_never_guesses():
    t = _tables()
    got, problems = facts.compute([
        {"label": "Economies whose largest lender is their largest market", "expr": "count('panel','top_lender_iso == top_dest_iso')", "unit": "countries"},
        {"label": "Canada's exports to its largest market", "expr": "cell('panel','CAN','top_dest_share_pct')", "unit": "%"},
        {"label": "broken", "expr": "cell('panel','ZZZ','x')", "unit": "%"},
        {"label": "bad unit", "expr": "cell('panel','CAN','vulnerability')", "unit": "furlongs"},
    ], t)
    assert [f["id"] for f in got] == ["F1", "F2"] and len(problems) == 2
    # a number read from the panel is cited to the view its columns came from, not to the whole join
    assert got[0]["inputs"] == ["ds-country"] and got[0]["period"] == "2026-06-30" and got[0]["publishable"] is True
    both, _ = facts.compute([{"label": "x", "expr": "spearman('panel','vulnerability','top_dest_share_pct')", "unit": "ratio"}], t)
    assert both == [] or both[0]["inputs"] == ["ds-board", "ds-country"]
    sheet = facts.sheet(got)
    assert "{{F1}} = three countries" in sheet and "{{F2}} = 60.8%" in sheet
    more, _ = facts.compute([{"label": "again", "expr": "cell('panel','CAN','top_dest_share_pct')", "unit": "%"},
                             {"label": "new", "expr": "median('panel','vulnerability')", "unit": "score"}], t, start=3, existing=got)
    assert [f["id"] for f in more] == ["F3"]          # a repeated expression is not a new fact


# ------------------------------------------------------------------ charts

def _catalog(t, tmp_path):
    return tables.write_datasets(tmp_path, t)


def test_a_chart_takes_its_values_from_the_table_and_refuses_what_is_not_there(tmp_path):
    t = _tables()
    cat = {d["id"]: d for d in _catalog(t, tmp_path)}
    fs, _ = facts.compute([{"label": "median", "expr": "median('panel','top_dest_share_pct')", "unit": "%"}], t)
    fmap = {f["id"]: f for f in fs}
    spec = {"id": "markets", "form": "bars", "table": "panel", "rows": {"sort": "top_dest_share_pct", "limit": 4}, "value": "top_dest_share_pct",
            "highlight": ["CAN"], "headline": "Mexico sells most to one market; the median is {{F1}}", "title": "Largest market", "subtitle": "% of exports",
            "alt": "Bars", "reference": {"fact": "F1", "label": "Median"}}
    ch = charts.build(spec, t, fmap, cat)
    assert [c["id"] for c in ch["categories"]] == ["MEX", "CAN", "RUS", "KOR"] and ch["categories"][0]["value"] == 74.9
    assert ch["axes"]["x"]["domain"][0] == 0 and ch["headline"]["en"].endswith("29.8%")
    assert ch["table"]["rows"][0] == {"label": "Mexico", "top_dest_share_pct": 74.9}
    assert ch["meta"]["sources"] == ["ds-country"] and "UN Comtrade" in ch["meta"]["attribution"]["en"] and ch["referenceLines"][0]["value"] == pytest.approx(29.8)
    for bad in ({**spec, "value": "nope"}, {**spec, "rows": ["CAN", "ZZZ"]}, {**spec, "table": "missing"}, {**spec, "form": "pie"},
                {**spec, "headline": ""}, {**spec, "rows": {"where": "__import__('os')"}}, {**spec, "rows": {"where": "top 5 by share"}}):
        with pytest.raises(charts.ChartError):
            charts.build(bad, t, fmap, cat)
    import re
    allow = [re.compile(p) for p in __import__("artools.checks", fromlist=["x"]).rules()["number_allow"]]
    assert charts.typed_numbers({"id": "x", "headline": "Canada sends 60.8% to the US in 2026"}, allow) != []
    assert charts.typed_numbers({"id": "x", "headline": "Canada sends {{F1}} to the US in Q2 2026"}, allow) == []


# ------------------------------------------------------------------ leads and watch

def test_the_screens_find_the_join_and_the_ledger_stops_repeats(tmp_path, monkeypatch):
    monkeypatch.setattr(leads, "LEDGER", tmp_path / "ledger.jsonl")
    p = _panel()
    found = leads.same_partner(p, None)
    assert found and found[0]["key"] == "same-partner" and set(found[0]["economies"]) == {"CAN", "MEX", "PRT"}
    left = leads.funding_against_exports(p, None)
    assert left == []                                    # two economies with outflows: below the screen's threshold of three
    monkeypatch.setattr(leads, "SCREENS", (leads.same_partner,))
    assert [l["key"] for l in leads.find(p, None, [])] == ["same-partner"]
    leads.record({"key": "same-partner", "screen": "same_partner", "outcome": "queued"})
    assert leads.find(p, None, []) == []                 # used within the cooldown
    assert leads._prev_quarter("2026-03-31") == "2025-12-31" and leads._prev_quarter("2026-06-30") == "2026-03-31"


def test_a_recent_note_about_an_economy_lowers_its_leads(tmp_path, monkeypatch):
    monkeypatch.setattr(leads, "LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(leads, "RUNS", tmp_path)
    (tmp_path / "r1" / "desk").mkdir(parents=True)
    (tmp_path / "r1" / "desk" / "brief.json").write_text(json.dumps({"focus": ["MEX"], "economies": ["MEX", "CAN", "USA"]}))
    p = _panel()
    monkeypatch.setattr(leads, "SCREENS", (leads.same_partner,))
    before = leads.find(p, None, [])[0]["score"]
    leads.record({"key": "other-lead", "screen": "movers", "run": "r1", "outcome": "queued"})
    after = leads.find(p, None, [])[0]
    assert leads.subjects("r1") == ["MEX"] and after["covered_recently"] == {"MEX": after["covered_recently"]["MEX"]}
    assert after["score"] < before                       # same-partner's first economies are MEX and CAN: half covered


def _hist(values, v=None):
    qs = [f"{2005 + i // 4}-{(3, 6, 9, 12)[i % 4]:02d}-{(31, 30, 30, 31)[i % 4]}" for i in range(len(values))]
    return [{"quarter": q, "j1": 6.0, "j2": x, "v": (v[i] if v else 40.0)} for i, (q, x) in enumerate(zip(qs, values))]


def test_history_screens_read_an_economy_against_its_own_past():
    p = _panel()
    calm = [20.0 + (i % 3) for i in range(40)]
    wobble = [40.0 + ((i * 2) % 7) / 2 for i in range(40)]                                     # the score moves a little, as scores do
    p["_hist"] = {"KOR": _hist(calm[:-1] + [35.0], v=wobble),                                 # a five-year high, score flat
                  "JPN": _hist(calm), "CAN": _hist(calm), "MEX": _hist(calm)}
    ext = [l for l in leads.own_extremes(p, None) if l["key"].startswith("history-j2")]
    assert ext and ext[0]["economies"][0] == "KOR" and ext[0]["numbers"]["KOR"]["now"] == 35.0
    dec = leads.decoupled(p, None)
    assert dec and dec[0]["economies"] == ["KOR"] and dec[0]["numbers"]["KOR"]["own_z_of_change"] >= 2
    p["_hist"]["KOR"] = _hist(calm[:-1] + [35.0], v=[40.0] * 39 + [60.0])                       # the score moved too: not decoupled
    assert leads.decoupled(p, None) == []


def test_charts_must_carry_the_note_and_show_the_join(tmp_path):
    t = _tables()
    cat = _catalog(t, tmp_path)
    cmap = {d["id"]: d for d in cat}
    fs, _ = facts.compute([{"label": "median", "expr": "median('panel','top_dest_share_pct')", "unit": "%"}], t)
    fmap = {f["id"]: f for f in fs}
    base = {"table": "panel", "headline": "h", "title": "t", "subtitle": "s", "alt": "a", "howToRead": "r"}
    assert charts.MAX_ROWS["table"] == 6                # a table is a small summary, never a data dump
    assert len(charts.build({**base, "id": "small", "form": "table", "columns": ["top_dest_share_pct"]}, t, fmap, cmap)["table"]["rows"]) == 6
    with pytest.raises(charts.ChartError):
        charts.build({**base, "id": "wide", "form": "table", "columns": ["vulnerability", "flow_pct", "top_dest_share_pct",
                                                                          "exports_yoy_pct", "bank_loans_usd_bn"]}, t, fmap, cmap)
    sc = charts.build({**base, "id": "join", "form": "scatter", "x": "top_dest_share_pct", "y": "top_lender_share_pct"}, t, fmap, cmap)
    bars = charts.build({**base, "id": "flow", "form": "bars", "value": "flow_pct", "rows": {"where": "flow_pct > 0"}}, t, fmap, cmap)
    assert review.chart_sides(sc, cat) >= {"funding", "trade"} and review.chart_sides(bars, cat) == {"funding"}


def test_get_the_data_lists_each_view_with_its_page_and_api_call(tmp_path):
    from artools.desk import reproduce
    t = _tables()
    t["pair"] = {**t["country"], "name": "pair", "app": "global-network", "path": "global-network/pairs/CAN/USA",
                 "params": {}, "title": "Canada and United States", "cite": "https://global-network.datasteg.com/en/c/CAN/with/USA"}
    cat = _catalog(t, tmp_path)
    draft = {"sections": [{"id": "a", "blocks": [{"type": "p", "text": "Text [[ds-panel]] and [[ds-pair]]."}]}]}
    r = reproduce.build(draft, [], {}, cat, t, {"focus": ["CAN"]})
    apis = {i["api"] for i in r["items"]}
    assert "https://api.datasteg.com/v1/money-flow/board?release=20261114.1" in apis       # money-flow keeps releases: pinned
    assert "https://api.datasteg.com/v1/global-network/pairs/CAN/USA" in apis              # the others are not
    assert all("ds-panel" not in i["api"] for i in r["items"])                              # the desk's join stands for its inputs
    assert r["code"].count("curl -s") == len(r["code"].splitlines()) and "format=csv" in r["code"]
    ko = reproduce.localise(r, "ko")
    assert {i["page"] for i in ko["items"]} >= {"https://global-network.datasteg.com/ko/c/CAN/with/USA"}
    assert [i["api"] for i in ko["items"]] == [i["api"] for i in r["items"]] and ko["docs"].endswith("/ko/technology/api")


def test_the_watch_tells_a_new_period_from_a_re_read():
    before = {"apps": {"money-flow": "20261113.1"}, "periods": {"board_quarter": "2026-03-31"},
              "datasets": {"bis.LBS": {"vintage": "2026-07-30", "newest": "2026-03-31", "name": "BIS LBS", "publisher": "BIS"},
                           "imf.WEO": {"vintage": "2026-10-14", "newest": "2031", "name": "IMF WEO", "publisher": "IMF"}}, "research": {}}
    now = {"apps": {"money-flow": "20261114.1"}, "periods": {"board_quarter": "2026-06-30"},
           "datasets": {"bis.LBS": {"vintage": "2026-10-30", "newest": "2026-06-30", "name": "BIS LBS", "publisher": "BIS"},
                        "imf.WEO": {"vintage": "2026-11-09", "newest": "2031", "name": "IMF WEO", "publisher": "IMF"}}, "research": {}}
    ch = watch.changes(now, before)
    kinds = [(c["kind"], c.get("dataset")) for c in ch]
    assert kinds[0] == ("period", "bis.LBS") and ("vintage", "imf.WEO") in kinds and ("release", None) in kinds
    assert "board" in ch[0]["views"]
    assert watch.changes(now, now) == []


# ------------------------------------------------------------------ the hard rules

def _draft():
    return {"kicker": "Funding and trade", "title": "In three economies the largest lender is also the largest customer",
            "dek": "In {{F1}} of the group the two coincide.", "keyNumbers": [{"value": "{{F1}}", "label": "economies", "cite": ["ds-panel"]}],
            "findings": ["a {{F1}}", "b", "c"], "question": {"asked": "q", "lookedAt": "l"},
            "sections": [{"id": "finding", "heading": "The finding", "blocks": [{"type": "p", "text": "US banks hold {{F2}} of loans to Canada [[ds-panel]]."}]},
                         {"id": "limits", "heading": "Limits", "blocks": [{"type": "p", "text": "Periods differ."}]},
                         {"id": "method", "heading": "How we counted", "blocks": [{"type": "p", "text": "We joined two tables."}]}],
            "insight": {"label": "Our read", "text": "Watch the lender."}, "citations": {"ds-panel": {"used_for": "the join"}}}


def test_consolidation_needs_a_number_that_reads_both_sides(tmp_path):
    t = _tables()
    cat = _catalog(t, tmp_path)
    fs, _ = facts.compute([
        {"label": "joined", "expr": "count('panel','top_lender_iso == top_dest_iso')", "unit": "countries"},
        {"label": "funding only", "expr": "cell('panel','CAN','top_lender_share_pct')", "unit": "%"}], t)
    con = review.consolidation(_draft(), fs, t, cat)
    assert con["joined_facts"] == ["F1"] and set(con["apps"]) == {"money-flow", "global-network"} and {"BIS", "UN Comtrade"} <= set(con["publishers"])
    one_sided = json.loads(json.dumps(_draft()).replace("{{F1}}", "{{F2}}"))
    assert review.consolidation(one_sided, fs, t, cat)["joined_facts"] == []


def test_the_reader_text_has_no_marks_and_the_review_text_keeps_fact_ids():
    t = _tables()
    fs, _ = facts.compute([{"label": "joined", "expr": "count('panel','top_lender_iso == top_dest_iso')", "unit": "countries"},
                           {"label": "share", "expr": "cell('panel','CAN','top_lender_share_pct')", "unit": "%"}], t)
    fmap = {f["id"]: f for f in fs}
    reader = text.article(_draft(), fmap, {}, "reader")
    assert "US banks hold 50.0% of loans to Canada." in reader and "[[" not in reader and "{" not in reader
    marked = text.article(_draft(), fmap, {}, "review")
    assert "50.0% {F2}" in marked and "[[ds-panel]]" in marked and "[section id: limits]" in marked


def test_lexicon_flags_codes_and_forecasts():
    assert review.CODES.search("its J3 signal fired") and review.CODES.search("score V of 60") and not review.CODES.search("{{F12}} and G20")
    assert review.FORECAST.search("exports will fall next year") and not review.FORECAST.search("if the lender cut, exports would fall")
    assert review.CAUSAL.search("the outflow was driven by") and review.CAUSAL.search("tariffs caused the fall") and not review.CAUSAL.search("went together with")


# ------------------------------------------------------------------ the bar

def test_the_bar_is_the_benchmarks_upper_quartile_and_blocking_issues_shelve(tmp_path, monkeypatch):
    monkeypatch.setattr(judge, "BENCH", tmp_path)
    cfg = config.load()
    assert judge.bar(cfg)["pass_mean"] == cfg["quality"]["min_overall"] and judge.bar(cfg)["from"] == "configured floor"
    pieces = {f"p{i}": {"mean": m, "dims": {k: m for k in judge.DIMS}} for i, m in enumerate([2.7, 3.0, 3.1, 3.3, 3.5, 3.6, 3.9, 4.0])}
    (tmp_path / "scores.json").write_text(json.dumps({"pieces": pieces, "summary": judge._summary(pieces)}))
    b = judge.bar(cfg)
    assert b["from"] == "the benchmark set's upper quartile" and 3.6 <= b["pass_mean"] <= 3.9
    good = {"mean": 4.1, "dims": {k: 4.1 for k in judge.DIMS}}
    assert judge.decide(good, b, [], cfg)["status"] == "pass"
    assert judge.decide(good, b, [{"issue": "x"}], cfg)["status"] == "shelve"
    assert judge.decide({"mean": 4.1, "dims": {**good["dims"], "D5": 2.5}}, b, [], cfg)["status"] == "shelve"
    assert judge.decide({"mean": 3.4, "dims": {k: 3.4 for k in judge.DIMS}}, b, [], cfg)["status"] == "shelve"


def test_the_judge_reads_a_benchmark_without_its_outlet(tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("TITLE: A title\nOUTLET: Some Bank Blog\nDATE: 2026-01-02\nAUTHORS: A. Person\nURL: https://example.org/x\n\nBody text.\n\nFIGURE: A chart\n\n"
                 "--- NOTES AND REFERENCES (not counted in body words) ---\n[1] A note.\n")
    b = judge.blind(f)
    assert b.startswith("A title\n\n2026-01-02\n\nBody text.") and "Some Bank Blog" not in b and "example.org" not in b and "[1] A note." in b


# ------------------------------------------------------------------ the editor's decision

def test_only_the_admin_apps_own_log_line_is_a_decision():
    good = {"id": "20261114-abc", "run": "20261114-desk", "digest": "d" * 20, "decision": "approve", "note": "", "at": "2026-11-14T00:00:00Z"}
    log = "\n".join([
        f"admin-1         | 2026-11-14T11:00:00.1Z DESK-DECISION {json.dumps(good)}",
        f'proxy-1         | 2026-11-14T11:00:01.1Z 1.2.3.4 - - [x] admin.example GET - "/DESK-DECISION {json.dumps(good)}" HTTP/1.1',
        f"proxy-1         | 2026-11-14T11:00:02.1Z DESK-DECISION {json.dumps({**good, 'id': 'forged'})}",
        "admin-1         | 2026-11-14T11:00:03.1Z DESK-DECISION {not json}",
        f"admin-1         | 2026-11-14T11:00:04.1Z DESK-DECISION {json.dumps({**good, 'id': 'x2', 'decision': 'publish-now'})}",
    ])
    assert [d["id"] for d in queue.parse_log(log)] == ["20261114-abc"]


def test_a_decision_applies_only_to_the_version_the_editor_saw(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "RUNS", tmp_path)
    monkeypatch.delenv("DESK_SIGNING_KEY", raising=False)
    monkeypatch.setattr(queue, "env_value", lambda name: None)
    monkeypatch.setattr(queue.korean, "status", lambda r: {"complete": True, "written": True, "open": []})   # the Korean edition has its own tests below
    run = tmp_path / "20261114-desk"
    for d in ("desk", "draft", "analysis", "charts"):
        (run / d).mkdir(parents=True)
    (run / "desk" / "result.json").write_text(json.dumps({"status": "queued", "lead": "same-partner"}))
    (run / "draft" / "en.json").write_text(json.dumps(_draft()))
    dg = queue.digest(run)
    d = {"id": "a1", "run": run.name, "digest": dg, "decision": "approve", "note": "", "at": "2026-11-14T00:00:00Z"}
    assert queue.check_decision(d) is None
    assert "no such desk run" in queue.check_decision({**d, "run": "../../etc"})
    assert "no such desk run" in queue.check_decision({**d, "run": "20261114-other"})
    (run / "draft" / "en.json").write_text(json.dumps({**_draft(), "title": "Changed after review"}))
    assert "changed after the editor saw it" in queue.check_decision(d)
    # with a signing key on this machine, an unsigned or wrongly signed line is refused
    d2 = {**d, "digest": queue.digest(run)}
    monkeypatch.setattr(queue, "env_value", lambda name: "k" * 40)
    assert "signature" in queue.check_decision(d2)
    assert queue.check_decision({**d2, "sig": queue._signature(d2, "k" * 40)}) is None
    # a note that is published is no longer open to a decision
    monkeypatch.setattr(queue, "env_value", lambda name: None)
    (run / "publish.json").write_text(json.dumps({"tag": "20261114.1"}))
    assert "not waiting" in queue.check_decision(d2)


def test_sync_applies_each_decision_once(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "DECISIONS", tmp_path / "decisions.jsonl")
    applied = []
    monkeypatch.setattr(queue, "apply", lambda d, dry_run=False: applied.append(d["id"]) or {"id": d["id"], "applied": True})
    lines = [{"id": "a", "run": "r", "digest": "x", "decision": "approve"}, {"id": "b", "run": "r", "digest": "x", "decision": "reject"}]
    assert queue.sync(lines=lines)["new"] == 2 and queue.sync(lines=lines)["new"] == 0 and applied == ["a", "b"]


# ------------------------------------------------------------------ roles and the pipeline file

def test_role_briefs_exist_and_include_the_standard():
    for r in config.load()["roles"]:
        b = roles.brief(r)
        assert "@include" not in b and len(b) > 400, r
    assert "What a note never does" in roles.brief("writer") and "Template: data note" in roles.brief("writer")
    assert "data desk" not in roles.brief("reader").split("\n", 3)[3][:0]     # the test reader is not told the house rules
    assert "What a note never does" not in roles.brief("reader") and "What a note never does" not in roles.brief("judge")
    # Fable only polishes the finished editions (19 Nov 2026, the owner); every other role is Opus or Sonnet
    assert all("fable" not in v["model"] for r, v in config.load()["roles"].items() if not r.startswith("polish-"))
    assert all("fable" in config.role(r)["model"] for r in ("polish-en", "polish-ko"))


def test_json_is_read_from_a_fenced_block_or_bare():
    assert roles.extract_json('Here:\n```json\n{"a": 1}\n```\n') == {"a": 1}
    assert roles.extract_json('{"a": {"b": 2}}') == {"a": {"b": 2}}
    with pytest.raises(roles.RoleError):
        roles.extract_json("no json here")


def test_the_data_note_pipeline_is_a_desk_pipeline_with_one_gate():
    p = pipelines.load("data-note")
    assert [s["gate"] for s in p["steps"] if "gate" in s] == ["publish"] and p["shape"]["gates"] == 1
    assert all(sum(k in s for k in pipelines.KINDS) == 1 for s in p["steps"])
    assert p["steps"][-1].get("manual") and p["steps"][-1].get("desk") == "publish"
    assert [s["desk"] for s in p["steps"] if s.get("desk")][:3] == ["watch", "leads", "editor"]


def test_the_driver_leaves_desk_runs_to_the_desk(tmp_path, monkeypatch):
    from artools import drive as drv
    run = tmp_path / "20261114-desk"
    (run / "logs").mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"id": run.name, "pipeline": "data-note", "stages": {}, "gates": {"publish": {"approved": False}}}))
    monkeypatch.setattr(drv, "run_dir", lambda _: run)
    called = []
    monkeypatch.setattr(drv, "run_skill", lambda *a, **k: called.append(a) or True)
    assert drv._drive(run, None, None, True) == 2 and called == []


# ------------------------------------------------------------------ the day

def _daily(monkeypatch, tmp_path, waiting=(), changed=(), spent=0.0, month_has_note=True, schedule=None):
    """desk daily with every outside call replaced; returns what it decided about today's note. The hourly schedule's
    gates (from 09:00, one note a day) are open unless `schedule` is given: they have their own test."""
    from artools.desk import run as run_mod
    import artools.desk.api as api_mod
    cfg = queue.config.load()
    cfg["schedule"] = schedule or {"note_from_hour": 0, "notes_per_day": 99}
    monkeypatch.setattr(queue.config, "load", lambda: cfg)
    monkeypatch.setattr(queue, "DESK", tmp_path)
    monkeypatch.setattr(queue, "proof_pdf", lambda r: {"blocking": [], "advisory": []})
    wrote = []
    runs = [tmp_path / f"{queue.dt.date.today():%Y%m%d}-desk-{i}" for i in range(len(waiting) or (1 if month_has_note else 0))]
    monkeypatch.setattr(queue, "sync", lambda **k: {"new": 0})
    monkeypatch.setattr(queue, "desk_runs", lambda: runs)
    monkeypatch.setattr(queue, "state", lambda r: (list(waiting) + ["published"] * 9)[runs.index(r)])
    monkeypatch.setattr(queue, "spent_today", lambda: spent)
    monkeypatch.setattr(queue, "export", lambda deploy=False, **k: {"deploy": deploy})
    monkeypatch.setattr(queue.korean, "status", lambda r: {"complete": True, "written": True, "open": []})
    monkeypatch.setattr(queue.korean, "make", lambda r, **k: 1 / 0)      # never a real qkr or claude call in a test
    monkeypatch.setattr(api_mod, "Api", lambda *a, **k: None)
    monkeypatch.setattr(watch, "snapshot", lambda api: {})
    monkeypatch.setattr(watch, "load", lambda: {})
    monkeypatch.setattr(watch, "changes", lambda now, before: list(changed))
    monkeypatch.setattr(run_mod, "note", lambda *a, **k: wrote.append(1) or {"status": "queued"})
    out = queue.daily(force=False, deploy=False)
    return out["note"], wrote


def test_the_hourly_daily_writes_one_note_a_day_after_the_morning_data_and_never_twice_at_once(tmp_path, monkeypatch):
    fresh = [{"app": "money-flow", "kind": "period", "what": "BIS LBS: newest 2026-03-31 → 2026-06-30", "views": ["board"]}]
    late = {"note_from_hour": 0, "notes_per_day": 1}
    note, wrote = _daily(monkeypatch, tmp_path, changed=fresh, schedule=late)       # today's run exists (month_has_note)
    assert wrote == [] and "already tried" in note["skipped"]
    note, wrote = _daily(monkeypatch, tmp_path, changed=fresh, month_has_note=False, schedule=late)
    assert wrote == [1]
    note, wrote = _daily(monkeypatch, tmp_path, changed=fresh, month_has_note=False, schedule={"note_from_hour": 24, "notes_per_day": 1})
    assert wrote == [] and "from 24:00" in note["skipped"]                           # never before the apps' morning data
    import fcntl
    with (tmp_path / "daily.lock").open("w") as held:                               # an hour-long revise still running
        fcntl.flock(held, fcntl.LOCK_EX)
        assert "still running" in queue.daily(deploy=False)["skipped"]


def test_an_unchanged_queue_keeps_its_build_time_so_the_admin_site_is_not_redeployed(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "LEDGER", tmp_path)
    monkeypatch.setattr(queue, "DECISIONS", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(queue, "desk_runs", lambda: [])
    monkeypatch.setattr(queue.judge_mod, "bar", lambda cfg: 3.594)
    queue.export()
    first = queue.read_json(tmp_path / "queue.json")
    monkeypatch.setattr(queue.runlib, "now", lambda: "2099-01-01T00:00:00Z")
    queue.export()
    assert queue.read_json(tmp_path / "queue.json")["built"] == first["built"]
    (tmp_path / "decisions.jsonl").write_text('{"id": "d1"}\n')
    queue.export()
    assert queue.read_json(tmp_path / "queue.json")["built"] == "2099-01-01T00:00:00Z"


def test_daily_writes_when_data_changed_and_nothing_waits(tmp_path, monkeypatch):
    fresh = [{"app": "money-flow", "kind": "period", "what": "BIS LBS: newest 2026-03-31 → 2026-06-30", "views": ["board"]}]
    note, wrote = _daily(monkeypatch, tmp_path, changed=fresh)
    assert wrote == [1] and note == {"status": "queued"}
    note, wrote = _daily(monkeypatch, tmp_path, waiting=["queued"], changed=fresh)      # the editor has one to read first
    assert wrote == [] and "wait for the editor" in note["skipped"]
    note, wrote = _daily(monkeypatch, tmp_path, changed=fresh, spent=99.0)               # the day's budget is a hard stop
    assert wrote == [] and "budget" in note["skipped"]
    monkeypatch.setattr(queue.dt, "date", type("D", (queue.dt.date,), {"today": classmethod(lambda c: queue.dt.date(2026, 11, 17))}))   # a Tuesday
    note, wrote = _daily(monkeypatch, tmp_path, changed=[{"app": "trade-flow", "kind": "release", "what": "x", "views": []}])
    assert wrote == [] and "no new data" in note["skipped"]                             # a rebuilt app with the same data is not news


# ------------------------------------------------------------------ the panel's own joins

class _FakeApi:
    """The four views the panel reads, for two economies."""
    def __init__(self):
        self.used = []

    def release(self, app):
        return "20261114.1"

    def get(self, path, **params):
        meta = {"cite": f"https://x.datasteg.com/{path}", "release": "20261114.1", "period": {"shown": "2026-06-30"}, "sources": []}
        if path == "money-flow/board":
            cols = ["economy", "name", "vulnerability", "flow_pct"]
            return {"data": {"quarter": "2026-06-30"}, "meta": meta,
                    "table": {"columns": [{"id": c} for c in cols], "rows": [["CAN", "Canada", 58.0, 13.8], ["SAU", "Saudi Arabia", 52.2, 6.8]]}}
        if path == "money-flow/sovereign":
            return {"data": {"economies": []}, "meta": meta}
        if path == "global-network/stress":
            return {"data": {"quarter": "2026-06-30", "period": {"shown": "2026-06-30"}, "economies": [
                {"economy": "CAN", "values": {"J1": 2.0, "J2": 40.0, "J5": 50.0}, "trade_window_to": "2026-06", "partial": False},
                {"economy": "SAU", "values": {"J1": None, "J2": 30.0, "J5": 0.0}, "trade_window_to": "2026-04", "partial": True,
                 "j1_not_meaningful": "net reserves are negative"}]}, "meta": meta}
        iso = path.rsplit("/", 1)[1]
        lender = {"CAN": ("USA", "United States", 50), "SAU": ("GBR", "UK", 29)}[iso]
        dests = {"CAN": [("USA", "United States", 60.8, True), ("CHN", "China", 4.9, True)],
                 "SAU": [("S19", "Asia, not elsewhere specified", 38.2, False), ("CHN", "China", 15.0, True)]}[iso]
        aq = {"CAN": ("2025-07", "2026-06", False), "SAU": ("2025-05", "2026-04", True)}[iso]
        return {"meta": meta, "data": {"region": "x", "advanced": True,
                "periods": {"funding_quarter": "2026-06-30", "bank_lenders_quarter": "2026-06-30", "goods_window": {"from": "2025-08", "to": "2026-07"},
                            "goods_window_at_quarter": {"quarter": "2026-06-30", "from": aq[0], "to": aq[1], "partial": aq[2]}},
                "funding": {"bank_lenders": {"total_loans_usd_bn": 90.0, "all_reporters_total_usd_bn": 100.0,
                                             "top": [{"lender": lender[0], "name": lender[1], "share_of_loans_pct": lender[2]}]}},
                "trade": {"exports_12m_usd_bn": 999.0, "exports_12m_newest_usd_bn": 999.0, "exports_12m_at_quarter_usd_bn": 400.0,
                          "exports_yoy_at_quarter_pct": 5.0, "exports_yoy_pct": 9.9,
                          "destinations": [{"partner": a, "name": b, "share_pct": c, "economy": d} for a, b, c, d in dests]}}}


def test_the_panel_joins_the_window_at_the_quarter_and_never_shows_asia_unspecified_as_a_market():
    p = panel_mod.build(_FakeApi())
    can, sau = p["rows"]["CAN"], p["rows"]["SAU"]
    # the trade columns are the window joined at the funding quarter, not the newest window (rule C2, 20261116-desk)
    assert can["exports_12m_usd_bn"] == 400.0 and can["exports_yoy_pct"] == 5.0 and can["goods_window_to"] == "2026-06"
    assert sau["goods_window_partial"] is True
    # loans over all BIS reporters at the same quarter, over the window at that quarter
    assert can["bank_loans_usd_bn"] == 100.0 and can["bank_loans_pct_exports"] == 25.0
    # the overlap is J5 from the stress board, over all partners, not a top-five sum
    assert can["lender_dest_overlap_pct"] == 50.0 and "exports_to_top_lender_pct" not in can
    # UN Comtrade 490 is not a market
    assert sau["top_dest"] == "China" and sau["exports_unspecified_asia_pct"] == 38.2
    assert panel_mod.views_of(["vulnerability", "top_dest_share_pct"]) == ["board", "country"]


def test_a_fact_may_not_multiply_measures_of_periods_that_do_not_belong_together():
    p = panel_mod.build(_FakeApi())
    t = {"panel": tables.from_panel(p)}
    # a quarter-end stock against the goods window joined at that quarter: allowed, and the period is the window
    v, _ = facts.evaluate("cell('panel','CAN','bank_loans_usd_bn') / cell('panel','CAN','exports_12m_usd_bn')", t)
    assert v == 0.25
    fs, probs = facts.compute([{"label": "x", "expr": "cell('panel','CAN','exports_12m_usd_bn')", "unit": "USD bn"}], t)
    assert fs[0]["period"] == "2025-07/2026-06"
    # a stock at the quarter against the share of the newest window: refused (the 251.6 bn of 20261116-desk)
    with pytest.raises(facts.FactError, match="rule C2"):
        facts.evaluate("cell('panel','CAN','bank_loans_usd_bn') * cell('panel','CAN','top_dest_share_pct')", t)
    # one measure with itself over time is fine
    t["panel_prev"] = dict(t["panel"], name="panel_prev", period={"funding_quarter": "2026-03-31"})
    facts.evaluate("cell('panel','CAN','bank_loans_usd_bn') / cell('panel_prev','CAN','bank_loans_usd_bn')", t)


# ------------------------------------------------------------------ the Korean edition (qkr drafts every string)

def test_the_english_sent_to_qkr_carries_what_the_korean_will_need():
    n = korean.normalise
    assert n("At end-June 2026 the US held it.") == "At the end of 2026-06 the United States held it."
    assert n("over the twelve months to June 2026") == "over the 12 months to 2026-06"
    assert n("the July trade window") == "the July (month 7) trade window"
    assert n("ranks fifth of all 36 economies; the first-round loss is zero") == "ranks 5th of all 36 economies; the 1st-round loss is 0"
    assert n("in Q2 2026, after 2010-Q4") == "in quarter 2 of 2026, after quarter 4 of 2010"
    from artools.content import render_fact
    five_bn = render_fact({"value": 5, "unit": "USD bn", "display": {"decimals": 0}}, "ko")     # the pipeline's own Korean form of the amount
    assert n("US-located banks and USD 5 bn") == f"United States-located banks and {five_bn}"
    assert n("funding left in the quarter to June 2026, exports rose over the year to June 2026") == \
        "funding left in quarter 2 of 2026, exports rose over the 12 months to 2026-06"
    assert n("Exports may rise; the two sides, one of them") == "Exports may rise; the 2 sides, one of them"
    assert n("*only* three parts on 14 Nov 2026") == "only 3 parts on 2026-11-14"
    assert n("take a fifth or more; a split at four-fifths; a quarter's surplus") == "take 1/5 or more; a split at 4/5; a quarter's surplus"
    # what a rewording may add: only the digit form of what the English already says
    assert {"5", "20"} <= korean._word_numbers("take 1/5 or more") and "30" not in korean._word_numbers("take 1/5 or more")


def test_a_korean_answer_may_not_add_or_lose_a_number_or_a_citation():
    it = {"id": "d:dek", "kind": "draft", "path": ["dek"], "profile": "article",
          "sent": "At the end of 2026-06 Canada's loans equalled 140% of exports, against 13.1% for Mexico [[ds-country]]."}
    good = "2026년 6월말 캐나다의 차입은 수출의 140%, 멕시코는 13.1%였다 [[ds-country]]."
    assert korean.problems(it, good) == []
    assert any("numbers the English does not" in p for p in korean.problems(it, good.replace("140%", "141%")))
    assert any("lost numbers" in p for p in korean.problems(it, good.replace(", 멕시코는 13.1%였다", "였다")))
    assert any("citation marks differ" in p for p in korean.problems(it, good.replace(" [[ds-country]]", "")))
    assert any("line break" in p for p in korean.problems(it, good.replace(", ", "\n")))
    # a number the English has as a word may be a digit in Korean; a headline has the site's limit
    words = {**it, "sent": "the twelve months to the end of 2026-06"}
    assert korean.problems(words, "2026년 6월말까지 12개월") == []
    title = {"id": "d:title", "kind": "draft", "path": ["title"], "profile": "headline", "sent": "Canada borrows more"}
    assert any("characters" in p for p in korean.problems(title, "가" * (korean.TITLE_MAX + 1)))
    # a name whose last syllable was taken for a particle
    names = {**it, "sent": "France and Belgium left out"}
    assert any("Belgium is misspelt" in p for p in korean.problems(names, "프랑스·벨기은 제외"))
    assert korean.problems(names, "벨기에·프랑스 제외") == []


def _ko_run(tmp_path):
    run = tmp_path / "20261115-desk"
    (run / "draft").mkdir(parents=True); (run / "charts").mkdir(); (run / "analysis").mkdir(); (run / "desk").mkdir(); (run / "logs").mkdir()
    (run / "analysis" / "analysis.json").write_text(json.dumps({"facts": [
        {"id": "F1", "label": "share", "value": 49.5, "unit": "%", "formula": "x", "inputs": [], "publishable": True, "display": {"decimals": 1}}]}))
    (run / "draft" / "en.json").write_text(json.dumps({
        "kicker": "Funding and trade", "title": "Canada borrows more", "dek": "US-located banks held {{F1}} at end-June 2026 [[ds-a]].",
        "keyNumbers": [{"value": "{{F1}}", "label": "Share held"}], "findings": [], "question": {"asked": None},
        "sections": [{"id": "finding", "heading": "The finding", "blocks": [{"type": "p", "text": "It held {{F1}} [[ds-a]]."}, {"type": "figure", "chart": "c1"}]}],
        "insight": {}, "citations": {"ds-a": {"used_for": "The share"}}, "byline": "x", "disclaimer": "y"}))
    (run / "charts" / "c1.json").write_text(json.dumps({
        "id": "c1", "form": "bars", "headline": {"en": "Canada leads"}, "title": {"en": "Share held"}, "subtitle": {"en": "%"}, "alt": {"en": "Canada leads."},
        "notes": [], "axes": {"x": {"label": {"en": "Share held"}}}, "categories": [{"id": "CAN", "label": {"en": "Canada"}, "value": 49.5}],
        "table": {"columns": [{"key": "label", "label": {"en": "Economy"}}, {"key": "v", "label": {"en": "Share held"}}], "rows": [{"label": "Canada", "v": 49.5}]},
        "meta": {"definition": {"en": "Share held"}, "attribution": {"en": "BIS via datasteg"}}}))
    return run


def _fake_qkr(monkeypatch, refuse=()):
    """qkr as a table: an answer per English string, a fallback for the strings in `refuse`."""
    def http(path, body=None, timeout=0):
        if path == "/v1/health":
            return {"ok": True, "llama": "up", "model_version": "m", "style_version": "1.3", "checks_version": "9"}
        it = body["items"][0]
        assert it["ko"] == "" and body["service"] == "articles" and body["expect_style_version"] == "1.3"
        if it["en"] in refuse:
            return {"items": [{"id": it["id"], "status": "fallback", "ko": "", "proposed": "거절", "checks": {"figures": "fail: new or changed number ['6']"}}]}
        nums = " ".join(korean.NUM.findall(korean.CITE.sub(" ", it["en"])))
        marks = " ".join(m.group(0) for m in korean.CITE.finditer(it["en"]))
        locked = " ".join(it.get("locked") or [])           # qkr keeps locked words (datasteg's service names) as written
        return {"model_version": "m", "style_version": "1.3", "items": [{"id": it["id"], "status": "refined", "ko": f"한국어 {nums} {marks} {locked}".strip(), "checks": {"figures": "pass"}}]}
    monkeypatch.setattr(korean, "_http", http)
    monkeypatch.setattr(roles, "call", lambda run, role, packet, **k: {"data": {"issues": [], "terms": [], "items": []}})
    monkeypatch.setattr(korean, "names", lambda: {"Canada": "캐나다", "Belgium": "벨기에"})


def test_the_korean_edition_is_qkrs_answers_and_nothing_else(tmp_path, monkeypatch):
    run = _ko_run(tmp_path)
    _fake_qkr(monkeypatch)
    out = korean.make(run)
    assert out["complete"] and not out["open"]
    ko = json.loads((run / "draft" / "ko.json").read_text())
    assert ko["dek"] == "한국어 49.5 2026 06 [[ds-a]]"                   # qkr saw the number, the month as a number, the mark
    assert ko["keyNumbers"][0]["value"] == "{{F1}}"                      # a key number stays a fact token in both editions
    ch = json.loads((run / "charts" / "c1.json").read_text())
    assert ch["categories"][0]["label"]["ko"] == "캐나다" and ch["table"]["rows"][0]["label"] == {"en": "Canada", "ko": "캐나다"}
    assert ch["headline"]["ko"].startswith("한국어") and ch["meta"]["definition"]["ko"]
    assert korean.verify(run) == [] and korean.status(run)["complete"]
    # a Korean string that is not the ledger's qkr answer is refused, whoever wrote it
    ko["dek"] = ko["dek"].replace("한국어", "손으로 고친")
    (run / "draft" / "ko.json").write_text(json.dumps(ko))
    assert any("not qkr's answer" in p for p in korean.verify(run))
    # and when the English changes, the Korean edition is out of date until it is drafted again
    en = json.loads((run / "draft" / "en.json").read_text())
    en["dek"] = "Another sentence."
    (run / "draft" / "en.json").write_text(json.dumps(en))
    assert korean.status(run)["stale"] and not korean.status(run)["complete"]


def test_the_korean_edition_is_written_with_its_open_points_for_the_editor(tmp_path, monkeypatch):
    # 16 Nov 2026: the editor reviews the Korean in the admin site, so the edition is always there once qkr answered;
    # a string qkr could not draft to the checks shows qkr's own draft, flagged beside the note
    monkeypatch.setattr(queue, "RUNS", tmp_path)
    monkeypatch.setattr(queue, "env_value", lambda name: None)
    run = _ko_run(tmp_path)
    (run / "desk" / "result.json").write_text(json.dumps({"run": run.name, "status": "queued"}))
    (run / "desk" / "score.json").write_text(json.dumps({"verdict": {"status": "pass", "reasons": []}}))
    _fake_qkr(monkeypatch, refuse=("It held 49.5% [[ds-a]].",))
    out = korean.make(run)
    assert not out["complete"] and out["written"] and out["flagged"] == 1
    assert out["open"][0]["kind"] == "no-answer" and out["open"][0]["shown_from"] == "qkr"
    ko = json.loads((run / "draft" / "ko.json").read_text())
    led = {x["id"]: x for x in json.loads((run / "desk" / "korean.json").read_text())["strings"]}
    flagged = next(x for x in led.values() if x.get("shown"))
    assert flagged["shown"] == "거절" and flagged["status"] != "ok"           # qkr's refused draft, as qkr wrote it
    assert any(n["who"] == "qkr" and "figures" in n["check"] for n in out["qkr_notes"])
    assert korean.verify(run) == []                                           # the flagged string is qkr's, so it passes
    st = korean.status(run)
    assert st["written"] and not st["complete"]
    assert queue.settle(run)["status"] == "queued"                            # Korean open points do not hold the note
    d = {"id": "1", "run": run.name, "digest": queue.digest(run), "decision": "approve"}
    assert queue.check_decision(d) is None
    # a flagged string changed by hand is refused like any other
    path = flagged["path"]
    obj = ko
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = "손으로 고친 문장"
    (run / "draft" / "ko.json").write_text(json.dumps(ko, ensure_ascii=False))
    assert any("not qkr's answer" in x for x in korean.verify(run))


def test_a_note_without_a_korean_edition_is_held_and_cannot_be_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "RUNS", tmp_path)
    monkeypatch.setattr(queue, "env_value", lambda name: None)
    run = _ko_run(tmp_path)
    (run / "desk" / "result.json").write_text(json.dumps({"run": run.name, "status": "queued"}))
    (run / "desk" / "score.json").write_text(json.dumps({"verdict": {"status": "pass", "reasons": []}}))
    def down(path, body=None, timeout=0):
        raise korean.KoreanDown("qkr cannot be reached")
    monkeypatch.setattr(korean, "_http", down)
    korean.make(run)
    assert queue.settle(run)["status"] == "shelved" and "Korean" in queue.settle(run)["held"][0]
    d = {"id": "1", "run": run.name, "digest": queue.digest(run), "decision": "approve"}
    assert "Korean edition" in queue.check_decision(d)
    assert queue.check_decision({**d, "decision": "reject"}) is None          # a rejection needs no Korean
    _fake_qkr(monkeypatch)                                                      # qkr answers: the note waits for the editor
    assert korean.make(run)["complete"] and queue.settle(run)["status"] == "queued"
    assert queue.check_decision({**d, "digest": queue.digest(run)}) is None


def test_the_budget_counts_the_english_not_the_korean(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    line = lambda c: json.dumps({"type": "result", "total_cost_usd": c, "result": "{}"}) + "\n"   # noqa: E731
    (logs / "desk-writer.1.jsonl").write_text(line(2.5))
    (logs / "desk-korean.1.jsonl").write_text(line(4.0))
    assert roles.spent(tmp_path) == 2.5 and roles.spent(tmp_path, korean=True) == 6.5
    assert config.load()["budget"]["usd_per_note"] == 20.0


def test_a_chart_headline_is_short_with_two_numbers_at_most():
    cfg = config.load()["note"]
    def rules(headline):
        ch = {"id": "c1", "form": "bars", "headline": {"en": headline}, "meta": {"sources": []}}
        return [b for b in review.figure_rules({"whyNow": "BIS bank data to end-June 2026 show Canada at a high in its own past."},
                                               {"c1": ch}, {}, [], cfg) if b.startswith("figure c1")]
    assert rules("Canada owes foreign banks 140% of a year's exports, more than any economy in the group") == []
    assert any("3 numbers" in b for b in rules("Canada owes foreign banks 140% of exports, against 13.1% for Mexico and 55.4% overall"))
    assert any("characters" in b for b in rules("Canada's overlap of lenders and export markets, 59.1% in Q2 2026, sits just below "
                                                  "its own median of 61.2% since Q4 2010"))
    assert rules("In Q2 2026 Canada's overlap was 59.1%, under its median since 2010") == []   # years and quarters are not counted
    assert rules("Japan's funding flow since 2005, its lowest since 2019, sits near 19%") == []      # "2005," is a year too


def test_qkr_down_stops_the_step_and_writes_no_korean(tmp_path, monkeypatch):
    run = _ko_run(tmp_path)
    def down(path, body=None, timeout=0):
        raise korean.KoreanDown("qkr cannot be reached")
    monkeypatch.setattr(korean, "_http", down)
    out = korean.make(run)
    assert not out["complete"] and "cannot be reached" in out["error"] and not (run / "draft" / "ko.json").exists()


def test_the_checker_only_writes_english_and_qkr_writes_the_korean_again(tmp_path, monkeypatch):
    run = _ko_run(tmp_path)
    _fake_qkr(monkeypatch)
    sent, calls = [], []
    real = korean._http

    def http(path, body=None, timeout=0):
        if body:
            sent.append(body["items"][0])
            it = body["items"][0]
            if it.get("ko"):                                   # refine mode: qkr's own answer comes back, with the required term
                ko = it["ko"]
                for a, b in (it.get("terms") or {}).items():
                    ko = ko.replace(a, b)
                return {"items": [{"id": it["id"], "status": "refined", "ko": ko + " 다듬음", "checks": {}}]}
        return real(path, body, timeout)
    monkeypatch.setattr(korean, "_http", http)

    def role(run_, name, packet, **k):
        calls.append(name)
        if name == "ko-checker" and calls.count("ko-checker") == 1:
            return {"data": {"issues": [
                {"id": "d:dek", "kind": "meaning", "quote_ko": "한국어", "problem": "who holds what is swapped",
                 "en": "Banks located in the United States held 49.5% at the end of 2026-06 [[ds-a]]."},
                {"id": "d:title", "kind": "meaning", "problem": "a number was added", "en": "Canada borrows 99% more"},      # not usable: a new number
                {"id": "c:c1:alt", "kind": "untranslated", "quote_ko": "한국어", "problem": "a garbled word"}], "terms": []}}
        return {"data": {"issues": [], "terms": [], "items": []}}
    monkeypatch.setattr(roles, "call", role)
    out = korean.make(run)
    assert out["complete"] and not out["open"] and calls.count("ko-checker") == 2      # a second read after the fixes
    led = {s["id"]: s for s in json.loads((run / "desk" / "korean.json").read_text())["strings"]}
    assert led["d:dek"]["how"] == "reworded after the check" and led["d:dek"]["sent"].startswith("Banks located")
    # a rewording that adds a number is never sent: qkr refines its own answer for the English as it stands
    assert led["d:title"]["how"] == "refined after the check" and led["d:title"]["sent"] == "Canada borrows more"
    assert not any("99%" in (i.get("en") or "") for i in sent)
    assert led["c:c1:alt"]["how"] == "refined after the check" and led["c:c1:alt"]["ko"].endswith("다듬음")
    assert korean.verify(run) == []


def test_a_paragraph_qkr_cannot_draft_whole_goes_sentence_by_sentence(tmp_path, monkeypatch):
    run = _ko_run(tmp_path)
    en = json.loads((run / "draft" / "en.json").read_text())
    en["sections"][0]["blocks"][0]["text"] = "It held {{F1}} [[ds-a]]. The rest was small. Nothing else changed."
    (run / "draft" / "en.json").write_text(json.dumps(en))
    whole = "It held 49.5% [[ds-a]]. The rest was small. Nothing else changed."
    _fake_qkr(monkeypatch, refuse=(whole,))
    monkeypatch.setattr(roles, "call", lambda run_, name, packet, **k: {"data": {"issues": [], "terms": [], "items": []}})   # no rewording comes
    out = korean.make(run)
    led = {s["id"]: s for s in json.loads((run / "desk" / "korean.json").read_text())["strings"]}
    p = led["d:sections/0/blocks/0/text"]
    assert out["complete"] and p["how"] == "drafted sentence by sentence" and p["ko"].count("한국어") == 3 and "[[ds-a]]" in p["ko"]
    assert korean.verify(run) == []


# ------------------------------------------------------------------ 16 Nov 2026: why today, chart mix, the data download

def _history(t):
    t["stress_can"] = {"name": "stress_can", "app": "global-network", "path": "global-network/stress", "params": {"economy": "CAN"},
                       "key": ["quarter"], "columns": [{"id": "quarter"}, {"id": "j2", "label": "Financing need, % of exports", "unit": "%"}],
                       "rows": [{"quarter": f"20{y:02d}-06-30", "j2": 40.0 + y, "_key": f"20{y:02d}-06-30"} for y in range(15, 26)],
                       "title": "Canada's joint signals", "summary": "s", "cite": "https://global-network.datasteg.com/en/stress",
                       "release": None, "period": {"shown": "2025-06-30"}, "sources": [], "publishers": ["BIS", "UN Comtrade"], "notes": []}
    return t


def test_a_brief_needs_a_hook_the_packet_shows_and_a_reason_for_its_economies():
    from artools.desk import run as run_mod
    changed = [{"app": "money-flow", "kind": "period", "what": "BIS bank positions to 2026-06-30"},
               {"app": "open-research", "kind": "documents", "what": "new papers"}]
    research = [{"title": "Dollar funding and trade credit"}]
    shortlist = [{"key": "history-j2-highest-2026-06-30", "screen": "own_extremes"}, {"key": "spotlight-CAN", "screen": "spotlight"}]
    why = "Canada is the only one of the nine whose largest lender and buyer are the same."
    ok = {"hook": {"kind": "data", "ref": "C1", "what": "BIS published bank positions to end-June 2026 last week."}, "why_these": why}
    assert run_mod.check_hook(ok, changed, research, shortlist) == []
    assert run_mod.check_hook({**ok, "hook": {**ok["hook"], "kind": "research", "ref": "R1"}}, changed, research, shortlist) == []
    releases = [{"what": "BIS LBS: data to 2026-06-30, read on 2026-10-30", "views": ["board"]}]
    assert run_mod.check_hook({**ok, "hook": {**ok["hook"], "ref": "D1"}}, [], research, shortlist, releases) == []
    assert run_mod.check_hook({**ok, "hook": {**ok["hook"], "ref": "D2"}}, [], research, shortlist, releases)
    assert run_mod.check_hook({**ok, "hook": {**ok["hook"], "kind": "extreme", "ref": "history-j2-highest-2026-06-30"}}, changed, research, shortlist) == []
    # what the Canada note of 14 Nov had: no hook, "nothing changed", a lead that is only a ranking
    assert run_mod.check_hook({"why_now": "Nothing in the data changed since the last note.", "why_these": why}, changed, research, shortlist)
    assert run_mod.check_hook({**ok, "hook": {**ok["hook"], "ref": "C2"}}, changed, research, shortlist)          # papers are not data
    assert run_mod.check_hook({**ok, "hook": {**ok["hook"], "ref": "C9"}}, changed, research, shortlist)          # not in the packet
    assert run_mod.check_hook({**ok, "hook": {**ok["hook"], "kind": "extreme", "ref": "spotlight-CAN"}}, changed, research, shortlist)
    assert any("why_these" in p for p in run_mod.check_hook({**ok, "why_these": ""}, changed, research, shortlist))


def test_charts_use_forms_that_fit_their_points_and_a_history_is_a_line(tmp_path):
    t = _history(_tables())
    cat = _catalog(t, tmp_path)
    cmap = {d["id"]: d for d in cat}
    fmap = {}
    base = {"headline": "h", "title": "t", "subtitle": "s", "alt": "a", "howToRead": "r"}
    sc = lambda i, x="top_dest_share_pct", y="top_lender_share_pct": charts.build({**base, "id": i, "form": "scatter", "table": "panel", "x": x, "y": y}, t, fmap, cmap)  # noqa: E731
    bars = charts.build({**base, "id": "flow", "form": "bars", "table": "panel", "value": "flow_pct"}, t, fmap, cmap)
    line = charts.build({**base, "id": "own-past", "form": "line", "table": "stress_can", "series": [{"col": "j2"}]}, t, fmap, cmap)
    cfg = config.load()["note"]
    draft = {**_draft(), "whyNow": "BIS bank positions to end-June 2026 put Canada at its highest financing need since 2015."}
    rules = lambda chs: review.figure_rules(draft, {c["id"]: c for c in chs}, t, cat, cfg)  # noqa: E731
    # the Canada note: two scatters and a table, and the stress history it pulled never drawn
    two_scatters = rules([sc("sc-a"), sc("sc-b", "vulnerability"), bars])
    assert any("scatter charts" in p for p in two_scatters) and any("history" in p for p in two_scatters)
    assert rules([sc("sc-a"), bars, line]) == []
    assert any("whyNow" in p for p in review.figure_rules({**draft, "whyNow": "Nothing has changed, but the join is new and worth a look."},
                                                            {c["id"]: c for c in [sc("sc-a"), bars, line]}, t, cat, cfg))
    assert any("whyNow" in p for p in review.figure_rules(_draft(), {c["id"]: c for c in [sc("sc-a"), bars, line]}, t, cat, cfg))
    assert any("read the data" in p for p in review.figure_rules({**draft, "whyNow": "The BIS bank data for end-June 2026, read on 30 October, give Canada's newest loans."},
                                                                 {c["id"]: c for c in [sc("sc-a"), bars, line]}, t, cat, cfg))


def test_the_data_download_holds_every_table_chart_and_number(tmp_path):
    import zipfile
    from artools.desk import reproduce
    t = _history(_tables())
    cat = _catalog(t, tmp_path)
    cmap = {d["id"]: d for d in cat}
    fs, _ = facts.compute([{"label": "Canada's share", "expr": "cell('panel','CAN','top_dest_share_pct')", "unit": "%"}], t)
    fmap = {f["id"]: f for f in fs}
    base = {"headline": "h", "title": "t", "subtitle": "s", "alt": "a", "howToRead": "r"}
    line = charts.build({**base, "id": "own-past", "form": "line", "table": "stress_can", "series": [{"col": "j2"}]}, t, fmap, cmap)
    draft = {**_draft(), "dek": "Canada sells {{F1}} of its goods to one buyer [[ds-panel]]."}
    rep = reproduce.build(draft, fs, {"own-past": line}, cat, t, {"focus": ["CAN"]})
    dl = reproduce.bundle(tmp_path, draft, fs, {"own-past": line}, cat, t, rep)
    z = zipfile.ZipFile(tmp_path / "download" / "data.zip")
    names = set(z.namelist())
    assert {"README.txt", "numbers.csv", "charts/own-past.csv", "tables/panel.csv", "tables/stress-can.csv"} <= names
    assert dl["files"] == len(names) and dl["bytes"] == (tmp_path / "download" / "data.zip").stat().st_size
    nums = z.read("numbers.csv").decode()
    assert "F1" in nums and "cell('panel','CAN','top_dest_share_pct')" in nums
    assert "api.datasteg.com" in z.read("README.txt").decode()
    first = (tmp_path / "download" / "data.zip").read_bytes()
    reproduce.bundle(tmp_path, draft, fs, {"own-past": line}, cat, t, rep)
    assert (tmp_path / "download" / "data.zip").read_bytes() == first          # the same inputs give the same archive


def test_a_chart_never_prints_an_apps_code():
    assert charts.plain("J5 Dual dependence") == "Dual dependence" and charts.plain("Import cover") == "Import cover"
    assert charts.plain("A2 short-term debt / net reserves (%)") == "Short-term debt / net reserves (%)"


def test_normalised_english_is_not_normalised_twice_and_a_lead_is_a_first_place():
    once = korean.normalise("the partner ratio on the July trade window")
    assert once == korean.normalise(once) and once.count("(month 7)") == 1      # a rewording passes through again
    assert "1" in korean._word_numbers("The United States leads all three shares.")   # Korean writes 1위


def _title_qkr(monkeypatch, sent):
    """_fake_qkr, with headlines drafted per English and mode, and the feedback endpoint recorded in `sent`."""
    _fake_qkr(monkeypatch)
    base = korean._http
    drafts = {("Canada and Mexico on borrowing from United States banks compared: Canada borrows more", "fast"): "캐나다·멕시코 은행차입 비교: 캐나다 우위",
              ("Canada and Mexico on borrowing from United States banks compared: Canada borrows more", "careful"): "캐나다 은행 대출 비교",
              ("Canada borrows more than Mexico", "fast"): "캐나다, 멕시코보다 차입 많아"}

    def http(path, body=None, timeout=0):
        if path == "/v1/feedback":
            sent.append(body)
            return {"ok": True}
        if path == "/v1/refine" and body["items"][0]["profile"] == "headline" and (body["items"][0]["en"], body["mode"]) in drafts:
            it = body["items"][0]
            return {"items": [{"id": it["id"], "status": "refined", "ko": drafts[(it["en"], body["mode"])], "checks": {}}]}
        return base(path, body, timeout)
    monkeypatch.setattr(korean, "_http", http)

    def call(run, role, packet, **k):
        if role != "ko-title":
            return {"data": {"issues": [], "terms": [], "items": []}}
        if "## Task: angles" in packet:
            assert "English title: Canada borrows" in packet
            return {"data": {"angles": [{"en": "Canada and Mexico on borrowing from US banks compared: Canada borrows more"},
                                        {"en": "Canada borrows more than Mexico"}, {"en": "Canada borrows 99% more"}]}}   # a new number: dropped
        assert "## Task: pick" in packet and "캐나다·멕시코 은행차입 비교" in packet
        return {"data": {"best": "c1", "ranking": [
            {"id": "c0", "faithful": True, "form": 2, "pull": 2, "why": "a translated sentence"},
            {"id": "c1", "faithful": True, "form": 5, "pull": 4, "why": "topic first, a two-part contrast"},
            {"id": "c2", "faithful": False, "form": 3, "pull": 3, "why": "loans by Canada's banks: borrower and lender swapped"}]}}
    monkeypatch.setattr(roles, "call", call)


def test_the_korean_title_is_tuned_among_qkrs_drafts_and_the_best_faithful_one_is_used(tmp_path, monkeypatch):
    monkeypatch.setattr(polish_mod, "on", lambda lang: False)      # the title tuning runs only without the polish (19 Nov 2026)
    monkeypatch.setattr(korean, "TITLES", tmp_path / "titles-ko.jsonl")
    run = _ko_run(tmp_path)
    sent = []
    _title_qkr(monkeypatch, sent)
    out = korean.make(run)
    t = out["title"]
    assert t["from"] == "tuned" and t["ko"] == "캐나다·멕시코 은행차입 비교: 캐나다 우위" and t["chosen"] == "c1"
    assert [c["ko"] for c in t["candidates"]] == ["한국어", "캐나다·멕시코 은행차입 비교: 캐나다 우위", "캐나다 은행 대출 비교", "캐나다, 멕시코보다 차입 많아"]
    assert t["candidates"][2]["faithful"] is False                              # shown to the editor, never used
    assert json.loads((run / "draft" / "ko.json").read_text())["title"] == t["ko"]
    assert korean.verify(run) == []                                             # every word of the title is qkr's
    assert any(n["check"].startswith("title: ko-title chose") for n in out["qkr_notes"])
    assert any(b["verdict"] == "rejected" and b["ko_final"] == t["ko"] for b in sent)   # qkr hears its first draft lost
    # a second make with the same English keeps the tuned title and makes no new call
    monkeypatch.setattr(roles, "call", lambda run, role, packet, **k: {"data": {"issues": [], "terms": []}} if role != "ko-title" else 1 / 0)
    assert korean.make(run)["title"]["ko"] == t["ko"]


def test_the_editors_korean_title_is_used_as_written_kept_and_sent_to_qkr(tmp_path, monkeypatch):
    monkeypatch.setattr(polish_mod, "on", lambda lang: False)      # the title tuning runs only without the polish (19 Nov 2026)
    monkeypatch.setattr(korean, "TITLES", tmp_path / "titles-ko.jsonl")
    monkeypatch.setattr(queue, "RUNS", tmp_path)
    monkeypatch.setattr(queue, "env_value", lambda name: None)
    run = _ko_run(tmp_path)
    (run / "desk" / "result.json").write_text(json.dumps({"run": run.name, "status": "shelved"}))
    (run / "desk" / "score.json").write_text(json.dumps({"verdict": {"status": "shelve", "reasons": ["x"]}}))
    sent = []
    _title_qkr(monkeypatch, sent)
    korean.make(run)
    mine = "캐나다·멕시코 대미 은행차입 비교: 비중은 동일 수준"
    d = {"id": "t1", "run": run.name, "digest": queue.digest(run), "decision": "retitle", "title_ko": mine}
    assert queue.check_decision({**d, "title_ko": "two\nlines 한"}) and queue.check_decision({**d, "title_ko": None})
    assert queue.apply(d)["applied"]
    assert json.loads((run / "draft" / "ko.json").read_text())["title"] == mine
    assert queue.state(run) == "shelved" and not (run / "desk" / "decision.json").exists()   # still waiting for a decision
    st = korean.status(run)
    assert st["title"]["from"] == "editor" and st["title"]["editor"]["ko"] == mine and korean.verify(run) == []
    assert sent[-1]["verdict"] == "edited" and sent[-1]["ko_final"] == mine and sent[-1]["ko_model"] == "캐나다·멕시코 은행차입 비교: 캐나다 우위"
    assert any(n["check"] == "editor" and "colon" in n["lesson"] for n in st["qkr_notes"])
    assert json.loads((tmp_path / "titles-ko.jsonl").read_text())["ko"] == mine     # ko-title reads it next time
    # the editor's words outlast a new Korean draft of the note, with no tuning call ...
    monkeypatch.setattr(roles, "call", lambda run, role, packet, **k: {"data": {"issues": [], "terms": []}} if role != "ko-title" else 1 / 0)
    assert korean.make(run, redo=True)["title"]["ko"] == mine
    # ... until the English title changes: then qkr drafts it again and the editor's words are shown as earlier words
    _title_qkr(monkeypatch, sent)
    en = json.loads((run / "draft" / "en.json").read_text())
    en["title"] = "Canada borrows far more"
    (run / "draft" / "en.json").write_text(json.dumps(en))
    t = korean.make(run)["title"]
    assert t["from"] != "editor" and t["editor_stale"]["ko"] == mine and korean.verify(run) == []


def test_a_failed_ship_is_kept_shown_and_tried_again_by_the_hourly_daily(tmp_path, monkeypatch):
    run = tmp_path / "20261114-desk-x"
    (run / "desk").mkdir(parents=True)
    out = '{"error": "the working folder has uncommitted changes; publishing commits only the article", "changes": [" M a.py", "?? b/"]}'
    monkeypatch.setattr(queue.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": out, "stderr": "", "returncode": 1})())
    r = queue.ship(run)
    assert r["shipped"] is None and r["ship_tries"] == 1 and r["ship_error"].startswith("the working folder has uncommitted changes")
    assert "a.py" in r["ship_error"]
    assert queue.read_json(run / "desk" / "ship.json")["tries"] == 1
    # desk daily tries it again while it is approved and has tries left
    tried = []
    monkeypatch.setattr(queue, "ship", lambda r: tried.append(r.name) or {"shipped": "t"})
    _daily(monkeypatch, tmp_path, waiting=["approved"], month_has_note=True)
    assert tried and tried[0].endswith("desk-0")


def test_a_print_problem_holds_the_note_and_a_stale_proof_is_printed_again(tmp_path, monkeypatch):
    from artools import pdf
    run = tmp_path / "20261117-desk"
    (run / "desk").mkdir(parents=True)
    (run / "pdf").mkdir()
    (run / "desk" / "result.json").write_text(json.dumps({"run": run.name, "status": "queued"}))
    (run / "desk" / "score.json").write_text(json.dumps({"verdict": {"status": "pass", "reasons": []}}))
    (run / "pdf" / "proof.json").write_text("{}")
    monkeypatch.setattr(queue.korean, "status", lambda r: {"complete": True, "written": True, "open": []})
    monkeypatch.setattr(pdf, "check", lambda r: {"blocking": ["en: Figure 3: chart labels run outside the plot", "ko: the PDF is older than the draft or the charts; print it again"], "advisory": []})
    held = queue.settle(run)["held"]
    assert held == ["PDF: en: Figure 3: chart labels run outside the plot"]          # a stale proof is not a held reason
    printed = []
    monkeypatch.setattr(pdf, "proof", lambda rid: printed.append(rid) or {"check": {"blocking": [], "advisory": []}})
    assert queue.proof_pdf(run) == {"blocking": [], "advisory": []} and printed == [run.name]


def test_an_update_is_only_for_a_published_note_and_goes_through_the_rewrite_then_the_ship(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "RUNS", tmp_path)
    run = tmp_path / "20261114-desk-u"
    (run / "desk").mkdir(parents=True)
    (run / "desk" / "result.json").write_text(json.dumps({"run": run.name, "status": "queued"}))
    assert queue.update(run.name, "fix the dek")["updated"] is False                 # not published: the queue's path applies
    (run / "publish.json").write_text(json.dumps({"tag": "20261117.1"}))
    seen = {}
    monkeypatch.setattr(queue, "revise", lambda rid, decision=None: seen.update(decision) or {"run": rid, "revised": True})
    monkeypatch.setattr(queue, "ship", lambda r: {"shipped": "20261117.2"})
    monkeypatch.setattr(queue, "export", lambda deploy=False: {})
    out = queue.update(run.name, "In the dek write 'the cross-border bank loans Canada owes'.")
    assert out["updated"] and seen["note"].startswith("In the dek") and "word for word" in seen["scope"]
    assert not (run / "corrections.json").exists()                                   # a wording fix gets no correction


def test_the_cli_parses_every_desk_command():
    # 17 Nov 2026: an indentation slip in cli.py stopped every `artools` command, the ship and the hourly desk with it
    import artools.cli as cli_mod
    src = __import__("pathlib").Path(cli_mod.__file__).read_text()
    compile(src, "cli.py", "exec")
    for c in ("update", "decide", "daily", "sync", "korean", "queue"):
        assert f'dk.add_parser("{c}"' in src


def test_an_update_rewrites_only_what_the_editor_named(tmp_path):
    base = {"dek": "Canada's bank loans equalled 140%.", "sections": [{"blocks": [{"text": "The difference makes Canada-located banks net creditors."}]}]}
    new = {"dek": "The cross-border bank loans Canada owes equalled 140%.", "sections": base["sections"]}
    changed = [v for k, v in queue._walk(new) if dict(queue._walk(base)).get(k) != v]
    assert changed == ["The cross-border bank loans Canada owes equalled 140%."]


def test_an_update_with_only_keeps_every_other_string_as_published():
    pub = {"dek": "old dek", "insight": {"label": "Our read", "text": "old read"}, "sections": [{"blocks": [{"text": "a"}, {"text": "b"}]}]}
    new = {"dek": "new dek", "insight": {"label": "Our read", "text": "new read"}, "sections": [{"blocks": [{"text": "A"}, {"text": "B"}]}]}
    out = queue._limit(new, pub, ["dek", "insight", "sections.0.blocks.1"])
    assert out == {"dek": "new dek", "insight": {"label": "Our read", "text": "new read"}, "sections": [{"blocks": [{"text": "a"}, {"text": "B"}]}]}
    assert queue._limit(new, pub, ["nowhere.3"]) == pub


def test_an_editors_point_on_the_published_korean_reaches_the_checker_and_only_that_string_changes(tmp_path, monkeypatch):
    run = _ko_run(tmp_path)
    _fake_qkr(monkeypatch)
    korean.make(run)
    before = json.loads((run / "draft" / "ko.json").read_text())
    seen = []

    def call(run_, role, packet, **k):
        if role != "ko-checker":
            return {"data": {"angles": [], "ranking": []}}
        seen.append(packet)
        found = [{"id": "d:dek", "kind": "meaning", "quote_ko": "한국어", "problem": "who owes", "en": "Banks located in the United States held 49.5% at end-2026-06 [[ds-a]]."},
                 {"id": "d:kicker", "kind": "meaning", "quote_ko": "한국어", "problem": "an old point elsewhere", "en": "Funding and trade flows"}]
        return {"data": {"issues": found if len(seen) == 1 else [], "terms": []}}
    monkeypatch.setattr(roles, "call", call)
    korean.make(run, only_changed=True, points=[{"id": "d:dek", "problem": "the Korean reads as loans by Canada"}])
    after = json.loads((run / "draft" / "ko.json").read_text())
    assert "## The editor's points" in seen[0] and "d:dek: the Korean reads as loans by Canada" in seen[0]
    assert after["kicker"] == before["kicker"]                     # a finding outside the points is listed, not acted on
    led = {s["id"]: s for s in json.loads((run / "desk" / "korean.json").read_text())["strings"]}
    assert led["d:dek"]["how"] == "reworded after the check"


def test_an_article_citing_datasteg_data_says_its_figures_follow_datasteg_rules():
    from artools import content
    assert content.uses_datasteg_data([{"url": "https://money-flow.datasteg.com/en/world"}])
    assert content.uses_datasteg_data([{"links": [{"url": "https://api.datasteg.com/v1/global-network/stress"}]}])
    assert not content.uses_datasteg_data([{"url": "https://www.bis.org/statistics"}, {"url": "https://articles.datasteg.com/en"}])


# ------------------------------------------------------------------ 18 Nov 2026: the refined pipeline
# Seeded faults from the notes of 14–18 Nov 2026 (F1–F11): each must be caught by the stage the plan gives it.

from artools.desk import claims as claims_mod, inference as inference_mod, preflight, replay as replay_mod  # noqa: E402
from artools.desk import run as run_mod  # noqa: E402

OLD_TITLE = "Economies that lost foreign funding in mid-2026 grew their dollar exports like the rest"
F1_HEADLINE = "Of the six outflow economies with data, three grew exports faster than the group median"
F3_HEADLINE = "The five highest double-hit scores all belong to economies that lost net funding"
F4_HEADLINE = "Outflow economies split three in surplus and three in deficit, much like the inflow economies"


def _chart(cid, headline, col="exports_yoy_pct", subtitle="Quarter to end-June 2026"):
    return {"id": cid, "form": "bars", "headline": {"en": headline}, "subtitle": {"en": subtitle}, "title": {"en": "x"},
            "table": {"columns": [{"key": "label", "label": {"en": "Economy"}}, {"key": col, "label": {"en": "x"}}], "rows": []}, "meta": {"sources": []}}


def _old_note():
    draft = {"title": OLD_TITLE, "dek": "Of the {{F4}} with export data, {{F80}} grew exports faster than the group median.",
             "keyNumbers": [{"value": "{{F80}}", "label": "Outflow economies with export growth above the group median"}],
             "findings": ["Among outflow economies, {{F80}} of {{F4}} grew exports faster than the group median."],
             "sections": [{"id": "finding", "blocks": [{"type": "p", "text": "Half sat above the group median."}]}]}
    charts = {"outflow-export-growth": _chart("outflow-export-growth", F1_HEADLINE), "double-hit-score": _chart("double-hit-score", F3_HEADLINE, "j3"),
              "outflow-current-account": _chart("outflow-current-account", F4_HEADLINE, "ca_gdp_pct")}
    return draft, charts


def test_seeded_f1_to_f4_are_caught_by_the_text_lints_without_a_ledger():
    draft, charts = _old_note()
    got = review.claim_lints(draft, charts)
    b, a = "\n".join(got["blocking"]), "\n".join(got["advisory"])
    assert "base-rate: `figure:outflow-export-growth`" in b                       # F1: a count against a median, no comparator
    assert "referent: `figure:outflow-export-growth` says “the group median”" in b and "referent: `dek`" in b   # F2
    assert "referent: `title` says “the rest”" in b
    assert "mechanical: figure double-hit-score ranks Double hit" in b            # F3: the score counts the funding loss
    assert "base-rate: `figure:double-hit-score`" in b
    assert "vague comparison: `figure:outflow-current-account` says “much like”" in a     # F4 (advisory, R3)
    assert "referent: finding says “group median”" in b                          # a body sentence names its population too
    # the regenerated forms pass
    good = {"title": "Outflow economies grew exports like those that received funding", "dek": "x", "keyNumbers": [], "findings": [], "sections": []}
    ok = {"c": _chart("c", "Three of six outflow economies grew exports faster than the median of all 34, against 14 of 28 that received funding")}
    assert review.claim_lints(good, ok)["blocking"] == []
    # comparisons in words that the first r2 draft used (18 Nov 2026) are comparisons
    for t in ("Exports grew as much where bank and bond funding left in mid-2026 as where it stayed",
              "Economies that lost funding grew dollar exports by a median 8.9%; those that kept it, 8.6%",
              "Exports rose in all six economies that lost funding, as in all 28 that kept it",
              "Dollar exports rose where foreign funding left in Q2 2026, and as often where it stayed",
              "Exports had grown in every economy with data, whether or not funding left in mid-2026",
              "Exports grew by a tenth or more in 50% of outflow economies with data and 46% of economies without one"):
        assert review.has_comparator(t), t
    assert not review.has_comparator(F1_HEADLINE) and not review.has_comparator("Half grew faster than the median")


def _ledger_facts():
    fs = [{"id": f"F{i}", "label": l, "value": v, "unit": u, "period": p} for i, (l, v, u, p) in enumerate([
        ("outflow above", 3, "count", "2026-06-30"), ("outflow n", 6, "count", "2026-06-30"), ("inflow above", 14, "count", "2026-06-30"),
        ("inflow n", 28, "count", "2026-06-30"), ("median of all", 8.6, "%", "2025-07/2026-06"), ("other window", 9.9, "%", "12 months to 2026-07")], 1)]
    for f, k in zip(fs, ("out_above", "n_out", "in_above", "n_in", "median_all", "other")):
        f["key"] = k
    return fs


def _claim(**k):
    c = {"id": "C1", "kind": "share_above", "measure": "goods_trade_growth",
         "subject": {"set": "outflow economies with export data", "n": "{{n_out}}", "where": "flow_pct < 0", "table": "panel"},
         "statistic": {"value": "{{out_above}}", "base": "{{n_out}}", "against": "the median of all 34 economies with export data", "ref": "{{median_all}}"},
         "comparator": {"set": "inflow economies with export data", "value": "{{in_above}}", "base": "{{n_in}}"},
         "period": "funding: quarter to 2026-06; exports: 12 months to 2026-06", "mechanical": False, "reading": "no_difference",
         "says": "Outflow economies did no better", "finding": True}
    c.update(k)
    return c


def test_a_claim_needs_its_base_its_population_and_its_comparator():
    fs, t = _ledger_facts(), _tables()
    cs, probs = claims_mod.resolve([_claim()], fs)
    assert not probs and cs[0]["statistic"]["value"] == "{{F1}}" and cs[0]["comparator"]["base"] == "{{F4}}"
    ok, probs, _ = claims_mod.validate(cs, fs, t)
    assert [c["id"] for c in ok] == ["C1"] and probs == []
    for bad, why in ((_claim(comparator=None), "needs a `comparator`"),
                     (_claim(statistic={"value": "{{out_above}}", "base": "{{n_out}}", "against": "the group median", "ref": "{{median_all}}"}), "population"),
                     (_claim(statistic={"value": "{{out_above}}", "against": "the median of all", "ref": "{{median_all}}"}), "needs `statistic.base`"),
                     (_claim(measure="short_term_debt"), "not a registry id"),
                     (_claim(statistic={"value": "{{median_all}}", "against": "the median of all 34", "ref": "{{other}}"}, kind="level",
                             comparator={"set": "inflow economies", "value": "{{other}}"}), "different periods")):          # F5 at the claim level
        cs, _ = claims_mod.resolve([bad], fs)
        _, probs, _ = claims_mod.validate(cs, fs, t)
        assert any(why in p["problem"] for p in probs), (why, probs)
    cs, probs = claims_mod.resolve([_claim(statistic={"value": "{{nope}}"})], fs)
    assert cs == [] and "do not exist" in probs[0]["problem"]


def test_a_claim_on_a_score_built_from_its_selection_must_be_mechanical():
    fs, t = _ledger_facts(), _tables()
    c = _claim(kind="rank", measure="signal:j3", reading="extreme", comparator=None, no_comparator="the top five are listed by name in the chart",
               statistic={"value": "{{out_above}}", "against": "the five highest double-hit scores"})
    cs, _ = claims_mod.resolve([c], fs)
    _, probs, _ = claims_mod.validate(cs, fs, t)
    assert any("`mechanical` must be true" in p["problem"] and "flow_pct" in p["problem"] for p in probs)        # F3
    cs, _ = claims_mod.resolve([{**c, "mechanical": True}], fs)
    assert claims_mod.validate(cs, fs, t)[1] == []
    assert "flow_score_f" in claims_mod.inputs_of("signal:j3") and "bank_flow_lbs" in claims_mod.inputs_of("signal:j3")


def test_every_surface_string_cites_a_claim_and_keeps_its_comparison():
    fs = _ledger_facts()
    cs, _ = claims_mod.resolve([_claim(), _claim(id="C2", kind="rank", measure="signal:j3", reading="extreme", mechanical=True, finding=False,
                                                 comparator=None, no_comparator="ranking of all economies on the score is drawn",
                                                 statistic={"value": "{{out_above}}", "against": "the five highest double-hit scores"})], fs)
    draft = {"title": "Outflow economies grew exports like those that received funding",
             "dek": "{{F1}} of {{F2}} outflow economies grew exports faster than the median of all, as did {{F3}} of {{F4}} inflow economies.",
             "keyNumbers": [{"value": "{{F1}}", "label": "of {{F2}} outflow economies above the median of all"}], "findings": []}
    answer = {"draft": draft, "figures": [{"id": "dh"}], "claims": {"title": "C1", "dek": "C1", "keyNumbers.0": "C1"}}
    assert claims_mod.check_map(answer, cs) == ["claims: `figure:dh` cites no claim; give the claim id it states in the answer's `claims` map "
                                                 "({\"figure:dh\": \"C1\"}), or rewrite it to state one of the ledger's claims"]
    answer["claims"]["figure:dh"] = "C2"
    assert claims_mod.check_map(answer, cs) == []
    charts = {"dh": _chart("dh", F3_HEADLINE, "j3")}
    b = "\n".join(review.claim_lints(draft, charts, cs, claims_mod.claim_map(answer), {f["id"]: f for f in fs})["blocking"])
    assert "key number: `keyNumbers.0` shows C1; its label must give the base and the comparator" in b       # no inflow count
    assert "mechanical: `figure:dh` states C2" in b
    assert "base-rate: `dek`" not in b and "base-rate: `title`" not in b
    charts = {"dh": _chart("dh", "The five highest double-hit scores belong to outflow economies, as the score counts the funding loss itself", "j3")}
    b = "\n".join(review.claim_lints(draft, charts, cs, claims_mod.claim_map(answer), {f["id"]: f for f in fs})["blocking"])
    assert "mechanical:" not in b


def test_seeded_f6_f9_f10_registry_names_and_a_number_compared_with_itself():
    draft = {"title": "x", "dek": "Canada's bank loans rose.", "keyNumbers": [], "findings": [],
             "sections": [{"id": "finding", "blocks": [{"type": "p", "text": "Korea's short-term external debt was {{F1}} of exports, {{F1}} rather than {{F1}}."}]}]}
    fmap = {"F1": {"id": "F1", "value": 114.0, "unit": "%", "display": {"decimals": 0}}}
    b = "\n".join(review.claim_lints(draft, {}, None, None, fmap)["blocking"])
    assert "registry name: finding calls BIS banks' claims due within a year “short-term external debt”" in b    # F6
    assert "registry name: dek calls Bank loans and deposits owed (BIS locational) “Canada's bank loans”" in b    # F9
    assert "self-comparison: finding compares 114% with itself" in b                                            # F10
    assert review.claim_lints({"title": "x", "dek": "Bank loans Canada owes rose from 90% to 114%.", "keyNumbers": [], "findings": [], "sections": []},
                              {}, None, None, fmap)["blocking"] == []


def test_seeded_f11_korean_keeps_the_comparison_and_the_service_names():
    # qkr's own answers of 18 Nov 2026: a headline compressed into an achievement, and a translated service name
    it = {"id": "c:x:headline", "kind": "chart", "path": ["headline"], "compare": {"numbers": ["14", "28"]},
          "sent": "Like the 14 of 28 inflow economies, 3 of 6 outflow economies grew exports faster than the median of all 34"}
    p = korean.problems(it, "자료가 있는 유출 경제 6곳 중 3곳, 수출 증가율이 그룹 중앙값 웃돌아")
    assert any("dropped the base or the comparator ['14', '28']" in x for x in p) and any("no comparison marker" in x for x in p)
    assert not [x for x in korean.problems(it, "유입 경제 28곳 중 14곳과 같은 비율 34 3 6") if x.startswith("comparison")]
    # a month named in words may be a digit in Korean (end-March → 3월말)
    assert not korean.problems({"id": "x", "path": ["x"], "kind": "draft"}, "3월말 수치", "Figures at end-March")
    # "A보다 낮다" is a comparison (20261119-desk-ko2: three of Fable's strings were refused without it)
    assert not [x for x in korean.problems(it, "유입 경제 28곳 중 14곳보다 유출 경제 6곳 중 3곳 34") if x.startswith("comparison")]
    src = {"id": "c:x:meta/attribution", "kind": "chart", "path": ["meta", "attribution"], "sent": "BIS via datasteg"}
    assert any("service name datasteg" in x for x in korean.problems(src, "자료: BIS(데이터스테그 경유)"))
    assert not any("service name" in x for x in korean.problems(src, "자료: BIS(datasteg 경유)"))


def test_the_inference_test_flags_a_reading_the_claims_contradict(tmp_path, monkeypatch):
    fs = _ledger_facts()
    cs, _ = claims_mod.resolve([_claim(), _claim(id="C2", kind="rank", measure="signal:j3", reading="extreme", mechanical=True, finding=False)], fs)
    cmap = {"title": ["C1"], "figure:out": ["C1"], "figure:dh": ["C2"]}
    concl = [{"says": "Outflow economies did better than inflow economies", "from": ["figure:out"], "subject": "outflow economies",
              "comparator": "inflow economies", "relation": "better"},
             {"says": "Economies losing funding are the most exposed to a double hit", "from": ["figure:dh.subtitle"], "subject": "economies that lost funding",
              "relation": "finding"},
             {"says": "Outflow economies grew exports like inflow ones", "from": ["title"], "subject": "outflow economies", "relation": "same"},
             {"says": "Japan dominated", "from": ["dek"], "subject": "Japan", "relation": "finding"}]
    m = claims_mod.match(concl, cs, cmap)
    assert [x["verdict"] for x in m] == ["contradicted", "contradicted", "supported", "unresolved"]
    # what code cannot tie to the claim's two sets goes to the match task, never to "supported"
    vague = claims_mod.match([{"says": "Outflow economies did better than most", "from": ["figure:out"], "subject": "outflow economies",
                               "relation": "better"}], cs, cmap)
    assert vague[0]["verdict"] == "unresolved"
    assert claims_mod.match([{"says": "Exports rose everywhere, outflow or not", "from": ["title"], "subject": "outflow economies",
                              "relation": "finding"}], cs, cmap)[0]["verdict"] == "supported"
    # through the role: a fake reader, the unresolved conclusion decided by the match task, the contradiction is blocking
    calls = []

    def role(run, name, packet, **k):
        calls.append(packet.split("\n")[0])
        if "Task: match" in packet:
            return {"data": {"matches": [{"n": 1, "verdict": "unsupported", "claim": None, "why": "no claim on Japan"}]}}
        figs = "A chart, seen alone" in packet
        assert figs != ("On the list page" in packet)                # the list page and the charts are read apart
        return {"data": {"conclusions": [x for x in concl if any(k.startswith("figure:") for k in x["from"]) == figs]}}
    monkeypatch.setattr(roles, "call", role)
    draft, charts = _old_note()
    res = inference_mod.run_test(tmp_path, draft, charts, {f["id"]: f for f in fs}, cs, cmap)
    assert len(res["blocking"]) == 2 and res["blocking"][0]["kind"] == "framing" and len(res["advisory"]) == 1
    assert calls == ["## Task: read", "## Task: read", "## Task: match"]
    assert [x["key"] for x in res["surface"]][:3] == ["title", "dek", "keyNumbers.0"]


def test_later_rounds_raise_new_issues_only_on_changed_strings_or_as_errors_of_fact():
    draft = {"title": "A title about outflows", "dek": "The dek says something about exports", "sections": [
        {"id": "limits", "blocks": [{"type": "p", "text": "A limits sentence that did not change at all"}]}]}
    late = {"owner": "checker", "quote": "A limits sentence that did not change at all", "issue": "taste", "kind": "rule"}
    fact = {"owner": "checker", "quote": "A limits sentence that did not change at all", "issue": "wrong", "kind": "fact"}
    on_changed = {"owner": "referee", "quote": "The dek says something about exports", "issue": "weak"}
    keep, demoted = run_mod.converge([late, fact, on_changed], [], {"dek"}, draft, {}, {})
    assert [b["issue"] for b in keep] == ["wrong", "weak"] and "raised late" in demoted[0]["issue"]
    # an issue on a path an earlier round raised is not new
    keep, demoted = run_mod.converge([dict(late)], [{"paths": ["sections.0.blocks.0.text"]}], set(), draft, {}, {})
    assert len(keep) == 1 and not demoted


def test_a_closing_pass_takes_only_the_strings_it_was_asked_to_fix():
    prev = {"draft": {"title": "Old title", "dek": "Old dek", "findings": ["a", "b"], "sections": []},
            "figures": [{"id": "f1", "headline": "old f1"}, {"id": "f2", "headline": "old f2"}], "claims": {"title": "C1", "figure:f1": "C2"}}
    new = {"draft": {"title": "New title", "dek": "New dek", "findings": ["a2", "b2"], "sections": []},
           "figures": [{"id": "f1", "headline": "new f1"}, {"id": "f2", "headline": "new f2"}], "claims": {"title": "C3", "figure:f1": "C4"}}
    got = run_mod._scoped(new, prev, ["dek", "findings.1", "figure:f2"])
    assert got["draft"]["title"] == "Old title" and got["draft"]["dek"] == "New dek" and got["draft"]["findings"] == ["a", "b2"]
    assert [f["headline"] for f in got["figures"]] == ["old f1", "new f2"] and got["claims"] == {"title": ["C1"], "figure:f1": ["C2"]}


def test_one_judge_and_a_second_only_near_the_bar(monkeypatch, tmp_path):
    cfg = config.load()
    bar = {"pass_mean": 3.6, "min_dimension": 3.0}
    scores = iter([4.5, 4.5, 3.7, 3.5])
    n = []

    def one(run, art):
        v = next(scores)
        n.append(v)
        return {"scores": {k: {"score": v, "why": ""} for k in judge.DIMS}, "finding": "", "weakest": "", "to_improve": []}
    monkeypatch.setattr(judge, "_one", one)
    s = judge.score_note(tmp_path, "x", bar, cfg)
    assert s["judges"] == 1 and s["second_judge"] is None
    s = judge.score_note(tmp_path, "x", bar, cfg)                    # 4.5: one judge only; then 3.7 is near the bar
    s = judge.score_note(tmp_path, "x", bar, cfg)
    assert s["judges"] == 2 and s["mean"] == pytest.approx(3.6) and "within" in s["second_judge"]


def test_preflight_reads_the_apps_checks_and_stops_the_note_on_a_failure(tmp_path, monkeypatch):
    gn, tf, mf = tmp_path / "gn.json", tmp_path / "tf.json", tmp_path / "mf.json"
    gn.write_text(json.dumps({"built": "x", "items": [{"id": k, "status": "pass"} for k in ("K1", "K2", "K3", "K8")]}))
    tf.write_text(json.dumps({"ok": True, "checks": []}))
    mf.write_text(json.dumps({"results": [{"id": "V27", "status": "pass"}]}))
    monkeypatch.setattr(preflight, "GN_CHECKS", gn)
    monkeypatch.setattr(preflight, "TF_CHECKS", tf)
    monkeypatch.setattr(preflight, "MF_CHECKS", mf)
    monkeypatch.setattr(preflight, "REGISTRY_COPIES", [])
    assert preflight.check(_tables()["panel"])["ok"]
    gn.write_text(json.dumps({"built": "x", "items": [{"id": "K1", "status": "fail", "figure": "13-month base"}] + [{"id": k, "status": "pass"} for k in ("K2", "K3", "K8")]}))
    r = preflight.check()
    assert not r["ok"] and "check K1 failed" in r["problems"][0]


def test_the_brief_names_its_finding_type_and_comparison():
    assert run_mod.check_finding({"finding_type": "no_difference", "comparison": "outflow economies against inflow economies on the same measure"}) == []
    assert len(run_mod.check_finding({"finding_type": "surprise", "comparison": "the rest"})) == 2


def test_the_refined_stages_cost_under_eight_dollars_on_the_stored_note():
    from artools.paths import RUNS
    run = RUNS / "20261118-desk"
    if not (run / "logs").is_dir():
        pytest.skip("the stored 20261118-desk run is not on this machine")
    est = replay_mod.cost_estimate(run)
    assert est["total"] < 8.0 and "desk-reader" not in est["by_stage"]


def test_the_cli_has_the_replay_and_compare_commands():
    import artools.cli as cli_mod
    src = __import__("pathlib").Path(cli_mod.__file__).read_text()
    for c in ("replay", "compare"):
        assert f'dk.add_parser("{c}"' in src
    assert "--rewrite-of" in src


def test_korean_needs_a_comparison_marker_only_where_the_english_compares_explicitly():
    it = {"id": "d:findings/0", "kind": "draft", "path": ["findings", 0], "compare": {"numbers": []},
          "sent": "Dollar goods exports rose in all 34 economies with UN Comtrade data, so counting growers cannot set them apart."}
    assert not [p for p in korean.problems(it, "한국어 34") if p.startswith("comparison")]
    it["sent"] = "Growth was about as common in outflow economies (50%) as in those without an outflow (46%)."
    assert [p for p in korean.problems(it, "한국어 50 46") if p.startswith("comparison")]


def test_a_level_claim_is_checked_by_the_match_task_not_passed_by_code():
    fs = _ledger_facts()
    cs, _ = claims_mod.resolve([_claim(id="C7", kind="level", reading="level", finding=False, comparator=None,
                                       subject={"set": "Russia and China", "n": "{{n_out}}"})], fs)
    m = claims_mod.match([{"says": "Outflows are concentrated in Russia and China", "from": ["figure:mix"], "subject": "Russia and China",
                           "relation": "finding"}], cs, {"figure:mix": ["C7"]})
    assert m[0]["verdict"] == "unresolved"



# ------------------------------------------------------------------ 19 Nov 2026: Fable polishes each edition

def test_the_english_polish_keeps_the_shape_tokens_and_key_numbers():
    answer = {"draft": {"title": "Old", "dek": "d", "keyNumbers": [{"value": "{{F1}}", "label": "x", "cite": ["ds-a"]}], "findings": ["f"],
                        "sections": [{"id": "finding", "blocks": [{"type": "p", "text": "a"}, {"type": "figure", "chart": "c1"}]}], "citations": {"ds-a": {"used_for": "u"}}},
              "figures": [{"id": "c1", "headline": "h {{F1}}", "notes": ["n"]}], "claims": {"title": "C1"}}
    new, probs = polish_mod._merge_en(answer, {"draft": {"title": "New", "sections": [{"id": "finding", "blocks": [{"type": "p", "text": "b"}, {"type": "figure", "chart": "zz"}]}],
                                                         "keyNumbers": [{"value": "{{F1}}", "label": "y"}]},
                                               "figures": {"c1": {"headline": "plainer {{F1}}", "notes": ["m"]}}})
    assert probs == [] and new["draft"]["title"] == "New" and new["draft"]["sections"][0]["blocks"][1] == {"type": "figure", "chart": "c1"}
    assert new["draft"]["keyNumbers"][0]["cite"] == ["ds-a"] and new["figures"][0]["headline"] == "plainer {{F1}}" and new["claims"] == {"title": ["C1"]} or new["claims"] == {"title": "C1"}
    _, probs = polish_mod._merge_en(answer, {"draft": {"sections": [{"id": "other", "blocks": []}], "keyNumbers": [{"value": "{{F2}}"}]}})
    assert any("sections changed" in p for p in probs) and any("keyNumbers.0.value" in p for p in probs)


def test_fable_refines_the_korean_and_a_string_that_fails_keeps_qkrs_draft(tmp_path, monkeypatch):
    run = _ko_run(tmp_path)
    _fake_qkr(monkeypatch)
    sent_fb, calls = [], []
    real = korean._http

    def http(path, body=None, timeout=0):
        if path == "/v1/feedback":
            sent_fb.append(body)
            return {"ok": True}
        return real(path, body, timeout)
    monkeypatch.setattr(korean, "_http", http)

    def role(run_, name, packet, **k):
        calls.append(name)
        if name == "polish-ko":
            assert "KO: " in packet and "EN:" not in packet               # the Korean alone (19 Nov 2026, the owner)
            assert packet.split("## Your answer")[0].split("### ")[-1].startswith("d:title")   # the title is written last (20 Nov 2026)
            return {"data": {"items": [{"id": "d:dek", "ko": "한국어 49.5 2026 06 [[ds-a]] 다듬음"},          # passes the checks
                                       {"id": "d:title", "ko": "한국어 99 다듬음"},                            # adds a number: refused
                                       {"id": "c:c1:headline", "ko": "한국어 고침"}]}}                         # the fact editor finds it differs
        if name == "polish-ko-facts":
            assert "QKR: " in packet and "KO: 한국어 고침" in packet and "d:title" not in packet
            return {"data": {"issues": [{"id": "c:c1:headline", "problem": "says another thing"}]}}
        return {"data": {"issues": [], "terms": [], "items": []}}
    monkeypatch.setattr(roles, "call", role)
    out = korean.make(run)
    led = {x["id"]: x for x in json.loads((run / "desk" / "korean.json").read_text())["strings"]}
    assert led["d:dek"]["ko"].endswith("다듬음") and led["d:dek"]["how"] == "refined by Fable" and led["d:dek"]["ko_qkr"] == "한국어 49.5 2026 06 [[ds-a]]"
    assert not led["d:title"]["ko"].endswith("다듬음") and led["c:c1:headline"]["ko"] == "한국어" and led["c:c1:headline"].get("polish_undone")
    assert out["polish"]["changed"] == 1 and len(out["polish"]["refused"]) == 1 and len(out["polish"]["reverted"]) == 1
    assert "ko-title" not in calls and calls.count("polish-ko") >= 1                                   # the title tuning is replaced
    assert any(f["verdict"] == "edited" and f["ko_final"].endswith("다듬음") for f in sent_fb)        # qkr learns from Fable's edit
    assert korean.verify(run) == []
    # verify holds Fable's rewrite to qkr's draft: a number lost on disk is found
    led_all = json.loads((run / "desk" / "korean.json").read_text())
    for x in led_all["strings"]:
        if x["id"] == "d:dek":
            x["ko"] = "한국어 2026 06 [[ds-a]] 다듬음"
    (run / "desk" / "korean.json").write_text(json.dumps(led_all, ensure_ascii=False))
    ko = json.loads((run / "draft" / "ko.json").read_text())
    ko["dek"] = "한국어 2026 06 [[ds-a]] 다듬음"
    (run / "draft" / "ko.json").write_text(json.dumps(ko, ensure_ascii=False))
    assert any("Fable's rewrite: numbers lost ['49.5']" in x for x in korean.verify(run))
    led_all["strings"] = [x if x["id"] != "d:dek" else {**x, "ko": "한국어 49.5 2026 06 [[ds-a]] 다듬음"} for x in led_all["strings"]]
    (run / "desk" / "korean.json").write_text(json.dumps(led_all, ensure_ascii=False))
    ko["dek"] = "한국어 49.5 2026 06 [[ds-a]] 다듬음"
    (run / "draft" / "ko.json").write_text(json.dumps(ko, ensure_ascii=False))
    # a second make does not polish again what was polished
    calls.clear()
    korean.make(run)
    assert "polish-ko" not in calls


def test_a_rewording_for_qkr_may_not_add_a_statement():
    korean._FILLED.clear()
    it = {"id": "d:dek", "sent": "Cover fell by 8.5% while reserves fell by 2.7%. Most of that step reflects a larger import bill."}
    korean._FILLED["d:dek"] = it["sent"]
    assert korean._usable(it, "Reserves fell by 2.7% while cover fell by 8.5%. Most of the fall reflects a larger import bill.")
    assert korean._usable(it, it["sent"] + " This is not the whole decline: over the year, lower reserves did more of it.") is None


def test_daily_leaves_a_busy_note_alone(tmp_path):
    """19 Nov 2026: the hourly job drafted t4-r2's Korean while the note's own Korean stage was running."""
    import datetime as dt
    from artools.desk import queue
    from artools.paths import write_json
    now = dt.datetime.now(dt.timezone.utc)
    write_json(tmp_path / "run.json", {"stages": {"desk-korean": {"state": "running", "started": now.isoformat()}}})
    assert queue.busy(tmp_path)
    write_json(tmp_path / "run.json", {"stages": {"desk-korean": {"state": "running", "started": (now - dt.timedelta(hours=7)).isoformat()}}})
    assert not queue.busy(tmp_path)
    write_json(tmp_path / "run.json", {"stages": {"desk-korean": {"state": "done", "started": now.isoformat()}}})
    assert not queue.busy(tmp_path)


def test_the_korean_title_is_held_to_the_note_not_to_qkrs_title():
    """20 Nov 2026: Fable writes the title last from the whole note; it need not keep qkr's title's numbers."""
    it = {"id": "d:title", "profile": "article", "path": ["title"], "kind": "draft"}
    assert polish_mod.ko_problems(it, "해외 자금 빠진 경제, 수출은 다른 곳만큼 늘었다", "34개 중 19.3위, 확률 17.5", {"34", "19.3", "17.5", "8"}) == []
    assert polish_mod.ko_problems(it, "8곳 중 6곳 수출 늘어", "34개 중 19.3위", {"34", "19.3", "8"}) == ["numbers the note does not have: ['6']"]
    assert any("numbers lost" in p for p in polish_mod.ko_problems({**it, "id": "d:dek"}, "수출 늘어", "34개 중 19.3위"))


def test_the_english_polish_locates_a_problem_to_keep_that_string():
    """20 Nov 2026: a rewrite that fails is taken string by string; the strings a check names keep the reviewers' text."""
    d = {"title": "x", "dek": "y", "findings": ["a", "b"], "sections": [{"id": "limits", "blocks": []}]}
    ch = {"flows": {}}
    assert polish_mod._locate("referent: `dek` says “the group” without naming the set", d, ch) == ["dek"]
    assert polish_mod._locate("referent: limits says “group's median”; name the population", d, ch) == ["sections.0"]
    assert polish_mod._locate("style: en.title: 110 characters (max 90)", d, ch) == ["title"]
    assert polish_mod._locate("figure flows: the headline is 126 characters", d, ch) == ["figure:flows"]
    assert polish_mod._locate("length: 1392 words of prose; the note runs 650–1100", d, ch) == []


def test_the_ideas_rank_weighs_interest_substance_and_news():
    """20 Nov 2026: the ideas preview ranks the questions by what lay readers would read, what the answer has, how new."""
    from artools.desk import ideas
    hi = {"read": 8, "useful": 6}
    s = ideas.score({"answer_kind": "extreme", "from": ["C1"]}, {"office": hi, "student": hi, "exporter": hi})
    assert s == {"interest": 7.0, "substance": 1.0, "fresh": 1.0, "score": 0.85}
    s2 = ideas.score({"answer_kind": "no_difference", "from": ["L3"]}, {"office": hi, "student": hi, "exporter": hi})
    assert s2["substance"] == 0.4 and s2["fresh"] == 0.4 and s2["score"] < s["score"]


def test_the_editor_removes_an_idea_from_the_admin_site(tmp_path, monkeypatch):
    """20 Nov 2026: a remove decision for a question of the ideas preview is applied and kept."""
    from artools.desk import queue
    monkeypatch.setattr(queue, "REMOVED", tmp_path / "removed.json")
    monkeypatch.setattr(queue, "env_value", lambda k: None)
    d = {"id": "x1", "run": "ideas:2026-11-20:Q5", "digest": "ideas", "decision": "remove", "note": "", "at": "2026-11-20T00:00:00Z"}
    assert queue.check_decision(d) is None
    assert queue.apply(d)["applied"] is True and "ideas:2026-11-20:Q5" in queue.removed()
    assert queue.check_decision({**d, "run": "ideas:2026-11-20;rm"}) == "no such desk run"
