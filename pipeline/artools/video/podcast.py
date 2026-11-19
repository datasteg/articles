"""The podcast video (pipeline video-podcast, guides/video-podcast.md): NotebookLM's two-host Audio Overview of the
article, transcribed with timestamps, with the article's own slides cut to it.

<run>/podcast/plan.json          the parts the hosts take in order, the sections each covers (make-podcast writes it)
<run>/podcast/<lang>.source.md   what is pasted into the notebook as its one source
<run>/podcast/<lang>.prompt.txt  the focus prompt
<run>/podcast/<lang>.json        the take: notebook url, title, seconds, attempts
<run>/audio/<lang>.m4a           the downloaded audio (deleted after upload: it stays in the notebook)
<run>/asr/<lang>.json            the transcript in timed segments (VibeVoice-ASR, in five-minute pieces)
<run>/podcast/<lang>.timeline.json  which slide and step shows from when (make-podcast-slides writes it)
<run>/asr/<lang>.<other>.json    the captions in the other language: one translation per transcript segment, same times
                                 (make-podcast-slides writes it; the Korean video gets English captions and vice versa)
<run>/video/<lang>.mp4 …         as in the narrated video; frames, audio and video are deleted after upload (clean)"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..content import CITE, GLOSS
from ..paths import CONTENT, read_json, run_dir, write_json
from . import cfg
from .assemble import _loudnorm
from .doctor import ffmpeg

LANGS = ("en", "ko")
WORD = {"part": {"en": "Part", "ko": "부분"}, "chart": {"en": "Chart", "ko": "차트"},
        "how": {"en": "How to read it", "ko": "읽는 법"}, "kn": {"en": "Key numbers", "ko": "핵심 숫자"},
        "kf": {"en": "Key findings", "ko": "핵심 결과"}, "q": {"en": "The question", "ko": "질문"},
        "a": {"en": "The short answer", "ko": "짧은 답"}, "read": {"en": "Our read", "ko": "우리의 판단"},
        "gl": {"en": "Glossary", "ko": "용어 풀이"}, "also": {"en": "Background (for context only)", "ko": "배경(참고용)"}}
ORDINAL = {"en": ["one", "two", "three", "four", "five", "six"], "ko": ["첫째", "둘째", "셋째", "넷째", "다섯째", "여섯째"]}


# "The chart below shows…": the hosts never point at a chart, so the source doesn't either
POINTER = re.compile(r"(?:^|(?<=[.!?] ))(?:(?:The (?:chart|table|figure)s? (?:below|above)|아래 (?:그림|표|차트))[^.!?\n]*"
                     r"|[^.!?\n]*(?:그래프에 담|(?:chart|table|figure)s? further down|아래 (?:그림|표|차트|그래프))[^.!?\n]*)[.!?]\s*")
# …and the pointing clauses inside a sentence ("…, as the chart below shows."; "…내렸으며, 아래 그림이 이를 보여준다.")
POINTER_CLAUSE = re.compile(r",? as the (?:chart|table|figure) (?:below|above) shows|\bin the (?:chart|table|figure) (?:below|above), "
                            r"|; the (?:chart|table|figure)s? (?:below|above)[^.!?\n]*")
POINTER_CLAUSE_KO = re.compile(r"으?며, 아래 (?:그림|표|차트)[이가] 이를 보여준다")
POINTER_PAREN_KO = re.compile(r"\s*\(아래 (?:그림|표|차트|그래프)\)")


def _plain(t: str, lang: str = "en") -> str:
    """Article marks off: citations dropped, glossary marks to their text (or the term), emphasis to plain."""
    def gloss(m):
        inner = m.group(0)[2:-2]
        if "|" in inner:
            return inner.split("|")[-1]
        g = read_json(CONTENT / "glossary" / f"{inner}.json", {}) or {}
        return _tx(g.get("term"), lang) or inner.replace("-", " ")
    t = GLOSS.sub(gloss, CITE.sub("", t))
    t = POINTER.sub("", POINTER_PAREN_KO.sub("", t.replace("*", "")))
    t = POINTER_CLAUSE_KO.sub("다", POINTER_CLAUSE.sub("", t))
    return re.sub(r" {2,}", " ", re.sub(r"\s+([,.;:)])", r"\1", t)).strip()


def _tx(v, lang: str) -> str:
    return (v.get(lang) or v.get("en") or "") if isinstance(v, dict) else (v or "")


def _blocks(sec: dict, run: Path, lang: str) -> list[str]:
    out = []
    for b in sec.get("blocks", []):
        if b.get("type") == "figure":
            c = read_json(run / "source" / "charts" / f"{b.get('chart')}.json", {}) or {}
            line = f"[{WORD['chart'][lang]}: {_plain(_tx(c.get('title'), lang), lang)}. {_plain(_tx(c.get('headline'), lang), lang)}"
            line += "" if line[-1] in ".!?" else "."
            how = _tx(c.get("howToRead"), lang)
            out.append(line + (f" {WORD['how'][lang]}: {_plain(how, lang)}" if how else "") + "]")
        elif b.get("text") and (t := _plain(b["text"], lang)):  # a block that was only a pointer leaves nothing
            out.append(t)
        for it in b.get("items", []) or []:
            out.append("- " + _plain(it if isinstance(it, str) else _tx(it.get("text"), lang), lang))
    return out


def plan_template(run: Path) -> dict:
    """A starting plan: one part per section, the last two sections as context. make-podcast edits it."""
    ed = read_json(run / "source" / "en.json")
    ko = {s["id"]: s for s in (read_json(run / "source" / "ko.json") or {}).get("sections", [])}
    return {"parts": [{"id": f"p{i + 1}", "title": {"en": s["heading"], "ko": ko.get(s["id"], {}).get("heading", "")},
                       "sections": [s["id"]]} for i, s in enumerate(ed["sections"])],
            "context": [], "drop": []}


def source(run_id: str) -> dict:
    """podcast/<lang>.source.md and <lang>.prompt.txt for both editions, from the edition and podcast/plan.json."""
    run = run_dir(run_id)
    plan = read_json(run / "podcast" / "plan.json")
    if not plan:
        (run / "podcast").mkdir(exist_ok=True)
        write_json(run / "podcast" / "plan.json", plan_template(run))
        raise RuntimeError("podcast/plan.json was missing: a template is written; group the sections into parts, then run again")
    meta = read_json(run / "source" / "meta.json", {}) or {}
    slug = meta.get("slug") or (read_json(run / "run.json") or {})["source"]["slug"]
    out = {}
    for lang in LANGS:
        ed = read_json(run / "source" / f"{lang}.json")
        secs = {s["id"]: s for s in ed["sections"]}
        used = [x for p in plan["parts"] for x in p["sections"]] + plan.get("context", []) + plan.get("drop", [])
        missing = [s for s in secs if s not in used]
        if missing:
            raise RuntimeError(f"plan.json leaves out sections {missing}: put each in a part, context or drop")
        q = ed.get("question") or {}
        L = [f"# {_plain(ed['title'], lang)}", "",
             f"datasteg · articles.datasteg.com/{lang}/a/{slug} · {meta.get('updated') or meta.get('date') or ''}", "",
             f"## {WORD['q'][lang]}", _plain(q.get("asked") or "", lang), "",
             f"## {WORD['a'][lang]}", _plain(ed["dek"], lang), "", f"### {WORD['kf'][lang]}"]
        L += [f"- {_plain(f, lang)}" for f in ed.get("findings", [])]
        L += ["", f"### {WORD['kn'][lang]}"] + [f"- {k['value']}: {_plain(k['label'], lang)}" for k in ed.get("keyNumbers", [])]
        for i, p in enumerate(plan["parts"]):
            L += ["", f"## {WORD['part'][lang]} {i + 1}: {_tx(p['title'], lang)}"]
            for sid in p["sections"]:
                L += ["", f"### {_plain(secs[sid]['heading'], lang)}"] + _blocks(secs[sid], run, lang)
        ins = ed.get("insight") or {}
        if ins.get("text"):
            L += ["", f"## {_plain(ins.get('label') or WORD['read'][lang], lang)}", _plain(ins["text"], lang)]
        for sid in plan.get("context", []):
            L += ["", f"## {_plain(secs[sid]['heading'], lang)}"] + _blocks(secs[sid], run, lang)
        gl = []
        for t in meta.get("terms", []):
            g = read_json(CONTENT / "glossary" / f"{t['id']}.json", {}) or {}
            if g.get("term"):
                ctx = _tx(t.get("context"), lang)
                gl.append(f"- {_tx(g['term'], lang)}: {_tx(g.get('definition'), lang)}" + (f" {ctx}" if ctx else ""))
        if gl:
            L += ["", f"## {WORD['gl'][lang]}"] + gl
        text = "\n".join(L).strip() + "\n"
        parts = "\n".join(f"   - {WORD['part'][lang] if lang == 'en' else ORDINAL['ko'][i]}"
                          f"{' ' + ORDINAL['en'][i] if lang == 'en' else ''}: {_tx(p['title'], lang)}"
                          for i, p in enumerate(plan["parts"]))
        prompt = cfg("podcast")["prompt"][lang].format(title=_plain(ed["title"], lang), question=_plain(q.get("asked") or "", lang),
                                                       answer=_plain(plan.get("answer", {}).get(lang) or ed["dek"], lang),
                                                       parts=parts, keynumbers="; ".join(
                                                           f"{k['value']} ({_plain(k['label'], lang).split(';')[0].split('. ')[0]})"
                                                           for k in ed.get("keyNumbers", [])))
        (run / "podcast" / f"{lang}.source.md").write_text(text, encoding="utf-8")
        (run / "podcast" / f"{lang}.prompt.txt").write_text(prompt, encoding="utf-8")
        out[lang] = {"source": str(run / "podcast" / f"{lang}.source.md"), "chars": len(text),
                     "words": len(text.split()), "prompt_chars": len(prompt)}
    return out


def _seconds(path: Path) -> float:
    """The audio's length, from ffmpeg's header read (no ffprobe on this machine)."""
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        raise RuntimeError(f"cannot read the length of {path.name}")
    return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2)


def takes_left(run: Path, lang: str) -> int:
    """How many more NotebookLM takes the edition may have: one normally, a second only after a blocking review."""
    done = len((read_json(run / "podcast" / f"{lang}.json", {}) or {}).get("takes", []))
    return max(0, int((cfg("podcast").get("notebooklm") or {}).get("takes", 2)) - done)


def ingest(run_id: str, lang: str, file: str, notebook: str | None = None, title: str | None = None) -> dict:
    """The downloaded Audio Overview moved into the run (audio/<lang>.m4a), and the take recorded."""
    run = run_dir(run_id)
    src = Path(file).expanduser()
    if not src.is_file():
        raise RuntimeError(f"no file {src}")
    dest = run / "audio" / f"{lang}{src.suffix.lower() or '.m4a'}"
    dest.parent.mkdir(exist_ok=True)
    shutil.move(str(src), dest)
    secs = _seconds(dest)
    rec_p = run / "podcast" / f"{lang}.json"
    rec = read_json(rec_p, {}) or {}
    if not takes_left(run, lang):
        raise RuntimeError(f"{lang} already has {len(rec.get('takes', []))} takes (podcast.yaml → notebooklm.takes)")
    takes = rec.get("takes", []) + [{"file": dest.name, "seconds": secs, "title": title, "notebook": notebook,
                                     "ingested": __import__("datetime").datetime.now().isoformat(timespec="seconds")}]
    lim = cfg("podcast").get("length") or {}
    rec.update(lang=lang, audio=str(dest), seconds=secs, minutes=round(secs / 60, 1), title=title,
               notebook=notebook or rec.get("notebook"), takes=takes,
               length_ok=lim.get("min_seconds", 0) <= secs <= lim.get("max_seconds", 1e9))
    write_json(rec_p, rec)
    return rec


# Transcription runs on this machine: VibeVoice-ASR in its own environment (podcast.yaml → asr; vibevoice_asr.py).
# Chosen over Gemini on 29 Oct 2026: as accurate in English, more in Korean, better
# speakers, and it writes what the hosts said. Gemini made two hosts' lines agree, turning a slip ("삼분의 이 퍼센트")
# into the article's number.
SENT = re.compile(r"(?<=[.?!])\s+")
SPEED = {"en": 4.5, "ko": 13.5}            # words (en) or characters (ko) per second: faster is an invented transcript


def _pauses(audio: Path) -> list:
    """[(start, end)] of the pauses of 0.2 s or more at -35 dB (ffmpeg silencedetect)."""
    r = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(audio), "-af", "silencedetect=noise=-35dB:d=0.2",
                        "-f", "null", "-"], capture_output=True, text=True)
    out, cur = [], None
    for line in r.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", line)
        if m:
            cur = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end: ([\d.]+)", line)
        if m and cur is not None:
            out.append((cur, float(m.group(1))))
            cur = None
    return out


def _cut(pauses: list, t: float, window: float = 30.0) -> float:
    """The middle of the longest pause within `window` seconds of t (t itself if there is none)."""
    near = [p for p in pauses if t - window <= (p[0] + p[1]) / 2 <= t + window]
    best = max(near, key=lambda p: p[1] - p[0]) if near else (t, t)
    return round((best[0] + best[1]) / 2, 2)


def _pieces(pauses: list, total: float, step: float) -> list:
    """[(start, end)] of about `step` seconds each, cut at pauses; a remainder under a minute rides with the last."""
    pts, t = [0.0], step
    while t < total - 60:
        pts.append(_cut(pauses, t))
        t = pts[-1] + step
    pts.append(total)
    return list(zip(pts, pts[1:]))


def _vibevoice(wav: Path, pieces: list, prompt: str | None, tmp: Path) -> list:
    """The worker's pieces (vibevoice_asr.py), run with the STT environment's Python."""
    acfg = cfg("podcast").get("asr") or {}
    py = Path(os.path.expanduser(acfg.get("python", "")))
    if not py.is_file():
        raise RuntimeError(f"no STT environment at {py}")
    req, res = tmp / "request.json", tmp / "result.json"
    req.write_text(json.dumps({"audio": str(wav), "pieces": pieces, "prompt": prompt, "model": acfg["model"],
                               "tokens_per_second": acfg.get("tokens_per_second", 12)}, ensure_ascii=False))
    env = {**os.environ, "HF_HOME": os.path.expanduser(acfg.get("hf_home", "/data/huggingface")), "HF_HUB_OFFLINE": "1",
           "MIOPEN_FIND_MODE": "FAST", "TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL": "1",
           "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
    res.unlink(missing_ok=True)
    r = subprocess.run([str(py), "-I", str(Path(__file__).with_name("vibevoice_asr.py")), str(req), str(res)],
                       env=env, capture_output=True, text=True)
    if r.returncode or not res.is_file():
        last = (r.stderr.strip().splitlines() or ["no output"])[-1]
        raise RuntimeError(f"VibeVoice-ASR failed: {last[:300]}")
    return json.loads(res.read_text(encoding="utf-8"))["pieces"]


def _bad(p: dict, lang: str) -> str:
    """Why a piece can't be used: broken off, run to the token cap (a loop), or faster than anyone speaks."""
    if not p["parsed_ok"] or p["tokens"] >= p["cap"]:
        return "broken off" if not p["parsed_ok"] else "token cap"
    text = " ".join(s[3] for s in p["segments"])
    size = len(text.split()) if lang == "en" else len(text.replace(" ", ""))
    if size / max(1.0, p["end"] - p["start"]) > SPEED[lang]:
        return f"{size} {'words' if lang == 'en' else 'characters'} in {p['end'] - p['start']:.0f} s"
    return ""


