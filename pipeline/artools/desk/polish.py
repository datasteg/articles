"""The polish (19 Nov 2026, the owner's decision): Fable refines the expression of each edition, separately.

The owner read Fable's rewrite of 20261118-desk-r6 as "much nicer and easy to understand" and asked for it in the
data-note pipeline. Two roles, each one `claude -p` call on Fable (config roles polish-en, polish-ko):

- English, after the review loop and before the judge: Fable rewrites the text of the writer's answer (the draft and
  the figures' words) for plain reading. Code then holds the result to everything the note had to pass: the shape of
  the draft, the build (typed numbers, figures), the mechanical checks and claim lints (no new blocking issue), the
  inference test (no framing contradiction) and the verifier (no new error of fact). What fails goes back to Fable once;
  what still fails leaves the note as the reviewers passed it. The judge scores the polished text.
- Korean, inside korean.make after qkr drafted every string and the side-by-side reader checked qkr's drafts against
  the English (it replaces the title tuning and the term rounds): Fable reads the whole note in Korean only and rewrites
  it for the general public (the owner, 19 Nov 2026: "focus only on Korean", the "friend" brief of 20261119-desk-ko3).
  Each answer must keep what qkr's draft of the same string has (numbers, marks, dates, service names, the title and
  label lengths), and a fact editor (role polish-ko-facts) compares it with qkr's draft; a string that fails either keeps
  qkr's version. qkr's draft is kept in the ledger (`ko_qkr`), and every accepted change goes to qkr's feedback endpoint
  as an edit, so qkr learns.

Fable's English counts against the note's budget; its Korean, like the rest of the Korean edition, does not.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from ..paths import read_json, write_json
from ..runlib import now
from . import config, roles

FIG_KEYS = ("headline", "title", "subtitle", "howToRead", "alt")
DRAFT_KEYS = ("kicker", "title", "dek", "whyNow", "keyNumbers", "findings", "question", "sections", "insight", "citations")


def on(lang: str) -> bool:
    return bool((config.load().get("polish") or {}).get(lang, True))


def _record(run: Path, lang: str, rep: dict) -> None:
    d = read_json(run / "desk" / "polish.json", {}) or {}
    d[lang] = {**rep, "at": now()}
    write_json(run / "desk" / "polish.json", d)


# ------------------------------------------------------------------ English

def _en_packet(answer: dict, fact_list: list, claims: list, cmap: dict, only: list | None, problems: list | None, previous: dict | None) -> str:
    from . import claims as claims_mod, facts as facts_mod
    draft = answer["draft"]
    d = {k: draft[k] for k in DRAFT_KEYS if k in draft}
    figs = {f["id"]: {k: f[k] for k in (*FIG_KEYS, "notes") if f.get(k)} for f in answer.get("figures") or [] if isinstance(f, dict) and f.get("id")}
    fmap = {f["id"]: f for f in fact_list}
    p = ("## The draft (rewrite its text)\n```json\n" + json.dumps(d, ensure_ascii=False, indent=1) + "\n```\n\n"
         "## The figures' words (rewrite them; tokens stay tokens)\n```json\n" + json.dumps(figs, ensure_ascii=False, indent=1) + "\n```\n\n"
         "## What each token prints (the fact sheet)\n" + facts_mod.sheet(fact_list)
         + ("\n\n## The claim ledger\n" + claims_mod.sheet(claims, fmap) + "\n\n## Which claim each surface string states\n" + json.dumps(cmap) if claims else ""))
    if only:
        p += ("\n\n## Only these places may change (a correction of a published note)\n" + ", ".join(only)
              + "\nReturn the whole draft; every other string must stay exactly as it is.")
    if problems:
        p += ("\n\n## Your previous answer\n```json\n" + json.dumps(previous, ensure_ascii=False) + "\n```\n\n"
              "## It failed these checks. Fix them and answer again in full\n" + "\n".join(f"- {x}" for x in problems))
    return p


def _merge_en(answer: dict, got: dict) -> tuple[dict, list[str]]:
    """The writer's answer with Fable's text in it, and what Fable broke in the shape."""
    new = copy.deepcopy(answer)
    old, nd = answer["draft"], got.get("draft") if isinstance(got.get("draft"), dict) else {}
    probs = []
    for k in DRAFT_KEYS:
        if k in nd:
            new["draft"][k] = nd[k]
    d = new["draft"]
    if [s.get("id") for s in d.get("sections") or []] != [s.get("id") for s in old.get("sections") or []]:
        probs.append("the sections changed: keep the same section ids in the same order")
    else:
        for a, b in zip(d["sections"], old["sections"]):
            if [x.get("type") for x in a.get("blocks") or []] != [x.get("type") for x in b.get("blocks") or []]:
                probs.append(f"section {a.get('id')}: keep the same blocks (types and order); rewrite their text only")
            for x, y in zip(a.get("blocks") or [], b.get("blocks") or []):
                if y.get("type") == "figure":
                    x.clear()
                    x.update(y)
    if len(d.get("keyNumbers") or []) != len(old.get("keyNumbers") or []) or len(d.get("findings") or []) != len(old.get("findings") or []):
        probs.append("keep the same number of key numbers and findings")
    for i, (k, o) in enumerate(zip(d.get("keyNumbers") or [], old.get("keyNumbers") or [])):
        if not isinstance(k, dict) or k.get("value") != o.get("value"):
            probs.append(f"keyNumbers.{i}.value must stay {o.get('value')}")
        elif isinstance(k, dict):
            k["cite"] = o.get("cite")
    for c in old.get("citations") or {}:
        if c not in (d.get("citations") or {}):
            d.setdefault("citations", {})[c] = old["citations"][c]
    figs = got.get("figures") if isinstance(got.get("figures"), dict) else {}
    for f in new.get("figures") or []:
        g = figs.get(f.get("id")) or {}
        for k in FIG_KEYS:
            if isinstance(g.get(k), str) and g[k].strip() and f.get(k):
                f[k] = g[k].strip()
        if isinstance(g.get("notes"), list) and len(g["notes"]) == len(f.get("notes") or []):
            f["notes"] = [str(x) for x in g["notes"]]
    return new, probs


def _locate(problem: str, draft: dict, charts: dict) -> list[str]:
    """Where a check's problem sits, as dotted draft paths or figure:<id>, or [] when it cannot be told (the length of
    the whole note). The mechanical checks name a path in backticks, "en.<path>", "figure <id>" or a section's id."""
    secs = {s.get("id"): f"sections.{i}" for i, s in enumerate(draft.get("sections") or []) if s.get("id")}

    def norm(p: str) -> str | None:
        p = p.strip().removeprefix("en.")
        if p.startswith("figure:") or p.startswith("figure "):
            cid = re.split(r"[:. ]", p, maxsplit=2)[1] if len(re.split(r"[:. ]", p)) > 1 else ""
            return f"figure:{cid}" if cid in charts else None
        if p in secs:
            return secs[p]
        head = p.split(".")[0]
        return p if head in draft or head in ("title", "dek", "whyNow") else None
    cands = re.findall(r"`([^`]+)`", problem)
    m = re.match(r"[\w -]+: en\.([\w.]+)", problem) or re.match(r"referent: ([\w.:-]+) says", problem)
    if m:
        cands.append(m.group(1))
    m = re.match(r"figure ([\w-]+)", problem)
    if m:
        cands.append(f"figure:{m.group(1)}")
    out = [n for n in (norm(c) for c in cands) if n]
    return sorted(set(out)) if out and len(out) == len(cands) else []


