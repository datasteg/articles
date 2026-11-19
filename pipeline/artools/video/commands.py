"""The video pipeline's `command:` steps (config/video/pipeline.yaml): run by the driver without a Claude session.
Each takes the run folder and returns a short note for run.json. Steps not listed here are not built yet."""
from __future__ import annotations

from pathlib import Path


def voice(run: Path) -> str:
    from .voice import voice as record
    res = [record(run.name, lang) for lang in ("en", "ko")]
    flagged = {r["lang"]: r["flagged"] for r in res if r["flagged"]}
    return "; ".join(f"{r['lang']} {r['speech_seconds']}s" for r in res) + (f"; flagged {flagged}" if flagged else "")


def assemble(run: Path) -> str:
    from .assemble import assemble as build
    res = [build(run.name, lang) for lang in ("en", "ko")]
    return "; ".join(f"{r['lang']} {r['minutes']} min" + ("" if r["length_ok"] else " (outside the length range)") for r in res)


def upload(run: Path) -> str:
    from .publish import upload as send
    res = [send(run.name, lang) for lang in ("en", "ko")]
    return "; ".join(f"{r['lang']} {r['url']} (public)" for r in res)


def finish(run: Path) -> str:
    from .publish import finish as wrap_up
    r = wrap_up(run.name)
    return f"processing {sorted(set(r['processing'].values()))}; thumbnails {r['thumbnail']}; crosslink {r['crosslink']}"


def transcribe(run: Path) -> str:
    from . import podcast
    res = [podcast.transcribe(run.name, lang) for lang in ("en", "ko")]
    chk = {lang: podcast.check(run.name, lang) for lang in ("en", "ko")}
    return "; ".join(f"{r['lang']} {r['segments']} segments, {chk[r['lang']]['numbers_not_in_source']} numbers not in the source"
                     for r in res)


def assemble_podcast(run: Path) -> str:
    from . import podcast
    res = [podcast.assemble(run.name, lang) for lang in ("en", "ko")]
    for lang in ("en", "ko"):
        try:
            podcast.thumb(run.name, lang)
        except RuntimeError:
            pass                       # no thumb slide: the upload goes without one
    return "; ".join(f"{r['lang']} {r['minutes']} min" + ("" if r["length_ok"] else " (outside the length range)") for r in res)


def clean(run: Path) -> str:
    from . import podcast
    res = {lang: podcast.clean(run.name, lang) for lang in ("en", "ko")}
    return "; ".join(f"{k} {v['deleted']} files, {v['freed_mb']} MB" for k, v in res.items())


STEPS = {"voice": voice, "assemble": assemble, "upload": upload, "finish": finish,
         "transcribe": transcribe, "assemble-podcast": assemble_podcast, "clean": clean}