def _voices(pieces: list) -> dict:
    """(piece, label) → A (the lower voice) or B. Each piece is heard on its own, so the model's labels can swap between
    pieces; the hosts' pitch does not. Voices too close to tell apart keep the order heard (A first)."""
    out = {}
    for i, p in enumerate(pieces):
        f = p.get("pitch") or {}
        heard = list(dict.fromkeys(s[2] for s in p["segments"]))
        if len(f) >= 2 and max(f.values()) / min(f.values()) > 1.25:
            cut = (max(f.values()) * min(f.values())) ** 0.5
            out.update({(i, s): ("A" if f[s] < cut else "B") if s in f else "?" for s in heard})
        else:
            out.update({(i, s): "AB"[k] if k < 2 else "?" for k, s in enumerate(heard)})
    return out


def _sentences(text: str, lang: str) -> list:
    """One sentence per segment, or clauses at the comma nearest the middle when it runs past 16 words or 40
    characters (podcast.yaml → asr.caption)."""
    cap = (cfg("podcast").get("asr") or {}).get("caption", {}).get(lang, 16 if lang == "en" else 40)
    size = (lambda s: len(s.split())) if lang == "en" else (lambda s: len(s.replace(" ", "")))
    out = []
    for s in SENT.split(text.strip()):
        while size(s) > cap:
            commas = [m.end() for m in re.finditer(r",\s", s)]
            if not commas:
                break
            k = min(commas, key=lambda c: abs(c - len(s) / 2))
            out.append(s[:k].strip())
            s = s[k:].strip()
        if s:
            out.append(s)
    return out


