"""Offline tests: no database, no network, no Claude sessions."""
from artools.content import render_fact, render_tokens
from artools.jejualps import _interrupted_match, normalise


def f(value, unit, **display):
    return {"id": "F1", "value": value, "unit": unit, "display": display}


def test_render_units():
    assert render_fact(f(96.7, "bp", decimals=0), "en") == "97bp"
    assert render_fact(f(24.4, "bp", decimals=0), "en", {"signed"}) == "+24bp"
    assert render_fact(f(-0.34, "%", decimals=2), "en") == "−0.34%"
    assert render_fact(f(0.2, "pp", decimals=1), "en") == "0.2 pp"
    assert render_fact(f(0.2, "pp", decimals=1), "ko") == "0.2%p"
    assert render_fact(f(1202.9, "bp", decimals=0), "en") == "1,203bp"
    assert render_fact(f("2012-07", "month"), "en") == "July 2012"
    assert render_fact(f("2012-07", "month"), "ko") == "2012년 7월"
    assert render_fact(f("2026-Q2", "quarter"), "ko") == "2026년 2분기"
    assert render_fact(f(5, "months", decimals=0), "en") == "five months"
    assert render_fact(f(5, "months", decimals=0), "ko") == "5개월"
    assert render_fact(f(440.6, "USD bn", decimals=1, en="USD {v}bn", ko="{v}억 달러"), "ko") == "4,406억 달러"
    assert render_fact(f(440.6, "USD bn", decimals=1, en="USD {v}bn", ko="{v}억 달러"), "en") == "USD 440.6bn"


def test_render_korean_billions_in_eok_and_jo():
    # Korean has no billion: bn amounts render in 억/조 with the fact's precision (1 bn = 10억), as the BoK writes them
    assert render_fact(f(279.2013, "USD bn", decimals=0, ko="{v}0억 달러"), "ko") == "2,790억 달러"
    assert render_fact(f(279.2013, "USD bn", decimals=1, ko="{v}0억 달러"), "ko") == "2,792억 달러"
    assert render_fact(f(-1.4299, "USD bn", decimals=1, ko="{v}0억 달러"), "ko") == "−14억 달러"
    assert render_fact(f(-146.885, "USD bn", decimals=0, ko="{v}0억 달러"), "ko", {"abs"}) == "1,470억 달러"
    assert render_fact(f(24.0, "USD bn", decimals=0, ko="{v}0억 달러"), "ko", {"signed"}) == "+240억 달러"
    assert render_fact(f(1014, "USD bn", decimals=0, ko="{v}0억 달러"), "ko") == "1조 140억 달러"
    assert render_fact(f(5000, "EUR bn", decimals=0, ko="{v}0억 유로"), "ko") == "5조 유로"
    assert render_fact(f(273.854, "EUR bn", decimals=1), "ko") == "2,739억 유로"
    assert render_fact(f(1.785, "USD tn", decimals=2), "ko") == "1.78조 달러"
    assert render_fact(f(1.785, "USD tn", decimals=2, en="${v}tn", ko="${v}tn"), "ko") == "$1.78tn"


def test_render_tokens_rounds_once():
    facts = {"F3": f(72.3, "bp", decimals=0), "F4": f(96.7, "bp", decimals=0), "F5": f(24.4, "bp", decimals=0)}
    assert render_tokens("{{F4}}, up {{F5}} from {{F3}}", facts, "en") == "97bp, up 24bp from 72bp"


def test_normalise_joins_hyphenation_and_ligatures():
    n, _ = normalise("credit-\nrisk ﬁnding  spread\n\nwidened")
    assert n == "creditrisk finding spread widened"


def test_interrupted_quote():
    text = ("Our main finding is that for most countries the CDS market 1 See Lehmann (2002) for a general "
            "discussion. 1 leads the bond market in terms of credit risk price discovery.")
    n, _ = normalise(text)
    q, _ = normalise("Our main finding is that for most countries the CDS market leads the bond market in terms of "
                     "credit risk price discovery.")
    m = _interrupted_match(n, q)
    assert m and m["skipped"].startswith("1 See Lehmann")
    assert _interrupted_match(n, q.replace("leads", "follows")) is None


# --- pipelines ---------------------------------------------------------------------------------------------------------

import json

from artools import drive as drv
from artools import pipelines


