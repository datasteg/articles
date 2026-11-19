"""`artools video voice`: the narration, one Gemini TTS request per beat, each take transcribed and compared with
what the narrator was meant to say; a beat whose numbers or words don't match is recorded again.

<run>/audio/<lang>/<beat>.wav   one take per beat (24 kHz mono)
<run>/audio/<lang>/voice.json   per beat: text, spoken text, seconds, takes, transcript, WER, numbers, flags
`--placeholder` writes silence of the estimated length instead, to test assembly before the voice is set up."""
from __future__ import annotations

import hashlib
import re
import wave
from pathlib import Path

from ..paths import read_json, run_dir, write_json
from . import cfg
from .script import facts_of
from .speech import render

MAX_TAKES = 3
MAX_WER = 0.05                       # numbers excluded; punctuation, spacing and loanword spellings make up the rest
NUM = re.compile(r"\d+(?:[.,]\d+)*")


NUMBER_WORDS = set("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
                   "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred "
                   "thousand million billion trillion point".split())


def _norm_words(t: str, lang: str) -> list[str]:
    """Words for the error rate, numbers left out: they are checked on their own, and a transcript may write
    "ten" as "10"."""
    t = t.lower().replace(",", "")
    if lang == "ko":
        # the script spells units out (퍼센트포인트, 베이시스포인트) where a transcript writes symbols (%p, bp)
        for sym, word in (("%포인트", "퍼센트포인트"), ("%p", "퍼센트포인트"), ("%", "퍼센트"), ("bp", "베이시스포인트")):
            t = t.replace(sym, word)
        return [c for c in re.sub(r"[^가-힣]", "", t)]                 # syllables
    t = t.replace("%", " percent ")                                    # the script says "percent", a transcript writes %
    return [w for w in re.findall(r"[a-z']+", t) if w not in NUMBER_WORDS]


def wer(ref: str, hyp: str, lang: str) -> float:
    r, h = _norm_words(ref, lang), _norm_words(hyp, lang)
    if not r:
        return 0.0
    prev = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, b in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b))
        prev = cur
    return round(prev[-1] / len(r), 3)


def numbers(t: str) -> list[str]:
    return [n.replace(",", "") for n in NUM.findall(t)]


def numbers_heard(said: str, heard: str) -> bool:
    """Every number the script says is in the transcript (which may add digits for numbers said in words)."""
    from collections import Counter
    return not (Counter(numbers(said)) - Counter(numbers(heard)))


def transcribe(wav: bytes, lang: str) -> str:
    """What the take actually says, by Gemini (config/video/voices.yaml → asr). Mechanical: no Claude tokens."""
    from google.genai import types
    from .tts import client
    model = (cfg("voices").get("asr") or {}).get("model", "gemini-3.5-flash")
    # Told not to "correct" years: given a whole paragraph about 2026 data, transcribers wrote 2024 for a 2026 the
    # voice said clearly (tested 26 Oct 2026, gemini-3.8-flash more often than gemini-3.5-flash).
    prompt = ("Transcribe this narration exactly as spoken, in " + ("Korean (Hangul)" if lang == "ko" else "English")
              + ". It was recorded in late 2026 and describes data up to 2026. Write numbers as digits. Do not correct, "
              "update or 'fix' any year, number or name to what you believe is true: write only what the speaker says. "
              # the site's name is not a word a transcriber knows: it heard "datastack" and "데이타스타크" (27 Oct 2026)
              + ("The narration may name the website 아티클스 닷 데이터스테그 닷 컴 (데이터스테그 is the publisher's name). "
                 if lang == "ko" else
                 "The narration may name the website articles dot datasteg dot com (datasteg is the publisher's name). ")
              + "Output only the transcript.")
    c = client()                           # keep a reference: a collected Client closes its connection
    res = c.models.generate_content(model=model, contents=[prompt, types.Part.from_bytes(data=wav, mime_type="audio/wav")])
    return (res.text or "").strip()


def _silence(seconds: float, rate: int = 24000) -> bytes:
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))
    return buf.getvalue()


def estimate_seconds(text: str, lang: str) -> float:
    rate = (cfg("speech").get("rate") or {}).get(lang, 150)
    n = len(re.findall(r"[가-힣]", text)) if lang == "ko" else len(text.split())
    return round(max(1.0, n / rate * 60), 2)