def transcribe(run_id: str, lang: str) -> dict:
    """asr/<lang>.json: the audio in timed segments, by VibeVoice-ASR on this machine (podcast.yaml → asr). The audio is
    cut at pauses into pieces of about five minutes (a piece that breaks off is heard again in two halves); each turn
    the model returns is split into sentences, timed by length, and every boundary is moved to the nearest pause. The
    24 kHz copy of the audio lives in a temporary folder that is deleted afterwards."""
    run = run_dir(run_id)
    rec = read_json(run / "podcast" / f"{lang}.json")
    if not rec or not Path(rec["audio"]).is_file():
        raise RuntimeError(f"no audio for {lang}: make-podcast first")
    acfg = cfg("podcast").get("asr") or {}
    audio = Path(rec["audio"])
    total = _seconds(audio)
    pauses = _pauses(audio)
    plan = _pieces(pauses, total, float(acfg.get("piece_seconds", 300)))
    with tempfile.TemporaryDirectory(prefix="podcast-asr-") as tmp:
        wav = Path(tmp) / "audio.wav"
        subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(audio), "-ac", "1", "-ar", "24000",
                        str(wav)], check=True)
        prompt = (acfg.get("context") or {}).get(lang)
        done = _vibevoice(wav, plan, prompt, Path(tmp))
        bad = [k for k, p in enumerate(done) if _bad(p, lang)]
        if bad:
            halves = []
            for k in bad:
                a, b = done[k]["start"], done[k]["end"]
                m = _cut(pauses, (a + b) / 2, window=(b - a) / 4)
                halves += [(a, m), (m, b)]
            again = iter(_vibevoice(wav, halves, prompt, Path(tmp)))
            redone = []
            for k, p in enumerate(done):
                redone += [next(again), next(again)] if k in bad else [p]
            done = redone
            still = [f"{p['start']:.0f}-{p['end']:.0f} s: {_bad(p, lang)}" for p in done if _bad(p, lang)]
            if still:
                raise RuntimeError(f"transcribing {lang} failed: {'; '.join(still)}")
    starts = sorted(b for a, b in pauses)           # where speech resumes
    mids = sorted((a + b) / 2 for a, b in pauses)
    near = lambda arr, t, lo, hi: min((x for x in arr if abs(x - t) <= 1.0 and lo < x < hi), key=lambda x: abs(x - t),
                                      default=t)
    voices, segs, repairs = _voices(done), [], 0
    for i, p in enumerate(done):
        for a, b, spk, text in p["segments"]:
            if not text:
                continue
            a, b = p["start"] + a, min(p["start"] + b, p["end"])
            prev = segs[-1]["start"] if segs else 0.0
            if a < prev:                           # out of order: pulled to the previous start (a repair)
                repairs += 1
                a = prev
            b = max(b, a + 0.3)
            a = near(starts, a, prev, b - 0.5)      # the model starts turns early: to the pause it follows
            parts = _sentences(text, lang)
            n = sum(len(x) for x in parts) or 1
            bounds, t = [a], a
            for x in parts[:-1]:
                t += (b - a) * len(x) / n
                bounds.append(near(mids, t, bounds[-1] + 0.3, b - 0.3))
            bounds.append(b)
            segs += [{"start": round(bounds[k], 2), "end": round(bounds[k + 1], 2), "speaker": voices.get((i, spk), "?"),
                      "text": x} for k, x in enumerate(parts)]
    for i, sg in enumerate(segs):                 # no overlaps: a segment ends where the next begins at the latest
        sg["i"] = i
        if i + 1 < len(segs):
            sg["end"] = min(sg["end"], segs[i + 1]["start"])
    gaps = [round(segs[i + 1]["start"] - segs[i]["end"], 1) for i in range(len(segs) - 1)]
    out = {"lang": lang, "model": acfg["model"], "seconds": total, "piece_seconds": acfg.get("piece_seconds", 300),
           "pieces": [{"start": p["start"], "end": p["end"], "seconds": p["seconds"], "tokens": p["tokens"],
                       "pitch": p.get("pitch")} for p in done],
           "repairs": repairs, "longest_gap": max(gaps or [0]), "segments": segs}
    write_json(run / "asr" / f"{lang}.json", out)
    return {"lang": lang, "segments": len(segs), "seconds": total, "pieces": len(done), "repairs": repairs,
            "longest_gap": out["longest_gap"], "gpu_seconds": round(sum(p["seconds"] for p in done)),
            "file": str(run / "asr" / f"{lang}.json")}


