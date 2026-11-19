"""artools: the command line the skills call. Every command prints JSON."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from .paths import ARTICLES, out, run_dir


def main() -> None:
    p = argparse.ArgumentParser(prog="artools", description=__doc__)
    sub = p.add_subparsers(dest="group", required=True)

    # ---- run
    r = sub.add_parser("run", help="create and track runs").add_subparsers(dest="cmd", required=True)
    x = r.add_parser("new"); x.add_argument("question"); x.add_argument("--id")
    x.add_argument("--type", default="explainer", help="the article type: a pipeline in config/pipelines/")
    x.add_argument("--model", help="model for every stage session, e.g. claude-fable-5-1 (default: the CLI's)")
    x.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="effort for every stage session")
    x = r.add_parser("runtime", help="show or set a run's model and effort"); x.add_argument("run")
    x.add_argument("--model"); x.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"]); x.add_argument("--note")
    x = r.add_parser("status"); x.add_argument("run", nargs="?")
    x = r.add_parser("start"); x.add_argument("run"); x.add_argument("stage"); x.add_argument("--version"); x.add_argument("--model")
    x = r.add_parser("done"); x.add_argument("run"); x.add_argument("stage"); x.add_argument("--note")
    x = r.add_parser("fail"); x.add_argument("run"); x.add_argument("stage"); x.add_argument("reason")
    x = r.add_parser("gate"); x.add_argument("run"); x.add_argument("name", help="a gate of the run's pipeline")
    x.add_argument("--approve", action="store_true"); x.add_argument("--by"); x.add_argument("--note"); x.add_argument("--override")

    # ---- jejualps
    j = sub.add_parser("jejualps", help="the archive, read-only").add_subparsers(dest="cmd", required=True)
    j.add_parser("ping")
    x = j.add_parser("search"); x.add_argument("--q", required=True); x.add_argument("--fields", choices=["meta", "body"], default="meta")
    x.add_argument("--from", dest="date_from"); x.add_argument("--to", dest="date_to"); x.add_argument("--units", nargs="*")
    x.add_argument("--limit", type=int, default=30); x.add_argument("--no-snippet", action="store_true")
    x.add_argument("--detail", choices=["lean", "why", "min"], default="lean",
                   help="why adds a keyword sentence and the best chunk's headline; min prints title lines only")
    x = j.add_parser("doc"); x.add_argument("doc", type=int)
    x = j.add_parser("cite", help="citation fields for Evidence doc blocks"); x.add_argument("docs", nargs="+", help="<id> or jejualps:<id>")
    x = j.add_parser("card"); x.add_argument("doc", type=int)
    x = j.add_parser("segments"); x.add_argument("doc", type=int); x.add_argument("--kinds", nargs="*"); x.add_argument("--max-chars", type=int, default=30000)
    x = j.add_parser("chunks"); x.add_argument("doc", type=int); x.add_argument("--around"); x.add_argument("--start", type=int)
    x.add_argument("--count", type=int, default=3); x.add_argument("--max-chars", type=int, default=24000)

    # ---- quote
    qv = sub.add_parser("quote", help="verify a quote against the stored text").add_subparsers(dest="cmd", required=True)
    x = qv.add_parser("verify"); x.add_argument("doc"); x.add_argument("quote")

    # ---- reading
    rd = sub.add_parser("reading", help="the reading-note cache").add_subparsers(dest="cmd", required=True)
    x = rd.add_parser("get"); x.add_argument("doc", help="jejualps:<id> or <id>")
    x = rd.add_parser("save"); x.add_argument("file"); x.add_argument("--run")

    # ---- data
    d = sub.add_parser("data", help="series").add_subparsers(dest="cmd", required=True)
    x = d.add_parser("ecb"); x.add_argument("action", choices=["get"]); x.add_argument("key"); x.add_argument("--run", required=True)
    x.add_argument("--indicator", required=True); x.add_argument("--from", dest="start"); x.add_argument("--id")
    x.add_argument("--scout", action="store_true"); x.add_argument("--range"); x.add_argument("--anchor", action="append"); x.add_argument("--geo")
    x = d.add_parser("eurostat"); x.add_argument("action", choices=["get"]); x.add_argument("dataset"); x.add_argument("--params", required=True)
    x.add_argument("--geo", required=True, help="comma-separated Eurostat geo codes (EL = Greece)"); x.add_argument("--run", required=True)
    x.add_argument("--indicator", required=True); x.add_argument("--id-prefix", required=True); x.add_argument("--since")
    x.add_argument("--scout", action="store_true"); x.add_argument("--range")
    x = d.add_parser("fred", add_help=False); x.add_argument("rest", nargs=argparse.REMAINDER)
    x = d.add_parser("ecos", add_help=False); x.add_argument("rest", nargs=argparse.REMAINDER)
    x = d.add_parser("query"); x.add_argument("run"); x.add_argument("--sql"); x.add_argument("--limit", type=int, default=200)

    # ---- analysis
    a = sub.add_parser("analysis", help="run the stage's analysis.py in the pipeline's environment").add_subparsers(dest="cmd", required=True)
    x = a.add_parser("run"); x.add_argument("run")

    # ---- validate, check
    x = sub.add_parser("validate", help="a stage's output against its contract"); x.add_argument("stage"); x.add_argument("run")
    x = sub.add_parser("check", help="mechanical checks"); x.add_argument("what", nargs="+",
                                                                     choices=["numbers", "style", "licences", "readability", "charts", "links", "glossary", "cover", "pdf", "video-script", "all"])
    x.add_argument("--run", required=True)

    # ---- render, preview, publish, drive
    rn = sub.add_parser("render", help="screenshots through the real web components").add_subparsers(dest="cmd", required=True)
    x = rn.add_parser("charts"); x.add_argument("run"); x.add_argument("--langs", nargs="*", default=["en", "ko"]); x.add_argument("--themes", nargs="*", default=["light", "dark"])
    x = rn.add_parser("page"); x.add_argument("run"); x.add_argument("--lang", default="en"); x.add_argument("--theme", default="light"); x.add_argument("--width", type=int, default=1040)
    x = rn.add_parser("cover", help="the cover on its card in the list, both themes and widths, and enlarged"); x.add_argument("run")
    x = rn.add_parser("pdf", help="the PDF edition's proof: each edition printed into <run>/pdf/, with page images"); x.add_argument("run")
    x = sub.add_parser("preview", help="write the run into .preview/ for the local site"); x.add_argument("run"); x.add_argument("--slug")
    x = sub.add_parser("publish", help="write an approved run into content/"); x.add_argument("run"); x.add_argument("--slug", required=True)
    x = sub.add_parser("ship", help="publish, check, commit, push and deploy an approved run, under one lock")
    x.add_argument("run"); x.add_argument("--slug"); x.add_argument("--tag"); x.add_argument("--dry-run", action="store_true")
    x = sub.add_parser("pdf", help="print published articles' PDF editions from content/ (ship does it for the article it publishes)")
    x.add_argument("slugs", nargs="*", help="article slugs; none prints every published article")
    x = sub.add_parser("preview-server", help="the shared preview site on port 3311"); x.add_argument("action", choices=["start", "stop"])
    x = sub.add_parser("images", help="this app's local Docker images").add_subparsers(dest="cmd", required=True)
    y = x.add_parser("prune", help="remove every local articles image except the live tag (ship does this after a deploy)")
    y.add_argument("--keep", help="the tag to keep (default: the live one, from ds status)")
    x = sub.add_parser("usage", help="tokens and list-price cost of a run, by stage and model (writes usage.json)")
    x.add_argument("run"); x.add_argument("--table", action="store_true", help="a markdown table instead of JSON")
    x = sub.add_parser("received", help="characters each artools subcommand returned, per stage, over runs (markdown)")
    x.add_argument("runs", nargs="+"); x.add_argument("--prefix", default="jejualps", help="subcommands starting with this ('' for all)")
    x = sub.add_parser("ledger", help="reduce runs to /data/articles/ledger (the admin Newsroom, dev only; never committed)")
    x.add_argument("runs", nargs="*"); x.add_argument("--all", action="store_true", help="every run")
    x.add_argument("--no-catalog", action="store_true", help="skip catalog.json (pipelines, skills, revisions)")
    x.add_argument("--deploy", action="store_true", help="then deploy the admin site with the ledger (newsroom.deploy)")
    x = sub.add_parser("logs", help="stage logs of finished runs: archive (zstd, images out) and prune to summaries").add_subparsers(dest="cmd", required=True)
    x.add_parser("status", help="plain, archived and pruned logs per run")
    y = x.add_parser("archive", help="archive one run's plain logs now"); y.add_argument("run")
    y = x.add_parser("prune", help="replace one run's logs with their summaries now"); y.add_argument("run")
    y = x.add_parser("tidy", help="what the driver does after every drive"); y.add_argument("--keep-days", type=int)
    x = sub.add_parser("drive", help="run the pipeline"); x.add_argument("run", help="a run id, or a question in quotes for a new run")
    x.add_argument("--only"); x.add_argument("--until", help="stop after this step id or skill")
    x.add_argument("--type", default="explainer", help="the article type, for a new run")
    x.add_argument("--allow-sample", action="store_true", help="run a pipeline whose status is sample (skills in draft)")
    x.add_argument("--model", help="for a new run: model for every stage session")
    x.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], help="for a new run: effort")
    x = sub.add_parser("compare", help="runs side by side: type, model, effort, tokens, cost, output, review rounds")
    x.add_argument("runs", nargs="+"); x.add_argument("--table", action="store_true")
    pl = sub.add_parser("pipelines", help="article types and their pipelines (config/pipelines/)").add_subparsers(dest="cmd", required=True)
    pl.add_parser("list"); pl.add_parser("check")
    x = pl.add_parser("show"); x.add_argument("id")
    x = pl.add_parser("mermaid"); x.add_argument("id"); x.add_argument("--lang", default="en")
    x = pl.add_parser("docs", help="regenerate docs/PIPELINES.md")

    # ---- the data desk
    dk = sub.add_parser("desk", help="the data desk: a daily note from datasteg's own apps, reviewed, scored and queued for approval").add_subparsers(dest="cmd", required=True)
    x = dk.add_parser("watch", help="what changed in the apps since the last note (no model)")
    x = dk.add_parser("leads", help="today's leads from the screens, best first (no model)"); x.add_argument("--offline", action="store_true")
    x = dk.add_parser("note", help="write today's note: editor, analyst, writer, reviewers, judge; ends queued or shelved")
    x.add_argument("--id", help="run id (default <date>-desk)"); x.add_argument("--lead", help="force a lead key from `desk leads`")
    x.add_argument("--offline", action="store_true", help="read only the API cache"); x.add_argument("--rounds", type=int)
    x.add_argument("--rewrite-of", dest="rewrite_of", help="a note this one rewrites from the same lead (its run id); the editor is told so")
    x.add_argument("--why", help="with --rewrite-of: why the old note is rewritten")
    x.add_argument("--idea", help="write the note for a question of the ideas preview, as <date>:<Q id> (e.g. 2026-11-20:Q5)")
    x = dk.add_parser("replay", help="the refined review stages (lints, inference test, Korean checks) on a stored run's draft, writing nothing into the run")
    x.add_argument("run"); x.add_argument("--against", help="match the conclusions against this run's claims (the note that regenerates it)")
    x.add_argument("--no-model", action="store_true", help="code checks only: no inference test")
    x = dk.add_parser("compare", help="set an old note beside the note that regenerates it; written to the new run's desk/compared.json")
    x.add_argument("old"); x.add_argument("new"); x.add_argument("--replay", help="the old note's replay.json (for its inference test)")
    x = dk.add_parser("daily", help="the cron entry: sync approvals and ship them, then write today's note if the data changed and none is waiting")
    x.add_argument("--force", action="store_true", help="write a note even when nothing changed"); x.add_argument("--no-deploy", action="store_true")
    x = dk.add_parser("status", help="a desk run's result, scores and cost, or every desk run"); x.add_argument("run", nargs="?")
    x = dk.add_parser("show", help="the note as text: reader (default), review (with fact ids) or judged"); x.add_argument("run")
    x.add_argument("--view", choices=["reader", "review", "judged"], default="reader")
    x = dk.add_parser("calibrate", help="score the benchmark set with the judge (sets the bar)"); x.add_argument("--n", type=int, default=2)
    x.add_argument("--only", nargs="*")
    x = dk.add_parser("rejudge", help="score a run's note again"); x.add_argument("run"); x.add_argument("--n", type=int, default=2)
    x = dk.add_parser("korean", help="draft the Korean edition of a note with qkr (every Korean string is qkr's), check it and write draft/ko.json")
    x.add_argument("run"); x.add_argument("--redo", action="store_true", help="draft every string again, not only what changed")
    x = dk.add_parser("ideas", help="the ideas preview: today's questions from what is new, scored by lay readers (writes no note)")
    x.add_argument("--force", action="store_true", help="write today's ideas again")
    x = dk.add_parser("queue", help="write the review queue for the admin site (and deploy it with --deploy)"); x.add_argument("--deploy", action="store_true")
    x = dk.add_parser("sync", help="read the editor's decisions from the admin site; ship what was approved"); x.add_argument("--dry-run", action="store_true")
    x = dk.add_parser("withdraw", help="the desk takes back its own waiting note (a data or code error); its lead may be written again")
    x.add_argument("run"); x.add_argument("--why", required=True)
    x = dk.add_parser("update", help="the editor's note on a published note: one rewrite, checks, Korean (qkr), PDF proof, republish (update-article for the desk)")
    x.add_argument("run"); x.add_argument("--note", required=True)
    x.add_argument("--correction", help="for a change of substance: one English sentence readers see under Corrections (qkr drafts its Korean)")
    x.add_argument("--only", help="the places the note may change, comma-separated (dek,insight,sections.2.blocks.5); the rest stays as published")
    x.add_argument("--ko", action="append", help="a point on the published Korean, '<string id>: <the problem>' (d:insight/text: …); the checker answers it and qkr drafts that string again")
    x = dk.add_parser("decide", help="record a decision by hand, as the admin site would (the editor's own terminal)")
    x.add_argument("run"); x.add_argument("decision", choices=["approve", "return", "reject", "retitle"]); x.add_argument("--by", required=True)
    x.add_argument("--note"); x.add_argument("--title-ko", dest="title_ko", help="the editor's own Korean title, used as written (retitle, or with any decision)")

    # ---- video
    v = sub.add_parser("video", help="the video explainer of a published article").add_subparsers(dest="cmd", required=True)
    x = v.add_parser("start", help="a video run for a published article"); x.add_argument("slug"); x.add_argument("--id")
    x.add_argument("--model"); x.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    x.add_argument("--mode", choices=["podcast", "narrated"], help="default: config/video/podcast.yaml → default_mode")
    x = v.add_parser("auto", help="the explainer's video step: start a video run for a live article and drive it in the background")
    x.add_argument("slug"); x.add_argument("--mode", choices=["podcast", "narrated"])
    x.add_argument("--replaces", help="an older video run of this article: unlisted once this revision is up (a correction)")
    x = v.add_parser("status"); x.add_argument("run")
    x = v.add_parser("facts", help="the run's facts with their tokens' written and spoken forms")
    x.add_argument("run"); x.add_argument("--grep", help="words that must all appear in the label or value")
    x = v.add_parser("render", help="a script string with its fact tokens rendered (written and spoken)")
    x.add_argument("run"); x.add_argument("text"); x.add_argument("--lang", default="en")
    x = v.add_parser("slides", help="render every slide and build step at 1920x1080, and the contact sheets")
    x.add_argument("run"); x.add_argument("--langs", nargs="*", default=["en", "ko"]); x.add_argument("--only", nargs="*")
    x = v.add_parser("transcript", help="what the narrator says, beat by beat, numbers as spoken")
    x.add_argument("run"); x.add_argument("--lang", choices=["en", "ko"], required=True)
    x.add_argument("--heard", action="store_true", help="the takes' transcriptions instead (after voice)")
    x = v.add_parser("voice", help="record the narration with Gemini TTS, transcribe and compare every take")
    x.add_argument("run"); x.add_argument("--lang", choices=["en", "ko"], required=True); x.add_argument("--beats", nargs="*")
    x.add_argument("--placeholder", action="store_true", help="silence of the estimated length, to test assembly")
    x.add_argument("--rescore", action="store_true", help="re-check the recorded takes from their transcripts; no TTS calls")
    x = v.add_parser("assemble", help="frames + narration → video/<lang>.mp4 with captions and chapters")
    x.add_argument("run"); x.add_argument("--lang", choices=["en", "ko"], required=True)
    x = v.add_parser("publish", help="upload an edition to YouTube as private, with captions and playlist, for the editor to watch")
    x.add_argument("run"); x.add_argument("--lang", choices=["en", "ko"], required=True)
    x = v.add_parser("release", help="after gate V: make an uploaded edition public, or schedule it (--at 2026-11-02T08:00:00+09:00)")
    x.add_argument("run"); x.add_argument("--lang", choices=["en", "ko"], required=True); x.add_argument("--at")
    x = v.add_parser("unlist", help="make both editions of an older video revision unlisted (a correction's new revision replaces it)")
    x.add_argument("run")
    x = v.add_parser("meta", help="refresh both editions' description, hashtags and tags on YouTube")
    x.add_argument("run")
    x = v.add_parser("channel", help="set the channel's introduction, keywords and Korean localization from config")
    x = v.add_parser("studio", help="the local slide studio (127.0.0.1:3313)"); x.add_argument("action", choices=["start", "stop"])
    x = v.add_parser("doctor", help="is the setup complete?"); x.add_argument("--online", action="store_true")
    x = v.add_parser("auth", help="connect to the YouTube channel")
    x.add_argument("step", choices=["url", "finish", "listen", "check"]); x.add_argument("address", nargs="?")
    x.add_argument("--minutes", type=int, default=15, help="listen: how long to wait")
    x = v.add_parser("playlists", help="the channel's playlists"); x.add_argument("--create", action="store_true")
    x = v.add_parser("podcast", help="the podcast video's steps (guides/video-podcast.md)")
    x.add_argument("action", choices=["plan", "source", "ingest", "transcribe", "check", "hear", "captions", "assemble", "thumb",
                                     "clean", "wait"])
    x.add_argument("run", nargs="?"); x.add_argument("--lang", choices=["en", "ko"]); x.add_argument("--file")
    x.add_argument("--notebook", help="ingest: the notebook's address"); x.add_argument("--title", help="ingest: the audio's title")
    x.add_argument("--seconds", type=int, default=240, help="wait: how long")
    x.add_argument("--at", type=float, help="hear: where, in seconds")
    x = v.add_parser("say", help="one test take with Gemini TTS"); x.add_argument("text"); x.add_argument("--lang", default="en")
    x.add_argument("--voice"); x.add_argument("--out")
    x = v.add_parser("audition", help="the same opening in every audition voice"); x.add_argument("--lang", default="en")
    x.add_argument("--voices", nargs="*")

    a = p.parse_args()
    g, c = a.group, getattr(a, "cmd", None)

    if g == "run":
        from . import runlib
        if c == "new":
            out(runlib.new(a.question, a.id, a.type, a.model, a.effort))
        elif c == "runtime":
            runlib.runtime(a.run, a.model, a.effort, a.note)
        elif c == "status":
            runlib.status(a.run)
        elif c == "start":
            runlib.start(a.run, a.stage, a.version, a.model)
        elif c == "done":
            runlib.done(a.run, a.stage, a.note)
        elif c == "fail":
            runlib.fail(a.run, a.stage, a.reason)
        elif c == "gate":
            runlib.gate(a.run, a.name, a.approve, a.by, a.note, a.override)
    elif g == "desk":
        from .desk import cli as D
        D.main(a)
    elif g == "jejualps":
        from . import jejualps as J
        if c == "ping":
            out(J.ping())
        elif c == "search":
            res = J.search_lines(a.q, a.fields, a.date_from, a.date_to, a.units, a.limit, not a.no_snippet, a.detail)
            lines = res.pop("results")
            for obj in [res, *lines]:      # a header line, then one line per document: half the characters of out()
                print(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str))
        elif c == "cite":
            out(J.cite([int(d.split(":")[-1]) for d in a.docs]))
        elif c == "doc":
            out(J.doc(a.doc))
        elif c == "card":
            out(J.card(a.doc))
        elif c == "segments":
            out(J.segments(a.doc, a.kinds, a.max_chars))
        elif c == "chunks":
            out(J.chunks(a.doc, a.around, a.start, a.count, a.max_chars))
    elif g == "quote":
        from . import jejualps as J
        doc = int(str(a.doc).split(":")[-1])
        out({"doc": doc, **J.verify_quote(doc, a.quote)})
    elif g == "reading":
        from . import readings
        if c == "get":
            src, _, did = a.doc.rpartition(":")
            out(readings.get(src or "jejualps", int(did)))
        else:
            out(readings.save(a.file, a.run))
    elif g == "data":
        from . import data
        if c == "ecb":
            out(data.ecb_get(a.key, a.run, a.indicator, a.start, a.id, a.scout, a.range, a.anchor, a.geo))
        elif c == "eurostat":
            out(data.eurostat_get(a.dataset, a.params, a.geo.split(","), a.run, a.indicator, a.id_prefix, a.scout, a.since, a.range))
        elif c in ("fred", "ecos"):
            sys.exit(data.passthrough(c, a.rest))
        elif c == "query":
            out(data.query(a.run, a.sql, a.limit))
    elif g == "analysis":
        run = run_dir(a.run)
        script = run / "analysis" / "analysis.py"
        rc = subprocess.call([sys.executable, str(script)], cwd=run)
        sys.exit(rc)
    elif g == "validate":
        from .validate import validate_stage
        probs = validate_stage(a.stage, run_dir(a.run))
        out({"stage": a.stage, "ok": not probs, "problems": probs})
        sys.exit(0 if not probs else 2)
    elif g == "check":
        from .checks import ALL, run_checks
        names = list(ALL) if "all" in a.what else a.what
        res = run_checks(a.run, names)
        out(res)
        sys.exit(2 if any(r["blocking"] for r in res.values()) else 0)
    elif g == "render":
        from . import render
        if c == "pdf":
            from . import pdf
            out(pdf.proof(a.run))
        else:
            out(render.charts(a.run, a.langs, a.themes) if c == "charts" else render.cover(a.run) if c == "cover"
                else render.page(a.run, a.lang, a.theme, a.width))
    elif g == "preview":
        from .content import preview
        from .render import slug_of
        out(preview(a.run, a.slug or slug_of(run_dir(a.run))))
    elif g == "publish":
        from .content import publish
        out(publish(a.run, a.slug))
    elif g == "ship":
        from .ship import ship
        out(ship(a.run, a.slug, a.tag, a.dry_run))
    elif g == "pdf":
        from . import pdf
        from .paths import CACHE, die
        from .runlib import flock_file
        with flock_file(CACHE / "publish.lock"):   # it writes content/, as ship does
            try:
                out(pdf.publish(a.slugs or None))
            except RuntimeError as e:
                die(str(e))
    elif g == "preview-server":
        from . import render
        from .paths import CACHE
        from .runlib import flock_file
        if a.action == "stop":
            out(render.stop_server())
        else:
            with flock_file(CACHE / "preview-server.lock"):
                render.serve()
            out({"url": f"http://127.0.0.1:{render.PORT}/en", "content_dir": str(render.PREVIEW)})
    elif g == "images":
        from .paths import CACHE
        from .runlib import flock_file
        from .ship import prune_images
        with flock_file(CACHE / "publish.lock"):
            out(prune_images(a.keep))
    elif g == "usage":
        from . import usage as U
        res = U.usage(a.run)
        print(U.table(res)) if a.table else out(res)
    elif g == "received":
        from .usage import received_table
        print(received_table(a.runs, a.prefix))
    elif g == "ledger":
        from .ledger import ledger
        from .paths import die
        if not a.runs and not a.all:
            die("give run ids or --all")
        res = ledger(a.runs, a.all, not a.no_catalog)
        if a.deploy:
            from .ledger import deploy_admin
            res["admin"] = deploy_admin(force=True)
        out(res)
    elif g == "logs":
        from . import logs as LG
        if a.cmd == "status":
            out(LG.status())
        elif a.cmd == "tidy":
            out(LG.housekeeping(a.keep_days))
        else:
            r = run_dir(a.run)
            if LG.busy(r):
                from .paths import die
                die(f"{r.name} has a stage running or a log written in the last ten minutes")
            out(LG.archive(r) if a.cmd == "archive" else LG.prune(r))
    elif g == "drive":
        from .drive import drive
        from .runlib import new
        rid = a.run
        if " " in rid:
            rid = new(rid, pipeline=a.type, model=a.model, effort=a.effort)["run"]
            print(f"new run {rid}", flush=True)
        sys.exit(drive(rid, a.only, a.until, a.allow_sample))
    elif g == "compare":
        from .usage import compare, compare_table
        res = compare(a.runs)
        print(compare_table(res)) if a.table else out(res)
    elif g == "pipelines":
        from . import pipelines as pls
        if c == "list":
            out({"pipelines": [{k: (p_ := pls.load(i))[k] for k in ("id", "version", "status")} | {"name": p_["name"]["en"],
                 "steps": len(p_["steps"]), "gates": pls.gates(p_)} for i in pls.ids()]})
        elif c == "show":
            out(pls.load(a.id))
        elif c == "check":
            res = {i: pls.check(pls.load(i)) for i in pls.ids() + list(pls.PRIVATE)}
            out({"ok": not any(res.values()), "problems": {k: v for k, v in res.items() if v}})
            sys.exit(1 if any(res.values()) else 0)
        elif c == "mermaid":
            print(pls.mermaid(pls.load(a.id), a.lang))
        elif c == "docs":
            from .paths import ARTICLES
            (ARTICLES / "docs" / "PIPELINES.md").write_text(pls.docs(), encoding="utf-8")
            out({"written": "docs/PIPELINES.md"})
    elif g == "video":
        from .paths import die
        try:
            _video(a, c)
        except RuntimeError as e:
            die(str(e))


def _video(a, c) -> None:
    if c == "start":
        from .video.run import start
        out(start(a.slug, a.id, a.model, a.effort, a.mode))
    elif c == "auto":
        from .video.run import auto
        out(auto(a.slug, a.mode, a.replaces))
    elif c == "status":
        from .video.run import status
        out(status(a.run))
    elif c == "facts":
        from .video.script import find_facts
        out(find_facts(run_dir(a.run), a.grep))
    elif c == "render":
        from .paths import read_json
        from .video.speech import render
        facts = {f["id"]: f for f in (read_json(run_dir(a.run) / "source" / "facts.json", {}) or {}).get("facts", [])}
        import re
        written = re.sub(r"\{\{(F\d+):spoken", r"{{\1", a.text)
        out({"written": render(written, facts, a.lang),
             "spoken": render(re.sub(r"\{\{(F\d+)", r"{{\1:spoken", written), facts, a.lang)})
    elif c == "slides":
        from .video.slides import shoot
        out(shoot(a.run, tuple(a.langs), a.only))
    elif c == "transcript":
        from .paths import read_json
        from .video.script import facts_of
        from .video.speech import render
        run = run_dir(a.run)
        if a.heard:
            vo = read_json(run / "audio" / a.lang / "voice.json", {}) or {}
            rows = [f"{b['beat']}: {b.get('heard') or '(not transcribed)'}" for b in vo.get("beats", [])]
        else:
            facts = facts_of(run)
            sc = read_json(run / "script" / f"{a.lang}.json", {}) or {}
            rows = [render(b["spoken"], facts, a.lang) for b in sc.get("beats", [])]
        print("\n\n".join(rows))
    elif c == "voice":
        from .video.voice import rescore, voice
        out(rescore(a.run, a.lang) if a.rescore else voice(a.run, a.lang, a.beats, a.placeholder))
    elif c == "assemble":
        from .video.assemble import assemble
        out(assemble(a.run, a.lang))
    elif c == "publish":
        from .video.publish import upload
        out(upload(a.run, a.lang))
    elif c == "release":
        from .video.publish import release
        out(release(a.run, a.lang, a.at))
    elif c == "unlist":
        from .video.publish import unlist
        out(unlist(a.run))
    elif c == "meta":
        from .video.publish import update_meta
        out(update_meta(a.run))
    elif c == "channel":
        from .video.youtube import update_channel
        out(update_channel())
    elif c == "studio":
        from .paths import CACHE
        from .runlib import flock_file
        from .video import slides
        if a.action == "stop":
            out(slides.stop())
        else:
            with flock_file(CACHE / "studio.lock"):
                slides.serve()
            out({"url": f"http://127.0.0.1:{slides.PORT}/"})
    elif c == "doctor":
        from .video.doctor import doctor
        res = doctor(a.online)
        out(res)
        sys.exit(0 if res["ok"] else 1)
    elif c == "auth":
        from .video import youtube
        if a.step == "url":
            out(youtube.auth_url())
        elif a.step == "listen":
            out(youtube.auth_listen(a.minutes * 60))
        elif a.step == "finish":
            if not a.address:
                raise RuntimeError("give the address the browser landed on: artools video auth finish '<address>'")
            out(youtube.auth_finish(a.address))
        else:
            out(youtube.channel())
    elif c == "playlists":
        from .video.youtube import playlists
        out(playlists(a.create))
    elif c == "podcast":
        from .video import podcast
        out(podcast.cli(a))
    elif c == "say":
        from .video.tts import say
        out(say(a.text, a.lang, a.voice, a.out))
    elif c == "audition":
        from .video.tts import audition
        out(audition(a.lang, a.voices))


if __name__ == "__main__":
    main()