def test_pipelines_are_valid():
    for pid in pipelines.ids():
        assert pipelines.check(pipelines.load(pid)) == [], pid


def _fake_run(tmp_path, gates, review_status="pass", verdict="answer"):
    run = tmp_path / "20261020-test"
    (run / "logs").mkdir(parents=True)
    (run / "run.json").write_text(json.dumps({"id": run.name, "stages": {}, "gates": {g: {"approved": ok} for g, ok in gates.items()}}))
    (run / "question-review.json").write_text(json.dumps({"verdict": verdict}))
    (run / "review.json").write_text(json.dumps({"status": review_status, "blocking": []}))
    (run / "litmap.json").write_text(json.dumps({"mechanisms": [{"indicators": [{"priority": "needed", "provider": "ECB"},
                                                                                 {"priority": "useful", "provider": "fred"}]}]}))
    return run


def _calls(monkeypatch, run):
    calls = []
    monkeypatch.setattr(drv, "run_dir", lambda _: run)
    monkeypatch.setattr(drv, "run_skill", lambda r, sk, mode=None, extra="", model=None: calls.append(f"{mode}:{sk}" if mode else sk) or True)
    monkeypatch.setattr(drv, "auto_gates", lambda: {})   # the editor's gates, whatever config/editorial.yaml says
    monkeypatch.setattr(drv, "ship_run", lambda r: calls.append("ship") or True)
    return calls


def test_explainer_drive_matches_the_original_order(tmp_path, monkeypatch):
    """The generic driver runs an explainer as the hard-coded driver did (drive.py before 20 Oct 2026), plus the
    cover (explainer 1.1) and the PDF proof (explainer 1.2) between the review and gate 3."""
    run = _fake_run(tmp_path, {"question": True, "plan": True, "publish": False})
    calls = _calls(monkeypatch, run)
    assert drv.drive(run.name) == 3                       # stops at gate 3
    assert calls == ["frame-question", "scout:search-jejualps", "scout:fetch-public-data", "refine-question",
                     "deep:search-jejualps", "map-literature", "fetch-public-data", "fetch-fred", "analyze-data",
                     "plan-article", "draft-article", "make-charts", "review-article", "make-cover", "make-pdf"]


def test_every_pipeline_makes_the_cover_and_the_pdf_after_the_review_and_before_the_publish_gate():
    for pid in pipelines.ids():
        if any(s.get("desk") for s in pipelines.load(pid)["steps"]):
            continue      # the data desk's note has no cover and no PDF proof; `artools ship` prints its PDF (tests/test_desk.py)
        order = [s.get("skill") or s.get("gate") for s in pipelines.load(pid)["steps"] if not s.get("follows")]
        assert order[-5:] == ["review-article", "make-cover", "make-pdf", "publish", "publish-article"], pid


def test_the_explainer_ends_with_its_video():
    """The video follows the publish step (explainer 1.3): publish-article starts it, the driver never reaches it."""
    steps = pipelines.load("explainer")["steps"]
    assert steps[-1]["skill"] == "make-video" and steps[-1]["follows"] == "publish"
    assert not pipelines.check(pipelines.load("explainer")) and not pipelines.check(pipelines.load("video"))


def test_drive_stops_at_the_first_closed_gate_and_until(tmp_path, monkeypatch):
    run = _fake_run(tmp_path, {"question": False, "plan": False, "publish": False})
    calls = _calls(monkeypatch, run)
    assert drv.drive(run.name) == 3 and calls[-1] == "refine-question"
    calls.clear()
    assert drv.drive(run.name, until="frame-question") == 0 and calls == ["frame-question"]


def test_declined_question_stops(tmp_path, monkeypatch):
    run = _fake_run(tmp_path, {"question": True, "plan": True, "publish": True}, verdict="decline")
    calls = _calls(monkeypatch, run)
    assert drv.drive(run.name) == 4 and calls[-1] == "refine-question"


