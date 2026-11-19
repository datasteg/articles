"""`artools video assemble`: frames + narration → the edition's video, with captions and chapters.

Timing comes from the takes: each beat lasts as long as its WAV, plus a pause (config/video/speech.yaml → pause, or
the beat's pause_after). A build step switches on its cue words, placed by their position in the beat's text. The
narration is normalised to −14 LUFS (two-pass loudnorm), the level YouTube plays at.

<run>/video/<lang>.mp4, <lang>.srt, <lang>.vtt, <lang>.json (duration, loudness, chapters, timeline)"""
from __future__ import annotations

import io
import json
import re
import subprocess
import wave
from pathlib import Path

from ..paths import read_json, run_dir, write_json
from . import cfg
from .doctor import ffmpeg
from .script import facts_of
from .speech import VTOKEN, render

CAPTION_LINE = {"en": 42, "ko": 24}
CHAPTER = {
    "open": {"en": "The question", "ko": "질문"},
    "limits": {"en": "What the data can't tell us", "ko": "데이터가 말하지 않는 것"},
    "recap": {"en": "The answer, again", "ko": "정리"},
}


def _wav_frames(p: Path) -> tuple[bytes, int]:
    with wave.open(str(p)) as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise RuntimeError(f"{p.name}: expected 16-bit mono")
        return w.readframes(w.getnframes()), w.getframerate()


def _ts(t: float, sep: str = ",") -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


def _chunks(text: str, lang: str) -> list[str]:
    """Caption cues: sentences, split further so each fits two lines."""
    width = CAPTION_LINE[lang] * 2
    out = []
    for sent in re.split(r"(?<=[.?!])\s+", text.strip()):
        words, cur = sent.split(), ""
        for w in words:
            if len(cur) + len(w) + 1 > width and cur:
                out.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        if cur:
            out.append(cur)
    return out