NUM = re.compile(r"\d+(?:[.,]\d+)*")
POINTING = {"en": re.compile(r"as you can see|this chart|on the screen|the chart (?:shows|here)|look at this", re.I),
            "ko": re.compile(r"보시는 것처럼|보시다시피|이 그래프|화면에|여기 보시면")}


def check(run_id: str, lang: str) -> dict:
    """Mechanical checks on what the hosts said: every number heard is in the source, nobody points at a screen, the
    length is in range. Writes asr/<lang>.check.json; the judgement is review-podcast's."""
    run = run_dir(run_id)
    asr = read_json(run / "asr" / f"{lang}.json")
    if not asr:
        raise RuntimeError(f"no transcript for {lang}: artools video podcast transcribe")
    src = (run / "podcast" / f"{lang}.source.md").read_text(encoding="utf-8")
    known = {n.replace(",", "") for n in NUM.findall(src)}
    known |= {n.rstrip("0").rstrip(".") for n in known if "." in n}
    unknown, pointing = [], []
    for sg in asr["segments"]:
        for n in NUM.findall(sg["text"]):
            k = n.replace(",", "")
            if k not in known and k.rstrip("0").rstrip(".") not in known and not (len(k) == 4 and k.startswith(("19", "20"))):
                unknown.append({"t": sg["start"], "number": n, "said": sg["text"]})
        if POINTING[lang].search(sg["text"]):
            pointing.append({"t": sg["start"], "said": sg["text"]})
    rec = read_json(run / "podcast" / f"{lang}.json", {}) or {}
    res = {"lang": lang, "seconds": asr["seconds"], "length_ok": rec.get("length_ok"),
           "numbers_not_in_source": unknown, "pointing": pointing, "segments": len(asr["segments"])}
    write_json(run / "asr" / f"{lang}.check.json", res)
    return {k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}