def test_auto_gates_approve_and_ship_unless_the_review_blocks(tmp_path, monkeypatch):
    """config/editorial.yaml → gates.auto: the driver opens each gate itself, signed `by`, and ships after the publish
    gate; a blocking issue left in review.json keeps the publish gate closed for the editor."""
    run = _fake_run(tmp_path, {"question": False, "plan": False, "publish": False})
    calls = _calls(monkeypatch, run)
    monkeypatch.setattr(drv, "auto_gates", lambda: {"auto": True, "by": "datasteg desk (autonomous agent)"})
    (run / "review.json").write_text(json.dumps({"status": "changes_required", "blocking": [{"owner": "make-charts"}]}))
    assert drv.drive(run.name) == 3 and calls[-1] == "make-pdf" and "ship" not in calls
    gates = json.loads((run / "run.json").read_text())["gates"]
    assert gates["plan"]["approved"] and gates["plan"]["by"] == "datasteg desk (autonomous agent)"
    assert not gates["publish"]["approved"]
    (run / "review.json").write_text(json.dumps({"status": "pass", "blocking": []}))
    calls.clear()
    assert drv.drive(run.name) == 0 and calls[-1] == "ship" and "make-video" not in calls
    assert json.loads((run / "run.json").read_text())["gates"]["publish"]["approved"]


def test_sample_pipelines_need_allow_sample(tmp_path, monkeypatch):
    run = _fake_run(tmp_path, {"plan": True, "publish": True})
    m = json.loads((run / "run.json").read_text()); m["pipeline"] = "data-brief"
    (run / "run.json").write_text(json.dumps(m))
    calls = _calls(monkeypatch, run)
    assert drv.drive(run.name) == 2 and calls == []
    assert drv.drive(run.name, allow_sample=True) == 0
    assert calls[:2] == ["frame-question", "select-indicators"] and "scout:search-jejualps" in calls


def test_mermaid_has_every_step():
    p = pipelines.load("explainer")
    m = pipelines.mermaid(p)
    assert all(s["id"].replace("-", "_") in m for s in p["steps"])


def test_stage_sessions_get_the_runs_model_and_effort(tmp_path, monkeypatch):
    run = _fake_run(tmp_path, {"question": False})
    m = json.loads((run / "run.json").read_text()); m["runtime"] = {"model": "claude-fable-5-1", "effort": "high"}
    (run / "run.json").write_text(json.dumps(m))
    seen = []

    class Done:
        returncode = 0
    monkeypatch.setattr(drv.subprocess, "run", lambda cmd, **k: seen.append(cmd) or Done())
    monkeypatch.setattr(drv, "stage_state", lambda r, s: "done" if seen else None)
    assert drv.run_skill(run, "frame-question")
    cmd = seen[0]
    assert cmd[cmd.index("--model") + 1] == "claude-fable-5-1" and cmd[cmd.index("--effort") + 1] == "high"


def test_no_runtime_means_cli_defaults(tmp_path, monkeypatch):
    run = _fake_run(tmp_path, {"question": False})
    seen = []

    class Done:
        returncode = 0
    monkeypatch.setattr(drv.subprocess, "run", lambda cmd, **k: seen.append(cmd) or Done())
    monkeypatch.setattr(drv, "stage_state", lambda r, s: "done" if seen else None)
    drv.run_skill(run, "frame-question")
    assert "--model" not in seen[0] and "--effort" not in seen[0]


# --- covers ------------------------------------------------------------------------------------------------------------

import re
from pathlib import Path

from artools.cover import PALETTE, check_svg

BG = '<rect x="0" y="0" width="480" height="320" class="f-frost"/>'


def svg(body, root='xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320"'):
    return f"<svg {root}>{BG}{body}</svg>"


def test_a_plain_cover_passes():
    r = check_svg(svg('<g class="f-ice s-tarn" stroke-width="10"><rect x="60" y="80" width="160" height="120"/>'
                      '<path d="M260 200 L420 120" fill="none"/></g><circle cx="300" cy="90" r="30" class="f-warm"/>'))
    assert r["blocking"] == [] and r["palette"] == ["frost", "ice", "tarn", "warm"]


