#!/usr/bin/env python3
"""One-off, 8 Nov 2026: fill meta.json → draws_on, draws_on_evidence
and fetch for the articles shipped before `artools publish` wrote them, from each article's published sources.json
and its run folder (/data/articles/runs/<meta.run.id>/), with the function publish now uses
(pipeline/artools/content.py → article_volume). Existing keys keep their order and values, new keys go at the end,
and the file keeps its indent and trailing newline. fetch is left out, with the reason printed, when the run folder
is missing or a number cannot be read.

    python3 scripts/backfill_meta_volume.py [--dry-run] [slug ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ARTICLES = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTICLES / "pipeline"))
from artools.content import app_hosts, article_volume  # noqa: E402
from artools.paths import RUNS  # noqa: E402

ADIR = ARTICLES / "content" / "articles"


def layout(text: str) -> tuple[int | None, str]:
    """The indent and the trailing newline the file was written with."""
    lines = text.splitlines()
    indent = len(lines[1]) - len(lines[1].lstrip(" ")) if len(lines) > 1 else None
    return (indent or None), ("\n" if text.endswith("\n") else "")


def dump(meta: dict, indent: int | None, nl: str) -> str:
    return json.dumps(meta, ensure_ascii=False, indent=indent) + nl


def notes(run: Path) -> list[str]:
    """What the counts leave out, for the record: folders without a catalog, CSVs no catalog entry names, catalog
    entries without their CSV, and the scout's own fetches (scout/data, not the article's data)."""
    out = []
    for d in sorted(p for p in (run / "data").iterdir() if p.is_dir()) if (run / "data").is_dir() else []:
        if d.name == "derived":
            continue
        if not (d / "catalog.json").is_file():
            out.append(f"data/{d.name}: no catalog.json, skipped ({', '.join(sorted(x.name for x in d.iterdir()))})")
            continue
        items = json.loads((d / "catalog.json").read_text(encoding="utf-8"))
        items = items.get("datasets", []) if isinstance(items, dict) else items
        named = {(run / e["file"]).resolve() if e.get("file") else (d / f"{e.get('id')}.csv").resolve() for e in items}
        stray = sorted(f.name for f in d.glob("*.csv") if f.resolve() not in named)
        gone = sorted(p.name for p in named if not p.is_file())
        if stray:
            out.append(f"data/{d.name}: {len(stray)} CSV not in catalog.json, not counted: {', '.join(stray)}")
        if gone:
            out.append(f"data/{d.name}: {len(gone)} catalog entries without their CSV, not counted: {', '.join(gone)}")
    if (run / "scout" / "data").is_dir():
        out.append("scout/data (" + ", ".join(sorted(p.name for p in (run / "scout" / "data").iterdir() if p.is_dir()))
                   + "): the scout's fetches, not counted")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    hosts = app_hosts()
    slugs = a.slugs or sorted(p.name for p in ADIR.iterdir() if (p / "meta.json").is_file())
    totals: dict[str, dict] = {}
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
        sources = json.loads((ADIR / slug / "sources.json").read_text(encoding="utf-8"))
        drew, why = article_volume(run if run and run.is_dir() else None, sources, meta, hosts)
        meta.update(drew)
        if "fetch" not in drew:
            meta.pop("fetch", None)
        if not a.dry_run:
            out = dump(meta, indent, nl)
            if out != text:
                f.write_text(out, encoding="utf-8")
        print(f"{slug}  run {run_id}  draws_on {drew['draws_on']} {drew['draws_on_evidence']}")
        if why:
            print(f"  fetch left out: {why}")
        for prov, v in (drew.get("fetch") or {}).items():
            print(f"  {prov:<9} series {v['series']:>3}  rows {v['rows']:>7}  bytes {v['bytes']:>9}")
            t = totals.setdefault(prov, {"series": 0, "rows": 0, "bytes": 0, "articles": 0})
            for k in ("series", "rows", "bytes"):
                t[k] += v[k]
            t["articles"] += 1
        for n in notes(run) if run and run.is_dir() else []:
            print(f"  note: {n}")
    print("totals" + (" (dry run, nothing written)" if a.dry_run else ""))
    for prov, t in sorted(totals.items()):
        print(f"  {prov:<9} series {t['series']:>3}  rows {t['rows']:>7}  bytes {t['bytes']:>9}  articles {t['articles']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
