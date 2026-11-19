"""`artools video publish` and `release`: an edition to YouTube.

upload  (publish) checks that the edition has a real voice and that the article hasn't changed since the video's
        source; uploads the MP4 (resumable) with the privacy in config/video/publish.yaml (public, since the editor
        chose on 26 Oct 2026 to publish directly), then its captions and thumbnail, adds it to the language's playlist,
        and, once both editions are up, links each description to the other. Records youtube/<lang>.json.
release makes an uploaded edition public now, or schedules it (`--at`, while it is still private), and links the
        editions.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ..content import CITE, GLOSS
from ..paths import CONTENT, publish_anyway, read_json, run_dir, write_json
from . import VDATA, cfg
from .run import content_hash

LANG_NAME = {"en": "English", "ko": "한국어"}
LINE = {"sources": {"en": "Sources", "ko": "출처"}, "article": {"en": "Read the full article", "ko": "기사 전문 읽기"},
        "other": {"en": "한국어로 보기", "ko": "Watch in English"}, "chapters": {"en": "Chapters", "ko": "챕터"}}


def _plain(t: str) -> str:
    return GLOSS.sub(lambda m: m.group(0)[2:-2].split("|")[-1], CITE.sub("", t)).replace("*", "").strip()


ARTICLE_URL = "https://articles.datasteg.com/{lang}/a/{slug}?utm_source=youtube&utm_medium=video"
COUNTRY = {"FR": ("France", "프랑스"), "DE": ("Germany", "독일"), "IT": ("Italy", "이탈리아"), "ES": ("Spain", "스페인"),
           "GR": ("Greece", "그리스"), "PT": ("Portugal", "포르투갈"), "US": ("United States", "미국"), "GB": ("United Kingdom", "영국"),
           "JP": ("Japan", "일본"), "KR": ("Korea", "한국"), "CN": ("China", "중국"), "BE": ("Belgium", "벨기에")}
BASE_TAGS = {"en": ["datasteg", "economics", "economics explained", "finance"], "ko": ["datasteg", "경제", "경제 해설", "금융"]}


def _topics(run: Path, lang: str) -> list[str]:
    meta = read_json(run / "source" / "meta.json", {}) or {}
    return [t["label"].get(lang) or t["label"]["en"] for t in meta.get("topics", []) if t.get("label")]


def hashtags(run: Path, lang: str) -> list[str]:
    """Up to five hashtags: the article's topics, then datasteg. YouTube shows the first three above the title and
    ignores all of them past fifteen."""
    tags = ["#" + re.sub(r"[^0-9A-Za-z가-힣]", "", t.title() if lang == "en" else t) for t in _topics(run, lang)]
    tags += ["#Economics" if lang == "en" else "#경제", "#datasteg"]
    return list(dict.fromkeys(t for t in tags if len(t) > 1))[:5]


def search_tags(run: Path, lang: str) -> list[str]:
    """The video's search tags (snippet.tags, at most 500 characters): topics, glossary terms, countries."""
    meta = read_json(run / "source" / "meta.json", {}) or {}
    out = _topics(run, lang)
    for t in meta.get("terms", []):
        g = read_json(CONTENT / "glossary" / f"{t['id']}.json", {}) or {}
        term = (g.get("term") or {}).get(lang)
        if term:
            out.append(term)
    out += [COUNTRY[c][0 if lang == "en" else 1] for c in meta.get("countries", []) if c in COUNTRY][:5]
    out += BASE_TAGS[lang]
    seen, keep, size = set(), [], 0
    for t in out:
        k = t.lower()
        if k in seen or size + len(t) + 1 > 480:
            continue
        seen.add(k); keep.append(t); size += len(t) + 1
    return keep


def description(run: Path, lang: str, other_url: str | None = None) -> str:
    """The article's address first (YouTube shows the opening lines before "…more"), then the answer, the other
    edition, chapters, sources, disclosure, disclaimer and hashtags."""
    m = read_json(run / "run.json")
    sc = read_json(run / "script" / f"{lang}.json")
    vi = read_json(run / "video" / f"{lang}.json", {}) or {}
    pub = cfg("publish")["youtube"]
    slug = m["source"]["slug"]
    srcs = read_json(run / "source" / "sources.json", []) or []
    names = list(dict.fromkeys(s.get("institution") or s.get("title") for s in srcs if s.get("kind") == "dataset"))[:4]
    papers = [s for s in srcs if s.get("kind") in ("paper", "policy-note", "report", "speech")][:4]
    parts = [f"{LINE['article'][lang]} ▶ {ARTICLE_URL.format(lang=lang, slug=slug)}"]
    if other_url:
        parts.append(f"{LINE['other'][lang]} ▶ {other_url}")
    parts += ["", _plain(sc["meta"]["summary"])]
    if vi.get("chapters"):
        parts += ["", f"{LINE['chapters'][lang]}"] + vi["chapters"]
    parts += ["", f"{LINE['sources'][lang]}"]
    parts += [f"· {n}" for n in names]
    parts += [f"· {p.get('institution') + ': ' if p.get('institution') else ''}{p.get('title')}" for p in papers]
    disclosure = (cfg("podcast")["disclosure"] if m.get("mode") == "podcast" else pub["disclosure"])[lang]
    corr = (read_json(CONTENT / "articles" / slug / "meta.json", {}) or {}).get("corrections") or []
    if corr:                                   # a wording correction to the article shows here too
        parts += ["", {"en": "Corrections", "ko": "정정"}[lang]]
        parts += [f"· {c['date']} {c['text'].get(lang) or c['text'].get('en', '')}" for c in corr]
    parts += ["", disclosure, pub["disclaimer"][lang], "", " ".join(hashtags(run, lang))]
    text = "\n".join(parts)
    return text[:4900]                         # YouTube's limit is 5,000 characters