def english(run: Path, answer: dict, brief: dict, tables: dict, fact_list: list, catalog: list, claims: list,
            only: list | None = None) -> tuple[dict, dict, dict, dict]:
    """Fable's English. Returns (answer, built, mech, report): the polished answer built into the run's files, or the
    writer's own answer rebuilt when Fable's could not pass. Since 20 Nov 2026 (the owner) a rewrite that fails is
    taken string by string: the strings the checks name keep the reviewers' text, the rest is Fable's, and the mix is
    checked again; and the title is a headline in words, written last, which need not carry the claim's comparator
    (the verifier reads it for saying more than the note)."""
    from . import claims as claims_mod, facts as facts_mod, inference as inference_mod, review, text
    from . import run as run_mod

    def build(ans):
        b = review.assemble(run, ans, brief, tables, fact_list, catalog)
        m = review.mechanical(run, b["draft"], b["charts"], fact_list, tables, catalog) if b["draft"] else {"blocking": [], "advisory": [], "stats": {}}
        return b, m

    before_built, before_mech = build(answer)
    before = set(before_built["problems"]) | set(before_mech["blocking"])
    rep = {"status": "kept", "attempts": 0, "problems": [], "words_before": before_mech["stats"].get("words")}
    if not on("en"):
        write_json(run / "desk" / "answer.json", answer)
        return answer, before_built, before_mech, {**rep, "status": "off"}
    cmap = claims_mod.load_map(run)
    fmap = {f["id"]: f for f in fact_list}

    def check(new: dict):
        """Every check the note passed, on a candidate: (built, mech, [(problem, paths)])."""
        b, m = build(new)
        found = [(p, _locate(p, b["draft"] or {}, b["charts"])) for p in b["problems"] + m["blocking"]
                 if p not in before and not p.startswith("base-rate: `title`")]      # the title states the finding in words
        if b["draft"] and claims:
            res = inference_mod.run_test(run, b["draft"], b["charts"], fmap, claims, cmap)
            found += [(f"framing: {x['issue']}", [k for k in (run_mod._paths_of({"where": x.get("where")}, b["draft"], b["charts"], fmap)
                                                              or [w.strip() for w in str(x.get("where") or "").split(",")]) if k and k != "surface"])
                      for x in res["blocking"]]
        if b["draft"]:
            v = roles.call(run, "verifier", "## The must-fix list\n[]\n\n## The draft, rewritten for plain reading\nAn editor rewrote the "
                           "expression of the note. Report under `new_errors` only a sentence the fact sheet or the claim ledger now "
                           "contradicts, or a claim the rewrite made stronger, weaker or different. The title is a headline in plain "
                           "words, written last: it need not carry the numbers or the claim's comparator; report it only when it says "
                           "something the note does not support or states the finding more strongly than the note does.\n\n"
                           + text.article(b["draft"], fmap, b["charts"], "review") + "\n\n## Fact sheet\n" + facts_mod.sheet(fact_list)
                           + ("\n\n## Claim ledger\n" + claims_mod.sheet(claims, fmap) if claims else ""))["data"] or {}
            found += [(f"error: {e.get('where')}: {e.get('issue')} (“{e.get('quote')}”)", run_mod._paths_of(e, b["draft"], b["charts"], fmap))
                      for e in v.get("new_errors") or []]
        return b, m, found

    def accept(new, b, m, status):
        rep.update(status=status, problems=[], words_after=m["stats"].get("words"))
        write_json(run / "desk" / "answer.json", new)
        _record(run, "en", rep)
        return new, b, m, rep

    got, probs, last = None, None, None
    # three calls (20 Nov 2026): the owner's short brief leaves the details to the checks, which send them back
    for attempt in (1, 2, 3):
        rep["attempts"] = attempt
        try:
            got = roles.call(run, "polish-en", _en_packet(answer, fact_list, claims, cmap, only, probs, got))["data"] or {}
        except roles.RoleError as e:
            rep["problems"] = [f"the polish call failed: {e}"]
            break
        new, probs = _merge_en(answer, got)
        if only:
            new = run_mod._scoped(new, answer, only)
        if probs:
            continue
        b, m, found = check(new)
        if not found:
            return accept(new, b, m, "polished")
        probs = [p for p, _ in found]
        last = (new, b, found)
        rep["problems"] = probs
        rep.setdefault("history", []).append({"attempt": attempt, "problems": probs[:12]})
    # string by string: the strings the checks named keep the reviewers' text, and the mix is checked again
    bad: set[str] = set()
    for rnd in (1, 2, 3):
        if not last or any(not paths for _, paths in last[2]):
            break                      # a problem no string can be blamed for (the note's length): not taken in part
        new, b, found = last
        bad |= {p.split(".")[0] if p.startswith("figure:") else p for _, paths in found for p in paths}
        changed = run_mod._changed_paths(answer["draft"], new["draft"], before_built["charts"], b["charts"])
        keep = sorted(p for p in changed if not any(p == x or p.startswith(x + ".") or p.startswith(x + ":") for x in bad)
                      and not (p.startswith("figure:") and p.split(".")[0] in bad))
        if not keep:
            break
        part = run_mod._scoped(new, answer, keep)
        b2, m2, found2 = check(part)
        rep.setdefault("history", []).append({"in_part": rnd, "kept_reviewers": sorted(bad), "problems": [p for p, _ in found2][:12]})
        if not found2:
            rep["kept_reviewers"] = sorted(bad)
            return accept(part, b2, m2, "polished in part")
        last = (part, b2, found2)
        rep["problems"] = [p for p, _ in found2]
    # Fable's text could not pass: the note stays as the reviewers passed it
    b, m = build(answer)
    write_json(run / "desk" / "answer.json", answer)
    rep["status"] = "kept (the polish failed its checks)" if rep["attempts"] else rep["status"]
    _record(run, "en", rep)
    return answer, b, m, rep