def hear(run_id: str, lang: str, at: float, seconds: float = 10) -> dict:
    """A second hearing of a few seconds, without the context prompt and apart from the piece around it, to tell a
    host's slip from a transcription slip before blocking a take."""
    run = run_dir(run_id)
    audio = (read_json(run / "podcast" / f"{lang}.json") or {}).get("audio")
    if not audio or not Path(audio).is_file():
        raise RuntimeError(f"no audio for {lang}")
    with tempfile.TemporaryDirectory(prefix="podcast-hear-") as tmp:
        clip = Path(tmp) / "clip.wav"
        subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(0, at - 1)}", "-t", f"{seconds}",
                        "-i", audio, "-ac", "1", "-ar", "24000", str(clip)], check=True)
        p = _vibevoice(clip, [(0.0, _seconds(clip))], None, Path(tmp))[0]
    return {"lang": lang, "at": at, "heard": " / ".join(s[3] for s in p["segments"])}


def _timeline(run: Path, lang: str, total: float) -> tuple[list, list]:
    """The checked cues and chapters of podcast/<lang>.timeline.json."""
    tl = read_json(run / "podcast" / f"{lang}.timeline.json")
    if not tl:
        raise RuntimeError(f"podcast/{lang}.timeline.json is missing: make-podcast-slides writes it")
    deck = read_json(run / "slides" / f"{lang}.resolved.json") or {}
    steps = {s["id"]: s["steps"] for s in deck.get("slides", [])}
    cues, probs, last = sorted(tl["cues"], key=lambda c: c["t"]), [], -1.0
    for c in cues:
        if c["slide"] not in steps:
            probs.append(f"cue at {c['t']}s: no slide {c['slide']}")
        elif c.get("step", 1) > steps[c["slide"]]:
            probs.append(f"cue at {c['t']}s: {c['slide']} has {steps[c['slide']]} steps")
        if c["t"] <= last or c["t"] >= total:
            probs.append(f"cue at {c['t']}s is out of order or past the end ({total}s)")
        last = c["t"]
    if cues and cues[0]["t"] > 0.5:
        probs.append("the first cue must start at 0")
    if probs:
        raise RuntimeError("; ".join(probs[:8]))
    return cues, sorted(tl.get("chapters", []), key=lambda c: c["t"])


