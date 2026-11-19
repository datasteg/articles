"""Stage logs after a run is finished (config/editorial.yaml → logs). A run's stream-json logs are 70–160 MB, a third of
it screenshots the stages read back as base64. Two steps, both run by the driver at the end of a drive:

1. archive: once the run is finished (the article shipped, or both video editions uploaded), every
   logs/<stage>.<n>.jsonl becomes <stage>.<n>.jsonl.zst with the image data taken out: about a fifth of the size,
   every line and every number kept. The readers (usage, received, the ledger) read .zst as they read .jsonl.
   A run that never finished counts as finished after a week without activity (a stopped test run).
2. prune: `keep_days` after the run finished, the archived logs are replaced by logs/PRUNED.json, each session's
   summary (tokens, cost, turns, characters received, the ledger's attempt record). usage.json and the ledger keep
   counting those sessions; only the raw transcripts are gone.

events.jsonl and the driver's text logs are small and stay."""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

from .paths import CONFIG, RUNS, load_yaml, read_json, write_json

IMAGE = re.compile(r'"data":\s*"[A-Za-z0-9+/=]{1000,}"')
SKIP = {"events.jsonl"}


def settings() -> dict:
    s = (load_yaml(CONFIG / "editorial.yaml") or {}).get("logs") or {}
    return {"archive": s.get("archive", True), "keep_days": s.get("keep_days", 90)}


def base(p: Path) -> str:
    """'draft-article.3' for draft-article.3.jsonl and draft-article.3.jsonl.zst."""
    return p.name.removesuffix(".zst").removesuffix(".jsonl")


def stage_logs(run: Path) -> list[Path]:
    """A run's stage session logs, plain or archived, in name order."""
    d = run / "logs"
    if not d.is_dir():
        return []
    return sorted((p for p in d.iterdir() if p.name not in SKIP and (p.name.endswith(".jsonl") or p.name.endswith(".jsonl.zst"))),
                  key=base)


def pruned(run: Path) -> dict:
    """logs/PRUNED.json → files: {base: {usage, received, attempt, end}} for sessions whose logs were pruned."""
    return (read_json(run / "logs" / "PRUNED.json", {}) or {}).get("files", {})


