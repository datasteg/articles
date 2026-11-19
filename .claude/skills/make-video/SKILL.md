---
name: make-video
description: The explainer's last step - turn the article that was just published into a video in English and Korean and publish both on the datasteg YouTube channel. Since 29 Oct 2026 the default is the podcast video (config/video/podcast-pipeline.yaml - NotebookLM's two-host conversation in the editor's Chrome, slides cut to it, review, public upload, disk cleaned); the narrated video (config/video/pipeline.yaml) stays as --mode narrated. Starts the run in the background with artools video auto, and reports where to follow it. Started by the driver right after the ship (config/editorial.yaml → gates.video), by publish-article when a ship was retried by hand, or for an article already live.
argument-hint: <article-run-id or slug>
arguments: [run_or_slug]
allowed-tools: Bash(artools *) Read
metadata:
  version: 1.0.0
  family: stage
---
# make-video

## Purpose

Every published explainer also becomes a video on YouTube (`guides/video.md`). The video is
made from the article as it is now live in `content/`, never from the run's research, so it adds nothing the review
didn't check. It is published directly, both editions public and linked to each other (the editor's choice, 26 Oct
2026).

## Steps

1. Find the slug: the argument, or `publish.json` → `slug` in the article run (`/data/articles/runs/<run>/`).
   The article must be live (`content/articles/<slug>/meta.json` with `review.approved`).
2. Which video: `config/video/podcast.yaml` → `default_mode` (podcast since 29 Oct 2026, `guides/video-podcast.md`).
   The podcast needs the editor's Chrome open on dev-host, signed in to notebook.google.com, with Claude in Chrome
   connected; if it isn't, say so and stop. `artools video doctor --online`. If the Gemini key, the YouTube token or the narrator voices are missing, stop and
   tell the editor what is missing.
3. `artools video auto <slug>` (add `--mode narrated` for the solo narrator). For the podcast the pipeline is
   `make-podcast` (Chrome) → transcribe → `make-podcast-slides` → assemble → `review-podcast` → upload (public, both
   editions, linked) → clean (audio, frames and video deleted) → `publish-video`. For the narrated video: It makes the video run (`<date>-<slug>-video`) and starts `artools drive` on it in the
   background, logging to `<video-run>/logs/drive.out`. The video pipeline then runs by itself:
   `write-video-script` → `make-slides` → voice (Gemini TTS) → assemble → `review-video` → upload (public, both
   editions, linked) → `publish-video` (checks and reports).
4. Report the video run id, the log, and that the videos appear on https://www.youtube.com/@datasteg in about an hour.

## Judgement

- Gemini's voice model allows 100 requests a day at Tier 1, and one video uses about 90. If the voice step stops on
  the daily limit, the run keeps every finished beat: run `artools drive <video-run>` again after the limit resets
  (Google's message says when).
- A video may run longer than ten minutes when the article needs it; the length check allows up to about fifteen.

## Never

- Start a second video for the same article while one is running (`artools video status <video-run>`).
- Publish an edition with beats still misread, or a silent placeholder: `artools video publish` refuses both.