# ------------------------------------------------------------------ Korean

def ko_problems(it: dict, ko: str, base: str, note_nums: set | None = None) -> list[str]:
    """What code finds wrong with Fable's Korean for one string, against qkr's draft of the same string (the polish
    sees no English since 19 Nov 2026: qkr's draft, checked against the English, is the source of the facts). The
    title is written anew from the whole note (20 Nov 2026): it need not keep qkr's title's numbers, and may use only
    numbers the note has (`note_nums`); its facts are read by the title's fact editor (polish-ko-title)."""
    from . import korean as ko_mod
    out = []
    if not ko or not ko.strip():
        return ["no Korean came back"]
    if "\n" in ko.strip():
        out.append("a line break; the string is one line")
    if it["id"] == "d:title" and note_nums is not None:
        if len(ko.strip()) > ko_mod.TITLE_MAX:
            out.append(f"the title is {len(ko.strip())} characters; at most {ko_mod.TITLE_MAX}")
        extra = sorted(ko_mod._nums(ko) - note_nums)
        if extra:
            out.append(f"numbers the note does not have: {extra}")
        return out
    if ko_mod._cites(base) != ko_mod._cites(ko):
        out.append(f"citation marks differ: qkr's draft {ko_mod._cites(base)}, now {ko_mod._cites(ko)}")
    have, got = ko_mod._nums(base), ko_mod._nums(ko)
    if got - have:
        out.append(f"new numbers {sorted(got - have)}: add none")
    lost = sorted(n for n in have - got if "." in n or len(n) >= 2)
    if lost:
        out.append(f"numbers lost {lost}: keep every number of the string")
    if re.search(r"(?<![\d-])(?:19|20)\d{2}-\d{2}(?![\d-])", ko):
        out.append("a date written as YYYY-MM; write 2026년 6월")
    for n in ko_mod.SERVICES:
        if n in base and n not in ko:
            out.append(f"the name {n} stays in Latin letters")
    if it["id"] == "d:title" and len(ko.strip()) > ko_mod.TITLE_MAX:
        out.append(f"the title is {len(ko.strip())} characters; at most {ko_mod.TITLE_MAX}")
    if it.get("profile") == "label" and len(ko) > len(base) + 8:
        out.append(f"a label of {len(ko)} characters, qkr's has {len(base)}: keep it short")
    return out


