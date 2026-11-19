"""YouTube: connecting artools to the datasteg channel, and the channel's playlists.

Sign-in is the installed-app flow with a loopback redirect, split in two so it works from any device: `auth url`
prints Google's link and keeps the PKCE verifier; `auth finish <redirected address>` exchanges the code. The client
secret and the token stay in private files outside the repository (mode 600)."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..paths import read_json, write_json
from . import VDATA, cfg, secret_path

PENDING = "youtube-auth-pending.json"


def _private_write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(p, 0o600)


def _settings() -> dict:
    return cfg("publish")["youtube"]


def _flow(state: str | None = None, verifier: str | None = None):
    from google_auth_oauthlib.flow import Flow
    client = secret_path("youtube_client")
    if not client.is_file():
        raise RuntimeError(f"no OAuth client at {client}")
    y = _settings()
    flow = Flow.from_client_secrets_file(str(client), scopes=y["scopes"], state=state,
                                         redirect_uri=f"http://localhost:{y['redirect_port']}/",
                                         code_verifier=verifier, autogenerate_code_verifier=verifier is None)
    return flow


def auth_url() -> dict:
    flow = _flow()
    # access_type=offline and prompt=consent: a refresh token on every sign-in. Nothing else: extra prompts
    # (select_account) have ended in Google's generic "400 malformed request" with brand channels.
    url, state = flow.authorization_url(access_type="offline", prompt="consent")
    pending = secret_path("youtube_token").with_name(PENDING)
    _private_write(pending, json.dumps({"state": state, "code_verifier": flow.code_verifier,
                                        "created": dt.datetime.now(dt.timezone.utc).isoformat()}))
    return {"url": url,
            "next": "Open the link, sign in with the channel owner's Google account, choose the channel and allow both permissions. "
                    "Then copy the whole address the browser lands on (http://localhost:…, the page itself fails to load) "
                    "and run: artools video auth finish '<that address>'"}


def auth_finish(redirected: str) -> dict:
    pending_p = secret_path("youtube_token").with_name(PENDING)
    pending = read_json(pending_p)
    if not pending:
        raise RuntimeError("no sign-in in progress: run `artools video auth url` first")
    q = parse_qs(urlparse(redirected.strip()).query)
    if q.get("error"):
        raise RuntimeError(f"Google returned an error: {q['error'][0]}")
    code, state = (q.get("code") or [None])[0], (q.get("state") or [None])[0]
    if not code:
        raise RuntimeError("the address has no code=…; copy the whole address from the browser's address bar")
    if state != pending["state"]:
        raise RuntimeError("the address belongs to a different sign-in; run `artools video auth url` again")
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")     # Google may list the granted scopes differently
    flow = _flow(state, pending["code_verifier"])
    flow.fetch_token(code=code)
    _private_write(secret_path("youtube_token"), flow.credentials.to_json())
    pending_p.unlink(missing_ok=True)
    return {"saved": str(secret_path("youtube_token")), **channel()}


def credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    tok = secret_path("youtube_token")
    if not tok.is_file():
        raise RuntimeError("not connected to YouTube: run `artools video auth url`")
    creds = Credentials.from_authorized_user_file(str(tok))
    if not creds.valid:
        creds.refresh(Request())
        _private_write(tok, creds.to_json())
    return creds


def service():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=credentials(), cache_discovery=False)


def channel() -> dict:
    res = service().channels().list(part="snippet,status", mine=True).execute()
    items = res.get("items") or []
    if not items:
        raise RuntimeError("this Google account has no YouTube channel; create the datasteg channel")
    ch = items[0]
    rec = {"channel": ch["snippet"]["title"], "channel_id": ch["id"],
           "long_uploads": (ch.get("status") or {}).get("longUploadsStatus")}
    old = read_json(VDATA / "channel.json", {}) or {}
    write_json(VDATA / "channel.json", {**old, **rec})
    return rec


def playlists(create: bool = False) -> dict:
    """The channel's two playlists (config/video/publish.yaml); `create` makes the missing ones (public)."""
    yt = service()
    have = {}
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        res = req.execute()
        for p in res.get("items", []):
            have[p["snippet"]["title"]] = p["id"]
        req = yt.playlists().list_next(req, res)
    out = {}
    for lang, spec in _settings()["playlists"].items():
        pid = have.get(spec["title"])
        if not pid and create:
            body = {"snippet": {"title": spec["title"], "description": spec["description"], "defaultLanguage": lang},
                    "status": {"privacyStatus": "public"}}
            pid = yt.playlists().insert(part="snippet,status", body=body).execute()["id"]
        out[lang] = {"title": spec["title"], "id": pid}
    old = read_json(VDATA / "channel.json", {}) or {}
    write_json(VDATA / "channel.json", {**old, "playlists": out})
    return {"playlists": out, "missing": [k for k, v in out.items() if not v["id"]]}


