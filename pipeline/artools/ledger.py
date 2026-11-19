"""The run ledger: a run's manifest, stage logs, driver logs and the git history of its skills reduced to one JSON file
(~50 KB) in /data/articles/ledger/runs/<run>.json, plus catalog.json (the pipelines and every skill's revisions).
The admin's Newsroom pages read them in its dev server. The ledger stays on this
machine: it is never committed and never deployed.

Each file is rebuilt from scratch, so a newer ledger.py fills in old runs (`artools ledger --all`). What can't be
recovered from an old run's logs goes in `gaps`, never a zero."""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from .paths import ARTICLES, CONFIG, DATA, RUNS, SKILLS, load_yaml, read_json, write_json

LEDGER = DATA / "ledger"
LEDGER_VERSION = 1
REPO = ARTICLES.parent
AGENTS = ARTICLES / ".claude" / "agents"
REVIEW_SKILLS = ("review-article", "review-podcast", "review-video")
GAP_S = 300                     # idle stretches longer than this count as waiting
WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}


# ---------- small helpers

def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def _iso(t: float | dt.datetime | None) -> str | None:
    if t is None:
        return None
    if isinstance(t, (int, float)):
        t = dt.datetime.fromtimestamp(t, dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


REDACT = [
    (re.compile(r"postgres(?:ql)?://\S+"), "postgres://…"),
    (re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key)\b(\s*[=:]\s*)\S+"), r"\1\2…"),
    (re.compile(re.escape(str(Path.home()))), "~"),
]


def redact(s: str, n: int | None = None) -> str:
    for rx, rep in REDACT:
        s = rx.sub(rep, s)
    return s if n is None or len(s) <= n else s[: n - 1] + "…"


def _count(word: str) -> int | None:
    return int(word) if word.isdigit() else WORDS.get(word.lower())


# ---------- skill revisions and fingerprints

def _version_at(commit: str | None, skill_md: Path) -> str | None:
    text = _git("show", f"{commit}:{skill_md.relative_to(REPO)}") if commit else skill_md.read_text(encoding="utf-8")
    m = re.search(r"^\s*version:\s*['\"]?([\w.]+)", text, re.M)
    return m.group(1) if m else None


def _revision(path: Path, md: Path, before: str | None, dirty: bool) -> dict:
    line = _git("log", "-1", "--format=%h %cI", *([f"--before={before}"] if before else []), "--", str(path.relative_to(REPO)))
    commit, date = (line.split() + [None, None])[:2] if line else (None, None)
    rec = {"version": _version_at(commit, md) if commit else None, "commit": commit, "date": date}
    if dirty:      # stamped at the run's start: the working copy is what the stages load
        rec["version"] = _version_at(None, md)
        rec["dirty"] = bool(_git("status", "--porcelain", "--", str(path.relative_to(REPO))))
    return rec


def skill_revisions(before: str | None = None, dirty: bool = False) -> dict:
    """Every skill's and agent's version and the last commit to its folder (before `before`, an ISO time). With
    dirty=True (the driver, at a run's start) the working copy's version, and whether it has uncommitted changes."""
    skills = {d.name: _revision(d, d / "SKILL.md", before, dirty) for d in sorted(SKILLS.iterdir()) if (d / "SKILL.md").exists()}
    agents = {f.stem: _revision(f, f, before, dirty) for f in sorted(AGENTS.glob("*.md"))}
    code = _git("log", "-1", "--format=%h", *([f"--before={before}"] if before else []), "--", "articles/pipeline")
    return {"skills": skills, "agents": agents, "pipeline_code": code or None}


def fingerprints(stages: dict, manifest: dict) -> dict:
    """What the logs show a skill did, which wins over git when the two disagree (uncommitted edits during a run)."""
    fp = {}
    got = {}
    for st in ("search-jejualps", "scout:search-jejualps"):
        got.update((stages.get(st) or {}).get("received") or {})
    if got:   # search-jejualps 0.2.0 (013aa07): search_lines() output and `cite` for Evidence doc blocks
        fp["search-jejualps"] = "lines" if any("jejualps cite" in k for k in got) else "rows"
    if str(manifest.get("pipeline", "")).startswith("video"):
        fp["video"] = manifest.get("mode") or ("podcast" if manifest.get("pipeline") == "video-podcast" else "narrated")
    return fp


# ---------- one stage session

def _attempt(p: Path) -> dict:
    res = init = None
    tools, recv, pend, val = Counter(), {}, {}, {}
    val_fail, rate = 0, {}
    from .logs import base, open_lines
    for line in open_lines(p):
        if not any(k in line for k in ('"tool_use"', '"tool_result"', '"result"', '"init"', "rate_limit_event")):
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = e.get("type")
        if t == "result":
            res = e
            continue
        if t == "system" and e.get("subtype") == "init":
            init = e
            continue
        if t == "rate_limit_event":
            for k, w in ((e.get("rate_limit_info") or {}).get("unifiedWindows") or {}).items():
                rate[k] = max(rate.get(k, 0), w.get("utilization") or 0)
            continue
        msg = e.get("message") if isinstance(e.get("message"), dict) else {}
        for c in msg.get("content") if isinstance(msg.get("content"), list) else []:
            if c.get("type") == "tool_use":
                tools[c.get("name")] += 1
                if c.get("name") == "Bash":
                    cmd = (c.get("input") or {}).get("command", "")
                    from .usage import ARTOOLS_CMD
                    subs = list(dict.fromkeys(" ".join(filter(None, m)) for m in ARTOOLS_CMD.findall(cmd)))
                    if subs:
                        pend[c["id"]] = "+".join(subs)
                    if re.search(r"\bartools\s+(validate|run\s+done)\b", cmd):
                        val[c["id"]] = True
            elif c.get("type") == "tool_result":
                tid = c.get("tool_use_id")
                cont = c.get("content")
                txt = cont if isinstance(cont, str) else "".join(
                    x.get("text", "") for x in cont or [] if isinstance(x, dict))
                if tid in pend:
                    d = recv.setdefault(pend.pop(tid), {"calls": 0, "chars": 0, "subagent_chars": 0})
                    d["calls"] += 1
                    d["chars"] += len(txt)
                    if e.get("parent_tool_use_id"):
                        d["subagent_chars"] += len(txt)
                if val.pop(tid, None) and (c.get("is_error") or re.search(r'"(ok|valid|passed)":\s*false', txt)):
                    val_fail += 1
    a = {"file": base(p) + ".jsonl", "end": _iso(p.stat().st_mtime), "complete": res is not None, "tools": dict(tools),
         "received": recv, "validate_failures": val_fail, "rate_limit": {k: round(v, 2) for k, v in rate.items()},
         "claude_code": (init or {}).get("claude_code_version")}
    if res is None:
        a["gap"] = "the session has no final result (killed, timed out or still running)"
        return a
    models, tok = {}, Counter()
    for m, u in (res.get("modelUsage") or {}).items():
        d = {"input": u.get("inputTokens", 0), "cache_write": u.get("cacheCreationInputTokens", 0),
             "cache_read": u.get("cacheReadInputTokens", 0), "output": u.get("outputTokens", 0),
             "thinking": u.get("thinkingTokens", 0)}
        tok.update(d)
        models[m] = {"cost_usd": round(u.get("costUSD", 0.0), 4), "tokens": sum(d[k] for k in ("input", "cache_write", "cache_read", "output"))}
    inp = tok["input"] + tok["cache_write"] + tok["cache_read"]
    den = Counter()
    for d in res.get("permission_denials") or []:
        den[_denial_key(d.get("tool_name") or "?", d.get("tool_input") or {})] += 1
    sub = res.get("subagent_stats") or {}
    a.update({
        "seconds": round((res.get("duration_ms") or 0) / 1000), "turns": res.get("num_turns"),
        "tokens": dict(tok), "cost_usd": round(res.get("total_cost_usd") or sum(m["cost_usd"] for m in models.values()), 4),
        "models": models, "cache_read_share": round(tok["cache_read"] / inp, 3) if inp else None,
        "subagents": sub.get("by_type") or {}, "denials": [{"pattern": k[0], "example": k[1], "count": n} for k, n in den.most_common()],
        "denial_count": sum(den.values()), "is_error": bool(res.get("is_error")), "end_reason": res.get("terminal_reason") or res.get("subtype"),
        "result": redact(res.get("result") or "", 900),
    })
    return a


def _denial_key(tool: str, inp: dict) -> tuple[str, str]:
    """A denied call as (pattern, example): Bash by its first command words with `cd …;` prefixes and paths removed."""
    if tool == "Bash":
        cmd = inp.get("command", "")
        body = re.sub(r"^\s*(cd\s+\S+\s*(;|&&)\s*)+", "", cmd)
        words = [w for w in re.split(r"\s+", body.strip()) if w][:2]
        head = " ".join("…" if "/" in w else w for w in words)
        return f"Bash: {head}", redact(cmd.replace("\n", " "), 160)
    target = inp.get("file_path") or inp.get("path") or inp.get("url") or ""
    return f"{tool}: {Path(target).parent.name or target}" if target else tool, redact(str(target), 160)


# ---------- driver logs and events

EXIT = re.compile(r"\] (\S+): exit (-?\d+), state (\w+), (\d+)s, log (\S+)")
LOOP = re.compile(r"\] review loop (\d+): fixing \[(.*?)\]")


def _driver_lines(run: Path) -> list[str]:
    files = [p for p in (run / "logs").iterdir() if p.suffix in (".txt", ".out") and not p.name.startswith(("ship", "korean-publish"))]
    lines = []
    for p in sorted(files, key=lambda x: x.stat().st_mtime):
        lines += p.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines


def _events(run: Path) -> list[dict]:
    p = run / "logs" / "events.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


# ---------- review rounds

def _round_files(run: Path) -> dict[int, Path]:
    found = {}
    for p in list(run.glob("review.round*.json")) + list((run / "reviews").glob("round-*.json")):
        m = re.search(r"(\d+)\.json$", p.name)
        if m:
            found[int(m.group(1))] = p
    return found


def _issues(rv: dict) -> list[dict]:
    return [{"where": redact(str(b.get("where", "")), 200), "issue": redact(str(b.get("issue", "")), 320),
             "owner": b.get("owner"), "kind": b.get("kind"), "from": b.get("from")} for b in rv.get("blocking") or []]


def _key(i: dict) -> str:
    return f"{i.get('owner')}|{re.sub(r'[^a-z0-9]+', ' ', str(i.get('where', '')).lower())[:50]}"


def _review(run: Path, reviews: list[dict], loops: dict[int, list[str]]) -> dict:
    files = _round_files(run)
    rounds, prev, gaps = [], None, []
    for i, a in enumerate(reviews, 1):
        r = {"n": i, "attempt": a["file"], "cost_usd": a.get("cost_usd"), "seconds": a.get("seconds")}
        rv = read_json(files[i]) if i in files else (read_json(run / "review.json") if i == len(reviews) else None)
        if rv:
            iss = _issues(rv)
            r.update({"blocking": len(iss), "advisory": len(rv.get("advisory") or []), "status": rv.get("status"),
                      "by_owner": dict(Counter(x["owner"] for x in iss)), "issues": iss, "recorded": "file"})
            keys = {_key(x) for x in iss}
            if prev is not None:
                for x in iss:
                    x["status"] = "carried" if _key(x) in prev else "new"
                r["closed"] = len(prev - keys)
            prev = keys
        else:
            prev = None
            m = re.search(r"\b(\d+|" + "|".join(WORDS) + r") (?:new )?blocking", a.get("result") or "", re.I)
            adv = re.search(r"\b(\d+|" + "|".join(WORDS) + r") advisory", a.get("result") or "", re.I)
            r.update({"blocking": _count(m.group(1)) if m else None, "advisory": _count(adv.group(1)) if adv else None,
                      "recorded": "summary" if m else "missing"})
            gaps.append(f"review round {i}: issues not kept" + ("" if m else ", count unknown"))
        if i in loops:
            r["sent_to"] = loops[i]
        rounds.append(r)
    return {"rounds": rounds, "gaps": gaps}


# ---------- time

def _busy(attempts: list[dict], cmds: list[dict]) -> list[tuple[float, float]]:
    iv = sorted((x["_s"], x["_e"]) for x in attempts + cmds if x.get("_s") is not None)
    merged = []
    for s, e in iv:
        if merged and s <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _waits(busy: list[tuple[float, float]], gates: dict, attempts: list[dict]) -> list[dict]:
    out = []
    for (s0, e0), (s1, _) in zip(busy, busy[1:]):
        if s1 - e0 < GAP_S:
            continue
        w = {"start": _iso(e0), "end": _iso(s1), "seconds": round(s1 - e0), "kind": "stopped"}
        for name, g in (gates or {}).items():
            at = _ts((g or {}).get("at"))
            if at and e0 - 60 <= at <= s1 + 60 and "driver" not in str(g.get("note") or "") and "autonomous" not in str(g.get("by") or ""):
                w.update(kind="gate", gate=name)
        before = [a for a in attempts if a.get("_e") and abs(a["_e"] - e0) < 120]
        if w["kind"] == "stopped" and any((a.get("rate_limit") or {}).get("five_hour", 0) >= 0.95 or a.get("is_error") for a in before):
            w["kind"] = "usage limit"
        out.append(w)
    return out


# ---------- one run

def _pipeline_yaml(pid: str | None) -> dict | None:
    from . import pipelines
    try:
        return pipelines.load(pid or pipelines.DEFAULT)
    except SystemExit:   # an old run whose pipeline id no longer exists
        return None


def _phase_map(manifest: dict) -> dict:
    m = {}
    for s in (_pipeline_yaml(manifest.get("pipeline")) or {}).get("steps", []):
        if s.get("skill"):
            m[s["skill"]] = s.get("phase")
        if s.get("command"):
            m[f"cmd:{s['command']}"] = s.get("phase")
        if s.get("sources") == "scout":
            m["scout:*"] = s.get("phase")
        if s.get("fetch") == "routed":
            m["fetch:*"] = s.get("phase")
    return m


def _phase_of(stage: str, pm: dict) -> str | None:
    if stage in pm:
        return pm[stage]
    if stage.startswith("scout:"):
        return pm.get("scout:*")
    if stage.startswith("fetch-"):
        return pm.get("fetch:*")
    return None


def build(run: Path) -> dict:
    manifest = read_json(run / "run.json", {}) or {}
    kind = "video" if str(manifest.get("pipeline", "")).startswith("video") or manifest.get("type") == "video" else "article"
    gaps: list[str] = []
    lines = _driver_lines(run)
    exits = {m.group(5): (int(m.group(2)), m.group(3), int(m.group(4))) for m in map(EXIT.search, lines) if m}
    loops: dict[int, list[str]] = {}
    for m in map(LOOP.search, lines):
        if m:   # one review loop numbering per drive; count them through the whole log
            loops[len(loops) + 1] = [x.strip(" '\"") for x in m.group(2).split(",") if x.strip()]
    ev = _events(run)
    for e in ev:
        if e.get("kind") == "stage_exit" and e.get("log"):
            exits[e["log"]] = (e.get("rc"), e.get("state"), e.get("seconds"))
    if not lines and not ev:
        gaps.append("no driver log: attempt times come from the session logs")

    from .logs import base, pruned, stage_logs
    attempts = []
    logs = {base(p): p for p in stage_logs(run)}
    gone = {b: v["attempt"] for b, v in pruned(run).items() if b not in logs and v.get("attempt")}
    if gone:
        gaps.append(f"{len(gone)} session log(s) pruned: their summaries are kept, not their transcripts")
    for name in sorted(set(logs) | set(gone)):
        m = re.match(r"(.+)\.(\d+)$", name)
        stage, n = (m.group(1), int(m.group(2))) if m else (name, 1)
        stage = stage.replace("_", ":", 1) if stage.startswith("scout_") else stage
        a = {"stage": stage, "n": n, **(_attempt(logs[name]) if name in logs else dict(gone[name]))}
        a.pop("_s", None), a.pop("_e", None)
        fname = f"{name}.jsonl"
        if fname in exits:
            rc, state, secs = exits[fname]
            a.update(exit=rc, state=state, wall_seconds=secs)
        secs = a.get("wall_seconds") or a.get("seconds")
        a["_e"] = _ts(a["end"])
        a["_s"] = a["_e"] - secs if secs else None
        a["start"] = _iso(a["_s"]) if a["_s"] else None
        attempts.append(a)
    attempts.sort(key=lambda a: a["_e"])

    # command steps (video): run.json keeps the last start and end; events.jsonl keeps every one
    cmds = []
    for name, st in (manifest.get("stages") or {}).items():
        if name.startswith("cmd:") and st.get("started") and st.get("ended"):
            s, e = _ts(st["started"]), _ts(st["ended"])
            cmds.append({"stage": name, "start": st["started"], "end": st["ended"], "seconds": round(e - s), "state": st.get("state"), "_s": s, "_e": e})

    # rounds: an attempt's round is the number of reviews finished before it
    reviews, done = [], 0
    for a in attempts:
        if a["stage"] in REVIEW_SKILLS:
            done += 1
            a["review_round"] = done
            reviews.append(a)
        else:
            a["round"] = done
    seen: set[str] = set()
    for a in attempts:   # a fix: a review round after the first, or a stage run again after a review sent issues back
        a["fix"] = a.get("review_round", 1) > 1 or (a.get("round", 0) > 0 and a["stage"] in seen)
        seen.add(a["stage"])
    review = _review(run, reviews, loops) if reviews else {"rounds": [], "gaps": []}
    gaps += review.pop("gaps")

    pm = _phase_map(manifest)
    stages: dict[str, dict] = {}
    for a in attempts:
        st = stages.setdefault(a["stage"], {"attempts": 0, "fix_attempts": 0, "seconds": 0, "cost_usd": 0.0, "fix_cost_usd": 0.0,
                                            "tokens": Counter(), "denials": 0, "validate_failures": 0, "received": {},
                                            "tools": Counter(), "phase": _phase_of(a["stage"], pm)})
        st["attempts"] += 1
        fix = a["fix"]
        st["fix_attempts"] += fix
        st["seconds"] += a.get("wall_seconds") or a.get("seconds") or 0
        st["cost_usd"] += a.get("cost_usd") or 0
        st["fix_cost_usd"] += (a.get("cost_usd") or 0) if fix else 0
        st["tokens"].update(a.get("tokens") or {})
        st["tools"].update(a.get("tools") or {})
        st["denials"] += a.get("denial_count") or 0
        st["validate_failures"] += a.get("validate_failures") or 0
        for k, d in (a.get("received") or {}).items():
            acc = st["received"].setdefault(k, {"calls": 0, "chars": 0, "subagent_chars": 0})
            for f in acc:
                acc[f] += d.get(f, 0)
    for c in cmds:
        stages[c["stage"]] = {"attempts": 1, "fix_attempts": 0, "seconds": c["seconds"], "cost_usd": 0.0, "fix_cost_usd": 0.0,
                              "tokens": {}, "denials": 0, "validate_failures": 0, "received": {}, "tools": {},
                              "phase": _phase_of(c["stage"], pm), "command": True}
    for st in stages.values():
        st["cost_usd"], st["fix_cost_usd"] = round(st["cost_usd"], 2), round(st["fix_cost_usd"], 2)
        st["tokens"], st["tools"] = dict(st["tokens"]), dict(st["tools"])

    phases: dict[str, dict] = {}
    for a in attempts + cmds:
        ph = _phase_of(a["stage"], pm) or "other"
        d = phases.setdefault(ph, {"id": ph, "cost_usd": 0.0, "seconds": 0, "_s": a["_s"], "_e": a["_e"]})
        d["cost_usd"] += a.get("cost_usd") or 0
        d["seconds"] += a.get("wall_seconds") or a.get("seconds") or 0
        if a["_s"] is not None:
            d["_s"] = min(x for x in (d["_s"], a["_s"]) if x is not None)
        d["_e"] = max(d["_e"], a["_e"])
    order = [p["id"] for p in ((_pipeline_yaml(manifest.get("pipeline")) or {}).get("phases") or [])]
    phase_list = sorted(phases.values(), key=lambda d: order.index(d["id"]) if d["id"] in order else 99)
    for d in phase_list:
        d.update(start=_iso(d.pop("_s")), end=_iso(d.pop("_e")), cost_usd=round(d["cost_usd"], 2))

    busy = _busy(attempts, cmds)
    pub = read_json(run / "publish.json", {}) or {}
    start = busy[0][0] if busy else _ts(manifest.get("created"))
    end_mark = _ts(pub.get("deployed_at")) if kind == "article" else None
    if kind == "video":
        ups = [_ts((read_json(run / "youtube" / f"{l}.json", {}) or {}).get("uploaded")) for l in ("en", "ko")]
        end_mark = max([u for u in ups if u] or [0]) or None
    last = max([busy[-1][1]] if busy else [0])
    end = max(x for x in (end_mark, last) if x) if (end_mark or last) else None
    waits = _waits(busy, manifest.get("gates") or {}, attempts)
    total = {"cost_usd": round(sum(a.get("cost_usd") or 0 for a in attempts), 2),
             "tokens": dict(sum((Counter(a.get("tokens") or {}) for a in attempts), Counter())),
             "attempts": len(attempts), "fix_attempts": sum(1 for a in attempts if a["fix"]),
             "denials": sum(a.get("denial_count") or 0 for a in attempts),
             "validate_failures": sum(a.get("validate_failures") or 0 for a in attempts),
             "rate_limit_max": {k: max((a.get("rate_limit") or {}).get(k, 0) for a in attempts) for k in ("five_hour", "seven_day")} if attempts else {}}
    by_model: dict[str, dict] = {}
    for a in attempts:
        for m, d in (a.get("models") or {}).items():
            acc = by_model.setdefault(m, {"cost_usd": 0.0, "tokens": 0})
            acc["cost_usd"] = round(acc["cost_usd"] + d["cost_usd"], 4)
            acc["tokens"] += d["tokens"]
    total["models"] = by_model
    if any(not a["complete"] for a in attempts):
        gaps.append(f"{sum(not a['complete'] for a in attempts)} session(s) without a final result: their cost is not counted")

    # configuration
    rt = manifest.get("runtime") or {}
    revs = rt.get("skills_stamp") or skill_revisions(before=_iso(start) if start else None)
    used = {a["stage"].split(":")[-1] for a in attempts} | {s.split(":")[-1] for s in (manifest.get("stages") or {}) if not s.startswith("cmd:")}
    skills = {k: v for k, v in revs["skills"].items() if k in used}
    for name, st in (manifest.get("stages") or {}).items():
        if st.get("version") and name.split(":")[-1] in skills:
            skills[name.split(":")[-1]]["declared"] = st["version"]
    fp = fingerprints(stages, manifest)
    for k, v in fp.items():
        if k in skills:
            skills[k]["fingerprint"] = v
    notes = [str((g or {}).get("note") or "") for g in (manifest.get("gates") or {}).values()] if isinstance(manifest.get("gates"), dict) else []
    gate_policy = "auto+publish-anyway" if any("on_blocking" in n for n in notes) else "auto" if any("gates.auto" in n for n in notes) else "manual" if notes else None
    people = [g for g in (manifest.get("gates") or {}).values() if isinstance(manifest.get("gates"), dict) and g and g.get("approved")
              and "driver" not in str(g.get("note") or "") and "autonomous" not in str(g.get("by") or "")]
    if gate_policy and people and gate_policy != "manual":
        gate_policy += " (some approved by hand)"
    config = {"pipeline": manifest.get("pipeline") or manifest.get("type") or "explainer", "pipeline_version": manifest.get("pipeline_version"),
              "model": rt.get("model"), "effort": rt.get("effort"), "subagents": rt.get("subagents"), "note": rt.get("note"),
              "recorded_afterwards": "afterwards" in str(rt.get("note") or ""), "gates": gate_policy,
              "claude_code": sorted({a["claude_code"] for a in attempts if a.get("claude_code")}),
              "skills": skills, "agents": revs.get("agents"), "pipeline_code": revs.get("pipeline_code"),
              "stamped": bool(rt.get("skills_stamp")), "fingerprints": fp}
    if config["recorded_afterwards"]:
        gaps.append("model and effort filled in afterwards from the CLI defaults")
    if not config["stamped"]:
        gaps.append("skill revisions inferred from git at the run's start (not stamped by the driver)")

    # outcome and links
    slug = pub.get("slug") or (manifest.get("source") or {}).get("slug")
    meta = read_json(ARTICLES / "content" / "articles" / slug / "meta.json", {}) if slug else {}
    outcome = {}
    if kind == "article":
        outcome = {"slug": slug, "commit": pub.get("commit"), "tag": pub.get("tag"), "deployed_at": pub.get("deployed_at"),
                   "url": pub.get("url"), "url_ko": pub.get("url_ko"),
                   "review_left": len(pub["review_left"]) if isinstance(pub.get("review_left"), list) else pub.get("review_left"),
                   "cover_left_out": pub.get("cover_left_out"), "corrections": len((meta or {}).get("corrections") or []),
                   "updated": (meta or {}).get("updated"), "previous": len(pub.get("previous") or []),
                   "steps": (meta or {}).get("run", {}).get("steps") if isinstance((meta or {}).get("run"), dict) else None,
                   "title": {l: (read_json(ARTICLES / "content" / "articles" / slug / f"{l}.json", {}) or {}).get("title")
                             for l in ("en", "ko")} if slug else None}
        video_runs = sorted(p.parent.name for p in RUNS.glob("*/run.json")
                            if ((read_json(p, {}) or {}).get("source") or {}).get("article_run") == run.name)
    else:
        rv = read_json(run / "review.json", {}) or {}
        outcome = {"slug": slug, "article_run": (manifest.get("source") or {}).get("article_run"), "mode": manifest.get("mode"),
                   "youtube": {l: {k: (read_json(run / "youtube" / f"{l}.json", {}) or {}).get(k) for k in ("video_id", "url", "privacy", "uploaded")}
                               for l in ("en", "ko") if (run / "youtube" / f"{l}.json").exists()},
                   "review_blocking": len(rv.get("blocking") or []), "review_advisory": len(rv.get("advisory") or []),
                   "replaces": manifest.get("replaces")}
        video_runs = []
    research = {}
    if kind == "article":
        for st, label in (("scout:search-jejualps", "scout"), ("search-jejualps", "deep")):
            got = (stages.get(st) or {}).get("received") or {}
            research[label] = {"chars": sum(d["chars"] for d in got.values()), "calls": sum(d["calls"] for d in got.values()),
                               "search_chars": sum(d["chars"] for k, d in got.items() if "jejualps search" in k),
                               "search_calls": sum(d["calls"] for k, d in got.items() if "jejualps search" in k)}
        steps = outcome.get("steps") or {}
        research["evidence"] = {"docs": (steps.get("search") or {}).get("docs"), "quotes": (steps.get("search") or {}).get("quotes"),
                                "scout_docs": (steps.get("scout") or {}).get("docs")}

    for a in attempts:
        a.pop("_s", None), a.pop("_e", None)
    for c in cmds:
        c.pop("_s", None), c.pop("_e", None)
    return {
        "id": run.name, "kind": kind, "ledger_version": LEDGER_VERSION, "built": _iso(dt.datetime.now(dt.timezone.utc)),
        "question": manifest.get("question"), "created": manifest.get("created"), "slug": slug,
        "video_runs": video_runs, "config": config,
        "time": {"start": _iso(start), "end": _iso(end), "wall_s": round(end - start) if start and end else None,
                 "working_s": sum(a.get("wall_seconds") or a.get("seconds") or 0 for a in attempts) + sum(c["seconds"] for c in cmds),
                 "busy_s": round(sum(e - s for s, e in busy)), "waits": waits},
        "total": total, "phases": phase_list, "stages": stages, "attempts": attempts, "commands": cmds,
        "review": review, "research": research, "outcome": outcome, "gaps": gaps,
    }


def write(run: Path) -> Path:
    led = build(run)
    p = LEDGER / "runs" / f"{run.name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_json(p, led)
    return p


# ---------- catalog

def catalog() -> Path:
    pipes = []
    files = sorted((CONFIG / "pipelines").glob("*.yaml")) + sorted((CONFIG / "video").glob("*pipeline*.yaml"))
    for f in files:
        y = load_yaml(f) or {}
        if not y.get("steps"):
            continue
        pid = y.get("id") or ("video-podcast" if "podcast" in f.name else "video")
        steps = []
        for s in y["steps"]:
            steps.append({k: s[k] for k in ("id", "skill", "phase", "gate", "command", "sources", "fetch", "mode", "loop",
                                            "manual", "follows", "chrome", "extra_scout") if k in s}
                         | {"label": (s.get("label") or {}).get("en"), "detail": (s.get("detail") or {}).get("en"),
                            "branches": [b.get("en") for b in s.get("branches") or []]})
        pipes.append({"id": pid, "file": str(f.relative_to(ARTICLES)), "version": str(y.get("version")), "status": y.get("status"),
                      "name": (y.get("name") or {}).get("en") if isinstance(y.get("name"), dict) else y.get("name"),
                      "phases": [{"id": p["id"], "label": (p.get("label") or {}).get("en")} for p in y.get("phases") or []],
                      "steps": steps,
                      "history": [dict(zip(("commit", "date", "subject"), l.split("|", 2)))
                                  for l in _git("log", "--format=%h|%cI|%s", "--", str(f.relative_to(REPO))).splitlines()]})

    def entry(path: Path, md: Path) -> dict:
        text = md.read_text(encoding="utf-8")
        fm = re.search(r"^---\n(.*?)\n---", text, re.S)
        y = load_yaml_text(fm.group(1)) if fm else {}
        hist = []
        for l in _git("log", "--format=%h|%cI|%s", "--", str(path.relative_to(REPO))).splitlines():
            h, d, s = l.split("|", 2)
            hist.append({"commit": h, "date": d, "subject": s, "version": _version_at(h, md)})
        return {"name": y.get("name") or path.stem, "description": y.get("description"),
                "version": (y.get("metadata") or {}).get("version") or y.get("version"), "family": (y.get("metadata") or {}).get("family"),
                "model": y.get("model"), "path": str(md.relative_to(REPO)),
                "dirty": bool(_git("status", "--porcelain", "--", str(path.relative_to(REPO)))), "history": hist}

    skills = {d.name: entry(d, d / "SKILL.md") for d in sorted(SKILLS.iterdir()) if (d / "SKILL.md").exists()}
    agents = {f.stem: entry(f, f) for f in sorted(AGENTS.glob("*.md"))}
    p = LEDGER / "catalog.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_json(p, {"built": _iso(dt.datetime.now(dt.timezone.utc)), "ledger_version": LEDGER_VERSION,
                   "repo": "https://github.com/datasteg/articles", "pipelines": pipes, "skills": skills, "agents": agents})
    return p