def test_unsafe_or_off_palette_markup_is_blocked():
    bad = {
        "<script>alert(1)</script>": "not allowed",
        '<text x="10" y="10" class="f-ink">97bp</text>': "not allowed",
        '<rect x="1" y="1" width="9" height="9" fill="#ff0000"/>': "colours are classes",
        '<rect x="1" y="1" width="9" height="9" class="f-red"/>': "not a palette colour",
        '<rect x="1" y="1" width="9" height="9" class="f-ice" onclick="x()"/>': "not allowed",
        '<rect x="1" y="1" width="9" height="9" class="f-ice" id="a"/>': "not allowed",
        '<rect x="1" y="1" width="9" height="9" class="f-ice" style="fill:red"/>': "not allowed",
        '<rect x="1" y="1" width="9" height="9"/>': "default fill is black",
        '<line x1="0" y1="0" x2="9" y2="9" class="s-ink" stroke-width="2"/>': "vanishes",
        '<path d="M0 0" class="f-ice" transform="url(#x)"/>': "characters",
    }
    for body, why in bad.items():
        assert any(why in p for p in check_svg(svg(body))["blocking"]), body
    assert any("viewBox" in p for p in check_svg(svg("", 'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"'))["blocking"])
    assert any("background" in p for p in check_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320"/>')["blocking"])
    assert any("DOCTYPE" in p for p in check_svg('<!DOCTYPE svg [<!ENTITY a "b">]>' + svg(""))["blocking"])


def test_the_site_has_a_rule_for_every_palette_colour():
    css = (Path(__file__).resolve().parents[2] / "apps/web/app/site.css").read_text(encoding="utf-8")
    rules = dict(re.findall(r"\.cover \.f-([a-z0-9]+)\s*\{\s*fill:\s*var\(--([a-z0-9-]+)\)", css))
    strokes = dict(re.findall(r"\.cover \.s-([a-z0-9]+)\s*\{\s*stroke:\s*var\(--([a-z0-9-]+)\)", css))
    assert rules == PALETTE and strokes == PALETTE


# --- local images ------------------------------------------------------------------------------------------------------

def test_prune_images_keeps_only_the_live_tag(monkeypatch):
    from artools import ship
    calls = []
    listing = "\n".join(["host.example:5000/articles:20261020.8", "host.example:5000/articles:20261020.7",
                         "datasteg-articles:local", "host.example:5000/main:0.2.0", "node:24-alpine"])
    monkeypatch.setattr(ship, "sh", lambda cmd, **k: calls.append(cmd) or (listing if cmd[:2] == ["docker", "images"] else ""))
    res = ship.prune_images("20261020.8")
    assert res["removed"] == ["host.example:5000/articles:20261020.7", "datasteg-articles:local"]
    assert calls[-1] == ["docker", "image", "rm", *res["removed"]]


def test_pdf_source_hash_follows_the_edition(tmp_path):
    from artools.pdf import source_hash
    (tmp_path / "charts").mkdir()
    (tmp_path / "en.json").write_text('{"title": "A"}')
    (tmp_path / "sources.json").write_text("[]")
    (tmp_path / "charts" / "b.json").write_text("{}")
    first = source_hash(tmp_path, "en")
    assert len(first) == 16 and first == source_hash(tmp_path, "en")
    (tmp_path / "ko.json").write_text('{"title": "가"}')     # the other edition is not part of it
    assert source_hash(tmp_path, "en") == first
    (tmp_path / "charts" / "b.json").write_text('{"id": "b"}')   # a chart is
    assert source_hash(tmp_path, "en") != first


def test_pdf_check_needs_a_fresh_proof(tmp_path):
    import json
    import os
    from artools.pdf import check
    (tmp_path / "draft").mkdir()
    (tmp_path / "pdf").mkdir()
    (tmp_path / "draft" / "en.json").write_text("{}")
    assert check(tmp_path)["blocking"][0].startswith("no proof yet")
    (tmp_path / "pdf" / "en.pdf").write_bytes(b"%PDF-1.4")
    proof = {"editions": {"en": {"file": "en.pdf", "pages": 9, "bytes": 8, "problems": [], "fonts_checked": True,
                                 "gaps": [{"page": 3, "gapMm": 60, "next": "Figure 2"}]}}}
    (tmp_path / "pdf" / "proof.json").write_text(json.dumps(proof))
    res = check(tmp_path)
    assert res["blocking"] == [] and res["pages"] == {"en": 9}
    assert res["advisory"] == ["en: page 3 ends 60 mm early: Figure 2 did not fit under it"]
    later = (tmp_path / "pdf" / "en.pdf").stat().st_mtime + 10   # the draft changed after the proof
    os.utime(tmp_path / "draft" / "en.json", (later, later))
    assert any("older than the draft" in x for x in check(tmp_path)["blocking"])


def test_received_counts_characters_per_artools_subcommand(tmp_path):
    import json
    from artools.usage import received

    def use(i, cmd, parent=None):
        return {"type": "assistant", "parent_tool_use_id": parent,
                "message": {"content": [{"type": "tool_use", "id": i, "name": "Bash", "input": {"command": cmd}}]}}

    def result(i, text, parent=None):
        return {"type": "user", "parent_tool_use_id": parent,
                "message": {"content": [{"type": "tool_result", "tool_use_id": i, "content": text}]}}

    events = [use("a", 'artools jejualps search --q "spread:*" --limit 30'), result("a", "x" * 100),
              use("b", "artools jejualps search --q risk"), result("b", [{"type": "text", "text": "y" * 50}]),
              use("c", "artools jejualps chunks 12 --start 0", "agent1"), result("c", "z" * 40, "agent1"),
              use("d", 'artools quote verify jejualps:1 "a"; artools quote verify jejualps:2 "b"'), result("d", "q" * 7),
              use("e", "ls /data"), result("e", "not counted")]
    p = tmp_path / "search-jejualps.1.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events))
    assert received(p) == {"jejualps search": {"calls": 2, "chars": 150, "subagent_chars": 0},
                           "jejualps chunks": {"calls": 1, "chars": 40, "subagent_chars": 40},
                           "quote verify": {"calls": 1, "chars": 7, "subagent_chars": 0}}


def test_publish_anyway_follows_editorial_gates(monkeypatch, tmp_path):
    from artools import paths
    (tmp_path / "editorial.yaml").write_text("gates: {auto: true, on_blocking: publish}\n")
    monkeypatch.setattr(paths, "CONFIG", tmp_path)
    assert paths.publish_anyway()
    (tmp_path / "editorial.yaml").write_text("gates: {auto: true, on_blocking: stop}\n")
    assert not paths.publish_anyway()
    (tmp_path / "editorial.yaml").write_text("gates: {auto: false, on_blocking: publish}\n")
    assert not paths.publish_anyway()


def test_ledger_attempt_denials_redaction_and_fingerprint(tmp_path):
    import json as _json
    from artools.ledger import _attempt, fingerprints, redact
    log = tmp_path / "search-jejualps.1.jsonl"
    events = [
        {"type": "system", "subtype": "init", "claude_code_version": "9.9.9"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash",
                                                       "input": {"command": "artools jejualps cite 1 2"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "abcd"}]}},
        {"type": "result", "duration_ms": 61000, "num_turns": 3, "total_cost_usd": 1.5, "result": "done",
         "modelUsage": {"m": {"inputTokens": 1, "cacheCreationInputTokens": 2, "cacheReadInputTokens": 7, "outputTokens": 4,
                              "thinkingTokens": 1, "costUSD": 1.5}},
         "permission_denials": [{"tool_name": "Bash", "tool_input": {"command": "cd /data/x; python3 -I -c 'postgres://u:pw@h/db'"}}]},
    ]
    log.write_text("\n".join(_json.dumps(e) for e in events), encoding="utf-8")
    a = _attempt(log)
    assert a["seconds"] == 61 and a["cost_usd"] == 1.5 and a["cache_read_share"] == 0.7
    assert a["received"]["jejualps cite"]["chars"] == 4 and a["claude_code"] == "9.9.9"
    assert a["denials"][0]["pattern"] == "Bash: python3 -I" and "pw@" not in a["denials"][0]["example"]
    assert fingerprints({"search-jejualps": {"received": a["received"]}}, {}) == {"search-jejualps": "lines"}
    assert fingerprints({"search-jejualps": {"received": {"jejualps search": {}}}}, {}) == {"search-jejualps": "rows"}
    assert redact("password=hunter2 token: abc") == "password=… token: …"