def voice(run_id: str, lang: str, beats: list[str] | None = None, placeholder: bool = False) -> dict:
    run = run_dir(run_id)
    facts = facts_of(run)
    sc = read_json(run / "script" / f"{lang}.json")
    if not sc:
        raise RuntimeError(f"script/{lang}.json is missing")
    folder = run / "audio" / lang
    folder.mkdir(parents=True, exist_ok=True)
    rec_p = folder / "voice.json"
    rec = read_json(rec_p, {}) or {}
    old = {b["beat"]: b for b in rec.get("beats", [])}
    out, flagged = [], []
    for b in sc["beats"]:
        bid = b["beat"]
        text = render(b["spoken"], facts, lang)                       # numbers as words: what must be heard
        h = hashlib.sha256(f"{text}|{placeholder}".encode()).hexdigest()[:12]
        wav_p = folder / f"{bid}.wav"
        prev = old.get(bid)
        redo = beats is not None and bid in beats
        if prev and prev.get("hash") == h and wav_p.is_file() and not redo:
            out.append(prev)
            continue
        if placeholder:
            secs = estimate_seconds(text, lang)
            wav_p.write_bytes(_silence(secs))
            out.append({"beat": bid, "text": text, "hash": h, "seconds": secs, "placeholder": True})
            continue
        from .tts import synthesize
        takes, audio = [], []
        for n in range(1, MAX_TAKES + 1):
            wav, meta = synthesize(text, lang)
            heard = transcribe(wav, lang)
            num_ok = numbers_heard(text, heard)
            if not num_ok:                                            # a second opinion before recording again
                again = transcribe(wav, lang)
                if numbers_heard(text, again):
                    heard, num_ok = again, True
            w = wer(text, heard, lang)
            takes.append({"take": n, "seconds": meta["seconds"], "heard": heard, "wer": w, "numbers_ok": num_ok})
            audio.append(wav)
            if num_ok and w <= MAX_WER:
                break
        best = min(range(len(takes)), key=lambda i: (not takes[i]["numbers_ok"], takes[i]["wer"]))
        wav_p.write_bytes(audio[best])                                # the best take, not necessarily the last
        t = takes[best]
        meta["seconds"] = t["seconds"]
        row = {"beat": bid, "text": text, "spoken": meta["text"], "hash": h, "seconds": meta["seconds"],
               "voice": meta["voice"], "model": meta["model"], "takes": len(takes), "heard": t["heard"],
               "wer": t["wer"], "numbers_ok": t["numbers_ok"]}
        if not (t["numbers_ok"] and t["wer"] <= MAX_WER):
            row["flag"] = "numbers misread" if not t["numbers_ok"] else f"WER {t['wer']}"
            flagged.append(bid)
        out.append(row)
        write_json(rec_p, {**rec, "lang": lang, "beats": out + [old[x["beat"]] for x in sc["beats"][len(out):] if x["beat"] in old],
                           "in_progress": True})                      # a restart keeps every finished beat
    total = round(sum(x["seconds"] for x in out), 1)
    size = sum(len(re.findall(r"[가-힣]", x["text"])) if lang == "ko" else len(x["text"].split()) for x in out)
    res = {"lang": lang, "beats": out, "speech_seconds": total,
           "rate": round(size / (total / 60), 1) if total else None, "placeholder": placeholder or None,
           "flagged": flagged}
    write_json(rec_p, res)
    return {"lang": lang, "beats": len(out), "speech_seconds": total, "rate_per_min": res["rate"], "flagged": flagged,
            "placeholder": placeholder}


def rescore(run_id: str, lang: str) -> dict:
    """Score the recorded takes again from their stored transcripts (after a change to the comparison); no TTS calls."""
    run = run_dir(run_id)
    rec_p = run / "audio" / lang / "voice.json"
    rec = read_json(rec_p, {}) or {}
    flagged = []
    for b in rec.get("beats", []):
        if b.get("placeholder") or "heard" not in b:
            continue
        b["wer"] = wer(b["text"], b["heard"], lang)
        b["numbers_ok"] = numbers_heard(b["text"], b["heard"])
        b.pop("flag", None)
        if not (b["numbers_ok"] and b["wer"] <= MAX_WER):
            b["flag"] = "numbers misread" if not b["numbers_ok"] else f"WER {b['wer']}"
            flagged.append(b["beat"])
    rec["flagged"] = flagged
    write_json(rec_p, rec)
    return {"lang": lang, "flagged": flagged, "max_wer": max((b.get("wer", 0) for b in rec.get("beats", [])), default=0)}