def load_yaml_text(s: str) -> dict:
    import yaml
    try:
        return yaml.safe_load(s) or {}
    except yaml.YAMLError:
        return {}


def deploy_admin(force: bool = False) -> dict:
    """config/editorial.yaml → newsroom.deploy: when a ledger file changed since the last admin deploy, copy the ledger
    into the admin app (admin/scripts/sync-ledger.sh, gitignored) and `ds deploy admin` the next tag. The ledger rides
    in the private image to the admin site, behind Google sign-in; it is never committed."""
    import hashlib
    from .runlib import flock_file
    if not ((load_yaml(CONFIG / "editorial.yaml") or {}).get("newsroom") or {}).get("deploy") and not force:
        return {"deployed": None, "why": "newsroom.deploy is off"}
    with flock_file(DATA / ".admin-deploy.lock"):
        state_f = LEDGER / ".deployed.json"
        state = read_json(state_f, {}) or {}
        files = sorted((LEDGER / "runs").glob("*.json")) + sorted((LEDGER / "desk").rglob("*.json"))   # runs, and the desk's review queue
        digest = hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()
        if digest == state.get("digest") and not force:
            return {"deployed": None, "why": "the ledger hasn't changed since the last deploy"}
        catalog()
        admin = REPO / "admin"
        st = subprocess.run(["ds", "status", "admin"], capture_output=True, text=True).stdout
        cur = re.search(r"current:\s*(\d{8})\.(\d+)", st)
        today = dt.datetime.now().strftime("%Y%m%d")
        tag = f"{today}.{int(cur.group(2)) + 1 if cur and cur.group(1) == today else 1}"
        subprocess.run([str(admin / "scripts" / "sync-ledger.sh")], cwd=admin, check=True, capture_output=True)
        r = subprocess.run(["ds", "deploy", "admin", tag], cwd=admin, capture_output=True, text=True, timeout=1500)
        if r.returncode != 0:
            return {"deployed": None, "tag": tag, "why": f"ds deploy failed: {(r.stdout + r.stderr)[-600:]}"}
        write_json(state_f, {"digest": digest, "tag": tag, "at": _iso(dt.datetime.now(dt.timezone.utc))})
        return {"deployed": tag}


def ledger(run_ids: list[str], all_runs: bool = False, with_catalog: bool = True) -> dict:
    from .paths import run_dir
    runs = sorted(p.parent for p in RUNS.glob("*/run.json")) if all_runs else [run_dir(r) for r in run_ids]
    written = [str(write(r)) for r in runs]
    if all_runs:   # a run folder that was removed takes its ledger file with it
        for f in (LEDGER / "runs").glob("*.json"):
            if not (RUNS / f.stem / "run.json").exists():
                f.unlink()
    return {"runs": written, "catalog": str(catalog()) if with_catalog else None}