def test_no_ledger_data_in_git():
    """The ledger stays on dev-host: no tracked JSON may be a ledger file."""
    import subprocess
    from artools.ledger import REPO
    files = subprocess.run(["git", "grep", "-l", '"ledger_version"', "--", "*.json"], cwd=REPO, capture_output=True, text=True).stdout
    assert files.strip() == ""


def test_logs_archive_and_prune_keep_the_numbers(tmp_path, monkeypatch):
    import json as _json
    import shutil
    import pytest
    if not shutil.which("zstd"):
        pytest.skip("zstd not installed")
    from artools import logs as G
    from artools.usage import usage
    run = tmp_path / "20990101-x"
    (run / "logs").mkdir(parents=True)
    (run / "run.json").write_text(_json.dumps({"id": run.name, "stages": {}, "gates": {}}))
    img = "A" * 2000
    events = [
        {"type": "user", "message": {"content": [{"type": "image", "source": {"data": img}}]}},
        {"type": "result", "duration_ms": 1000, "num_turns": 2, "total_cost_usd": 0.5, "result": "ok",
         "modelUsage": {"m": {"inputTokens": 1, "cacheCreationInputTokens": 0, "cacheReadInputTokens": 3, "outputTokens": 2, "costUSD": 0.5}}},
    ]
    (run / "logs" / "draft-article.1.jsonl").write_text("\n".join(_json.dumps(e) for e in events))
    (run / "logs" / "events.jsonl").write_text("{}\n")
    before = usage(run)["total"]
    a = G.archive(run)
    assert a["files"] == 1 and not (run / "logs" / "draft-article.1.jsonl").exists()
    assert img not in "".join(G.open_lines(run / "logs" / "draft-article.1.jsonl.zst"))
    assert usage(run)["total"] == before
    monkeypatch.setattr("artools.ledger.write", lambda r: None)
    G.prune(run)
    assert [p.name for p in G.stage_logs(run)] == [] and "draft-article.1" in G.pruned(run)
    assert usage(run)["total"] == before and (run / "logs" / "events.jsonl").exists()


