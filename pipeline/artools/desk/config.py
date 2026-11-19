"""config/desk.yaml: the desk's models, budgets, thresholds and approval path, with defaults that work without it."""
from __future__ import annotations

from ..paths import CONFIG, load_yaml

DEFAULTS = {
    "pipeline": "data-note",
    # one model per role; `fable` is never used by the desk (config/desk.yaml documents why)
    "roles": {
        "editor":  {"model": "claude-sonnet-5-5", "effort": "medium"},
        "analyst": {"model": "claude-sonnet-5-5", "effort": "medium"},
        "writer":  {"model": "claude-opus-5-5", "effort": "high"},
        "referee": {"model": "claude-opus-5-5", "effort": "medium"},
        "reader":  {"model": "claude-sonnet-5-5", "effort": "low"},        # retired 18 Nov 2026 (rule R5)
        "inference": {"model": "claude-sonnet-5-5", "effort": "low"},
        "checker": {"model": "claude-sonnet-5-5", "effort": "medium"},
        "verifier": {"model": "claude-sonnet-5-5", "effort": "medium"},
        "judge":   {"model": "claude-opus-5-5", "effort": "medium"},
        "ko-source": {"model": "claude-sonnet-5-5", "effort": "low"},
        "ko-checker": {"model": "claude-sonnet-5-5", "effort": "high"},
        "ko-title": {"model": "claude-opus-5-5", "effort": "medium"},
        "ko-writer": {"model": "claude-opus-5-5", "effort": "medium"},
        # the polish: Fable refines the expression of each finished edition (19 Nov 2026, the owner); the only Fable roles
        "polish-en": {"model": "claude-fable-5-2", "effort": "high"},
        "polish-ko": {"model": "claude-fable-5-2", "effort": "high"},
    },
    "polish": {"en": True, "ko": True},
    "budget": {"usd_per_note": 20.0, "usd_per_day": 20.0, "soft_usd_first_queue": 10.0},
    "loop": {"max_rounds": 2, "closing_passes": 2, "converge": True, "scoped_closing": True},
    "quality": {"min_overall": 3.3, "min_dimension": 3.0, "benchmark": "q3", "benchmark_margin": 0.0, "judges": 1,
                "second_judge": {"near_bar": 0.15, "near_floor": 0.25}},
    # rules R1–R4 and R10: a brief names its finding type, the analyst writes a claim ledger, the writer cites a
    # claim for every surface string, the inference test reads the surface, and the apps' consistency checks are read
    # before the editor role is paid for
    "claims": {"required": True, "inference": True, "inference_korean": True, "preflight": True},
    "note": {"words": [650, 1100], "figures": [3, 4], "forms": 2, "max_same": {"scatter": 1, "default": 2}, "history_line": True,
             "require_hook": True, "min_apps": 2, "min_publishers": 2,
             "chart_headline": {"max_chars": 110, "max_numbers": 2}},
    "approval": {"source": "ssh-logs", "by": "datasteg"},
    "schedule": {"note_from_hour": 9, "notes_per_day": 1},
    "leads": {"shortlist": 8, "cooldown_days": 45, "entity_cooldown_days": 35, "entity_penalty": 0.3},
    "korean": {"required": True, "rewrites": 3, "check_rounds": 3, "workers": 4, "service": "articles", "style": "1.3", "engine": "qkr",
               "title": {"angles": 5, "modes": ["fast", "careful"], "examples": 12, "rounds": 2}},
    "caveats": [],
}


def load() -> dict:
    f = CONFIG / "desk.yaml"
    cfg = (load_yaml(f) or {}) if f.is_file() else {}
    out = {}
    for k, v in DEFAULTS.items():
        got = cfg.get(k)
        if isinstance(v, dict):
            out[k] = {**v, **(got or {})}
            if k == "roles":
                out[k] = {r: {**v.get(r, {}), **((got or {}).get(r) or {})} for r in {**v, **(got or {})}}
        else:
            out[k] = got if got is not None else v
    return out


def role(name: str) -> dict:
    r = load()["roles"].get(name)
    if not r:
        raise KeyError(f"config/desk.yaml has no role {name}")
    return r