def _caption_cues(segs: list, lang: str) -> list:
    """Captions from the timed segments: each split to fit two lines, timed by length within its segment."""
    from .assemble import _chunks, _wrap
    out = []
    for sg in segs:
        parts = _chunks(sg["text"], lang)
        total = sum(len(x) for x in parts) or 1
        t = sg["start"]
        span = max(0.4, sg["end"] - sg["start"])
        for x in parts:
            d = span * len(x) / total
            out.append((t, t + d, _wrap(x, lang)))
            t += d
    return out


OTHER = {"en": "ko", "ko": "en"}
READ_RATE = {"en": 21, "ko": 12}        # characters per second a viewer can read: longer captions are flagged


def _translated(run: Path, lang: str) -> tuple[list, list]:
    """The other-language captions (asr/<lang>.<other>.json) laid on the transcript's times, and what is wrong with
    them: a segment missing or empty, too long to read in its time, a number in one language and not the other."""
    to = OTHER[lang]
    asr = read_json(run / "asr" / f"{lang}.json") or {}
    tr = read_json(run / "asr" / f"{lang}.{to}.json")
    if not tr:
        return [], [f"asr/{lang}.{to}.json is missing: make-podcast-slides writes the {to} captions of the {lang} video"]
    segs, got, probs = asr.get("segments", []), {x["i"]: x.get("text", "").strip() for x in tr.get("segments", [])}, []
    out = []
    for i, sg in enumerate(segs):
        text = got.get(i, "")
        if not text:
            probs.append(f"segment {i} ({sg['start']:.0f}s) has no translation")
            continue
        rate = len(text) / max(0.8, sg["end"] - sg["start"])
        if rate > READ_RATE[to] * 1.5:
            probs.append(f"segment {i} ({sg['start']:.0f}s): {rate:.0f} characters a second, shorten it")
        big = lambda t: {n for n in NUM.findall(t.replace(",", "")) if "." in n or len(n) > 1}   # 4분기 is "Q4" or "fourth"
        a, b = big(sg["text"]), big(text)
        if a != b:
            probs.append(f"segment {i} ({sg['start']:.0f}s): numbers {sorted(a)} said, {sorted(b)} in the translation")
        out.append({**sg, "text": text})
    extra = sorted(set(got) - set(range(len(segs))))
    if extra:
        probs.append(f"translations for segments that don't exist: {extra[:5]}")
    return out, probs


def captions(run_id: str, lang: str) -> dict:
    """`artools video podcast captions`: check the other-language captions before assembly."""
    segs, probs = _translated(run_dir(run_id), lang)
    return {"to": OTHER[lang], "segments": len(segs), "problems": probs}