def auth_listen(timeout: int = 900) -> dict:
    """Sign in from a browser on this machine: print Google's link, catch the redirect on localhost and finish by
    itself, so nothing has to be copied. From another device, use `auth url` and `auth finish` instead."""
    import html
    import socket
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port = _settings()["redirect_port"]
    start = auth_url()
    print(json.dumps({"url": start["url"], "note": "Open the link in a browser on dev-host; this waits up to "
                      f"{timeout // 60} minutes."}, ensure_ascii=False), flush=True)
    result: dict = {}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):                    # noqa: N802 - the http.server API
            if "code=" not in self.path and "error=" not in self.path:
                self.send_response(404)
                self.end_headers()
                return
            try:
                result.update(auth_finish(f"http://localhost:{port}{self.path}"))
                body = f"<h1>Connected</h1><p>artools can now upload to <b>{html.escape(result['channel'])}</b>. You can close this tab.</p>"
            except Exception as e:  # noqa: BLE001 - show the reason in the browser and in the command's output
                result["error"] = str(e)
                body = f"<h1>Not connected</h1><p>{html.escape(str(e))}</p>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(("<!doctype html><meta charset=utf-8><body style='font:16px system-ui;padding:32px'>"
                              + body).encode())
            done.set()

        def log_message(self, *args):        # quiet
            pass

    class V6(HTTPServer):
        address_family = socket.AF_INET6

    servers = [HTTPServer(("127.0.0.1", port), Handler)]
    try:
        servers.append(V6(("::1", port), Handler))     # browsers may try ::1 first for "localhost"
    except OSError:
        pass
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        if not done.wait(timeout):
            raise RuntimeError(f"no sign-in within {timeout // 60} minutes")
    finally:
        for s in servers:
            s.shutdown()
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result



def update_channel() -> dict:
    """The channel's introduction, keywords and country from config/video/publish.yaml, with a Korean localization."""
    ch = _settings()["channel"]
    yt = service()
    cur = yt.channels().list(part="brandingSettings,localizations,snippet", mine=True).execute()["items"][0]
    branding = cur.get("brandingSettings") or {}
    chan = dict(branding.get("channel") or {})
    chan.update(description=ch["description"]["en"], keywords=ch["keywords"], country=ch["country"], defaultLanguage="en")
    branding["channel"] = chan
    locs = dict(cur.get("localizations") or {})
    locs["ko"] = {"title": cur["snippet"]["title"], "description": ch["description"]["ko"]}
    # YouTube takes brandingSettings only on its own, so two calls
    yt.channels().update(part="brandingSettings", body={"id": cur["id"], "brandingSettings": branding}).execute()
    yt.channels().update(part="localizations", body={"id": cur["id"], "localizations": locs}).execute()
    return {"channel": cur["snippet"]["title"], "handle": cur["snippet"].get("customUrl"), "description_chars": len(chan["description"]),
            "localized": sorted(locs), "url": f"https://www.youtube.com/{cur['snippet'].get('customUrl') or 'channel/' + cur['id']}"}
