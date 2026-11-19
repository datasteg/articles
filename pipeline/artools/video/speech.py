"""Numbers for the video: fact tokens rounded for the ear, written for the slide and captions, spoken for the voice.

`{{F4}}` renders the written form and `{{F4:spoken}}` the words the narrator reads; both use the same rounding
(config/video/speech.yaml → round), so what is heard is what is shown (guides/video.md § Numbers)."""
from __future__ import annotations

import re

from ..content import MINUS, MONTHS_EN, MON_EN, fmt_number, render_fact
from . import cfg

VTOKEN = re.compile(r"\{\{(F\d+)(:spoken)?(?:\|([a-z,]+))?\}\}")
CURRENCY = {"USD": ("dollars", "달러"), "EUR": ("euros", "유로"), "KRW": ("won", "원"), "JPY": ("yen", "엔"),
            "GBP": ("pounds", "파운드"), "CNY": ("yuan", "위안")}
SCALE = {"tn": 1e12, "bn": 1e9, "mn": 1e6, "m": 1e6}
SCALE_EN = {"tn": "trillion", "bn": "billion", "mn": "million", "m": "million"}
MONEY_UNIT = re.compile(r"^(USD|EUR|KRW|JPY|GBP|CNY) (tn|bn|mn|m)$")
ORDINAL_Q = {"1": "first", "2": "second", "3": "third", "4": "fourth"}
DATE_UNITS = ("month", "date", "quarter", "year")


def ear(f: dict) -> dict:
    """The fact with its decimals lowered to the ear's rounding (never raised)."""
    v = f.get("value")
    if not isinstance(v, (int, float)) or f.get("unit") in DATE_UNITS:
        return f
    rnd = cfg("speech").get("round") or {}
    unit = (f.get("unit") or "").strip()
    cap = int(rnd.get(unit, rnd.get("default", 1)))
    disp = dict(f.get("display") or {})
    dec = int(disp.get("decimals", 0 if abs(v) >= 100 else 1))
    disp["decimals"] = min(dec, cap)
    return {**f, "display": disp}


def ko_amount(x: float) -> str:
    """A raw amount in 조/억/만 groups, at most two groups: 1.2e12 → '1조 2,000억', 4.406e11 → '4,406억'."""
    sign, x = (MINUS if x < 0 else ""), abs(x)
    groups = [(1e12, "조"), (1e8, "억"), (1e4, "만"), (1.0, "")]
    for i, (size, name) in enumerate(groups[:-1]):
        if x >= size:
            hi = int(x // size)
            nsize, nname = groups[i + 1]
            lo = int(round((x - hi * size) / nsize))
            if lo * nsize >= size:          # rounding carried into the larger group
                hi, lo = hi + 1, 0
            return sign + f"{hi:,}{name}" + (f" {lo:,}{nname}" if lo else "")
    return sign + f"{round(x):,}"


def _money(f: dict, lang: str) -> str | None:
    m = MONEY_UNIT.match((f.get("unit") or "").strip())
    if not m or not isinstance(f.get("value"), (int, float)):
        return None
    cur, scale = m.groups()
    if lang == "ko":
        return f"{ko_amount(f['value'] * SCALE[scale])} {CURRENCY[cur][1]}"
    return None                                  # English keeps the article's "USD 440.6bn"


def written(f: dict, lang: str, opts: set[str] | None = None) -> str:
    """The slide and caption form."""
    f = ear(f)
    money = _money(f, lang)
    if money and not (opts or set()) & {"signed"}:
        return money
    return render_fact(f, lang, opts)


def spoken(f: dict, lang: str, opts: set[str] | None = None) -> str:
    """The narrator's form: units as words, signs as words, no thousands separators."""
    f = ear(f)
    opts = opts or set()
    unit = (f.get("unit") or "").strip()
    v = f.get("value")
    if unit in DATE_UNITS or isinstance(v, str):
        s = render_fact(f, lang, opts)
        if lang == "en":
            q = re.fullmatch(r"Q([1-4]) (\d{4})", s)
            if q:
                return f"the {ORDINAL_Q[q.group(1)]} quarter of {q.group(2)}"
            s = re.sub(r"\b(" + "|".join(MON_EN) + r")\b", lambda m: MONTHS_EN[MON_EN.index(m.group(1))], s)
        return s
    money = MONEY_UNIT.match(unit)
    if money:
        cur, scale = money.groups()
        if lang == "ko":
            text = ko_amount(f["value"] * SCALE[scale]) + " " + CURRENCY[cur][1]
        else:
            dec = int((f.get("display") or {}).get("decimals", 1))
            text = f"{fmt_number(abs(v) if 'abs' in opts else v, dec)} {SCALE_EN[scale]} {CURRENCY[cur][0]}"
        return _say_signs(text.replace(",", ""), lang, "signed" in opts and v > 0)
    w = render_fact(f, lang, opts)
    if lang == "en":
        w = re.sub(r"(?<=\d)bp\b", " basis points", w)
        w = re.sub(r"(?<=\d) pp\b", " percentage points", w)
        w = re.sub(r"(?<=\d)%", " percent", w)
        w = re.sub(r"\bUSD ([\d.,]+) per barrel", r"\1 dollars a barrel", w)
    else:
        w = re.sub(r"(?<=\d)bp", "베이시스포인트", w)
        w = re.sub(r"(?<=\d)%p", "퍼센트포인트", w)
        w = re.sub(r"(?<=\d)%", "퍼센트", w)
    w = re.sub(r"(?<=\d),(?=\d{3})", "", w)
    return _say_signs(w, lang, False)


def _say_signs(s: str, lang: str, plus: bool) -> str:
    minus_word, plus_word = ("minus ", "plus ") if lang == "en" else ("마이너스 ", "플러스 ")
    s = s.replace(MINUS, minus_word)
    if s.startswith("+"):
        s = plus_word + s[1:]
    elif plus:
        s = plus_word + s
    return s


def render(text: str, facts: dict, lang: str) -> str:
    """Render every video token in a script string: {{F4}} written, {{F4:spoken}} spoken."""
    def sub(m):
        f = facts.get(m.group(1))
        if not f:
            raise KeyError(f"unknown fact token {m.group(0)}")
        opts = set((m.group(3) or "").split(",")) - {""}
        return spoken(f, lang, opts) if m.group(2) else written(f, lang, opts)
    return VTOKEN.sub(sub, text)


def lexicon(lang: str) -> dict:
    return cfg(f"lexicon.{lang}") or {}


def apply_lexicon(text: str, lang: str, lex: dict | None = None) -> str:
    """How the narrator says terms it may misread (config/video/lexicon.<lang>.yaml); longest entries first."""
    lex = lexicon(lang) if lex is None else lex
    for k in sorted(lex, key=len, reverse=True):
        say = str(lex[k])
        if re.search(r"[A-Za-z]", k):
            pat = re.compile(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])")
        else:
            pat = re.compile(re.escape(k))
        text = pat.sub(lambda m: (" " if lang == "en" and m.start() and text[m.start() - 1].isdigit() else "") + say, text)
    return text