def _wrap(cue: str, lang: str) -> str:
    n = CAPTION_LINE[lang]
    if len(cue) <= n:
        return cue
    cut = cue.rfind(" ", 0, max(len(cue) // 2 + 6, 1))
    cut = cut if cut > 0 else cue.find(" ", len(cue) // 2)
    return cue if cut <= 0 else cue[:cut] + "\n" + cue[cut + 1:]


def _loudnorm(exe: str, src: Path) -> tuple[str, dict]:
    """Two-pass loudnorm: measure, then the filter string with the measured values."""
    target = "I=-14:TP=-1:LRA=11"
    r = subprocess.run([exe, "-hide_banner", "-nostats", "-i", str(src), "-af", f"loudnorm={target}:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        return f"loudnorm={target}", {}
    v = json.loads(m.group(0))
    try:
        if not -99 <= float(v["input_i"]) <= 0:
            raise ValueError
    except ValueError:                       # silence (a placeholder voice) measures -inf: nothing to normalise
        return "anull", {"input_lufs": None, "note": "silent narration, not normalised"}
    f = (f"loudnorm={target}:measured_I={v['input_i']}:measured_TP={v['input_tp']}:measured_LRA={v['input_lra']}"
         f":measured_thresh={v['input_thresh']}:offset={v['target_offset']}:linear=true")
    return f, {"input_lufs": float(v["input_i"]), "input_true_peak": float(v["input_tp"])}


def assemble(run_id: str, lang: str) -> dict:
    run = run_dir(run_id)
    exe = ffmpeg()
    if not exe:
        raise RuntimeError("no ffmpeg (artools video doctor)")
    sb = read_json(run / "storyboard.json")
    sc = read_json(run / "script" / f"{lang}.json")
    vo = read_json(run / "audio" / lang / "voice.json")
    deck = read_json(run / "slides" / f"{lang}.resolved.json")
    if not (sb and sc and vo and deck):
        raise RuntimeError("needs storyboard.json, script, audio/<lang>/voice.json and slides (run slides and voice first)")
    facts = facts_of(run)
    pauses = cfg("speech").get("pause") or {}
    steps = {s["id"]: s["steps"] for s in deck["slides"]}
    script_beats = {b["beat"]: b for b in sc["beats"]}
    takes = {b["beat"]: b for b in vo["beats"]}
    frames_dir = run / "slides" / lang

    pcm, rate, t = bytearray(), None, 0.0
    events, captions, chapters = [], [], []
    roadmap_items = next((deck_s["fields"].get("items") for deck_s in deck["slides"] if deck_s["template"] == "roadmap"), None) or []
    cur_slide, cur_step, last_part = None, 1, None
    beat_times = []
    for i, b in enumerate(sb["beats"]):
        bid = b["id"]
        wav_p = run / "audio" / lang / f"{bid}.wav"
        data, r = _wav_frames(wav_p)
        rate = rate or r
        if r != rate:
            raise RuntimeError(f"{bid}: sample rate {r}, others {rate}")
        secs = len(data) / 2 / rate
        if b["part"] != last_part and b["part"] != "end" and not (b["part"] == "answer" and last_part == "open"):
            title = CHAPTER.get(b["part"], {}).get(lang)
            if b["part"].startswith("p") and b["part"][1:].isdigit():
                n = int(b["part"][1:])
                title = roadmap_items[n - 1] if n <= len(roadmap_items) else ("Part " if lang == "en" else "") + str(n)
            if title:
                chapters.append((t, title))
        last_part = b["part"]
        # the frame: a new slide starts at its beat's step; the same slide keeps its step
        if b["slide"] != cur_slide:
            cur_slide, cur_step = b["slide"], b.get("step") or 1
        else:
            cur_step = max(cur_step, b.get("step") or 1)
        events.append((t, cur_slide, cur_step))
        beat_times.append({"id": bid, "t": round(t, 2), "part": b["part"], "slide": b["slide"]})
        sbeat = script_beats[bid]
        said = takes.get(bid, {}).get("text") or render(sbeat["spoken"], facts, lang)
        for c in sorted(sbeat.get("cues", []), key=lambda c: said.find(c["at"])):
            pos = max(0, said.find(c["at"]))
            if c["step"] <= steps.get(cur_slide, 1):
                cur_step = c["step"]
                events.append((t + secs * pos / max(1, len(said)), cur_slide, cur_step))
        # captions: the written form (97bp), timed by length within the beat
        written = render(VTOKEN.sub(lambda m: "{{" + m.group(1) + ("|" + m.group(3) if m.group(3) else "") + "}}",
                                    sbeat["spoken"]), facts, lang)
        cues = _chunks(written, lang)
        total = sum(len(x) for x in cues) or 1
        ct = t
        for cue in cues:
            d = secs * len(cue) / total
            captions.append((ct, ct + d, _wrap(cue, lang)))
            ct += d
        pause = sbeat.get("pause_after")
        if pause is None:
            nxt = sb["beats"][i + 1]["part"] if i + 1 < len(sb["beats"]) else None
            pause = pauses.get("part", 1.0) if nxt and nxt != b["part"] else pauses.get("beat", 0.4)
        pcm += data + b"\x00\x00" * int(pause * rate)
        t += secs + pause
    tail = 1.5
    pcm += b"\x00\x00" * int(tail * rate)
    duration = t + tail

    out_dir = run / "video"
    out_dir.mkdir(exist_ok=True)
    narr = out_dir / f"{lang}.narration.wav"
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(pcm))
    narr.write_bytes(buf.getvalue())

    # frames list for ffmpeg's concat demuxer
    lines = []
    for k, (start, sid, step) in enumerate(events):
        end = events[k + 1][0] if k + 1 < len(events) else duration
        if end - start <= 0.01:
            continue
        p = frames_dir / f"{sid}-{step}.png"
        if not p.is_file():
            raise RuntimeError(f"missing frame {p.name}: run artools video slides {run.name}")
        lines.append(f"file '{p}'\nduration {end - start:.3f}")
    lines.append(f"file '{frames_dir / (events[-1][1] + '-' + str(events[-1][2]) + '.png')}'")
    concat = out_dir / f"{lang}.frames.txt"
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")

    af, measured = _loudnorm(exe, narr)
    mp4 = out_dir / f"{lang}.mp4"
    cmd = [exe, "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(narr),
           "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "18",
           "-af", af, "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
           "-metadata", f"language={'eng' if lang == 'en' else 'kor'}", "-movflags", "+faststart", "-shortest", str(mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-800:])

    srt = "\n".join(f"{i + 1}\n{_ts(a)} --> {_ts(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(captions))
    (out_dir / f"{lang}.srt").write_text(srt, encoding="utf-8")
    vtt = "WEBVTT\n\n" + "\n".join(f"{_ts(a, '.')} --> {_ts(b, '.')}\n{txt}\n" for a, b, txt in captions)
    (out_dir / f"{lang}.vtt").write_text(vtt, encoding="utf-8")
    chap = [(0.0, chapters[0][1])] + chapters[1:] if chapters else []
    chap_lines = [f"{int(a // 60):02d}:{int(a % 60):02d} {title}" for a, title in chap]
    info = {"lang": lang, "file": str(mp4), "seconds": round(duration, 1), "minutes": round(duration / 60, 2),
            "placeholder_voice": bool(vo.get("placeholder")), "loudness": measured, "chapters": chap_lines,
            "frames": len(lines) - 1, "captions": len(captions), "bytes": mp4.stat().st_size}
    lo, hi = 540, 960                      # 9 to 16 minutes (speech.yaml → budget)
    info["length_ok"] = lo <= duration <= hi
    write_json(out_dir / f"{lang}.json", {**info, "beats": beat_times,
                                          "timeline": [{"t": round(a, 2), "slide": s, "step": st} for a, s, st in events]})
    return info