def open_lines(p: Path) -> Iterator[str]:
    if p.name.endswith(".zst"):
        proc = subprocess.Popen(["zstd", "-dcq", str(p)], stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        assert proc.stdout is not None
        yield from proc.stdout
        proc.wait()
    else:
        with p.open(encoding="utf-8", errors="replace") as f:
            yield from f


def finished_at(run: Path) -> float | None:
    """When the run was finished: the article's deploy, or the later of the two video uploads."""
    pub = read_json(run / "publish.json", {}) or {}
    stamps = [pub.get("deployed_at")] + [(read_json(run / "youtube" / f"{l}.json", {}) or {}).get("uploaded") for l in ("en", "ko")]
    ts = []
    for s in stamps:
        try:
            ts.append(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
        except (AttributeError, ValueError):
            pass
    if (run / "youtube").is_dir() and len(ts) < 2:
        return None          # a video run counts once both editions are up
    return max(ts) if ts else None


def busy(run: Path) -> bool:
    """A log written in the last ten minutes, or a stage marked running or redo in a run touched in the last day: leave
    the run alone. A 'running' left by a session that died days ago (a usage limit) doesn't count."""
    now = dt.datetime.now().timestamp()
    logs = [p.stat().st_mtime for p in stage_logs(run)]
    if any(now - t < 600 for t in logs):
        return True
    m = read_json(run / "run.json", {}) or {}
    touched = max(logs + [(run / "run.json").stat().st_mtime])
    return now - touched < 86400 and any((s or {}).get("state") in ("running", "redo") for s in (m.get("stages") or {}).values())


def abandoned_at(run: Path, idle_days: int = 7) -> float | None:
    """A run that never finished and hasn't been touched for idle_days (a stopped test run): its last activity."""
    stamps = [p.stat().st_mtime for p in stage_logs(run)] + [(run / "run.json").stat().st_mtime]
    last = max(stamps)
    return last if dt.datetime.now().timestamp() - last > idle_days * 86400 else None


def archive(run: Path) -> dict:
    """Every plain stage log → .jsonl.zst without image data; the original is removed only after zstd -t passes."""
    before = after = 0
    done = []
    for p in stage_logs(run):
        if not p.name.endswith(".jsonl"):
            continue
        out = p.with_name(p.name + ".zst")
        tmp = out.with_name(out.name + ".tmp")
        st = p.stat()
        z = subprocess.Popen(["zstd", "-19", "-q", "-T0", "-f", "-o", str(tmp)], stdin=subprocess.PIPE, text=True, encoding="utf-8")
        assert z.stdin is not None
        with p.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                z.stdin.write(IMAGE.sub('"data":"[image removed]"', line))
        z.stdin.close()
        if z.wait() != 0 or subprocess.run(["zstd", "-tq", str(tmp)]).returncode != 0:
            tmp.unlink(missing_ok=True)
            continue
        tmp.rename(out)
        os.utime(out, (st.st_atime, st.st_mtime))     # the ledger reads a session's end from its log's mtime
        before += st.st_size
        after += out.stat().st_size
        p.unlink()
        done.append(out.name)
    if done:
        rec = read_json(run / "logs" / "ARCHIVED.json", {}) or {"archives": []}
        rec["archives"].append({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "files": len(done), "bytes_before": before, "bytes_after": after})
        write_json(run / "logs" / "ARCHIVED.json", rec)
    return {"run": run.name, "files": len(done), "mb_before": round(before / 1e6, 1), "mb_after": round(after / 1e6, 1)}


def prune(run: Path) -> dict:
    """Replace the archived logs with their summaries (logs/PRUNED.json). Plain logs are archived first."""
    from .ledger import _attempt, write as write_ledger
    from .usage import read_log, received
    archive(run)
    files = [p for p in stage_logs(run) if p.name.endswith(".jsonl.zst")]
    if not files:
        return {"run": run.name, "pruned": 0}
    rec = read_json(run / "logs" / "PRUNED.json", {}) or {"files": {}}
    freed = 0
    for p in files:
        rec["files"][base(p)] = {"usage": read_log(p), "received": received(p), "attempt": _attempt(p)}
    rec["at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_json(run / "logs" / "PRUNED.json", rec)
    for p in files:
        freed += p.stat().st_size
        p.unlink()
    write_ledger(run)
    return {"run": run.name, "pruned": len(files), "mb_freed": round(freed / 1e6, 1)}


def housekeeping(keep_days: int | None = None, only: Path | None = None) -> list[dict]:
    """The regular step (end of every drive): archive finished runs, prune those finished more than keep_days ago."""
    s = settings()
    if not s["archive"]:
        return []
    keep = s["keep_days"] if keep_days is None else keep_days
    from .runlib import flock_file
    out = []
    with flock_file(RUNS.parent / ".logs.lock"):       # one housekeeping at a time across parallel drives
        for run in [only] if only else sorted(p.parent for p in RUNS.glob("*/run.json")):
            t = finished_at(run) or abandoned_at(run)
            if t is None or busy(run):
                continue
            out += _tidy(run, t, keep)
    return out


def _tidy(run: Path, t: float, keep: int | None) -> list[dict]:
    logs = stage_logs(run)
    old = keep is not None and keep >= 0 and dt.datetime.now(dt.timezone.utc).timestamp() - t > keep * 86400
    if old and logs:
        return [prune(run)]
    if any(p.name.endswith(".jsonl") for p in logs):
        return [archive(run)]
    return []


def status() -> list[dict]:
    rows = []
    for run in sorted(p.parent for p in RUNS.glob("*/run.json")):
        logs = stage_logs(run)
        rows.append({"run": run.name, "plain_mb": round(sum(p.stat().st_size for p in logs if p.name.endswith(".jsonl")) / 1e6, 1),
                     "archived_mb": round(sum(p.stat().st_size for p in logs if p.name.endswith(".zst")) / 1e6, 1),
                     "pruned": len(pruned(run)), "finished": finished_at(run) is not None,
                     "abandoned": finished_at(run) is None and abandoned_at(run) is not None})
    return rows
