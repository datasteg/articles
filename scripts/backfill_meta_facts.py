#!/usr/bin/env python3
"""One-off, 10 Nov 2026 (the articles views): give each published fact in meta.json → facts
the two fields `artools publish` now writes (pipeline/artools/content.py → fact_entries), for the articles shipped
before it did: `publishable` (false for a fact the analysis blocked, which the site's API never serves) and `sources`
(the sources.json ids it was computed from; `series` names the series when the article cites none of them). Read from
each article's run folder (/data/articles/runs/<meta.run.id>/analysis/analysis.json and its data catalogs) and its
published sources.json. Values, units and periods are not touched: a fact whose value or period no longer matches
its run stops the script. Existing keys keep their order, and the file keeps its indent and trailing newline.

    python3 scripts/backfill_meta_facts.py [--dry-run] [slug ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ARTICLES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTICLES / "pipeline"))
from artools.content import fact_entries, load_run  # noqa: E402
from artools.paths import RUNS  # noqa: E402

ADIR = ARTICLES / "content" / "articles"


def layout(text: str) -> tuple[int | None, str]:
    """The indent and the trailing newline the file was written with."""
    lines = text.splitlines()
    indent = len(lines[1]) - len(lines[1].lstrip(" ")) if len(lines) > 1 else None
    return (indent or None), ("\n" if text.endswith("\n") else "")


def dump(meta: dict, indent: int | None, nl: str) -> str:
    return json.dumps(meta, ensure_ascii=False, indent=indent) + nl


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    slugs = a.slugs or sorted(p.name for p in ADIR.iterdir() if (p / "meta.json").is_file())
    bad = 0
    for slug in slugs:
        f = ADIR / slug / "meta.json"
        text = f.read_text(encoding="utf-8")
        meta = json.loads(text)
        indent, nl = layout(text)
        if dump(meta, indent, nl) != text:
            print(f"{slug}: skipped, its formatting can't be reproduced (indent {indent}), so a rewrite would change more than the new keys")
            continue
        run_id = (meta.get("run") or {}).get("id")
        run = RUNS / run_id if run_id else None
        if not run or not (run / "analysis" / "analysis.json").is_file():
            print(f"{slug}: skipped, no analysis.json in its run folder ({run})")
            continue
        sources = json.loads((ADIR / slug / "sources.json").read_text(encoding="utf-8"))
        entries = {e["id"]: e for e in fact_entries(load_run(run), sources)}
        facts, drift = [], []
        for x in meta.get("facts") or []:
            e = entries.get(x["id"])
            if not e or any(e[k] != x.get(k) for k in ("value", "unit", "period")):
                drift.append(x["id"])
                continue
            y = {k: v for k, v in x.items() if k not in ("publishable", "sources", "series")}
            y.update({k: e[k] for k in ("publishable", "sources", "series") if k in e})
            facts.append(y)
        if drift:
            bad += 1
            print(f"{slug}: stopped, {len(drift)} fact(s) differ from run {run_id} or are missing from it: {', '.join(drift[:10])}")
            continue
        meta["facts"] = facts
        if not a.dry_run:
            out = dump(meta, indent, nl)
            if out != text:
                f.write_text(out, encoding="utf-8")
        pub = [x for x in facts if x["publishable"]]
        print(f"{slug}  run {run_id}  facts {len(facts)}  publishable {len(pub)}  with a source id {sum(1 for x in pub if x['sources'])}"
              f"  named by series only {sum(1 for x in pub if not x['sources'] and x.get('series'))}")
    print("dry run, nothing written" if a.dry_run else "done")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