def _write_captions(out_dir: Path, name: str, caps: list) -> None:
    from .assemble import _ts
    (out_dir / f"{name}.srt").write_text("\n".join(f"{i + 1}\n{_ts(a)} --> {_ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(caps)),
                                        encoding="utf-8")
    (out_dir / f"{name}.vtt").write_text("WEBVTT\n\n" + "\n".join(f"{_ts(a, '.')} --> {_ts(b, '.')}\n{t}\n" for a, b, t in caps),
                                        encoding="utf-8")


FPS = 30
FADE = 0.4                               # seconds: each slide cross-fades from the one before
RAIL_FILL = "0x89E0F8"                   # --meltwater, the dark theme's --link


def _spans(cues: list, part_of: dict, order: list, total: float) -> dict:
    """Each part's time on air: from its first cue to the first cue of a later part (or the recap)."""
    first = {}
    for c in cues:
        first.setdefault(part_of.get(c["slide"]), c["t"])
    out = {}
    for i, p in enumerate(order):
        if p not in first:
            continue
        later = [first[q] for q in order[i + 1:] + ["recap", "end"] if q in first and first[q] > first[p]]
        out[p] = (first[p], min(later) if later else total)
    return out


def _segment(exe: str, out: Path, still: Path, clip: Path | None, prev: Path | None, frames: int, rail: tuple | None) -> None:
    """One cue: a cross-fade from the previous slide, the slide's enter clip (or its still), held to the next cue;
    on a rail slide, the current part's track filling as the audio runs through it (rail = x, y, w, h, t0, span)."""
    hold = frames / FPS + 1
    cmd, inputs = [exe, "-hide_banner", "-loglevel", "error", "-y"], 0
    if prev:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", str(FADE), "-i", str(prev)]
        inputs += 1
    cmd += ["-i", str(clip)] if clip else ["-loop", "1", "-framerate", str(FPS), "-t", str(hold), "-i", str(still)]
    body = f"[{inputs}:v]fps={FPS},format=yuv420p,setsar=1" + (f",tpad=stop_mode=clone:stop_duration={hold:.2f}" if clip else "")
    graph = [body + "[b]"]
    last = "b"
    if prev:
        graph.append(f"[0:v]fps={FPS},format=yuv420p,setsar=1[a]")
        graph.append(f"[a][b]xfade=transition=fade:duration={FADE}:offset=0[x]")
        last = "x"
    if rail:
        x, y, w, h, t0, span = rail
        graph.append(f"[{last}]split[m][c]")
        graph.append(f"[c]crop={w}:{h}:{x}:{y}[trk]")
        graph.append(f"color=c={RAIL_FILL}:s={w}x{h}:r={FPS}[fill]")
        graph.append(f"[trk][fill]overlay=x='-{w}+{w}*min(1,({t0:.3f}+t)/{span:.3f})':y=0:shortest=1[bar]")
        graph.append(f"[m][bar]overlay={x}:{y}[r]")
        last = "r"
    cmd += ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-frames:v", str(frames), "-r", str(FPS),
            "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "20", "-pix_fmt", "yuv420p", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg failed on {out.name}: {r.stderr[-600:]}")


def render_video(run: Path, lang: str, cues: list, total: float, audio: Path | None, mp4: Path,
                 until: float | None = None) -> int:
    """The picture: one segment per cue (podcast decks with motion: cross-fade, enter clip, hold, rail), joined
    without re-encoding, then the audio. Segments live in a temporary folder. `until` cuts a preview short."""
    exe = ffmpeg()
    frames_dir = run / "slides" / lang
    deck = read_json(run / "slides" / f"{lang}.resolved.json") or {}
    shot = read_json(run / "slides" / "render.json", {}) or {}
    rec = {(f["slide"], f["step"]): f for f in shot.get("list", []) if f["lang"] == lang}
    part_of = {s["id"]: s["part"] for s in deck.get("slides", [])}
    order = [p["id"] for p in deck.get("story") or []]
    spans = _spans(cues, part_of, order, total)
    rail = (shot.get("rail") or {}).get(lang) or {}
    end = min(total, until) if until else total
    with tempfile.TemporaryDirectory(prefix="podcast-") as tmp:
        lst, prev = [], None
        for k, c in enumerate(cues):
            t0 = c["t"]
            if t0 >= end:
                break
            t1 = min(cues[k + 1]["t"] if k + 1 < len(cues) else total, end)
            frames = round(t1 * FPS) - round(t0 * FPS)
            step = c.get("step", 1)
            still = frames_dir / f"{c['slide']}-{step}.png"
            if not still.is_file():
                raise RuntimeError(f"missing frame {still.name}: artools video slides {run.name} --langs {lang}")
            f = rec.get((c["slide"], step), {})
            clip = Path(f["clip"]["file"]) if f.get("clip") and Path(f["clip"]["file"]).is_file() else None
            p = part_of.get(c["slide"])
            bar = None
            if f.get("rail") and p in spans and p in rail and spans[p][0] <= t0 < spans[p][1]:
                a, b = spans[p]
                bar = (*rail[p], t0 - a, max(1.0, b - a))
            seg = Path(tmp) / f"{k:04d}.mp4"
            _segment(exe, seg, still, clip, prev if prev != still else None, frames, bar)
            lst.append(f"file '{seg}'")
            prev = still
        (Path(tmp) / "list.txt").write_text("\n".join(lst) + "\n")
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt"]
        if audio:
            af, _ = _loudnorm(exe, audio)
            cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-metadata", f"language={'eng' if lang == 'en' else 'kor'}", "-shortest"]
        else:
            cmd += ["-c:v", "copy"]
        cmd += ["-movflags", "+faststart", str(mp4)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError("ffmpeg failed: " + r.stderr[-800:])
    return len(lst)


def assemble(run_id: str, lang: str) -> dict:
    """video/<lang>.mp4: the slides at their cue times over the NotebookLM audio (normalised to -14 LUFS), each
    entering with its animation, with captions from the transcript in both languages and chapters from the timeline."""
    run = run_dir(run_id)
    rec = read_json(run / "podcast" / f"{lang}.json")
    asr = read_json(run / "asr" / f"{lang}.json")
    if not (rec and asr):
        raise RuntimeError("needs the audio and its transcript (make-podcast, transcribe)")
    tr, probs = _translated(run, lang)
    if not tr:
        raise RuntimeError(probs[0])
    audio = Path(rec["audio"])
    total = _seconds(audio)
    cues, chapters = _timeline(run, lang, total)
    out_dir = run / "video"
    out_dir.mkdir(exist_ok=True)
    mp4 = out_dir / f"{lang}.mp4"
    n = render_video(run, lang, cues, total, audio, mp4)
    _, measured = _loudnorm(ffmpeg(), audio)
    caps = _caption_cues(asr["segments"], lang)
    _write_captions(out_dir, lang, caps)
    other = _caption_cues(tr, OTHER[lang])
    _write_captions(out_dir, f"{lang}.{OTHER[lang]}", other)
    chap = [f"{int(c['t'] // 60):02d}:{int(c['t'] % 60):02d} {c['title']}" for c in chapters]
    if chap and not chap[0].startswith("00:00"):
        chap[0] = "00:00 " + chap[0].split(" ", 1)[1]
    lim = cfg("podcast").get("length") or {}
    info = {"lang": lang, "file": str(mp4), "seconds": round(total, 1), "minutes": round(total / 60, 2),
            "placeholder_voice": False, "loudness": measured, "chapters": chap, "frames": n,
            "captions": len(caps), "captions_other": {"lang": OTHER[lang], "cues": len(other), "problems": probs[:10]},
            "bytes": mp4.stat().st_size, "length_ok": lim.get("min_seconds", 0) <= total <= lim.get("max_seconds", 1e9)}
    write_json(out_dir / f"{lang}.json", {**info, "beats": [], "timeline": cues})
    return info


def thumb(run_id: str, lang: str) -> dict:
    """video/<lang>-thumb.png: the deck's thumb slide (template thumb) at 1280x720, under YouTube's 2 MB."""
    run = run_dir(run_id)
    tl = read_json(run / "podcast" / f"{lang}.timeline.json", {}) or {}
    sid = tl.get("thumb") or "thumb"
    src = run / "slides" / lang / f"{sid}-1.png"
    if not src.is_file():
        raise RuntimeError(f"no frame {src.name} for the thumbnail")
    dest = run / "video" / f"{lang}-thumb.png"
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vf", "scale=1280:720",
                    str(dest)], check=True)
    return {"thumb": str(dest), "bytes": dest.stat().st_size}


