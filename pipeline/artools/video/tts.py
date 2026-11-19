"""The narrator's voice: Gemini TTS through the Interactions API (docs: ai.google.dev/gemini-api/docs/speech-generation).

The request text is a verbatim transcript; delivery goes in speech_metadata.style, kept short (config/video/voices.yaml).
The key is read from a private file (config/video/publish.yaml → secrets) and never printed."""
from __future__ import annotations

import base64
import datetime as dt
import io
import time
import wave
from pathlib import Path

from ..paths import env_value, write_json
from . import VDATA, cfg, secret_path
from .speech import apply_lexicon

AUDITION_TEXT = {
    "en": ("In September 2026, France paid 97 basis points more than Germany to borrow for ten years. "
           "That is just under one percentage point, and the widest gap since July 2012. So is this 2011 again? "
           "The short answer is no. What the data show is a French problem in a calm market, not a crisis of the euro area."),
    "ko": ("2026년 9월, 프랑스는 독일보다 비싼 이자를 내고 돈을 빌렸습니다. 10년 만기 국채의 금리 차이는 97bp였습니다. "
           "1%포인트에 조금 못 미치는 차이로, 2012년 7월 이후 가장 큽니다. 그렇다면 2011년 같은 유로존 위기가 다시 오는 걸까요? "
           "결론부터 말씀드리면, 지금은 유로존 전체의 위기라기보다 프랑스의 문제에 가깝습니다."),
}


def api_key() -> str | None:
    return env_value("GEMINI_API_KEY", [secret_path("gemini_env")])


def client():
    from google import genai
    key = api_key()
    if not key:
        raise RuntimeError(f"no GEMINI_API_KEY ({secret_path('gemini_env')})")
    # A time limit on every request: without one, a request on a connection Google had closed hung for 20 minutes
    # (26 Oct 2026); with one it fails and synthesize() retries it.
    return genai.Client(api_key=key, http_options={"timeout": 120_000})


def voice_for(lang: str, voice: str | None = None) -> tuple[str, str, str]:
    """(model, voice, style) for an edition: the given voice, else the chosen one, else the first to audition."""
    v = cfg("voices")
    ed = v.get(lang) or {}
    name = voice or ed.get("voice") or (ed.get("audition") or ["Charon"])[0]
    return v.get("model", "gemini-3.8-flash-tts"), name, ed.get("style") or ""


def _audio_bytes(inter) -> bytes:
    """The WAV bytes of an interaction: output_audio.data (base64), else the first audio content in its steps."""
    oa = getattr(inter, "output_audio", None)
    data = getattr(oa, "data", None) if oa is not None else None
    if not data:
        for step in getattr(inter, "steps", None) or []:
            for c in getattr(step, "content", None) or []:
                if getattr(c, "data", None):
                    data = c.data
                    break
            if data:
                break
    if not data:
        raise RuntimeError("the response has no audio")
    return base64.b64decode(data) if isinstance(data, str) else bytes(data)


ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
TIMEOUT = (10, 120)      # seconds to connect, to receive the audio: the SDK's own timeouts didn't reach TTS calls, and a
                         # stalled request blocked a run for 30 minutes (26 Oct 2026), so voice calls go over REST


def _request(body: dict) -> bytes:
    """One TTS request over REST with a hard time limit; returns the WAV bytes."""
    import httpx
    key = api_key()
    if not key:
        raise RuntimeError(f"no GEMINI_API_KEY ({secret_path('gemini_env')})")
    t = httpx.Timeout(TIMEOUT[1], connect=TIMEOUT[0])
    r = httpx.post(ENDPOINT, json=body, headers={"x-goog-api-key": key}, timeout=t)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    data = None
    for step in r.json().get("steps") or []:
        for c in step.get("content") or []:
            if c.get("data"):
                data = c["data"]
                break
        if data:
            break
    if not data:
        raise RuntimeError("the response has no audio")
    return base64.b64decode(data)


def synthesize(text: str, lang: str, voice: str | None = None, style: str | None = None, lexicon: bool = True,
               retries: int = 5) -> tuple[bytes, dict]:
    """One beat: text (already rendered, no tokens) → WAV bytes, and a record of how it was made. A timeout, a 429 or
    a 5xx is retried with backoff; a spend cap or a bad request is not."""
    model, name, default_style = voice_for(lang, voice)
    style = default_style if style is None else style
    say = apply_lexicon(text, lang) if lexicon else text
    part = {"type": "text", "text": say}
    if style:
        part["annotations"] = [{"type": "speech_metadata", "style": style}]
    body = {"model": model, "input": [{"type": "user_input", "content": [part]}], "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": name}]}}
    for attempt in range(1, retries + 1):
        try:
            wav = _request(body)
            return wav, {"model": model, "voice": name, "style": style, "text": say, "seconds": wav_seconds(wav),
                         "attempts": attempt}
        except Exception as e:  # noqa: BLE001 - httpx timeouts, HTTP errors and parse errors
            msg = f"{type(e).__name__}: {e}"
            spend_cap = any(x in msg.lower() for x in ("spend cap", "spending cap", "spending limit", "prepayment",
                                                         "requests per day"))   # Tier 1: 100 TTS requests a day
            transient = any(x in msg for x in ("Timeout", "429", "500", "502", "503", "504", "RESOURCE_EXHAUSTED",
                                               "UNAVAILABLE", "Connect", "RemoteProtocol", "ReadError", "no audio"))
            if spend_cap or not transient or attempt == retries:
                raise RuntimeError(f"TTS failed after {attempt} attempt(s): {msg[:400]}") from e
            time.sleep(min(60, 4 * 2 ** attempt))
    raise RuntimeError("unreachable")


def wav_seconds(wav: bytes) -> float:
    try:
        with wave.open(io.BytesIO(wav)) as w:
            return round(w.getnframes() / float(w.getframerate()), 2)
    except wave.Error:
        return 0.0


def say(text: str, lang: str, voice: str | None = None, out: str | None = None) -> dict:
    """A test take: writes the WAV under /data/articles/video/say/ (or `out`)."""
    wav, rec = synthesize(text, lang, voice)
    p = Path(out) if out else VDATA / "say" / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{lang}-{rec['voice']}.wav"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(wav)
    return {"file": str(p), **{k: v for k, v in rec.items() if k != "text"}, "spoken_text": rec["text"]}


def audition(lang: str, voices: list[str] | None = None, text: str | None = None) -> dict:
    """The same opening read by every voice on the audition list, for choosing by ear."""
    names = voices or (cfg("voices").get(lang) or {}).get("audition") or []
    avoid = set(cfg("voices").get("avoid") or [])
    folder = VDATA / "audition" / f"{dt.date.today():%Y%m%d}-{lang}"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        if name in avoid:
            rows.append({"voice": name, "skipped": "on the avoid list"})
            continue
        try:
            wav, rec = synthesize(text or AUDITION_TEXT[lang], lang, name)
            p = folder / f"{name}.wav"
            p.write_bytes(wav)
            rows.append({"voice": name, "file": str(p), "seconds": rec["seconds"]})
        except Exception as e:  # noqa: BLE001 - keep going: one voice failing shouldn't lose the others
            rows.append({"voice": name, "error": str(e)[:300]})
    res = {"lang": lang, "folder": str(folder), "takes": rows}
    write_json(folder / "audition.json", res)
    return res