def korean(run: Path, items: list[dict], state: dict, name_map: dict, filled: dict, fresh: set | None = None) -> dict:
    """Fable's Korean, inside korean.make (brief `polish-ko`: the owner's short brief of 20 Nov 2026, tried on
    20261114-desk-t4-r3: "easy for adults who never studied economics; keep the content, change only the expression;
    anything goes inside a string", the title written last). Fable reads the whole note in Korean only, in reading order
    with the title at the end, and rewrites qkr's accepted drafts. Code holds each string to qkr's draft (ko_problems),
    the fact editor (polish-ko-facts) compares each rewrite with qkr's draft, and a second fact editor (polish-ko-title)
    reads the new title against the whole note. What fails goes back to Fable, up to three calls; what still fails keeps
    qkr's version. Changes `state` in place; returns the report. `filled` is unused (no English is shown)."""
    from . import korean as ko_mod
    rep = {"status": "off" if not on("ko") else "kept", "changed": 0, "reverted": [], "refused": [], "fixed_flags": 0}
    if not on("ko"):
        return rep
    text = {it["id"]: (state[it["id"]].get("ko") if state[it["id"]].get("status") in ko_mod.SETTLED else state[it["id"]].get("shown"))
            for it in items}
    # qkr's accepted drafts only: a flagged string failed a check against its English, which Fable no longer sees, and is
    # shown to the editor as it is; the editor's own words are never touched
    todo = [it for it in items if (fresh is None or it["id"] in fresh) and state[it["id"]].get("status") == "ok"
            and not state[it["id"]].get("polished") and text.get(it["id"])]
    if not todo:
        return {**rep, "status": "nothing to refine"}
    cur = {it["id"]: text[it["id"]] for it in todo}
    ids = {it["id"] for it in todo}
    byid = {it["id"]: it for it in items}
    order = [it for it in items if text.get(it["id"]) and it["id"] != "d:title"] + [it for it in items if it["id"] == "d:title" and text.get(it["id"])]
    note_nums = set().union(*(ko_mod._nums(text[it["id"]]) for it in order))
    used = sorted({ko for ko in name_map.values() if ko and any(ko in text[it["id"]] for it in order)})
    got: dict[str, str] = {}

    def packet(probs: list[str] | None) -> str:
        p = ("Economy names as the sites write them: " + ", ".join(used)
             + "\n\n## The note, in reading order, the title last (strings marked AS IS are the note around the others: answer nothing for them)\n"
             + "\n".join(f"### {it['id']} ({it['profile']}){'' if it['id'] in ids else ' AS IS'}\nKO: {text[it['id']]}" for it in order))
        if probs:
            p += ("\n\n## Your answer\n" + "\n".join(f"### {i}\n{got[i]}" for i in cur if i in got)
                  + "\n\n## These strings failed the desk's checks; answer only these again\n" + "\n".join(f"- {x}" for x in probs))
        return p

    probs, mech, facts = None, {}, {}
    for attempt in (1, 2, 3):
        try:
            data = roles.call(run, "polish-ko", packet(probs), label="korean")["data"] or {}
        except roles.RoleError as e:
            rep["error"] = str(e)
            break
        for x in data.get("items") or []:
            if x.get("id") in ids and str(x.get("ko") or "").strip():
                got[str(x["id"])] = str(x["ko"]).strip()
        mech = {i: p for i in cur if i in got and got[i] != cur[i] for p in [ko_problems(byid[i], got[i], cur[i], note_nums)] if p}
        changed = [i for i in cur if i in got and got[i] != cur[i] and i not in mech]
        facts = {}
        try:
            body = [i for i in changed if i != "d:title"]
            if body:
                fp = ("## The strings (QKR: qkr's draft, the facts; KO: the rewrite)\n"
                      + "\n".join(f"### {i} ({byid[i]['profile']})\nQKR: {cur[i]}\nKO: {got[i]}" for i in body))
                res = roles.call(run, "polish-ko-facts", fp, label="korean")["data"] or {}
                facts = {x["id"]: str(x.get("problem") or "")[:300] for x in res.get("issues") or [] if x.get("id") in body}
            if "d:title" in changed:
                tp = ("## The note\n" + "\n".join(f"[{it['id']}] {text[it['id']]}" for it in order if it["id"] != "d:title")
                      + f"\n\n## The headline\n{got['d:title']}")
                res = roles.call(run, "polish-ko-title", tp, label="korean")["data"] or {}
                if res.get("ok") is False:
                    facts["d:title"] = str(res.get("problem") or "")[:300]
        except roles.RoleError as e:
            rep["check_error"] = str(e)
        probs = [f"{i}: {'; '.join(p)}" for i, p in mech.items()] + [f"{i}: the fact editor: {p}" for i, p in facts.items()]
        rep.setdefault("history", []).append({"attempt": attempt, "changed": len(changed), "problems": probs[:20]})
        if not probs:
            break
    for it in todo:
        i, st = it["id"], state[it["id"]]
        ko = got.get(i)
        if got:
            st["polished"] = True      # read by Fable: not sent again while its English stays the same
        if not ko or ko == cur[i]:
            continue
        if i in mech:
            rep["refused"].append({"id": i, "ko": ko, "why": "; ".join(mech[i])[:300]})
            st["polish_refused"] = "; ".join(mech[i])[:300]
            continue
        if i in facts:
            rep["reverted"].append({"id": i, "ko": ko, "why": facts[i]})
            st["polish_undone"] = facts[i]
            continue
        st["ko_qkr"] = cur[i]
        st.update(ko=ko, how="refined by Fable", why=[], polished=True,
                  versions={**(st.get("versions") or {}), "polish": f"claude-p:{config.role('polish-ko')['model']}"})
        rep["changed"] += 1
    rep["status"] = "refined" if rep["changed"] else "kept"
    return rep


def feedback(cfg: dict, items: list[dict], state: dict) -> int:
    """Every Korean string Fable refined goes to qkr's feedback as an edit of qkr's draft, for its next training round."""
    from . import korean as ko_mod
    if ko_mod._engine() == "claude":
        return 0
    n = 0
    for it in items:
        st = state[it["id"]]
        if st.get("ko_qkr") and st.get("ko") != st["ko_qkr"] and not st.get("polish_reported"):
            try:
                ko_mod._http("/v1/feedback", {"service": cfg["service"], "id": f"desk:{it['id']}", "profile": it["profile"], "ko_src": "",
                                              "ko_model": st["ko_qkr"], "ko_final": st["ko"], "verdict": "edited",
                                              "note": (f"data note, drafted from English: {st.get('sent') or it['sent']!r}. A newspaper editor (Fable) "
                                                       "rewrote qkr's draft for the general public, from the Korean alone; the desk's checks and its "
                                                       "fact editor accepted it.")[:1500]}, timeout=60)
                st["polish_reported"] = True
                n += 1
            except Exception:
                return n
    return n
