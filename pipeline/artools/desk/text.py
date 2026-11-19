"""A draft as plain text: what the reviewers read, what the judge scores, what the editor sees in the admin queue.

Three views of the same draft:
- `review`: numbers filled in, each followed by its fact id (`50.0% {F2}`), citation marks kept, figures as data,
  so a reviewer can point at a sentence and at the fact behind it;
- `reader`: the article as a reader meets it: no marks, no ids, figures as their words and a short data table;
- `judged`: the reader's view in the layout the benchmark texts use (title, date line, body, `FIGURE:` lines,
  sources), so the judge reads a desk note and an institution's article in the same shape.
"""
from __future__ import annotations

import re

from ..content import CITE, GLOSS, TOKEN, render_fact


def _fill(text: str, facts: dict, ids: bool, lang: str = "en") -> str:
    def sub(m):
        f = facts.get(m.group(1))
        if not f:
            return m.group(0)
        shown = render_fact(f, lang, set((m.group(2) or "").split(",")) - {""})
        return f"{shown} {{{f['id']}}}" if ids else shown
    return TOKEN.sub(sub, text)


def _plain(text: str, facts: dict, ids: bool = False, cites: bool = False, lang: str = "en") -> str:
    text = _fill(text, facts, ids, lang)
    if not cites:
        text = CITE.sub("", text)
    text = GLOSS.sub(lambda m: m.group(0)[2:-2].split("|")[-1], text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return re.sub(r"\s+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip()


def _tx(v, lang: str = "en") -> str:
    """A chart text or a table cell in one edition (the English when the Korean is not there)."""
    if isinstance(v, dict):
        return v.get(lang) or v.get("en", "")
    return v or ""


def figure_text(ch: dict, rows: int = 14, data: bool = True) -> str:
    """A figure in English (the reviewers and the judge read the English edition)."""
    out = [f"FIGURE: {_tx(ch.get('headline'))}", f"  {_tx(ch.get('title'))}. {_tx(ch.get('subtitle'))}".rstrip()]
    if ch.get("howToRead"):
        out.append(f"  How to read: {_tx(ch['howToRead'])}")
    for n in ch.get("notes") or []:
        out.append(f"  Note: {_tx(n)}")
    t = ch.get("table") or {}
    if data and t.get("rows"):
        cols = t["columns"]
        out.append("  Data (" + ch["form"] + "): " + " | ".join(_tx(c.get("label")) for c in cols))
        for r in t["rows"][:rows]:
            out.append("    " + " | ".join("–" if r.get(c["key"]) is None else
                                           (f"{r[c['key']]:,.2f}".rstrip("0").rstrip(".") if isinstance(r[c["key"]], float) else str(_tx(r[c["key"]])))
                                           for c in cols))
        if len(t["rows"]) > rows:
            out.append(f"    … {len(t['rows']) - rows} more rows")
    att = _tx((ch.get("meta") or {}).get("attribution"))
    if att:
        out.append(f"  Source: {att}. Data to {(ch.get('meta') or {}).get('lastObservation')}.")
    return "\n".join(out)


def article(draft: dict, facts: dict, charts: dict, view: str = "reader", sources: list[str] | None = None,
            date: str | None = None) -> str:
    ids, cites = view == "review", view == "review"
    P = lambda s: _plain(s or "", facts, ids, cites)   # noqa: E731
    out = [P(draft.get("title")), ""]
    if view == "judged" and date:
        out += [date, ""]
    out += [P(draft.get("dek")), ""]
    if draft.get("whyNow"):
        out += [("WHY THIS NOTE: " if view != "judged" else "Why this note: ") + P(draft["whyNow"]), ""]
    if draft.get("keyNumbers"):
        out.append("KEY NUMBERS" if view != "judged" else "Key numbers")
        out += [f"- {P(k.get('value'))}: {P(k.get('label'))}" for k in draft["keyNumbers"]]
        out.append("")
    if draft.get("findings"):
        out.append("FINDINGS" if view != "judged" else "Key takeaways")
        out += [f"- {P(f)}" for f in draft["findings"]]
        out.append("")
    q = draft.get("question") or {}
    if q.get("asked"):
        out += [f"The question: {P(q['asked'])}", f"What we looked at: {P(q.get('lookedAt'))}"]
        if q.get("premiseNote"):
            out.append(f"Note: {P(q['premiseNote'])}")
        out.append("")
    for s in draft.get("sections", []):
        out.append(f"## {P(s.get('heading'))}" + (f"   [section id: {s.get('id')}]" if view == "review" else ""))
        for b in s.get("blocks", []):
            if b.get("type") == "p":
                out.append(P(b.get("text")))
            elif b.get("type") == "list":
                out += [f"- {P(i)}" for i in b.get("items", [])]
            elif b.get("type") == "figure":
                ch = charts.get(b.get("chart"))
                # the judge reads a chart as the benchmark texts carry theirs: its words, not its data; a table figure is its rows
                out.append(figure_text(ch, data=view != "judged" or ch.get("form") == "table") if ch else f"[figure {b.get('chart')} was not built]")
                if view == "review" and ch:
                    out[-1] = out[-1].replace("FIGURE:", f"FIGURE [{ch['id']}]:", 1)
            out.append("")
    ins = draft.get("insight") or {}
    if ins.get("text"):
        out += [f"## {ins.get('label') or 'Our read'}", P(ins["text"]), ""]
    if sources:
        out += ["Sources", *[f"- {s}" for s in sources]]
    return "\n".join(out).strip() + "\n"


def words(draft: dict) -> int:
    """English words a reader reads as prose (findings, paragraphs, lists, insight), tokens counted as one word."""
    from ..content import _body_words
    return _body_words(draft, "en")
