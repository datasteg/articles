"""One model call per role. A role is a brief (guides/desk/roles/<role>.md) sent as the system prompt, and a packet
the code prepared sent as the message. The session has no tools, no skills, no project memory and no MCP servers, so
a call carries only what the role needs: a few thousand tokens instead of the hundred turns of an agent session.

Each call's stream-json transcript is written to <run>/logs/desk-<role>.<n>.jsonl, the same place and shape as the
driver's stage sessions, so `artools usage`, `artools compare` and the ledger count the desk's calls as they count
every other run's.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from ..paths import ARTICLES, read_json
from . import config

ROLES = ARTICLES / "guides" / "desk" / "roles"
CALL_TIMEOUT_S = 1200


class RoleError(RuntimeError):
    pass


def brief(role: str) -> str:
    """The role's brief with the files it includes: a line `@include <path>` (relative to articles/) is replaced by
    that file, so the standard and the template live in one place."""
    text = (ROLES / f"{role}.md").read_text(encoding="utf-8")

    def inc(m):
        return (ARTICLES / m.group(1).strip()).read_text(encoding="utf-8").strip()
    return re.sub(r"^@include\s+(\S+)\s*$", inc, text, flags=re.M)


_log_lock = threading.Lock()


def _next_log(run: Path, stage: str) -> Path:
    """The next numbered log of a stage, created here so two calls of one role running at once (the two judges, the
    three reviewers) never take the same file."""
    d = run / "logs"
    d.mkdir(parents=True, exist_ok=True)
    with _log_lock:
        ns = [int(m.group(1)) for p in d.iterdir() if (m := re.match(re.escape(stage) + r"\.(\d+)\.jsonl", p.name))]
        f = d / f"{stage}.{1 + max(ns or [0])}.jsonl"
        f.touch()
        return f


def _result(logf: Path) -> dict | None:
    res = None
    with logf.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"type":"result"' in line or '"type": "result"' in line:
                try:
                    res = json.loads(line)
                except json.JSONDecodeError:
                    pass
    return res


def extract_json(text: str):
    """The JSON value in a model answer: the last fenced ```json block, or the outermost braces."""
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", text, flags=re.S)
    for cand in reversed(blocks):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(text[i:j + 1])
        except json.JSONDecodeError:
            pass
    raise RoleError("the answer holds no JSON value")


def call(run: Path, role: str, packet: str, *, expect_json: bool = True, model: str | None = None,
         effort: str | None = None, label: str | None = None) -> dict:
    """Run one role. Returns {"data": parsed JSON or None, "text": the answer, "cost_usd", "seconds", "log"}.
    A reply that is not the JSON asked for is sent back once with the parse error."""
    cfg = config.role(role)
    model, effort = model or cfg["model"], effort or cfg["effort"]
    stage = f"desk-{label or role}"
    system = brief(role)
    msg = packet
    out = None
    for attempt in (1, 2):
        logf = _next_log(run, stage)
        cmd = ["claude", "-p", "--model", model, "--effort", effort, "--tools", "", "--disable-slash-commands",
               "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence",
               "--system-prompt", system, "--output-format", "stream-json", "--verbose"]
        if cfg.get("max_budget_usd"):
            cmd += ["--max-budget-usd", str(cfg["max_budget_usd"])]
        t0 = time.time()
        with logf.open("w", encoding="utf-8") as f:
            try:
                rc = subprocess.run(cmd, input=msg, text=True, cwd=str(run), stdout=f, stderr=subprocess.STDOUT,
                                    timeout=CALL_TIMEOUT_S,
                                    # a role call is one request and is never continued, so a cache write (twice the
                                    # input price) would buy nothing: measured 14 Nov 2026, the same call costs half
                                    env={**{k: v for k, v in os.environ.items() if k != "ARTICLES_RUN"},
                                         "DISABLE_PROMPT_CACHING": "1"}).returncode
            except subprocess.TimeoutExpired:
                rc = -1
            except OSError as e:
                # the CLI was not there for a moment (16 Nov 2026: an update moved it while t8's Korean ran): retried
                # once after the pause below, then a RoleError, which the steps handle, never a crash
                f.write(f"{type(e).__name__}: {e}\n")
                rc = -2
        res = _result(logf)
        if rc != 0 or not res or res.get("is_error"):
            why = (res or {}).get("result") or f"exit {rc}"
            if attempt == 2:
                raise RoleError(f"{role}: {str(why)[:300]} (log {logf.name})")
            time.sleep(20)
            continue
        text = res.get("result") or ""
        out = {"text": text, "data": None, "cost_usd": res.get("total_cost_usd"), "seconds": round(time.time() - t0),
               "log": logf.name, "model": model, "effort": effort}
        if not expect_json:
            return out
        try:
            out["data"] = extract_json(text)
            return out
        except RoleError as e:
            if attempt == 2:
                raise RoleError(f"{role}: {e} (log {logf.name})") from e
            msg = (packet + "\n\n---\nYour previous answer could not be read as JSON (" + str(e)
                   + "). Answer again with the JSON value only, in one ```json block.")
    raise RoleError(f"{role}: no answer")


def spent(run: Path, korean: bool = False) -> float:
    """List-price USD of the desk calls logged in the run so far: what counts against the note's budget. The Korean
    edition's helpers (desk-korean.*) are left out unless asked for: the editor does not cap the Korean (16 Nov 2026)."""
    total = 0.0
    d = run / "logs"
    for p in sorted(d.glob("desk-*.jsonl")) if d.is_dir() else []:
        if not korean and p.name.startswith("desk-korean."):
            continue
        r = _result(p)
        total += (r or {}).get("total_cost_usd") or 0.0
    return round(total, 4)
