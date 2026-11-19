"""Where things live, and the settings every command shares."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ARTICLES = Path(__file__).resolve().parents[2]          # the articles folder
DATA = Path(os.environ.get("ARTICLES_DATA", "/data/articles"))
RUNS = DATA / "runs"
READINGS = DATA / "readings"
CACHE = DATA / "cache"
CONTRACTS = ARTICLES / "contracts"
CONFIG = ARTICLES / "config"
SKILLS = ARTICLES / ".claude" / "skills"
CONTENT = ARTICLES / "content"
PREVIEW = ARTICLES / ".preview"
JEJUALPS_ENV = Path(os.environ.get("JEJUALPS_ENV", Path.home() / ".config/jejualps/.env"))


def env_value(name: str, files: list[Path] | None = None) -> str | None:
    """Environment first, then KEY=value lines in the given .env files (comments allowed)."""
    if os.environ.get(name):
        return os.environ[name]
    for f in files or [ARTICLES / ".env", ARTICLES.parent / ".env"]:
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.strip().partition("=")
            v = v.split(" #")[0].strip().strip('"').strip("'")
            if sep and k.strip() == name and v and not v.startswith("#"):
                return v
    return None


def run_dir(run_id: str) -> Path:
    p = Path(run_id)
    if p.is_absolute() and p.is_dir():
        return p
    d = RUNS / run_id
    if not d.is_dir():
        die(f"no run {run_id} under {RUNS}")
    return d


def out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def die(msg: str, code: int = 1, **extra) -> None:
    print(json.dumps({"error": msg, **extra}, ensure_ascii=False, indent=1), file=sys.stdout)
    sys.exit(code)


def read_json(p: Path, default=None):
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_yaml(p: Path):
    import yaml
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def publish_anyway() -> bool:
    """config/editorial.yaml → gates: auto with on_blocking: publish. Articles and videos go live without the editor,
    with quality issues left over (review blockers, a cover that fails its check, misread beats); the editor reviews
    them on the sites afterwards and asks for an update (the update-article skill). Authorship stays a hard stop:
    unpublishable data, citations and source lines, the slug of another run."""
    g = (load_yaml(CONFIG / "editorial.yaml") or {}).get("gates") or {}
    return bool(g.get("auto")) and g.get("on_blocking") == "publish"
