"""The video explainer: a published article as a narrated slide video (config/video/)."""
from __future__ import annotations

import os
from pathlib import Path

from ..paths import CONFIG, DATA, load_yaml

VCONFIG = CONFIG / "video"
VDATA = DATA / "video"          # auditions, test takes, the channel record: not tied to one run


def cfg(name: str) -> dict:
    """config/video/<name>.yaml"""
    return load_yaml(VCONFIG / f"{name}.yaml") or {}


def secret_path(key: str) -> Path:
    """A secret file named in config/video/publish.yaml (outside the repo, mode 600)."""
    return Path(os.path.expanduser(cfg("publish")["secrets"][key]))
