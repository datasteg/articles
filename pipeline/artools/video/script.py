"""The storyboard and scripts: finding facts, and the mechanical check `artools check video-script`
(guides/video.md). Blocking problems stop `artools run done`; advisory ones go to the review."""
from __future__ import annotations

import re
from pathlib import Path

from ..paths import read_json
from . import cfg
from .speech import VTOKEN, render

POINTING = {
    "en": [r"\bas you can see\b", r"\bthis chart\b", r"\bthe chart (above|below)\b", r"\bhere you see\b", r"\bon the (left|right)\b",
           r"\bthe (red|blue|green|orange|grey|gray) line\b", r"\bon (the )?screen\b"],
    "ko": [r"보시는 것처럼", r"보시다시피", r"이 그래프", r"화면", r"여기(를)? 보", r"왼쪽", r"오른쪽", r"(빨간|파란|초록|주황|회색) 선"],
}
BANNED = {
    "en": [r"let'?s dive", r"\bdive (deep|in)\b", r"\bfascinating\b", r"here'?s the thing", r"\bsimply put\b",
           r"you might be thinking", r"game[- ]changer", r"\bexactly\b", r"\bwow\b", r"!"],
    "ko": [r"에 대해 알아보겠습니다", r"파고들어", r"흥미롭게도", r"무려", r"여러분", r"^자,", r"!"],
}
SINO_PAIRS = {"인상": "올렸다", "인하": "내렸다", "증가": "늘었다", "감소": "줄었다", "상승": "올랐다", "하락": "떨어졌다"}
TEMPLATE_FIELDS = {"question": ["text"], "answer": ["text"], "roadmap": ["items"], "number": ["label"],
                   "figure": ["headline"], "compare": ["items"], "findings": ["items"], "term": ["kicker", "text"],
                   "quote": ["text", "source"], "read": ["text"], "end": ["items", "text", "label"]}
LONG_TEXT = {"question", "quote", "term", "read", "end"}
PART_ORDER = ["open", "answer", "p1", "p2", "p3", "p4", "limits", "recap", "end"]
SENT = re.compile(r"(?<=[.?!。])\s+")


def facts_of(run: Path) -> dict:
    return {f["id"]: f for f in (read_json(run / "source" / "facts.json", {}) or {}).get("facts", [])}


def find_facts(run: Path, grep: str | None = None, limit: int = 60) -> dict:
    """The run's facts with their written and spoken forms, filtered by label or value text."""
    rows = []
    for f in facts_of(run).values():
        line = f"{f.get('label', '')} {f.get('value')} {f.get('period', '')}"
        if grep and not all(w.lower() in line.lower() for w in grep.split()):
            continue
        rows.append({"id": f["id"], "label": f.get("label"), "period": f.get("period"),
                     "en": render(f"{{{{{f['id']}}}}}", {f["id"]: f}, "en"),
                     "ko": render(f"{{{{{f['id']}}}}}", {f["id"]: f}, "ko"),
                     "spoken_en": render(f"{{{{{f['id']}:spoken}}}}", {f["id"]: f}, "en")})
    return {"count": len(rows), "facts": rows[:limit]}


def _syllables(s: str) -> int:
    return len(re.findall(r"[가-힣]", s))


def _words(s: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’.-]*", s))


