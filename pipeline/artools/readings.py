"""Reading notes: the question-independent core of what a paper says, with verified quotes.

Cache key: (source, doc id, text sha1, reader version). A note for a document whose text changed is not reused.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import jejualps
from .paths import READINGS, die, read_json, write_json

READER_VERSION = 1
REQUIRED = ["doc", "question", "method", "findings"]


def path_for(source: str, doc_id: int, sha: str | None, version: int = READER_VERSION) -> Path:
    return READINGS / source / f"{doc_id}.{(sha or 'nosha')[:12]}.r{version}.json"


def get(source: str, doc_id: int) -> dict:
    if source != "jejualps":
        die("only jejualps readings exist so far")
    sha = jejualps.text_sha1(doc_id)
    p = path_for(source, doc_id, sha)
    note = read_json(p)
    return {"found": note is not None, "path": str(p), "note": note}


def save(file: str, run: str | None = None) -> dict:
    note = json.loads(Path(file).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in note]
    if missing:
        die(f"reading note lacks {missing}")
    ref = note["doc"].get("ref", "") if isinstance(note["doc"], dict) else str(note["doc"])
    source, _, did = ref.partition(":")
    doc_id = int(did)
    text = jejualps.full_text(doc_id)
    sha = jejualps.text_sha1(doc_id)
    checked, failed = 0, []
    for f in note.get("findings", []):
        if f.get("quote"):
            v = jejualps.verify_quote(doc_id, f["quote"], text)
            f["verified"] = v["verified"]
            if v["verified"]:
                f.setdefault("locator", {}).update(chunk=v["chunk"], offset=v["offset"])
            else:
                failed.append(f["quote"][:80])
            checked += 1
    note.update(text_sha1=sha, reader_version=READER_VERSION)
    p = path_for(source, doc_id, sha)
    write_json(p, note)
    if run:
        from .paths import run_dir
        write_json(run_dir(run) / "readings" / source / f"{doc_id}.json", note)
    return {"saved": str(p), "quotes_checked": checked, "quotes_failed": failed}
