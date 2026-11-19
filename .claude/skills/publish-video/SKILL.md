---
name: publish-video
description: The video explainer's last step - check that both editions are public on YouTube with their captions, synthetic-media label, playlist and links to each other, fix what didn't stick, and report the links to the editor. Uploading (public, since 26 Oct 2026) is the driver's upload step; the editor reviews the public videos afterwards and asks for corrections (D13, through update-article).
argument-hint: <run-id> [en|ko]
arguments: [run_id, lang]
allowed-tools: Bash(artools *) Read
metadata:
  version: 0.2.0
  family: stage
---
# publish-video

## Purpose

The last step of the video pipeline. Since 26 Oct 2026 the editor publishes directly: the driver's
`upload` step puts each edition on YouTube as a **public** video (`artools video publish`, privacy from
`config/video/publish.yaml`), after `review-video`. This step checks the result and reports it.

## Steps

1. `artools video status $run_id`, and `youtube/<lang>.json` for each edition: `video_id`, `privacy` public, steps
   `captions` and `playlist` ok, `crosslink` done. An edition not uploaded yet: `artools video publish $run_id --lang <lang>`.
2. If the cross-links are missing (one edition was uploaded later or failed), `artools video release $run_id --lang <lang>`
   sets it public and links both descriptions.
3. Report both public links, anything that failed (a thumbnail, captions), the leftover review issues and misread
   beats from `youtube/<lang>.json` → `steps`, and one reminder for the editor's review: **Altered content** in
   YouTube Studio should say Yes on both videos (the API accepts the flag but doesn't echo it back). Don't wait for it.

## Never

- Upload a placeholder (silent) video: `publish` refuses it; don't work around it.
- Delete a public video. A correction follows the `update-article` skill: for wording, the
  article's correction appears in the description (`artools video meta <run>`); for a number or the answer, a new
  revision (`artools video auto <slug>`) and the old one unlisted (`artools video unlist <old-run>`).
- Schedule (`release --at`) or unlist without the editor's word.