def clean(run_id: str, lang: str) -> dict:
    """After the upload: the audio, frames and video deleted (they live in NotebookLM and on YouTube); the JSON,
    transcripts and captions stay."""
    run = run_dir(run_id)
    if not (read_json(run / "youtube" / f"{lang}.json", {}) or {}).get("video_id"):
        raise RuntimeError(f"{lang} is not on YouTube yet: nothing is deleted before the upload")
    gone = [p for p in [*(run / "audio").glob(f"{lang}.*"), *(run / "slides" / lang).glob("*.png"),
                        *(run / "slides" / lang).glob("*.mp4"),
                        run / "slides" / f"{lang}-sheet.png", run / "video" / f"{lang}.mp4",
                        run / "video" / f"{lang}.frames.txt", run / "video" / f"{lang}-thumb.png"] if p.is_file()]
    freed = sum(p.stat().st_size for p in gone)
    for p in gone:
        p.unlink()
    return {"deleted": len(gone), "freed_mb": round(freed / 1e6, 1)}


def cli(a) -> dict:
    """`artools video podcast <action> <run>`"""
    import time
    if a.action == "wait":                     # the hosts take ten minutes or more: a pause the stage sessions can take
        time.sleep(max(1, min(a.seconds, 600)))
        return {"waited": a.seconds}
    if not a.run:
        raise RuntimeError("give the run id")
    langs = (a.lang,) if a.lang else LANGS
    if a.action == "plan":
        run = run_dir(a.run)
        p = run / "podcast" / "plan.json"
        if p.is_file():
            return {"exists": str(p), "plan": read_json(p)}
        p.parent.mkdir(exist_ok=True)
        write_json(p, plan_template(run))
        return {"written": str(p), "plan": read_json(p)}
    if a.action == "source":
        return source(a.run)
    if a.action == "hear":
        if not (a.lang and a.at is not None):
            raise RuntimeError("hear needs --lang and --at <seconds>")
        return hear(a.run, a.lang, a.at)
    if a.action == "ingest":
        if not (a.lang and a.file):
            raise RuntimeError("ingest needs --lang and --file (the downloaded audio)")
        return ingest(a.run, a.lang, a.file, a.notebook, a.title)
    fn = {"transcribe": transcribe, "check": check, "captions": captions, "assemble": assemble, "thumb": thumb,
          "clean": clean}[a.action]
    return {lang: fn(a.run, lang) for lang in langs}
