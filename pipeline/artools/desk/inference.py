"""The inference test (rule R4): what a reader takes away from what they see first.

A note can be true sentence by sentence and still mislead: most readers see only its title, dek, key numbers and
chart headlines, and they draw a conclusion from those alone. The `inference` role (Sonnet, effort low) is that
reader. It gets only those strings and says what it concludes, with direction and comparison. Code then matches each
conclusion to the claims the strings cite (claims.match); what code cannot tie to a claim goes to the same role's
`match` task with the claim ledger. A conclusion the ledger contradicts is a blocking issue of kind `framing`, owned
by the writer. It replaces the reader role (R5).

The same test reads the Korean edition's title, dek, key-number labels and chart headlines, and answers in English:
no model writes Korean here.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..paths import read_json, write_json
from ..runlib import now as runlib_now
from . import claims as claims_mod, roles


def _packet(surf: list[dict], lang: str) -> str:
    """The list page (title, dek, key numbers) is read together; each chart (its headline with its title and subtitle)
    is read alone, as a reader who scrolls to it or sees it shared does (20261118: the dek's "same share" did not
    reach a reader of the chart that said "three of six above the group median")."""
    page = [x for x in surf if not x["key"].startswith("figure:")]
    figs: dict[str, list[dict]] = {}
    for x in surf:
        if x["key"].startswith("figure:"):
            figs.setdefault(x["key"].split(".")[0], []).append(x)
    out = ["## Task: read\n", "The strings are the Korean edition's; answer in English.\n" if lang == "ko" else ""]
    if page:
        out.append("## On the list page (read together)\n" + "\n".join(f"- `{x['key']}`: {x['text']}" for x in page))
    for k, xs in figs.items():
        out.append(f"## A chart, seen alone ({k})\n" + "\n".join(f"- `{x['key']}`: {x['text']}" for x in xs))
    return "\n\n".join(o for o in out if o)


def _match_packet(items: list[dict], claims: list[dict], fmap: dict) -> str:
    return ("## Task: match\n\n## The conclusions\n" + "\n".join(f"{n}. {x['says']} (from {', '.join(x.get('from') or [])})"
                                                          for n, x in enumerate(items, 1))
            + "\n\n## The note's claims\n" + claims_mod.sheet(claims, fmap, ids=False))


def run_test(run: Path, draft: dict, charts: dict, fmap: dict, claims: list[dict], cmap: dict, lang: str = "en",
             surf: list[dict] | None = None, label: str = "inference") -> dict:
    """One inference test on a draft (or on given surface strings). Returns {lang, surface, conclusions (each with
    its verdict), blocking, advisory}."""
    surf = surf if surf is not None else claims_mod.surface(draft, charts, fmap, lang)
    # two reads: the list page, then the charts, each chart on its own (a reader of one call merged a chart's headline
    # into the dek's comparison, which a reader who sees only the chart never has)
    page = [x for x in surf if not x["key"].startswith("figure:")]
    figs = [x for x in surf if x["key"].startswith("figure:")]
    concl = []
    for part in [p for p in (page, figs) if p]:
        got = roles.call(run, "inference", _packet(part, lang), label=label)["data"] or {}
        concl += [x for x in got.get("conclusions") or [] if isinstance(x, dict) and x.get("says")][:10]
    m = claims_mod.match(concl, claims, cmap)
    todo = [x for x in m if x["verdict"] == "unresolved"]
    if todo and claims:
        try:
            ans = roles.call(run, "inference", _match_packet(todo, claims, fmap), label=label)["data"] or {}
            by = {int(a.get("n")): a for a in ans.get("matches") or [] if str(a.get("n") or "").isdigit()}
            for n, x in enumerate(todo, 1):
                a = by.get(n) or {}
                if a.get("verdict") in ("supported", "contradicted", "unsupported"):
                    x.update(verdict=a["verdict"], why=a.get("why") or x["why"], decided="model")
                    if a.get("claim"):
                        x["claims"] = sorted(set(x["claims"]) | {str(a["claim"])})
        except roles.RoleError as e:
            for x in todo:
                x["why"] = (x.get("why") or "") + f" (the match call failed: {e})"
    blocking, advisory = [], []
    for x in m:
        where = ", ".join(x.get("from") or []) or "surface"
        if x["verdict"] == "contradicted":
            blocking.append({"owner": "inference", "kind": "framing", "where": where, "quote": x["says"],
                             "issue": f"a reader who sees only the title, dek, key numbers and chart headlines"
                                      f"{' (Korean edition)' if lang == 'ko' else ''} concludes “{x['says']}”; {x['why']}",
                             "fix": "reword the strings it comes from so they state the claim they cite, with its comparison; "
                                    "a result that follows from how a measure is built must say so",
                             "claims": x.get("claims")})
        elif x["verdict"] in ("unsupported", "unresolved"):
            advisory.append({"owner": "inference", "where": where,
                             "issue": f"a skimming reader concludes “{x['says']}”, which no claim states ({x.get('why') or 'unsupported'})"})
    return {"lang": lang, "surface": surf, "conclusions": m, "blocking": blocking, "advisory": advisory, "at": runlib_now()}


def record(run: Path, res: dict, stage: str) -> None:
    """Keep the latest test per language, and every test in order, in desk/inference.json."""
    d = read_json(run / "desk" / "inference.json", {}) or {}
    d[res["lang"]] = {**res, "stage": stage}
    d.setdefault("history", []).append({"stage": stage, "lang": res["lang"], "at": res["at"],
                                        "conclusions": [{k: x.get(k) for k in ("says", "verdict", "claims")} for x in res["conclusions"]]})
    write_json(run / "desk" / "inference.json", d)


def korean_surface(run: Path, fmap: dict) -> list[dict]:
    """The Korean edition's surface strings (draft/ko.json and the charts' ko), keyed as the English ones."""
    ko = read_json(run / "draft" / "ko.json", None)
    if not ko:
        return []
    charts = {p.stem: read_json(p) for p in sorted((run / "charts").glob("*.json"))}
    return claims_mod.surface(ko, charts, fmap, "ko")


def card(run: Path) -> dict | None:
    """What the admin page shows under "What a reader takes away"."""
    d = read_json(run / "desk" / "inference.json", None)
    if not d:
        return None
    out = {}
    for lang in ("en", "ko"):
        r = d.get(lang)
        if r:
            out[lang] = {"stage": r.get("stage"), "at": r.get("at"),
                         "conclusions": [{k: x.get(k) for k in ("says", "from", "relation", "verdict", "why", "claims")} for x in r["conclusions"]]}
    return out or None


def dumps(res: dict) -> str:
    return json.dumps(res, ensure_ascii=False, indent=1)
