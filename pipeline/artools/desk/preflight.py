"""Preflight (rule R10): before the editor role is paid for, are the inputs sound?

The desk takes the apps' numbers on trust: F7 (a 13-month base for export growth in every note until the
consistency plan) came from upstream and no desk check could see it. Each app now runs its own consistency checks in
its build, so the desk reads their latest results and writes no note on a day when one failed:

- global-network: the build's K1–K3 and K8 (data/checks.json.br);
- trade-flow: data/checks/consistency.json.br (k1 growth base and the rest), `ok`;
- money-flow: V27 (net reserves and A2's base) in /data/money-flow/checks/site-checks.json;
- every panel column has a period (rule C2), and every app's copy of the measures registry equals
  family/measures.json (rule C1).

A failure means no note today, with the reason in the daily log.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ..paths import ARTICLES

ROOT = ARTICLES.parent
GN_CHECKS = ROOT / "global-network" / "data" / "checks.json.br"
TF_CHECKS = ROOT / "trade-flow" / "data" / "checks" / "consistency.json.br"
MF_CHECKS = Path(os.environ.get("MONEY_FLOW_CHECKS", "/data/money-flow/checks/site-checks.json"))
REGISTRY_COPIES = ["money-flow/app/lib/measures.json", "trade-flow/apps/web/lib/measures.json", "global-network/app/lib/measures.json",
                   "open-research/app/lib/measures.json", "main/app/lib/measures.json", "articles/apps/web/lib/measures.json"]
GN_NEED = ("K1", "K2", "K3", "K8")


def _read(p: Path):
    if p.suffix != ".br":
        return json.loads(p.read_text(encoding="utf-8"))
    try:
        import brotli          # noqa: PLC0415
        return json.loads(brotli.decompress(p.read_bytes()))
    except ImportError:
        out = subprocess.run(["node", "-e", "process.stdout.write(require('zlib').brotliDecompressSync(require('fs').readFileSync(process.argv[1])))", str(p)],
                             capture_output=True, timeout=60, check=True).stdout
        return json.loads(out)


def check(panel_table: dict | None = None) -> dict:
    """{"ok", "problems": [...], "checked": {...}}."""
    problems, checked = [], {}
    try:
        g = _read(GN_CHECKS)
        items = {x.get("id"): x for x in g.get("items") or g.get("checks") or []}
        for k in GN_NEED:
            st = (items.get(k) or {}).get("status")
            if st is None:
                problems.append(f"global-network: its build log has no check {k}")
            elif st == "fail":
                problems.append(f"global-network: check {k} failed in the build of {g.get('built')}: {(items[k].get('figure') or '')[:160]}")
        checked["global-network"] = {"built": g.get("built"), **{k: (items.get(k) or {}).get("status") for k in GN_NEED}}
    except Exception as e:
        problems.append(f"global-network: its checks could not be read ({type(e).__name__}: {e})")
    try:
        t = _read(TF_CHECKS)
        bad = [c.get("id") for c in t.get("checks") or [] if c.get("status") == "fail"]
        if not t.get("ok", False) or bad:
            problems.append(f"trade-flow: consistency checks failed at {t.get('run_at')}: {bad or 'ok is false'}")
        checked["trade-flow"] = {"run_at": t.get("run_at"), "ok": t.get("ok")}
    except Exception as e:
        problems.append(f"trade-flow: its consistency checks could not be read ({type(e).__name__}: {e})")
    try:
        m = _read(MF_CHECKS)
        v = next((x for x in m.get("results") or [] if x.get("id") == "V27"), None)
        if not v:
            problems.append("money-flow: its site checks have no V27")
        elif v.get("status") == "fail":
            problems.append(f"money-flow: V27 failed: {(v.get('summary') or '')[:160]}")
        checked["money-flow"] = {"V27": (v or {}).get("status")}
    except Exception as e:
        problems.append(f"money-flow: its site checks could not be read ({type(e).__name__}: {e})")
    try:
        src = json.loads((ROOT / "family" / "measures.json").read_text(encoding="utf-8"))
        stale = [c for c in REGISTRY_COPIES if (ROOT / c).is_file() and json.loads((ROOT / c).read_text(encoding="utf-8")) != src]
        if stale:
            problems.append(f"registry: these copies differ from family/measures.json (run node family/sync.mjs): {stale}")
        checked["registry"] = {"copies": len(REGISTRY_COPIES), "stale": stale}
    except Exception as e:
        problems.append(f"registry: could not be compared ({type(e).__name__}: {e})")
    if panel_table is not None:
        from .panel import COLS, PERIOD
        none = sorted(c for c in COLS if c not in PERIOD)
        cols = {c.get("id"): c for c in panel_table.get("columns") or []}
        none += sorted(c for c, col in cols.items() if c in COLS and not (col.get("period") or PERIOD.get(c)))
        if none:
            problems.append(f"panel: columns without a period (rule C2): {sorted(set(none))}")
        checked["panel"] = {"columns": len(cols), "without_period": sorted(set(none))}
    return {"ok": not problems, "problems": problems, "checked": checked}
