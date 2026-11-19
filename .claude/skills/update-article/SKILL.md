---
name: update-article
description: Update a published article after the editor reviewed it on the site - turn the editor's notes (or the issues the publication left, publish.json → review_left) into owned fixes, rerun the owning stages and one review, republish the same slug with its first date kept, an updated date and, for a change of substance, a correction readers see, then bring the YouTube video in line (D13). Use when the editor gives notes on a live article or its video.
argument-hint: <slug> <notes>
arguments: [slug, notes]
allowed-tools: Bash(artools *) Read Write Glob
metadata:
  version: 0.1.0
  family: front-end
---
# update-article

Since 31 Oct 2026 articles and videos go live without the editor (`config/editorial.yaml` → `gates`). The editor reviews them on articles.datasteg.com and YouTube, then sends notes. This skill applies them to the live article without asking anything more. When a note is ambiguous, take its most literal reading and say so in the report.

## Steps

**A data-desk note** (`config/pipelines/data-note.yaml`, runs named `<date>-desk…`): `artools drive` does not run
it. Do steps 1–2 for the record, then `artools desk update <run> --note "<the editor's note>" --only <places>` does
3–6: one rewrite of the named places only (`dek`, `insight`, `sections.2.blocks.5`; every other string stays as
published), the checker, the judge, the Korean of what changed (qkr), the PDF proof, and `artools ship`. Add
`--correction "<one English sentence>"` for a change of substance (qkr drafts its Korean). Always pass `--only`: on
17 Nov 2026 a dek fix without it also rewrote two other sentences and five Korean strings.

1. **Find the runs.** `content/articles/$slug/meta.json` → `run.id` is the article run (`/data/articles/runs/<run>`); read its `publish.json` (`review_left`, `cover_left_out`) and `review.json`. The video runs are `/data/articles/runs/*-$slug-video*/` (Glob their `run.json`); the current one is the newest whose `youtube/en.json` → `privacy` is `public`.
2. **Turn the notes into issues.** One blocking issue per note:
   `{"where": "<section heading and the sentence's first words>", "issue": "<the editor's point>", "fix": "<the editor's wording, if given>", "owner": "<stage>", "from": "editor", "kind": "wording | substance"}`.
   - Owners: `analyze-data` (a number is wrong or missing), `draft-article` (words, citations, glossary), `make-charts` (a chart), `make-cover` (the cover).
   - `substance`: a number, a fact, a quote or the answer changes. `wording`: style, clarity, typos, layout, a chart's look.
   - "Fix what the review left" means: take `publish.json` → `review_left` (full text in `review.json`) as the notes.
   Save the current `review.json` as `update/review-<YYYY-MM-DD>.json`, then write a new `review.json`: `{"status": "changes_required", "round": "update-<YYYY-MM-DD>", "blocking": [...], "advisory": [], "summary": "Editor's notes of <date>"}`.
3. **Fix.** In pipeline order, each owner that has an issue, in fix mode (`--only` reads the issues it owns): `artools drive <run> --only analyze-data`, then `--only draft-article` (always after analyze-data: the words carry the facts), `--only make-charts` (when it or analyze-data had issues), `--only make-cover`.
4. **Review once.** `artools drive <run> --only review-article`. If it says an editor's note was not done, run that owner and the review once more. Anything else it leaves goes live and is listed in `publish.json` → `review_left`, as on first publication.
5. **Corrections.** For each `substance` issue, add an entry to `<run>/corrections.json` (a JSON array; keep the earlier entries): `{"date": "<YYYY-MM-DD>", "text": {"en": "…", "ko": "…"}}`. Write one plain sentence: what the earlier version said, and what is right. The site shows it under "Corrections"; the video descriptions show it too. A `wording` fix gets no entry.
6. **Republish.** `artools ship <run>`. The publish gate is still approved. `ship` keeps the first `date`, sets `updated`, carries the corrections, prints the PDFs again, deploys, and keeps the earlier publication in `publish.json` → `previous`. If uncommitted changes under `articles/` from another session block it, message the peer sessions (`ListAgents`, `SendMessage`) to commit them, then ship again.
7. **Video,** when a video run exists:
   - only `wording` fixes: leave the video;
   - corrections added but the video's content still holds (the correction is about a sentence the video doesn't use): `artools video meta <video-run>` (the descriptions list the corrections);
   - a `substance` fix that the video repeats (a number, a quote or the answer it uses): `artools video auto $slug --replaces <video-run>`. It makes a new revision in the background, and once both editions are up it unlists the old ones (never deletes them).
8. **Report.** For each note, what changed and where; the review's leftovers; the correction lines; the URLs, tag and commit; and what happened to the video (left, descriptions refreshed, or new revision run with its log).

## Never

- Change the slug, or edit `content/` by hand: the owners fix the run, `ship` republishes.
- Fix a run file yourself: the owning stage does, so the trail stays clear.
- Delete a video, or unlist one before its replacement is up.
- Write a correction for a wording fix, or leave out one for a changed number, quote or answer.