def check(run: Path) -> dict:
    from ..checks import rules
    from ..validate import check as schema_check
    blocking, advisory, stats = [], [], {}
    sb = read_json(run / "storyboard.json")
    if not sb:
        return {"blocking": ["storyboard.json is missing"], "advisory": [], "stats": {}}
    blocking += schema_check(sb, "video/storyboard", "storyboard.json")
    facts = facts_of(run)
    slides = {s["id"]: s for s in sb.get("slides", [])}
    beats = sb.get("beats", [])
    parts = [p["id"] for p in sb.get("parts", [])]

    # parts in order, all present
    order = [p for p in PART_ORDER if p in parts]
    if parts != order:
        blocking.append(f"parts out of order: {parts}; the order is {PART_ORDER}")
    for need in ("open", "answer", "p1", "p2", "limits", "recap", "end"):
        if need not in parts:
            blocking.append(f"part {need} is missing")
    # slides and beats agree
    for b in beats:
        if b["slide"] not in slides:
            blocking.append(f"{b['id']}: slide {b['slide']} is not in the storyboard")
        elif slides[b["slide"]]["part"] != b["part"]:
            blocking.append(f"{b['id']}: in part {b['part']} but its slide {b['slide']} is in {slides[b['slide']]['part']}")
        for fid in b.get("facts", []):
            if fid not in facts:
                blocking.append(f"{b['id']}: unknown fact {fid}")
    # chapters: hook, example, point, evidence, wrap (guides/video.md § Chapters)
    for part in [x["id"] for x in sb.get("parts", []) if x.get("kind") == "part"]:
        roles = [b.get("role") for b in beats if b["part"] == part]
        if roles and "example" not in roles:
            blocking.append(f"chapter {part}: no example beat (role example): tell one concrete case")
        if roles and roles[-1] != "wrap":
            blocking.append(f"chapter {part}: its last beat must be the wrap-up (role wrap)")
    if not 24 <= len(beats) <= 32:
        advisory.append(f"{len(beats)} beats: aim for 24–32 longer beats (each is one voice request; Gemini allows 100 a day)")
    unused = set(slides) - {b["slide"] for b in beats}
    if unused:
        blocking.append(f"slides no beat shows: {sorted(unused)}")
    charts = {s.get("chart") for s in slides.values() if s["template"] == "figure"}
    if len(charts) > 4:
        blocking.append(f"{len(charts)} charts; at most four")
    for c in charts - {None}:
        if not (run / "source" / "charts" / f"{c}.json").is_file():
            blocking.append(f"chart {c} is not one of the article's charts")
    for s in slides.values():
        if s["template"] == "figure" and not s.get("chart"):
            blocking.append(f"{s['id']}: a figure slide needs chart")
        if s["template"] in ("number", "compare") and not s.get("facts"):
            blocking.append(f"{s['id']}: a {s['template']} slide needs facts")
        for fid in s.get("facts", []):
            if fid not in facts:
                blocking.append(f"{s['id']}: unknown fact {fid}")

    allow = [re.compile(p) for p in rules()["number_allow"]]
    budget = cfg("speech").get("budget") or {}
    for lang in ("en", "ko"):
        sc = read_json(run / "script" / f"{lang}.json")
        if not sc:
            blocking.append(f"script/{lang}.json is missing")
            continue
        blocking += schema_check(sc, "video/script", f"script/{lang}.json")
        sbeats = sc.get("beats", [])
        if [b["beat"] for b in sbeats] != [b["id"] for b in beats]:
            blocking.append(f"script/{lang}.json: beats differ from the storyboard's (same ids, same order)")
        by_id = {b["beat"]: b for b in sbeats}

        def texts():
            for sid, fields in (sc.get("slides") or {}).items():
                for k, v in fields.items():
                    for t in (v if isinstance(v, list) else [v]):
                        yield f"slide {sid}.{k}", t
            for b in sbeats:
                yield f"beat {b['beat']}", b["spoken"]
            for k in ("title", "summary", "thumbnail"):
                if (sc.get("meta") or {}).get(k):
                    yield f"meta.{k}", sc["meta"][k]

        for where, t in texts():
            for m in VTOKEN.finditer(t):
                if m.group(1) not in facts:
                    blocking.append(f"{lang} {where}: unknown fact {m.group(0)}")
            bare = VTOKEN.sub("", t)
            for rx in allow:
                bare = rx.sub("", bare)
            if re.search(r"\d", bare):
                blocking.append(f"{lang} {where}: a typed number; use a fact token: “{t[:70]}”")
            if where.startswith("slide") and re.search(r":spoken", t):
                blocking.append(f"{lang} {where}: slides show the written form ({{{{F1}}}}), not :spoken")
        # slides: every storyboard slide has its fields
        for sid, s in slides.items():
            fields = (sc.get("slides") or {}).get(sid)
            if fields is None:
                blocking.append(f"script/{lang}.json: no wording for slide {sid}")
                continue
            for need in TEMPLATE_FIELDS.get(s["template"], []):
                if not fields.get(need):
                    blocking.append(f"{lang} slide {sid} ({s['template']}): needs {need}")
            for k, v in fields.items():
                for t in (v if isinstance(v, list) else [v]):
                    try:
                        t = render(t, facts, lang)
                    except KeyError:
                        pass                      # reported above as an unknown fact
                    n, cap = ((_words(t), 25 if s["template"] in LONG_TEXT else 12) if lang == "en"
                              else (len(t.replace(" ", "")), 60 if s["template"] in LONG_TEXT else 30))
                    if k == "items":
                        cap = 10 if lang == "en" else 24
                    if n > cap:
                        (blocking if n > cap * 1.5 else advisory).append(
                            f"{lang} slide {sid}.{k}: {n} {'words' if lang == 'en' else 'characters'} (≤ {cap})")
        # cues
        for b in sbeats:
            sl = slides.get(next((x["slide"] for x in beats if x["id"] == b["beat"]), ""), {})
            for c in b.get("cues", []):
                if c["at"] not in b["spoken"]:
                    blocking.append(f"{lang} {b['beat']}: cue text “{c['at']}” is not in what the narrator says")
                if c["step"] > sl.get("steps", 1):
                    blocking.append(f"{lang} {b['beat']}: cue step {c['step']} but slide {sl.get('id')} has {sl.get('steps', 1)} steps")
        # what is said
        try:
            said = {b["beat"]: render(b["spoken"], facts, lang) for b in sbeats}
        except KeyError as e:
            blocking.append(f"{lang}: {e}")
            continue
        all_text = " ".join(said.values())
        # numbers spoken: few, and only the ones to remember (guides/video.md § Numbers)
        spoken_n = {b["beat"]: len([m for m in VTOKEN.finditer(b["spoken"]) if m.group(2)]) for b in sbeats}
        total_n = sum(spoken_n.values())
        stats[lang] = {"spoken_numbers": total_n}
        if total_n > 12:
            blocking.append(f"{lang}: {total_n} numbers spoken; at most 12 (say sizes in words, leave the rest on slides)")
        for bid, n in spoken_n.items():
            if n >= 3:
                blocking.append(f"{lang} {bid}: {n} numbers in one beat; at most one")
            elif n == 2:
                advisory.append(f"{lang} {bid}: two numbers in one beat; one is easier to hear")
        day = (r"\b\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|December)\b"
               if lang == "en" else r"\d{1,2}월 \d{1,2}일")
        days = [bid for bid, t in ((b["beat"], b["spoken"]) for b in sbeats) if re.search(day, t)]
        if days:
            advisory.append(f"{lang}: day-level dates spoken in {days}; name the episode by its year and leave the day to the slide")
        for part in {b["part"] for b in beats}:
            n = sum(spoken_n.get(b["id"], 0) for b in beats if b["part"] == part)
            if n > 3:
                advisory.append(f"{lang} {part}: {n} numbers in one chapter; three at most")
        for pat in POINTING[lang]:
            for bid, t in said.items():
                if re.search(pat, t, re.I if lang == "en" else 0):
                    blocking.append(f"{lang} {bid}: points at the screen (/{pat}/): “{t[:70]}”")
        for pat in BANNED[lang]:
            for bid, t in said.items():
                if re.search(pat, t, (re.I | re.M) if lang == "en" else re.M):
                    blocking.append(f"{lang} {bid}: banned in narration (/{pat}/): “{t[:70]}”")
        end_text = " ".join(said[b["id"]] for b in beats if b["part"] == "end" and b["id"] in said)
        need_end = {"en": ["investment advice", "synthetic"], "ko": ["투자", "합성"]}[lang]
        for w in need_end:
            if w not in end_text:
                blocking.append(f"{lang}: the end part must say the disclaimer and the synthetic voice (missing “{w}”)")
        # length: the ten minutes
        size = _words(all_text) if lang == "en" else _syllables(all_text)
        lo, hi = (budget.get("total") or {}).get(lang, [0, 10 ** 6])
        pz = cfg("speech").get("pause") or {}
        breaks = sum(1 for a, b in zip(beats, beats[1:]) if a["part"] != b["part"])
        pause_s = (len(said) - 1 - breaks) * pz.get("beat", 0.4) + breaks * pz.get("part", 1.0)
        stats[lang] = {**stats.get(lang, {}), "beats": len(said), ("words" if lang == "en" else "syllables"): size,
                       "minutes_est": round(size / (cfg("speech").get("rate") or {}).get(lang, 150) + pause_s / 60, 1)}
        if size < lo * 0.9 or size > hi * 1.1:
            blocking.append(f"{lang}: {size} {'words' if lang == 'en' else 'syllables'}, outside {lo}–{hi} by more than 10%")
        elif not lo <= size <= hi:
            advisory.append(f"{lang}: {size} {'words' if lang == 'en' else 'syllables'}, outside {lo}–{hi}")
        per_part = {}
        for b in beats:
            if b["id"] in said:
                t = said[b["id"]]
                per_part[b["part"]] = per_part.get(b["part"], 0) + (_words(t) if lang == "en" else _syllables(t))
        stats[lang]["parts"] = per_part
        for p, n in per_part.items():
            key = "part" if p.startswith("p") else p
            want = (budget.get(key) or {}).get(lang)
            if want and not 0.6 * want <= n <= 1.4 * want:
                advisory.append(f"{lang} part {p}: {n} against a budget of about {want}")
        # sentences
        sents = [s for t in said.values() for s in SENT.split(t.strip()) if s]
        if lang == "en":
            lens = [_words(s) for s in sents]
            avg = sum(lens) / max(1, len(lens))
            stats[lang]["avg_sentence_words"] = round(avg, 1)
            if avg > 16:
                advisory.append(f"en: average sentence {avg:.1f} words (aim for about 14)")
            advisory += [f"en: {n}-word sentence: “{s[:70]}…”" for s, n in zip(sents, lens) if n > 22][:8]
        else:
            lens = [len(s) for s in sents]
            avg = sum(lens) / max(1, len(lens))
            stats[lang]["avg_sentence_chars"] = round(avg, 1)
            if avg > 33:
                advisory.append(f"ko: average sentence {avg:.0f} characters (aim for about 30)")
            advisory += [f"ko: {n}-character sentence: “{s[:50]}…”" for s, n in zip(sents, lens) if n > 45][:8]
            for s in sents:
                if re.search(r"(요|죠)[.!]?$", s.strip()) and not s.strip().endswith("까요?"):
                    blocking.append(f"ko: 해요체 mixed with 하십시오체: “{s[:50]}”")
            for w, native in SINO_PAIRS.items():
                n = len(re.findall(w + r"(했|됐|하|되)", all_text))
                if n:
                    advisory.append(f"ko: {n}× '{w}' as a verb; by ear, '{native}' is clearer")
            for pat, fix in rules().get("ko_translationese", {}).items():
                n = len(re.findall(pat, all_text))
                if n:
                    advisory.append(f"ko: {n}× /{pat}/ ({fix})")
    # every finding of the article is explained somewhere
    n_find = len((read_json(run / "source" / "en.json", {}) or {}).get("findings", []))
    covered = {p.get("finding") for p in sb.get("parts", []) if p.get("finding")}
    missing = [i for i in range(1, n_find + 1) if i not in covered]
    if missing:
        advisory.append(f"findings no part explains: {missing} (fine if the recap carries them)")
    return {"blocking": blocking[:60], "advisory": advisory[:60], "stats": stats}

