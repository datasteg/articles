"""Token usage of a run: every stage session's final stream-json `result` event (subagents included), summed
by stage and by model. Costs are Claude Code's list-price figures, a yardstick, not a bill: the pipeline runs
under the claude.ai login."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .paths import read_json, run_dir, write_json

FIELDS = ("input", "cache_write", "cache_read", "output", "thinking")


def _blank() -> dict:
    return {k: 0 for k in FIELDS} | {"cost_usd": 0.0}


def _add(a: dict, b: dict) -> None:
    for k in FIELDS:
        a[k] += b.get(k, 0)
    a["cost_usd"] += b.get("cost_usd", 0.0)


def _total(d: dict) -> int:
    return d["input"] + d["cache_write"] + d["cache_read"] + d["output"]


def read_log(p: Path) -> dict | None:
    from .logs import open_lines
    result, per_msg = None, {}
    for line in open_lines(p):
        if '"type":"result"' not in line and '"type": "result"' not in line and '"usage"' not in line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "result":
            result = e
        elif e.get("type") == "assistant":   # fallback for a running or killed session: one entry per message id
            msg = e.get("message") or {}
            u = msg.get("usage") or {}
            per_msg[msg.get("id") or len(per_msg)] = (msg.get("model") or "unknown", u)
    if result is None:
        models = {}
        for model, u in per_msg.values():
            d = models.setdefault(f"{model} (estimate, stage not finished)", _blank())
            d["input"] += u.get("input_tokens", 0)
            d["cache_write"] += u.get("cache_creation_input_tokens", 0)
            d["cache_read"] += u.get("cache_read_input_tokens", 0)
            d["output"] += u.get("output_tokens", 0)
        return {"complete": False, "models": models, "turns": len(per_msg), "duration_s": None, "subagents": None}
    models = {}
    for m, u in (result.get("modelUsage") or {}).items():
        models[m] = {"input": u.get("inputTokens", 0), "cache_write": u.get("cacheCreationInputTokens", 0),
                     "cache_read": u.get("cacheReadInputTokens", 0), "output": u.get("outputTokens", 0),
                     "thinking": u.get("thinkingTokens", 0), "cost_usd": u.get("costUSD", 0.0)}
    sub = result.get("subagent_stats") or {}
    return {"complete": True, "models": models, "turns": result.get("num_turns"),
            "duration_s": round((result.get("duration_ms") or 0) / 1000), "subagents": sub.get("spawned"),
            "subagent_types": sub.get("by_type")}


ARTOOLS_CMD = re.compile(r"\bartools\s+([\w-]+)(?:\s+([a-z][\w-]*))?")


def received(p: Path) -> dict:
    """Characters each artools subcommand returned to a session (tool results of Bash calls, subagents included,
    which `subagent_chars` repeats), from its stream-json log. A command that chains several calls counts once,
    under its subcommands joined with '+'."""
    from .logs import open_lines
    pend, got = {}, {}
    for line in open_lines(p):
        if '"tool_use"' not in line and '"tool_result"' not in line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = e.get("message") if isinstance(e.get("message"), dict) else {}
        for c in msg.get("content") if isinstance(msg.get("content"), list) else []:
            if c.get("type") == "tool_use" and c.get("name") == "Bash":
                subs = list(dict.fromkeys(" ".join(filter(None, m)) for m in
                                          ARTOOLS_CMD.findall(c.get("input", {}).get("command", ""))))
                if subs:
                    pend[c["id"]] = "+".join(subs)
            elif c.get("type") == "tool_result" and c.get("tool_use_id") in pend:
                cont = c.get("content")
                txt = cont if isinstance(cont, str) else "".join(
                    x.get("text", "") for x in cont or [] if isinstance(x, dict))
                d = got.setdefault(pend.pop(c["tool_use_id"]), {"calls": 0, "chars": 0, "subagent_chars": 0})
                d["calls"] += 1
                d["chars"] += len(txt)
                if e.get("parent_tool_use_id"):
                    d["subagent_chars"] += len(txt)
    return got


def usage(run_id: str | Path) -> dict:
    run = run_id if isinstance(run_id, Path) else run_dir(run_id)
    from .logs import base, pruned, stage_logs
    stages, models, total = {}, {}, _blank()
    logs = {base(p): p for p in stage_logs(run)}
    gone = {b: v for b, v in pruned(run).items() if b not in logs}   # sessions whose logs were pruned: their summaries
    for name in sorted(set(logs) | set(gone)):
        m = re.match(r"(.+)\.(\d+)$", name)
        stage, attempt = (m.group(1), int(m.group(2))) if m else (name, 1)
        stage = stage.replace("_", ":", 1) if stage.startswith("scout_") else stage
        r = read_log(logs[name]) if name in logs else gone[name].get("usage")
        if r is None:
            continue
        st = stages.setdefault(stage, {"attempts": 0, "complete": True, "turns": 0, "duration_s": 0, "subagents": 0, **_blank()})
        st["attempts"] += 1
        st["complete"] = st["complete"] and r["complete"]
        st["turns"] += r["turns"] or 0
        st["duration_s"] += r["duration_s"] or 0
        st["subagents"] += r["subagents"] or 0
        for sub, d in (received(logs[name]) if name in logs else gone[name].get("received") or {}).items():
            acc = st.setdefault("received", {}).setdefault(sub, {"calls": 0, "chars": 0, "subagent_chars": 0})
            for k in acc:
                acc[k] += d[k]
        for model, u in r["models"].items():
            _add(st, u)
            _add(models.setdefault(model, _blank()), u)
            _add(total, u)
    for d in list(stages.values()) + list(models.values()) + [total]:
        d["total_tokens"] = _total(d)
        d["cost_usd"] = round(d["cost_usd"], 2)
    manifest = read_json(run / "run.json", {}) or {}
    res = {"run": run.name, "question": manifest.get("question"), "pipeline": manifest.get("pipeline") or "explainer",
           "runtime": manifest.get("runtime") or {"model": None, "effort": None, "note": "not recorded (CLI defaults)"},
           "stages": stages, "models": models, "total": total,
           "note": "Tokens from each stage session's final result (subagents included). total_tokens = input + cache "
                   "writes + cache reads + output; thinking is part of output. cost_usd is Claude Code's list-price "
                   "figure, a yardstick: the pipeline runs under the claude.ai login. The session that drove the run "
                   "is not included. received: characters each artools subcommand returned to the stage's sessions "
                   "(subagents included; subagent_chars is their share)."}
    write_json(run / "usage.json", res)
    return res


def table(res: dict) -> str:
    def row(name, d, extra=""):
        return (f"| {name} | {d.get('attempts', '')} | {d['input'] + d['cache_write']:,} | {d['cache_read']:,} | "
                f"{d['output']:,} | {d['thinking']:,} | {d['total_tokens']:,} | {d['cost_usd']:,.2f} |{extra}")
    rt = res.get("runtime") or {}
    lines = [f"Token usage, run {res['run']}",
             f"Type {res.get('pipeline', 'explainer')} · model {rt.get('model') or 'default'} · effort {rt.get('effort') or 'default'}"
             + (f" ({rt['note']})" if rt.get("note") else "")
             + f" · subagents: {', '.join(f'{k} {v}' for k, v in (rt.get('subagents') or {}).items()) or 'as defined'}", "",
             "| Stage | Attempts | Input + cache writes | Cache reads | Output | of which thinking | Total | List-price USD |",
             "|---|---|---|---|---|---|---|---|"]
    for s, d in res["stages"].items():
        lines.append(row(s, d))
    lines.append(row("**all stages**", {**res["total"], "attempts": sum(d["attempts"] for d in res["stages"].values())}))
    lines += ["", "| Model | Input + cache writes | Cache reads | Output | Total | List-price USD |", "|---|---|---|---|---|---|"]
    for m, d in res["models"].items():
        lines.append(f"| {m} | {d['input'] + d['cache_write']:,} | {d['cache_read']:,} | {d['output']:,} | {d['total_tokens']:,} | {d['cost_usd']:,.2f} |")
    lines += ["", res["note"]]
    return "\n".join(lines)


def received_table(run_ids: list[str], prefix: str = "jejualps") -> str:
    """Characters received per artools subcommand per stage, run by run and on average; `prefix` keeps the
    subcommands that start with it ('' keeps all)."""
    per = {}
    for rid in run_ids:
        for stage, st in usage(rid)["stages"].items():
            for sub, d in (st.get("received") or {}).items():
                if sub.startswith(prefix):
                    per.setdefault((stage, sub), {})[rid] = d
    lines = ["| Stage | Subcommand | " + " | ".join(run_ids) + " | Mean chars | Mean calls |",
             "|---|---|" + "---|" * (len(run_ids) + 2)]
    for (stage, sub), by in sorted(per.items()):
        chars = [by.get(r, {}).get("chars", 0) for r in run_ids]
        calls = [by.get(r, {}).get("calls", 0) for r in run_ids]
        lines.append(f"| {stage} | {sub} | " + " | ".join(f"{c:,}" for c in chars)
                     + f" | {sum(chars) / len(run_ids):,.0f} | {sum(calls) / len(run_ids):.1f} |")
    return "\n".join(lines)


def compare(run_ids: list[str]) -> dict:
    """Runs side by side, for weighing model, effort and article type against what each run cost and produced."""
    import datetime as dt
    from . import pipelines
    from .content import _body_words
    rows = []
    for rid in run_ids:
        run = run_dir(rid)
        u = usage(rid)
        m = read_json(run / "run.json", {}) or {}
        plan = read_json(run / "plan.json", {}) or {}
        pub = read_json(run / "publish.json", {}) or {}
        rv = read_json(run / "review.json", {}) or {}
        words = _body_words(read_json(run / "draft" / "en.json", {}) or {}, "en") if (run / "draft" / "en.json").exists() else 0
        stats = pipelines.run_stats(run, {"en": words})
        got = {}
        for sid, st in stats["steps"].items():          # first step that reports a count wins; the scout pass never does
            if sid != "scout":
                for k, v in st.items():
                    got.setdefault(k, v)
        closed = [g for g, v in m.get("gates", {}).items() if not v.get("approved")]
        running = [k for k, v in m.get("stages", {}).items() if v.get("state") in ("running", "redo")]
        state = (f"published {pub.get('tag')}" if pub.get("tag") else f"running {running[0]}" if running
                 else f"at gate {closed[0]}" if closed else "approved")
        end = pub.get("deployed_at") or max([v.get("ended") or "" for v in m.get("stages", {}).values()] or [""])
        hours = None
        if m.get("created") and end:
            t = lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
            hours = round((t(end) - t(m["created"])).total_seconds() / 3600, 1)
        usd = u["total"]["cost_usd"]
        rows.append({
            "run": rid, "title": (plan.get("headline") or {}).get("en") or (m.get("question") or "")[:80],
            "type": u["pipeline"], "model": u["runtime"].get("model"), "effort": u["runtime"].get("effort"), "state": state,
            "sessions": sum(d["attempts"] for d in u["stages"].values()),
            "session_hours": round(sum(d["duration_s"] for d in u["stages"].values()) / 3600, 1), "wall_hours": hours,
            "total_tokens": u["total"]["total_tokens"], "output_tokens": u["total"]["output"], "usd": usd,
            "review_rounds": got.get("rounds"), "review_status": rv.get("status"),
            "blocking_left": len(rv.get("blocking", [])), "advisory_left": len(rv.get("advisory", [])),
            "docs": got.get("docs"), "quotes": got.get("quotes"), "series": got.get("series"), "facts": got.get("facts"),
            "charts": got.get("charts"), "words_en": words or None,
            "usd_per_1000_words": round(usd / words * 1000, 2) if words else None,
        })
    return {"runs": rows, "note": "usd is Claude Code's list price, a yardstick. words_en counts the English prose "
                                  "(findings, paragraphs, lists, quotes, insight). Quality is not measured here: "
                                  "read the articles."}


def compare_table(res: dict) -> str:
    cols = [("run", "Run"), ("type", "Type"), ("model", "Model"), ("effort", "Effort"), ("state", "State"),
            ("usd", "USD"), ("total_tokens", "Tokens"), ("output_tokens", "Output"), ("sessions", "Sessions"),
            ("wall_hours", "Hours"), ("review_rounds", "Review rounds"), ("docs", "Docs"), ("quotes", "Quotes"),
            ("series", "Series"), ("facts", "Facts"), ("charts", "Charts"), ("words_en", "Words"),
            ("usd_per_1000_words", "USD / 1k words")]
    f = lambda v: "—" if v is None else f"{v:,}" if isinstance(v, int) else f"{v:,.2f}" if isinstance(v, float) else str(v)
    lines = ["| " + " | ".join(h for _, h in cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(f(r.get(k)) for k, _ in cols) + " |" for r in res["runs"]]
    return "\n".join(lines + ["", res["note"]])