def update_meta(run_id: str) -> dict:
    """Refresh both editions' title, description (with the other edition's link), tags and flags on YouTube."""
    from .youtube import service
    run = run_dir(run_id)
    yt = service()
    recs = {lang: read_json(run / "youtube" / f"{lang}.json", {}) or {} for lang in ("en", "ko")}
    out = {}
    for lang, other in (("en", "ko"), ("ko", "en")):
        r = recs[lang]
        if not r.get("video_id"):
            continue
        v = yt.videos().list(part="snippet", id=r["video_id"]).execute()["items"][0]["snippet"]
        snippet = {k: v[k] for k in ("title", "categoryId", "defaultLanguage", "defaultAudioLanguage") if k in v}
        snippet["description"] = description(run, lang, recs[other].get("url"))
        snippet["tags"] = search_tags(run, lang)
        yt.videos().update(part="snippet", body={"id": r["video_id"], "snippet": snippet}).execute()
        out[lang] = {"video": r["url"], "hashtags": hashtags(run, lang), "tags": len(snippet["tags"])}
    return out


def _publish_blocked(run: Path) -> bool:
    """True when the video goes public even with blocking issues left after the review loop: every video under the
    editor's policy (editorial.yaml → gates.on_blocking: publish, 31 Oct 2026), and the podcast video under
    podcast.yaml → on_blocking: publish (29 Oct 2026). The upload record lists them."""
    if publish_anyway():
        return True
    return (read_json(run / "run.json", {}) or {}).get("mode") == "podcast" and cfg("podcast").get("on_blocking") == "publish"


def _checks(run: Path, lang: str) -> list[str]:
    m = read_json(run / "run.json")
    probs = []
    mp4 = run / "video" / f"{lang}.mp4"
    vi = read_json(run / "video" / f"{lang}.json", {}) or {}
    if not mp4.is_file():
        probs.append(f"video/{lang}.mp4 is missing")
    if vi.get("placeholder_voice"):
        probs.append("this video has a placeholder (silent) voice")
    sc_p = run / "script" / f"{lang}.json"
    if mp4.is_file() and sc_p.is_file() and sc_p.stat().st_mtime > mp4.stat().st_mtime:
        probs.append(f"script/{lang}.json changed after the video was assembled (a review fix): record the changed beats "
                     f"and assemble again (artools video voice {run.name} --lang {lang}; artools video assemble …)")
    rv = read_json(run / "review.json", {}) or {}
    if rv.get("blocking") and not _publish_blocked(run):
        probs.append(f"review.json has {len(rv['blocking'])} blocking issue(s): fix them and review again before a public upload")
    vo = read_json(run / "audio" / lang / "voice.json", {}) or {}
    if vo.get("flagged") and not publish_anyway():   # a misread the re-records couldn't fix (else listed in the record)
        probs.append(f"beats {vo['flagged']} were still misread after three takes: re-record them "
                     f"(artools video voice {run.name} --lang {lang} --beats …) or fix the lexicon")
    if (vi.get("minutes") or 0) > 15:        # an unverified account's 18-minute upload was removed twice (29 Oct 2026)
        from .youtube import service
        st = service().channels().list(part="status", mine=True).execute()["items"][0]["status"]
        if st.get("longUploadsStatus") != "allowed":
            probs.append(f"the video runs {vi['minutes']} min and the channel can't take uploads over 15 min "
                         f"(longUploadsStatus {st.get('longUploadsStatus')}): verify it at https://www.youtube.com/verify")
    src = CONTENT / "articles" / m["source"]["slug"]
    if src.is_dir() and content_hash(src) != m["source"]["content_hash"]:
        probs.append("the article changed after this video was made (a correction?): make a new revision")
    return probs


