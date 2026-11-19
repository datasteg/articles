"""The datasteg API as the desk's only data door (https://api.datasteg.com/v1, read-only, no key).

Every answer is kept with what makes it citable: the page it mirrors (meta.cite), the app's release, the period and
the publishers behind it. Answers are cached per app release, so a day without new data costs no calls, and calls are
spaced to stay under the API's limit for one caller (30 a minute during the test period; api/src/limits.ts).
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..paths import DATA, read_json, write_json

BASE = "https://api.datasteg.com"
UA = "datasteg-desk/0.1 (+https://articles.datasteg.com)"
DESK = DATA / "desk"
CACHE = DESK / "cache"
MIN_INTERVAL_S = 2.2            # 30 calls a minute allowed; 27 used
APPS = ("money-flow", "trade-flow", "global-network", "open-research", "articles")


class ApiError(RuntimeError):
    pass


class Api:
    def __init__(self, cache: Path = CACHE, base: str = BASE, min_interval: float = MIN_INTERVAL_S, offline: bool = False):
        self.cache, self.base, self.min_interval, self.offline = cache, base.rstrip("/"), min_interval, offline
        self._last = 0.0
        self._health: dict | None = None
        self.calls = 0          # network calls made by this object
        self.used: list[dict] = []   # every answer handed out, cached or not: the run's provenance

    # ------------------------------------------------------------------ releases

    def health(self, refresh: bool = False) -> dict:
        """{app: {release, up}} from /health; the release decides which cached answers are still current."""
        if self._health is None or refresh:
            if self.offline:
                self._health = read_json(self.cache / "health.json", {}) or {}
            else:
                h = self._fetch("/health")
                self._health = {a: {"release": v.get("release"), "up": v.get("up")} for a, v in (h.get("apps") or {}).items()}
                self._health["_api"] = {"release": h.get("version"), "up": h.get("status") == "ok"}
                write_json(self.cache / "health.json", self._health)
        return self._health

    def release(self, app: str) -> str | None:
        return (self.health().get(app) or {}).get("release")

    # ------------------------------------------------------------------ calls

    def get(self, path: str, max_age_h: float | None = None, **params) -> dict:
        """GET /v1/<path>. Cached while the app's release is unchanged (and, with max_age_h, no older than that)."""
        path = "/" + path.strip("/")
        params = {k: v for k, v in sorted(params.items()) if v is not None}
        app = next((a for a in APPS if path.startswith("/" + a)), "_core")
        key = hashlib.sha1((path + "?" + urllib.parse.urlencode(params)).encode()).hexdigest()[:20]
        f = self.cache / app / f"{key}.json"
        hit = read_json(f, None)
        rel = self.release(app) if app != "_core" else "|".join(f"{a}:{self.release(a)}" for a in APPS)
        if hit and (self.offline or (hit.get("_release") == rel and
                                     (max_age_h is None or time.time() - hit.get("_at", 0) < max_age_h * 3600))):
            ans = hit["answer"]
        else:
            if self.offline:
                raise ApiError(f"offline and no cached answer for {path} {params}")
            ans = self._fetch("/v1" + path, params)
            write_json(f, {"_release": rel, "_at": time.time(), "path": path, "params": params, "answer": ans})
        meta = ans.get("meta") or {}
        self.used.append({"path": path, "params": params, "app": app, "release": meta.get("release") or rel,
                          "cite": meta.get("cite") or (ans.get("links") or {}).get("page"),
                          "period": meta.get("period"), "built": meta.get("built")})
        return ans

    def _fetch(self, path: str, params: dict | None = None) -> dict:
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        for attempt in range(4):
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            self.calls += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=40) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                if e.code == 429 or e.code >= 500:
                    time.sleep(min(60, float(e.headers.get("Retry-After") or 5 * (attempt + 1))))
                    continue
                raise ApiError(f"{url}: HTTP {e.code} {body}") from e
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                if attempt == 3:
                    raise ApiError(f"{url}: {type(e).__name__} {e}") from e
                time.sleep(3 * (attempt + 1))
        raise ApiError(f"{url}: no answer after 4 attempts")


def table_rows(ans: dict) -> list[dict]:
    """An answer's `table` as a list of row dicts keyed by column id."""
    t = ans.get("table") or {}
    cols = [c.get("id") or c.get("key") if isinstance(c, dict) else c for c in t.get("columns", [])]
    return [dict(zip(cols, r)) for r in t.get("rows", [])]
