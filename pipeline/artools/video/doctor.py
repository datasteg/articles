"""`artools video doctor`: is everything the video pipeline needs in place?

Every check says ok, todo (a setup step you haven't done) or fail, and never prints a secret."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from importlib import metadata
from pathlib import Path

from . import cfg, secret_path


def _row(name: str, state: str, detail: str = "") -> dict:
    return {"check": name, "state": state, "detail": detail}


def _private(p) -> str:
    mode = stat.S_IMODE(p.stat().st_mode)
    return "" if mode & 0o077 == 0 else f"mode {oct(mode)}: run chmod 600 {p}"


def ffmpeg() -> str | None:
    """The system ffmpeg, else the one bundled with imageio-ffmpeg."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def local() -> list[dict]:
    rows = []
    for pkg, need in (("google-genai", "2.25.0"), ("google-api-python-client", None), ("google-auth-oauthlib", None),
                      ("imageio-ffmpeg", None)):
        try:
            v = metadata.version(pkg)
            ok = need is None or tuple(map(int, v.split(".")[:3])) >= tuple(map(int, need.split(".")))
            rows.append(_row(f"package {pkg}", "ok" if ok else "fail", v + ("" if ok else f" (needs ≥ {need})")))
        except metadata.PackageNotFoundError:
            rows.append(_row(f"package {pkg}", "fail", "missing: uv tool install --editable articles/pipeline --force"))
    exe = ffmpeg()
    if exe:
        ver = subprocess.run([exe, "-version"], capture_output=True, text=True).stdout.split("\n")[0]
        filters = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        rows.append(_row("ffmpeg", "ok" if " loudnorm " in filters else "fail",
                         ver[:60] + ("" if " loudnorm " in filters else " (no loudnorm filter)")))
    else:
        rows.append(_row("ffmpeg", "fail", "neither a system ffmpeg nor imageio-ffmpeg's"))

    env = secret_path("gemini_env")
    if not env.is_file():
        rows.append(_row("Gemini key", "todo", f"{env} missing"))
    else:
        has = any(line.startswith("GEMINI_API_KEY=") and len(line.strip()) > 20
                  for line in env.read_text(encoding="utf-8").splitlines())
        rows.append(_row("Gemini key", "ok" if has and not _private(env) else "fail",
                         _private(env) or ("present" if has else "no GEMINI_API_KEY= line")))

    asr = cfg("podcast").get("asr") or {}             # speech to text for the podcast video
    py = Path(os.path.expanduser(asr.get("python", "")))
    hub = Path(os.path.expanduser(asr.get("hf_home", "/data/huggingface"))) / "hub"
    snap = hub / ("models--" + asr.get("model", "?").replace("/", "--")) / "snapshots"
    rows.append(_row("STT environment", "ok" if py.is_file() else "todo", str(py) if py.is_file() else
                     f"{py} missing"))
    rows.append(_row("STT model", "ok" if snap.is_dir() and any(snap.iterdir()) else "todo",
                     asr.get("model", "?") if snap.is_dir() else f"not in {hub}"))

    client = secret_path("youtube_client")
    if not client.is_file():
        rows.append(_row("YouTube OAuth client", "todo", f"{client} missing"))
    else:
        try:
            kind = next(iter(json.loads(client.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, StopIteration):
            kind = "?"
        state = "ok" if kind == "installed" and not _private(client) else "fail"
        rows.append(_row("YouTube OAuth client", state, _private(client) or
                         ("Desktop app" if kind == "installed" else f"type {kind}: create a Desktop app client")))

    tok = secret_path("youtube_token")
    rows.append(_row("YouTube token", "ok" if tok.is_file() and not _private(tok) else "todo",
                     (_private(tok) or "present") if tok.is_file() else "run artools video auth url"))

    v = cfg("voices")
    chosen = {lang: (v.get(lang) or {}).get("voice") for lang in ("en", "ko")}
    rows.append(_row("narrator voices", "ok" if all(chosen.values()) else "todo",
                     ", ".join(f"{k}: {x or 'not chosen (artools video audition --lang ' + k + ')'}" for k, x in chosen.items())))
    return rows


def online() -> list[dict]:
    rows = []
    try:
        from .tts import client, voice_for
        model = voice_for("en")[0]
        c = client()                       # keep a reference: a collected Client closes its connection
        m = c.models.get(model=model)
        rows.append(_row("Gemini API", "ok", f"{model} reachable ({getattr(m, 'display_name', '') or m.name})"))
    except Exception as e:  # noqa: BLE001
        rows.append(_row("Gemini API", "todo" if "no GEMINI_API_KEY" in str(e) else "fail", str(e)[:200]))
    try:
        from .youtube import channel
        ch = channel()
        rows.append(_row("YouTube channel", "ok", f"{ch['channel']} ({ch['channel_id']})"))
    except Exception as e:  # noqa: BLE001
        rows.append(_row("YouTube channel", "todo" if "not connected" in str(e) else "fail", str(e)[:200]))
    return rows


def doctor(include_online: bool = False) -> dict:
    rows = local() + (online() if include_online else [])
    return {"ok": all(r["state"] == "ok" for r in rows), "checks": rows,
            "todo": [r["check"] for r in rows if r["state"] == "todo"],
            "fail": [r["check"] for r in rows if r["state"] == "fail"]}
