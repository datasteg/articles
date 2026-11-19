"""Offline tests of the video tools: no network, no keys."""
from artools.video.speech import apply_lexicon, ko_amount, render


def f(value, unit, **display):
    return {"id": "F1", "value": value, "unit": unit, "display": display}


FACTS = {"F1": f(96.7, "bp", decimals=0), "F2": f(4.44, "%", decimals=2), "F3": f(0.22, "pp", decimals=2),
         "F4": f("2012-07", "month"), "F5": f(-0.34, "%", decimals=2), "F6": f(440.6, "USD bn", decimals=1),
         "F7": f("2026-Q2", "quarter"), "F8": f(24.4, "bp", decimals=0), "F9": f("2026-10-16", "date"),
         "F10": f(1.2, "EUR tn", decimals=1)}


def test_written_and_spoken_share_the_ears_rounding():
    assert render("{{F2}}", FACTS, "en") == "4.4%"
    assert render("{{F2:spoken}}", FACTS, "en") == "4.4 percent"
    assert render("{{F2}}", FACTS, "ko") == "4.4%"
    assert render("{{F2:spoken}}", FACTS, "ko") == "4.4퍼센트"
    assert render("{{F3:spoken}}", FACTS, "ko") == "0.2퍼센트포인트"


def test_spoken_units_dates_and_signs():
    assert render("{{F1:spoken}}", FACTS, "en") == "97 basis points"
    assert render("{{F1:spoken}}", FACTS, "ko") == "97베이시스포인트"
    assert render("{{F5:spoken}}", FACTS, "en") == "minus 0.3 percent"
    assert render("{{F8:spoken|signed}}", FACTS, "ko") == "플러스 24베이시스포인트"
    assert render("{{F7:spoken}}", FACTS, "en") == "the second quarter of 2026"
    assert render("{{F9:spoken}}", FACTS, "en") == "16 October 2026"
    assert render("{{F4:spoken}}", FACTS, "ko") == "2012년 7월"


def test_money_in_korean_groups_by_jo_and_eok():
    assert ko_amount(4.406e11) == "4,406억"
    assert ko_amount(1.2e12) == "1조 2,000억"
    assert ko_amount(1.99996e12) == "2조"
    assert render("{{F6}}", FACTS, "ko") == "4,406억 달러"
    assert render("{{F10:spoken}}", FACTS, "ko") == "1조 2000억 유로"
    assert render("{{F6:spoken}}", FACTS, "en") == "440.6 billion dollars"


def test_lexicon_whole_words_longest_first():
    lex = {"ECB": "이시비", "bp": "베이시스포인트", "%p": "퍼센트포인트", "%": "퍼센트"}
    assert apply_lexicon("ECB는 0.2%p, 4.4% 올렸다", "ko", lex) == "이시비는 0.2퍼센트포인트, 4.4퍼센트 올렸다"
    assert apply_lexicon("ECBX stays", "en", {"ECB": "E C B"}) == "ECBX stays"
    assert apply_lexicon("97bp wide", "en", {"bp": "basis points"}) == "97 basis points wide"