def upload(run_id: str, lang: str) -> dict:
    from googleapiclient.http import MediaFileUpload
    from .youtube import service
    run = run_dir(run_id)
    probs = _checks(run, lang)
    if probs:
        raise RuntimeError("; ".join(probs))
    rec_p = run / "youtube" / f"{lang}.json"
    rec = read_json(rec_p, {}) or {}
    if rec.get("video_id"):
        raise RuntimeError(f"already uploaded as {rec['url']}; a new revision needs a new run")
    pub = cfg("publish")["youtube"]
    sc = read_json(run / "script" / f"{lang}.json")
    yt = service()
    body = {"snippet": {"title": sc["meta"]["title"][:100], "description": description(run, lang),
                        "categoryId": pub["category"], "defaultLanguage": lang, "defaultAudioLanguage": lang,
                        "tags": search_tags(run, lang)},
            "status": {"privacyStatus": pub["privacy_on_upload"], "selfDeclaredMadeForKids": pub["made_for_kids"],
                       "containsSyntheticMedia": pub["synthetic_media"]}}
    media = MediaFileUpload(str(run / "video" / f"{lang}.mp4"), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    rec = {"video_id": vid, "url": f"https://youtu.be/{vid}", "studio": f"https://studio.youtube.com/video/{vid}/edit",
           "uploaded": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "privacy": pub["privacy_on_upload"],
           "steps": {}}
    left = (read_json(run / "review.json", {}) or {}).get("blocking") or []
    if left:
        rec["steps"]["review"] = f"published with {len(left)} blocking issue(s) left (on_blocking: publish)"
    flagged = (read_json(run / "audio" / lang / "voice.json", {}) or {}).get("flagged")
    if flagged:
        rec["steps"]["voice"] = f"published with beats {flagged} still misread"
    write_json(rec_p, rec)
    srt = run / "video" / f"{lang}.srt"
    try:
        yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": lang, "name": LANG_NAME[lang],
                                                               "isDraft": False}},
                             media_body=MediaFileUpload(str(srt), mimetype="application/octet-stream")).execute()
        rec["steps"]["captions"] = "ok"
    except Exception as e:  # noqa: BLE001 - the upload stands; the editor can add captions in Studio
        rec["steps"]["captions"] = f"failed: {str(e)[:200]}"
    other = "ko" if lang == "en" else "en"
    srt2 = run / "video" / f"{lang}.{other}.srt"          # the podcast video: captions in the other language too
    if srt2.is_file():
        try:
            yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": other, "name": LANG_NAME[other],
                                                                   "isDraft": False}},
                                 media_body=MediaFileUpload(str(srt2), mimetype="application/octet-stream")).execute()
            rec["steps"][f"captions_{other}"] = "ok"
        except Exception as e:  # noqa: BLE001
            rec["steps"][f"captions_{other}"] = f"failed: {str(e)[:200]}"
    thumb = run / "video" / f"{lang}-thumb.png"
    if thumb.is_file():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/png")).execute()
            rec["steps"]["thumbnail"] = "ok"
        except Exception as e:  # noqa: BLE001 - unverified channels can't set thumbnails
            rec["steps"]["thumbnail"] = f"failed: {str(e)[:200]}"
    else:
        rec["steps"]["thumbnail"] = "none made yet"
    pl = ((read_json(VDATA / "channel.json", {}) or {}).get("playlists") or {}).get(lang, {}).get("id")
    if pl:
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pl, "resourceId": {
                "kind": "youtube#video", "videoId": vid}}}).execute()
            rec["steps"]["playlist"] = "ok"
        except Exception as e:  # noqa: BLE001
            rec["steps"]["playlist"] = f"failed: {str(e)[:200]}"
    else:
        rec["steps"]["playlist"] = "no playlist: artools video playlists --create"
    write_json(rec_p, rec)
    try:
        rec["steps"]["crosslink"] = crosslink(run, yt) or "waiting for the other edition"
    except Exception as e:  # noqa: BLE001 - the upload stands; `artools video release` links them later
        rec["steps"]["crosslink"] = f"failed: {str(e)[:200]}"
    write_json(rec_p, rec)
    return {"lang": lang, **rec}


def crosslink(run: Path, yt=None) -> list[str]:
    """When both editions are on YouTube, each description gets the other's link."""
    if yt is None:
        from .youtube import service
        yt = service()
    recs = {lang: read_json(run / "youtube" / f"{lang}.json", {}) or {} for lang in ("en", "ko")}
    if not all(r.get("video_id") for r in recs.values()):
        return []
    linked = []
    for la, other in (("en", "ko"), ("ko", "en")):
        v = yt.videos().list(part="snippet", id=recs[la]["video_id"]).execute()["items"][0]["snippet"]
        snippet = {k: v[k] for k in ("title", "categoryId", "defaultLanguage", "defaultAudioLanguage") if k in v}
        snippet["description"] = description(run, la, recs[other]["url"])
        snippet["tags"] = search_tags(run, la)
        yt.videos().update(part="snippet", body={"id": recs[la]["video_id"], "snippet": snippet}).execute()
        linked.append(la)
    return linked


