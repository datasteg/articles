---
name: publish-article
description: Publish an article run whose publish gate is approved (by the driver under config/editorial.yaml → gates.auto, or by the editor) - write it into content/, print its PDF editions, run the site's checks and build, commit on main, deploy to articles.datasteg.com with ds deploy (all through artools ship), then start the YouTube video. The driver does this itself for unattended runs; use it by hand to retry a failed ship.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Bash(git *) Bash(pnpm *) Bash(ds *) Bash(curl *) Read
metadata:
  version: 0.4.0
  family: stage
---
# publish-article

Since 31 Oct 2026 the editor publishes without reviewing first (`config/editorial.yaml` → `gates`: `auto`, `on_blocking: publish`, `video`): the driver approves the gate, ships and starts the video. Use this skill when that ship failed, or when the editor types `/publish-article <run-id>`. Don't ask the editor before shipping.

1. `artools run status $run_id`: gate `publish` must be approved. If not, stop and say so.
2. `artools ship $run_id --dry-run`: writes the article into `content/`, runs the production content checks, and undoes the write. Fix nothing by hand; if it fails, report the problem.
3. `artools ship $run_id`. It refuses a run whose pipeline makes a cover or proofs a PDF until `make-cover` and `make-pdf` are done; then, under one machine-wide lock, it:
   - pulls `main`; staged changes or changes under `articles/` stop it, another session's work elsewhere doesn't (if another session's files under `articles/` block it, message the peer sessions to commit them; never stash or delete them);
   - writes `content/articles/<slug>/` (the quotes were verified by the stages and the review), with `meta.json` → `citation` stamped from `config/editorial.yaml` → `citation` (author, publisher) and the article's title, date and URLs: the "Cite this article" block readers copy. Every article type gets it;
   - prints the PDF edition of each language from the published article (`artools pdf <slug>`): `content/articles/<slug>/pdf/<lang>.pdf`, recorded in `meta.json` → `pdf`, served as `/pdf/<slug>-<lang>.pdf` and linked from the article's header and its "Cite this article" block;
   - runs the content checks (they fail an approved article without a citation that matches its titles and URLs, or without a PDF of each edition printed from the edition as it now is);
   - commits "article: <slug>" and pushes;
   - runs `ds deploy articles <YYYYMMDD.N>`;
   - checks `/health`, the article URL and the PDFs;
   - writes `publish.json` (with `review_left`, the blocking issues that went live, and `cover_left_out`, a cover that failed its check) and marks the stage done;
   - removes this app's older local Docker images, keeping the live one.
   If the deploy fails it reverts and pushes the commit, so `main` matches what is live.
4. The video (the explainer's last step, `video`), unless the driver already started it: `artools video auto <slug>`. It starts the video pipeline in the
   background (script, slides, Gemini voice, review, public upload of both editions to the datasteg YouTube channel);
   see the `make-video` skill. If `artools video doctor --online` reports a missing key or token, skip it and say so.
5. Report, for the editor's review on the site: each `review_left` issue in one line and `cover_left_out`; corrections go through `/update-article`. Then the URLs (`/en/a/<slug>`, `/ko/a/<slug>`), the PDFs (`/pdf/<slug>-en.pdf`, `/pdf/<slug>-ko.pdf`, with their pages from `publish.json`), the tag, the commit, and the English citation line as the article now shows it (from `content/articles/<slug>/meta.json` → `citation`): author (year), "title", publisher, date, URL; and the video run id with its log.

Never deploy from a branch other than `main`, never write `content/` for a run whose publish gate is closed, never commit run files. Authorship checks (citations, source lines, unpublishable data, another run's slug) are hard stops: fix the cause in the owning stage, never work around them.