def _fixture(tmp_path, ko_end="합성 음성으로 읽었습니다. 투자 권유가 아닙니다."):
    import json
    run = tmp_path / "run"
    (run / "source" / "charts").mkdir(parents=True)
    (run / "script").mkdir()
    (run / "source" / "facts.json").write_text(json.dumps({"facts": [{**f, "id": k} for k, f in FACTS.items()]}))
    (run / "source" / "en.json").write_text(json.dumps({"findings": ["a", "b"]}))
    (run / "source" / "charts" / "spread-history.json").write_text("{}")
    parts = ["open", "answer", "p1", "p2", "limits", "recap", "end"]
    kinds = {"open": "open", "answer": "answer", "p1": "part", "p2": "part", "limits": "limits", "recap": "recap", "end": "end"}
    slides, beats = [], []
    for i in range(14):
        part = parts[min(i // 2, 6)]
        t = "figure" if i == 4 else "end" if part == "end" else "answer"
        slides.append({"id": f"s{i + 1:02d}", "template": t, "part": part, **({"chart": "spread-history"} if t == "figure" else {})})
        for j in range(2):
            role = ("example" if j == 0 else "wrap") if part.startswith("p") and i % 2 == 1 else ("hook" if part.startswith("p") else part)
            beats.append({"id": f"b{len(beats) + 1:02d}", "part": part, "slide": f"s{i + 1:02d}", "role": role, "says": "x"})
    sb = {"slug": "x", "parts": [{"id": p, "kind": kinds[p]} for p in parts], "slides": slides, "beats": beats}
    (run / "storyboard.json").write_text(json.dumps(sb))
    for lang, line, end in (("en", "France paid {{F1:spoken}} more than Germany in {{F4:spoken}}.",
                             "This is not investment advice. The voice is synthetic."), ("ko", "프랑스는 {{F1:spoken}} 더 냈습니다.", ko_end)):
        sl = {s["id"]: ({"headline": "{{F1}}"} if s["template"] == "figure" else
                        {"items": ["a"], "text": "t", "label": "l"} if s["template"] == "end" else {"text": "t"}) for s in slides}
        bs = [{"beat": b["id"], "spoken": end if b["part"] == "end" else line} for b in beats]
        (run / "script" / f"{lang}.json").write_text(json.dumps({"lang": lang, "meta": {"title": "t", "summary": "s"},
                                                                  "slides": sl, "beats": bs}, ensure_ascii=False))
    return run


def test_video_script_check_runs_and_flags(tmp_path):
    from artools.video.script import check
    res = check(_fixture(tmp_path))
    assert not any("unknown fact" in b or "typed number" in b for b in res["blocking"]), res["blocking"]
    assert any("outside" in b for b in res["blocking"])          # far too short for ten minutes
    res = check(_fixture(tmp_path / "2", ko_end="투자 권유가 아니에요."))
    assert any("합성" in b for b in res["blocking"]) and any("해요체" in b for b in res["blocking"])


def test_video_script_check_counts_spoken_numbers(tmp_path):
    from artools.video.script import check
    res = check(_fixture(tmp_path))
    assert any("numbers spoken; at most 12" in b for b in res["blocking"])   # the fixture speaks two in each of 28 beats
    assert not any("no example beat" in b or "wrap-up" in b for b in res["blocking"]), res["blocking"]


def test_podcast_pieces_cut_at_the_longest_pause_and_keep_no_short_tail():
    from artools.video.podcast import _pieces
    pauses = [(290.0, 290.3), (305.0, 306.0), (598.0, 599.0)]
    assert _pieces(pauses, 640.0, 300) == [(0.0, 305.5), (305.5, 640.0)]   # 34 s left over rides with the last piece
    assert _pieces([], 200.0, 300) == [(0.0, 200.0)]


def test_podcast_transcript_sentences_and_voices():
    from artools.video.podcast import _bad, _sentences, _voices
    assert _sentences("Is that right? Yes. It is.", "en") == ["Is that right?", "Yes.", "It is."]
    long = "one two three four five six seven eight nine, ten eleven twelve thirteen fourteen fifteen sixteen seventeen."
    assert len(_sentences(long, "en")) == 2
    pieces = [{"segments": [[0, 1, "0", "a"], [1, 2, "1", "b"]], "pitch": {"0": 210.0, "1": 110.0}},
              {"segments": [[0, 1, "0", "c"], [1, 2, "1", "d"]], "pitch": {"0": 105.0, "1": 220.0}},
              {"segments": [[0, 1, "1", "e"], [1, 2, "0", "f"]], "pitch": {"0": 150.0, "1": 160.0}}]
    v = _voices(pieces)
    assert (v[(0, "1")], v[(1, "0")]) == ("A", "A")      # the lower voice, whatever the model called it
    assert (v[(2, "1")], v[(2, "0")]) == ("A", "B")      # too close to tell: the order heard
    loop = {"parsed_ok": True, "tokens": 900, "cap": 900, "start": 0, "end": 60, "segments": []}
    assert _bad(loop, "en") == "token cap"
    ok = {"parsed_ok": True, "tokens": 500, "cap": 976, "start": 0, "end": 60, "segments": [[0, 60, "0", "word " * 150]]}
    assert _bad(ok, "en") == ""


def test_podcast_part_spans_run_to_the_next_part():
    from artools.video.podcast import _spans
    part_of = {"q": "open", "c1": "p1", "t1": "p1", "c2": "p2", "s9": "recap"}
    cues = [{"t": 0, "slide": "q"}, {"t": 100, "slide": "c1"}, {"t": 150, "slide": "t1"}, {"t": 240, "slide": "c2"},
            {"t": 300, "slide": "t1"}, {"t": 700, "slide": "s9"}]
    assert _spans(cues, part_of, ["p1", "p2", "p3"], 800.0) == {"p1": (100, 240), "p2": (240, 700)}


def test_podcast_translated_captions_keep_times_and_numbers(tmp_path):
    import json
    from artools.video.podcast import _translated
    run = tmp_path / "run"
    (run / "asr").mkdir(parents=True)
    segs = [{"start": 0.0, "end": 3.0, "speaker": "A", "text": "실효 관세율은 11.3퍼센트였습니다."},
            {"start": 3.0, "end": 4.0, "speaker": "B", "text": "3배요?"},
            {"start": 4.0, "end": 5.0, "speaker": "A", "text": "네."}]
    (run / "asr" / "ko.json").write_text(json.dumps({"segments": segs}, ensure_ascii=False))
    assert "missing" in _translated(run, "ko")[1][0]
    tr = [{"i": 0, "text": "The effective tariff rate was 11.8 percent."}, {"i": 1, "text": "Three times?"}]
    (run / "asr" / "ko.en.json").write_text(json.dumps({"from": "ko", "to": "en", "segments": tr}))
    out, probs = _translated(run, "ko")
    assert [s["start"] for s in out] == [0.0, 3.0] and out[1]["text"] == "Three times?"
    assert any("segment 0" in p and "11.3" in p for p in probs)          # a number changed in translation
    assert any("segment 2" in p and "no translation" in p for p in probs)
    assert not any("segment 1" in p for p in probs)                        # 3 → "three" is fine


def test_podcast_two_takes_at_most(tmp_path):
    import json
    from artools.video.podcast import takes_left
    run = tmp_path / "run"
    (run / "podcast").mkdir(parents=True)
    assert takes_left(run, "ko") == 2
    (run / "podcast" / "ko.json").write_text(json.dumps({"takes": [{"file": "ko.m4a"}]}))
    assert takes_left(run, "ko") == 1
    (run / "podcast" / "ko.json").write_text(json.dumps({"takes": [{}, {}]}))
    assert takes_left(run, "ko") == 0