def finish(run_id: str, wait_minutes: int = 60) -> dict:
    """After both uploads: wait for YouTube to finish processing, then set the thumbnails and cross-link the editions,
    which fail with 403 while a video is still processing (29 Oct 2026). Runs before clean, which deletes the thumbs."""
    import time
    from googleapiclient.http import MediaFileUpload
    from .youtube import service
    run = run_dir(run_id)
    yt = service()
    recs = {lang: read_json(run / "youtube" / f"{lang}.json", {}) or {} for lang in ("en", "ko")}
    ids = {lang: r["video_id"] for lang, r in recs.items() if r.get("video_id")}
    state = {}
    for _ in range(max(1, wait_minutes)):
        items = yt.videos().list(part="processingDetails", id=",".join(ids.values())).execute().get("items", [])
        state = {i["id"]: (i.get("processingDetails") or {}).get("processingStatus") for i in items}
        if state and all(v in ("succeeded", "failed", "terminated") for v in state.values()):
            break
        time.sleep(60)
    for lang, vid in ids.items():
        rec, thumb = recs[lang], run / "video" / f"{lang}-thumb.png"
        if not str(rec["steps"].get("thumbnail", "")).startswith("ok") and thumb.is_file():
            try:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/png")).execute()
                rec["steps"]["thumbnail"] = "ok (after processing)"
            except Exception as e:  # noqa: BLE001
                rec["steps"]["thumbnail"] = f"failed: {str(e)[:200]}"
        write_json(run / "youtube" / f"{lang}.json", rec)
    try:
        linked = crosslink(run, yt)
    except Exception as e:  # noqa: BLE001
        linked = f"failed: {str(e)[:200]}"
    for lang in ids:
        rec = read_json(run / "youtube" / f"{lang}.json")
        rec["steps"]["crosslink"] = linked
        write_json(run / "youtube" / f"{lang}.json", rec)
    res = {"processing": state, "thumbnail": {lang: recs[lang]["steps"].get("thumbnail") for lang in ids}, "crosslink": linked}
    old = (read_json(run / "run.json", {}) or {}).get("replaces")
    if old and len(ids) == 2:                  # a correction's revision is up: retire the older one
        try:
            res["replaced"] = unlist(old)
        except Exception as e:  # noqa: BLE001 - the new revision stands; unlist the old one by hand
            res["replaced"] = f"failed: {str(e)[:200]}; run `artools video unlist {old}`"
    return res


def unlist(run_id: str) -> dict:
    """Both editions of an older video revision made unlisted (a new revision replaces it). The link keeps
    working for anyone who has it; nothing is deleted."""
    from .youtube import service
    run = run_dir(run_id)
    yt = service()
    out = {}
    for lang in ("en", "ko"):
        rec_p = run / "youtube" / f"{lang}.json"
        rec = read_json(rec_p, {}) or {}
        if not rec.get("video_id"):
            continue
        items = yt.videos().list(part="status", id=rec["video_id"]).execute().get("items") or []
        if not items:
            out[lang] = "not found on YouTube"
            continue
        status = {k: v for k, v in items[0]["status"].items()        # keep every other flag as it is
                  if k in ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids", "containsSyntheticMedia")}
        status["privacyStatus"] = "unlisted"
        yt.videos().update(part="status", body={"id": rec["video_id"], "status": status}).execute()
        rec.update(privacy="unlisted", unlisted=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        write_json(rec_p, rec)
        out[lang] = rec["url"]
    return {"run": run.name, "unlisted": out}


def release(run_id: str, lang: str, at: str | None = None) -> dict:
    """An uploaded edition made public now, or scheduled (`at`, while it is still private)."""
    from .youtube import service
    run = run_dir(run_id)
    rec_p = run / "youtube" / f"{lang}.json"
    rec = read_json(rec_p, {}) or {}
    if not rec.get("video_id"):
        raise RuntimeError("not uploaded yet: artools video publish <run> --lang " + lang)
    yt = service()
    status = {"privacyStatus": "private", "publishAt": at} if at else {"privacyStatus": "public"}
    pub = cfg("publish")["youtube"]
    status.update(selfDeclaredMadeForKids=pub["made_for_kids"], containsSyntheticMedia=pub["synthetic_media"])
    yt.videos().update(part="status", body={"id": rec["video_id"], "status": status}).execute()
    rec.update(privacy="scheduled" if at else "public", released=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               publish_at=at)
    write_json(rec_p, rec)
    return {**rec, "linked": crosslink(run, yt)}
