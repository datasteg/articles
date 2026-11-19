"""VibeVoice-ASR worker: run by podcast.py with the STT environment's Python
(podcast.yaml → asr.python), not by artools' own: the model needs transformers >= 5.3 and a ROCm build of PyTorch.

    python -I vibevoice_asr.py request.json result.json

request: {"audio": a 24 kHz mono WAV, "pieces": [[start, end], ...] in seconds, "prompt": context text or null,
          "model": "microsoft/VibeVoice-ASR-HF", "tokens_per_second": 12}
result:  {"load_s", "peak_gb", "pieces": [{"start", "end", "seconds", "tokens", "cap", "parsed_ok",
          "segments": [[start, end, speaker, text], ...] (times within the piece), "pitch": {speaker: Hz}}]}

Whole files fail on this GPU (out of memory at 18 minutes; a loop to the token cap at 13 minutes, 4 hours): the
caller cuts the audio at pauses into pieces of about five minutes, and the token cap stops a loop early."""
import json
import re
import sys
import time

import librosa
import numpy as np
import soundfile as sf
import torch
from transformers import AutoProcessor, VibeVoiceAsrForConditionalGeneration

SEG = re.compile(r'\{\s*"Start"\s*:\s*([\d.]+)\s*,\s*"End"\s*:\s*([\d.]+)\s*,\s*"Speaker"\s*:\s*"?(\w+)"?\s*,'
                 r'\s*"Content"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}')


def parse(raw: str):
    """The model writes a JSON list of {Start, End, Speaker, Content}; if it breaks off, keep the complete objects."""
    raw = raw[raw.find("["):] if "[" in raw else raw
    try:
        return [[float(x["Start"]), float(x["End"]), str(x["Speaker"]), str(x["Content"]).strip()]
                for x in json.loads(raw)], True
    except Exception:  # noqa: BLE001
        return [[float(a), float(b), c, json.loads(f'"{d}"').strip()] for a, b, c, d in SEG.findall(raw)], False


def pitch(clip: np.ndarray, sr: int, segs: list) -> dict:
    """Median pitch of each speaker's voiced frames: the caller maps labels to voices across pieces."""
    hop = sr // 50
    f0 = librosa.yin(clip, fmin=65, fmax=400, sr=sr, frame_length=2048, hop_length=hop)
    rms = librosa.feature.rms(y=clip, frame_length=2048, hop_length=hop)[0][:len(f0)]
    t = np.arange(len(f0)) * hop / sr
    voiced = (rms > np.percentile(rms, 40)) & (f0 > 70) & (f0 < 380)
    out = {}
    for spk in {s[2] for s in segs}:
        m = np.zeros(len(f0), bool)
        for a, b, s, _ in segs:
            if s == spk:
                m |= (t >= a) & (t < b)
        v = f0[m & voiced]
        if len(v) >= 50:
            out[spk] = round(float(np.median(v)), 1)
    return out


def main(req_path: str, out_path: str) -> None:
    req = json.loads(open(req_path, encoding="utf-8").read())
    t0 = time.time()
    proc = AutoProcessor.from_pretrained(req["model"])
    model = VibeVoiceAsrForConditionalGeneration.from_pretrained(req["model"], dtype=torch.bfloat16, device_map="cuda:0")
    load_s = time.time() - t0
    audio, sr = sf.read(req["audio"], dtype="float32")
    torch.cuda.reset_peak_memory_stats()
    pieces = []
    for a, b in req["pieces"]:
        clip = audio[int(a * sr):int(b * sr)]
        t1 = time.time()
        inputs = proc.apply_transcription_request(audio=clip, prompt=req.get("prompt")).to(model.device, model.dtype)
        cap = int((b - a) * req.get("tokens_per_second", 12)) + 256
        out = model.generate(**inputs, max_new_tokens=cap, do_sample=False)
        gen = out[:, inputs["input_ids"].shape[1]:]
        segs, ok = parse(proc.decode(gen, skip_special_tokens=True)[0])
        pieces.append({"start": a, "end": b, "seconds": round(time.time() - t1, 1), "tokens": int(gen.shape[1]),
                       "cap": cap, "parsed_ok": ok, "segments": segs, "pitch": pitch(clip, sr, segs)})
        print(f"{a:.0f}-{b:.0f} s: {gen.shape[1]} tokens, {len(segs)} segments, {pieces[-1]['seconds']} s", flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"load_s": round(load_s, 1), "peak_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                   "pieces": pieces}, f, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
