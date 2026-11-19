"""The driver: runs the steps of a run's pipeline (config/pipelines/<type>.yaml), each stage as its own headless
Claude Code session, source skills in parallel, stopping at the editor's gates.

Each stage is `claude -p "/<skill> <run-id> [mode]"` started in articles/, so the project skills and agents load.
A stage is done when its skill has called `artools run done` (which validates the output). Logs go to
<run>/logs/<stage>.jsonl (stream-json)."""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import pipelines, runlib
from .paths import ARTICLES, CONFIG, DATA, RUNS, SKILLS, load_yaml, read_json, run_dir

# Stage sessions may write only inside /data/articles (their run, the reading cache): the repository's code, skills
# and site are shared by every run. Edit(...) rules cover Write and Edit alike.
ALLOWED = [
    "Read", "Edit(//data/articles/**)", "Glob", "Grep", "Agent", "TodoWrite",
    "Bash(artools *)",
    f"Bash(python3 {SKILLS}/*)",
]
# Claude in Chrome, for steps marked `chrome: true` (the podcast video's NotebookLM step)
CHROME_TOOLS = ["ToolSearch", "mcp__claude-in-chrome__*", f"Read({Path.home()}/Downloads/**)"]
STAGE_TIMEOUT_S = 60 * 60
PROVIDER_SKILL = {"ecb": "fetch-public-data", "eurostat": "fetch-public-data", "imf": "fetch-public-data",
                  "bis": "fetch-public-data", "oecd": "fetch-public-data", "fred": "fetch-fred", "ecos": "fetch-ecos"}
