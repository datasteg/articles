---
name: make-slides
description: Render the video explainer's slides - the article's own components at 1920x1080 in the site's dark theme, every build step, both languages - through the local studio, look at the contact sheets and the flagged frames, and fix what reads badly by shortening slide wording or adjusting a slide's template, chart or build steps. Never touches the narration. Writes slides/slides.json.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob
metadata:
  version: 0.1.0
  family: stage
---
# make-slides

## Purpose

The slides show a part of what the narrator says: the exact number, the chart, a few words of label. They are the
article page's components at video size (`apps/studio`, `guides/video.md` § For the eye), so you don't design
anything: you check that this video's words and charts fit those components, and fix the words when they don't.
Viewers watch on phones, so every label must read at a quarter of the screen.

## Inputs

- `storyboard.json` (templates, charts, builds) and `script/en.json`, `script/ko.json` (`slides` wording), written by
  `write-video-script` and passing `artools check video-script`.
- `guides/video.md` § For the eye and § Templates.
- In fix mode, `review.json`: fix every blocking issue whose `owner` is `make-slides`.

## Steps

1. `artools run start $run_id make-slides --version 0.1.0`
2. `artools video slides $run_id`. It resolves every token, renders each slide and build step through the studio at
   1920×1080 into `slides/<lang>/<slide>-<step>.png`, draws `slides/<lang>-sheet.png`, and lists in
   `slides/render.json` → `problems` anything that runs into the caption zone or past a side margin.
3. Read both contact sheets first. Then open the frames `render.json` flags, and any slide the sheet makes you doubt.
   Look for:
   - text that runs into the hatched caption zone or is cut off, or a headline that takes three lines;
   - a chart whose highlight or annotation doesn't show the thing the beat names, or whose labels collide;
   - a build step that changes nothing visible;
   - Korean broken mid-word, English words in a Korean slide where the article has a Korean term, boxes for missing
     glyphs;
   - a slide that says something the narration doesn't (compare with the beat's `spoken`);
   - two slides in a row that look the same.
4. Fix, in this order of preference:
   - shorten the slide wording in `script/<lang>.json` → `slides` (never `beats`);
   - in `storyboard.json` → `slides`, change a slide's `steps`, `builds`, `chart` or `template`, keeping its id, part
     and facts.

   Then run `artools check video-script --run $run_id` (it must still pass) and render again:
   `artools video slides $run_id --only s05 s07` for just the slides you changed. Three rounds at most.
5. Write `slides/slides.json` (`contracts/video/slides.schema.json`):
   - `rounds`;
   - `checked`: what each look covered and changed;
   - `accepted`: any `render.json` problem you judged fine, with the reason (a figure's axis label sitting 2 px into
     the zone, say);
   - `for_editor`: what the editor should glance at in gate V, with slide ids.
6. `artools run done $run_id make-slides`. It checks that every frame exists and that every remaining problem is
   accepted with a reason.

## Judgement

- The slide is a subset of the narration. If wording must go, cut the slide's words, not the narrator's.
- A number slide shows one number. A figure slide's headline is the takeaway, as in the article.
- Korean slides are worded like a Korean newspaper headline ("2012년 이후 최대"), not a translation of the English.

## Never

- Change `beats`, `spoken`, `parts` or any fact token's id. The narration and the facts belong to
  `write-video-script`, and the review checks them against the article.
- Edit the studio (`apps/studio`), the site (`apps/web`) or the shared packages: the components are shared. Report a
  layout fault in `for_editor` instead.
- Add a chart the article doesn't have, or data to one.