def test_meta_volume_counts_the_runs_own_fetches_and_the_apps_it_cites(tmp_path):
    import json
    from artools.content import article_volume
    run = tmp_path / "run"
    for prov, rows in (("fred", 3), ("derived", 5)):
        d = run / "data" / prov
        d.mkdir(parents=True)
        (d / f"{prov}-a.csv").write_text("date,value\n" + "".join(f"2026-0{i + 1},1\n" for i in range(rows)))
        (d / "catalog.json").write_text(json.dumps([{"id": f"{prov}-a", "file": f"data/{prov}/{prov}-a.csv"},
                                                    {"id": f"{prov}-gone", "file": f"data/{prov}/{prov}-gone.csv"}]))
    (run / "data" / "fred" / "fred-stray.csv").write_text("date,value\n2026-01,1\n")      # no catalog entry: not counted
    (run / "data" / "public-data").mkdir()
    (run / "data" / "public-data" / "public-data.log.json").write_text("{}")             # a stage log: left out
    hosts = {"money-flow": "money-flow.datasteg.com", "open-research": "open-research.datasteg.com"}
    sources = [{"id": "S1", "kind": "paper", "ref": "jejualps:1"}, {"id": "S2", "kind": "paper", "ref": "jejualps:2"},
               {"id": "S3", "kind": "web", "url": "https://money-flow.datasteg.com/en/world"},
               {"id": "S4", "kind": "dataset", "url": "https://fred.stlouisfed.org/series/GS10"}]
    drew, why = article_volume(run, sources, hosts=hosts)
    assert why is None
    assert drew == {"draws_on": ["money-flow", "open-research"], "draws_on_evidence": {"money-flow": 1, "open-research": 2},
                    "fetch": {"fred": {"series": 1, "rows": 3, "bytes": (run / "data" / "fred" / "fred-a.csv").stat().st_size}}}
    bare = tmp_path / "bare"
    bare.mkdir()
    assert article_volume(bare, [], hosts=hosts) == ({"draws_on": [], "draws_on_evidence": {}, "fetch": {}}, None)   # measured zeros
    kept, _ = article_volume(bare, [], before={"draws_on": ["trade-flow"], "draws_on_note": "by hand"}, hosts=hosts)
    assert kept["draws_on"] == ["trade-flow"] and kept["draws_on_note"] == "by hand" and kept["draws_on_evidence"] == {}
    assert article_volume(None, [], hosts=hosts) == ({"draws_on": [], "draws_on_evidence": {}}, "no run folder")
    (run / "data" / "ecos").mkdir()
    (run / "data" / "ecos" / "ecos-a.csv").write_text("date,value\n")
    drew, why = article_volume(run, sources, hosts=hosts)
    assert "fetch" not in drew and why == "data/ecos has CSV files but no catalog.json"