SOURCE_SKILL = {"jejualps": "search-jejualps", "public-data": "fetch-public-data", "ecb": "fetch-public-data",
                "eurostat": "fetch-public-data", "fred": "fetch-fred", "ecos": "fetch-ecos"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def event(run: Path, kind: str, **fields) -> None:
    """logs/events.jsonl: one JSON line per driver event (UTC), read by `artools ledger`; the text log is for people."""
    try:
        with (run / "logs" / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": runlib.now(), "kind": kind, **fields}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def keep_review(run: Path) -> None:
    """Every review round's review.json, as reviews/round-<n>.json (the next round overwrites review.json)."""
    if not (run / "review.json").exists():
        return
    d = run / "reviews"
    d.mkdir(exist_ok=True)
    shutil.copy2(run / "review.json", d / f"round-{len(list(d.glob('round-*.json'))) + 1}.json")


def stamp_skills(run: Path) -> None:
    """run.json → runtime.skills_stamp at the run's first drive: each skill's and agent's version, the last commit to
    its folder and whether it had uncommitted changes, so the ledger knows what the stages loaded."""
    m = read_json(run / "run.json", {}) or {}
    if (m.get("runtime") or {}).get("skills_stamp") or m.get("stages"):
        return
    from .ledger import skill_revisions
    stamp = skill_revisions(dirty=True)
    with runlib.locked(run):
        m = runlib.load(run)
        m.setdefault("runtime", {})["skills_stamp"] = stamp
        from .paths import write_json
        write_json(run / "run.json", m)


def stage_state(run: Path, stage: str) -> str | None:
    return (read_json(run / "run.json", {}).get("stages", {}).get(stage) or {}).get("state")


def run_skill(run: Path, skill: str, mode: str | None = None, extra: str = "", model: str | None = None,
              chrome: bool = False) -> bool:
    stage = f"scout:{skill}" if mode == "scout" else skill
    if stage_state(run, stage) == "done" and not extra:
        log(f"{stage}: already done")
        return True
    for attempt in (1, 2):
        prompt = f"/{skill} {run.name}" + (f" {mode}" if mode else "")
        if extra:
            prompt += f"\n\n{extra}"
        if attempt == 2:
            st = read_json(run / "run.json", {}).get("stages", {}).get(stage, {})
            prompt += ("\n\nA previous attempt did not finish. Problems reported: "
                       + "; ".join(st.get("problems") or [st.get("note") or "the stage was not marked done"])
                       + ". Fix them, then run `artools run done` again.")
        cmd = ["claude", "-p", prompt, "--permission-mode", "dontAsk", "--allowedTools", *ALLOWED,
               *(CHROME_TOOLS if chrome else []), "--add-dir", str(DATA), "--output-format", "stream-json", "--verbose"]
        if chrome:                     # a step that works in the editor's signed-in Chrome (Claude in Chrome)
            cmd.insert(1, "--chrome")
        rt = read_json(run / "run.json", {}).get("runtime") or {}
        if model or rt.get("model"):
            cmd += ["--model", model or rt["model"]]
        if rt.get("effort"):
            cmd += ["--effort", rt["effort"]]
        base = stage.replace(':', '_')
        from .logs import base as log_base, pruned, stage_logs   # archived (.zst) and pruned sessions keep their numbers
        names = [log_base(x) for x in stage_logs(run)] + list(pruned(run))
        n = 1 + max([int(x.rsplit(".", 1)[1]) for x in names if x.rsplit(".", 1)[0] == base and x.rsplit(".", 1)[1].isdigit()] or [0])
        logf = run / "logs" / f"{base}.{n}.jsonl"     # never overwrite: every session's usage is counted
        log(f"{stage}: starting (attempt {attempt})")
        event(run, "stage_start", stage=stage, attempt=attempt, log=logf.name)
        t0 = time.time()
        with logf.open("w", encoding="utf-8") as f:
            try:
                rc = subprocess.run(cmd, cwd=ARTICLES, stdout=f, stderr=subprocess.STDOUT,
                                    timeout=STAGE_TIMEOUT_S, env={**os.environ, "ARTICLES_RUN": run.name}).returncode
            except subprocess.TimeoutExpired:
                rc = -1
        state = stage_state(run, stage)
        log(f"{stage}: exit {rc}, state {state}, {time.time() - t0:.0f}s, log {logf.name}")
        event(run, "stage_exit", stage=stage, attempt=attempt, rc=rc, state=state, seconds=round(time.time() - t0), log=logf.name)
        if skill.startswith("review-") and state == "done":
            keep_review(run)
        try:                           # usage.json after every session: tokens, and characters each artools call returned
            from .usage import usage
            usage(run)
        except Exception as e:
            log(f"usage.json not updated: {type(e).__name__}: {e}")
        if state == "done":
            return True
    return False


def scout_skills(run: Path) -> list[str]:
    brief = read_json(run / "brief.v1.json", {}) or {}
    skills = []
    for s in brief.get("sources", []):
        sk = SOURCE_SKILL.get(s)
        if sk and sk not in skills:
            skills.append(sk)
    return skills or ["search-jejualps", "fetch-public-data"]


def routed_fetch_skills(run: Path) -> list[str]:
    lm = read_json(run / "litmap.json", {}) or {}
    skills = []
    for m in lm.get("mechanisms", []):
        for ind in m.get("indicators", []):
            if ind.get("priority") in ("needed", "useful"):
                sk = PROVIDER_SKILL.get(str(ind.get("provider", "")).lower())
                if sk and sk not in skills:
                    skills.append(sk)
    return skills


def gate_open(run: Path, name: str) -> bool:
    return bool(read_json(run / "run.json", {}).get("gates", {}).get(name, {}).get("approved"))


def auto_gates() -> dict:
    """config/editorial.yaml → gates, when the editor lets the driver approve gates and ship by itself; else {}."""
    g = (load_yaml(CONFIG / "editorial.yaml") or {}).get("gates") or {}
    return g if g.get("auto") else {}


def ship_run(run: Path, tries: int = 3, wait_s: int = 600) -> bool:
    """`artools ship` after the automatic publish gate: a dry run first, then the real one. Someone else's uncommitted
    edit in the shared folder stops a ship; wait and try again, as the autonomous runs did."""
    if subprocess.run(["artools", "ship", run.name, "--dry-run"], cwd=ARTICLES).returncode != 0:
        log("ship: the dry run failed; see its output")
        return False
    for n in range(1, tries + 1):
        r = subprocess.run(["artools", "ship", run.name], cwd=ARTICLES, capture_output=True, text=True)
        print(r.stdout[-4000:], flush=True)
        if r.returncode == 0:
            log("ship: published")
            event(run, "ship", ok=True, attempt=n)
            return True
        if "uncommitted changes" not in r.stdout or n == tries:
            log(f"ship: failed (exit {r.returncode})")
            return False
        log(f"ship: the working folder has uncommitted changes; trying again in {wait_s // 60} min ({n}/{tries})")
        time.sleep(wait_s)
    return False


def parallel(run: Path, skills: list[str], mode: str | None) -> bool:
    with cf.ThreadPoolExecutor(max_workers=max(1, len(skills))) as ex:
        res = list(ex.map(lambda s: run_skill(run, s, mode), skills))
    return all(res)


GATE_HINT = {
    "question": "review question-review.json and brief.json",
    "plan": "review plan.json",
    "publish": "preview with `artools preview {run}`, look at the cover in cover/render/ and the PDF proofs in pdf/",
    "selection": "review selection.json",
    "themes": "review themes.json",
    "model": "review model.json",
    "video": "watch both editions (the admin site, or video/ in the run) and read review/review.json",
}


def run_command(run: Path, step: dict) -> bool:
    """A step without a Claude session (`command:` in the pipeline): an `artools video` command on the run."""
    stage = f"cmd:{step['command']}"
    if stage_state(run, stage) == "done":
        log(f"{stage}: already done")
        return True
    from .video import commands
    fn = commands.STEPS.get(step["command"])
    if fn is None:
        log(f"{stage}: not built yet (artools/video/commands.py)")
        return False
    runlib.set_stage(run, stage, state="running", started=runlib.now(), ended=None)
    log(f"{stage}: starting")
    event(run, "cmd_start", stage=stage)
    t0 = time.time()
    try:
        note = fn(run)
    except Exception as e:  # noqa: BLE001 - recorded on the stage, the driver stops
        runlib.set_stage(run, stage, state="failed", ended=runlib.now(), note=str(e)[:500])
        log(f"{stage}: failed: {e}")
        event(run, "cmd_exit", stage=stage, state="failed", seconds=round(time.time() - t0))
        return False
    runlib.set_stage(run, stage, state="done", ended=runlib.now(), note=note, problems=[])
    log(f"{stage}: done")
    event(run, "cmd_exit", stage=stage, state="done", seconds=round(time.time() - t0))
    return True


def review_loop(run: Path, step: dict, steps: list | None = None) -> None:
    """Send the review's blocking issues back to the stages that own them, then review again, at most loop.max times.
    Command steps between the owners and the review (the video's voice and assemble) run again after each fix, so the
    review sees what the fix made."""
    allowed = step["loop"]["owners"]
    steps = steps or []
    ids = [s.get("skill") for s in steps]
    first = min((ids.index(o) for o in allowed if o in ids), default=None)
    redo_cmds = [s for s in steps[first:ids.index(step["skill"])] if s.get("command")] if first is not None else []
    for n in range(1, step["loop"].get("max", 2) + 1):
        rv = read_json(run / "review.json", {}) or {}
        if rv.get("status") == "pass":
            return
        owners = {b.get("owner") for b in rv.get("blocking", [])} & set(allowed)
        if "make-podcast" in owners:           # a podcast edition gets two takes at most (podcast.yaml → notebooklm.takes)
            from .video.podcast import takes_left
            langs = {b.get("lang") for b in rv["blocking"] if b.get("owner") == "make-podcast"}
            if not any(takes_left(run, lang) for lang in langs if lang):
                log(f"review loop {n}: no takes left for {sorted(x for x in langs if x)}; the slides answer it")
                owners.discard("make-podcast")
        if not owners:
            return
        # a fixed stage's output feeds the later owners (the script's slide wording is drawn by make-slides): re-run them too
        order = allowed[min(allowed.index(o) for o in owners):]
        log(f"review loop {n}: fixing {order}")
        event(run, "review_loop", n=n, owners=order, blocking=len(rv.get("blocking", [])))
        for o in order:
            runlib.set_stage(run, o, state="redo")
            chrome = any(s.get("skill") == o and s.get("chrome") for s in steps)   # a retake needs NotebookLM in Chrome
            run_skill(run, o, extra="Fix mode: address every blocking issue in review.json whose owner is this stage.",
                      **({"chrome": True} if chrome else {}))
        for c in redo_cmds:
            runlib.set_stage(run, f"cmd:{c['command']}", state="redo")
            if not run_command(run, c):
                return
        runlib.set_stage(run, step["skill"], state="redo")
        run_skill(run, step["skill"])


def drive(run_id: str, only: str | None = None, until: str | None = None, allow_sample: bool = False) -> int:
    """Run the steps of the run's pipeline (config/pipelines/<type>.yaml) in order, stopping at the first closed gate.
    Every drive ends by refreshing the run's ledger file (/data/articles/ledger, for the admin's Newsroom in dev)."""
    run = run_dir(run_id)
    stamp_skills(run)
    event(run, "drive_start", only=only, until=until, pid=os.getpid())
    rc = 1
    try:
        rc = _drive(run, only, until, allow_sample)
        return rc
    finally:
        event(run, "drive_exit", rc=rc)
        if run.parent == RUNS:      # not for runs elsewhere (the tests' tmp runs)
            _after_drive(run, rc)


def _after_drive(run: Path, rc: int = 1) -> None:
    """The run's ledger file; for a finished run, an admin deploy carrying the ledger; then the logs of finished runs:
    archived (images out, zstd), pruned after logs.keep_days."""
    try:
        from .ledger import write
        write(run)
    except Exception as e:  # noqa: BLE001 - the ledger never stops a run
        log(f"ledger not updated: {type(e).__name__}: {e}")
    try:   # a finished run (article shipped, video up): the admin's Newsroom gets the new ledger (newsroom.deploy)
        from .logs import finished_at
        if rc == 0 and finished_at(run) is not None:
            from .ledger import deploy_admin
            log(f"admin: {deploy_admin()}")
    except Exception as e:  # noqa: BLE001 - the admin deploy never stops a run
        log(f"admin not deployed: {type(e).__name__}: {e}")
    try:
        from .logs import housekeeping
        for h in housekeeping():
            log(f"logs: {h}")
    except Exception as e:  # noqa: BLE001 - housekeeping never stops a run
        log(f"logs not tidied: {type(e).__name__}: {e}")


def _drive(run: Path, only: str | None, until: str | None, allow_sample: bool) -> int:
    if only:   # re-run one stage, even if it is done (a fix after a gate, or an edited input)
        mode = "scout" if only.startswith("scout:") else None
        skill = only.split(":")[-1]
        runlib.set_stage(run, only, state="redo")
        extra = ""
        rv = read_json(run / "review.json", {}) or {}
        if any(b.get("owner") == skill for b in rv.get("blocking", [])):
            extra = "Fix mode: address every blocking issue in review.json whose owner is this stage."
        chrome = any(s.get("skill") == skill and s.get("chrome") for s in pipelines.of_run(run)["steps"])
        return 0 if run_skill(run, skill, mode, extra=extra, **({"chrome": True} if chrome else {})) else 1

    p = pipelines.of_run(run)
    if any(s.get("desk") for s in p["steps"]):     # the data desk's notes have their own runner (artools/desk/run.py)
        log(f"{p['id']} is a desk pipeline: use `artools desk note` and `artools desk status {run.name}`")
        return 2
    if p["status"] != "live" and not allow_sample:
        log(f"pipeline {p['id']} is a {p['status']}: its skills are drafts. Pass --allow-sample to run it anyway")
        return 2
    for step in p["steps"]:
        if "gate" in step:
            name = step["gate"]
            if not gate_open(run, name):
                auto = auto_gates()
                blocking = (read_json(run / "review.json", {}) or {}).get("blocking") if name == "publish" else None
                if auto and (not blocking or auto.get("on_blocking") == "publish"):
                    note = "approved by the driver (config/editorial.yaml → gates.auto)"
                    if blocking:           # the review loop ran out of rounds; the editor publishes anyway (on_blocking)
                        note += f"; {len(blocking)} blocking issue(s) left in review.json (gates.on_blocking: publish)"
                    runlib.approve_gate(run, name, auto.get("by") or "datasteg desk (autonomous agent)", note)
                    event(run, "gate", gate=name, approved=True, by="driver", blocking=len(blocking or []))
                    log(f"GATE ({name}): approved automatically" + (f" with {len(blocking)} blocking issue(s) left" if blocking else ""))
                    continue
                if auto:
                    log(f"GATE ({name}): review.json still has {len(blocking)} blocking issue(s); not approved automatically")
                event(run, "gate", gate=name, approved=False, blocking=len(blocking or []))
                hint = GATE_HINT.get(name, "review the run").format(run=run.name)
                log(f"GATE ({name}): {hint}, then `artools run gate {run.name} {name} --approve --by <name>` and drive again")
                return 3
            continue
        if step.get("manual"):
            if step.get("skill") == "publish-article" and auto_gates():
                log("publish: shipping (config/editorial.yaml → gates.auto)")
                if not ship_run(run):
                    return 1
                if auto_gates().get("video") and any(s.get("skill") == "make-video" for s in p["steps"]):
                    from .video.run import auto as video_auto
                    v = video_auto((read_json(run / "publish.json", {}) or {})["slug"])
                    log(f"video: run {v['run']} started in the background (gates.video), log {v['log']}")
                    event(run, "video_start", video_run=v["run"])
                return 0
            if step.get("skill") == "publish-video" and auto_gates():
                log("publish: the videos are public; the editor watches them on YouTube, corrections go through update-article")
                return 0
            log(f"approved: the editor runs /{step['skill']} {run.name}")
            return 0
        if step.get("command"):
            if not run_command(run, step):
                return 1
        elif step.get("sources") == "scout":
            if not parallel(run, scout_skills(run), "scout"):
                log("scout: a source failed; the next step will see the gap")
        elif step.get("fetch") == "routed":
            fetchers = routed_fetch_skills(run)
            log(f"data skills routed by the litmap: {fetchers or 'none'}")
            if fetchers and not parallel(run, fetchers, None):
                return 1
        else:
            if not run_skill(run, step["skill"], step.get("mode"), **({"chrome": True} if step.get("chrome") else {})):
                return 1
            if step.get("extra_scout"):
                review = read_json(run / "question-review.json", {}) or {}
                if review.get("needs_scout") and stage_state(run, "scout-extra") != "done":
                    log(f"{step['skill']} asked for one more scout round: {review['needs_scout']}")
                    extra = "Extra scout round for: " + "; ".join(review["needs_scout"])
                    for sk in scout_skills(run):
                        run_skill(run, sk, "scout", extra=extra)
                    runlib.set_stage(run, "scout-extra", state="done")
                    runlib.set_stage(run, step["skill"], state="redo")
                    if not run_skill(run, step["skill"]):
                        return 1
            if step.get("decline_stops") and (read_json(run / "question-review.json", {}) or {}).get("verdict") == "decline":
                log(f"{step['skill']} declined the question; see question-review.json")
                return 4
            if step.get("loop") and not gate_open(run, "publish"):   # once publish is approved, the fixes are over
                review_loop(run, step, p["steps"])
        if until and until in (step["id"], step.get("skill")):
            return 0
    return 0
