---
name: make-podcast-slides
description: Cut the article's slides to the NotebookLM conversation and make them tell the story - read each edition's timed transcript, build one slide library both editions share (the article's components - numbers, charts, terms, quotes, findings - plus flow chains that show what leads to what, a chapter card per part carrying the story so far, a story recap and a thumbnail), word it in both languages with each part's short label and takeaway, render it with its enter animations, write each edition's timeline, and translate each transcript into the other language's captions. Writes storyboard.json, script/<lang>.json, podcast/<lang>.timeline.json and asr/<lang>.<other>.json.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob
metadata:
  version: 2.0.0
  family: stage
---
# make-podcast-slides

## Purpose

The audio came first (make-podcast), so the slides follow it: when a host names a number, its tile is on screen; when
they explain how one thing leads to another, the flow builds step by step; when they turn to the next part, its chapter
card shows what the earlier parts found. A viewer glancing down sees the exact figure and where the story stands; a
listener who only hears loses nothing. Slides that only repeat what is said are wasted: each one adds the figure, the
mechanism or the place in the story.

Read `guides/video-podcast.md` first (§ The slides), then `guides/video.md` § For the eye and § Templates.

## Inputs

- `asr/<lang>.json`: the transcript in timed segments (`start`, `end`, `speaker`, `text`), one sentence each, times at
  the speakers' pauses (VibeVoice-ASR; speaker A is the lower voice); `asr/<lang>.check.json`.
- `podcast/plan.json` (the parts), `source/<lang>.json`, `source/charts/*.json`, `source/facts.json`.
- In fix mode, `review.json`: fix every blocking issue whose `owner` is `make-podcast-slides`.

## How the slides move (automatic)

Every podcast slide enters with a mild animation (`apps/studio/app/studio.css` § motion): text rises a little and fades
in, items one after another, a number grows in with its accent bar, a chart is drawn left to right, a flow's arrow
before the step it leads to. Each cue cross-fades from the slide before (0.4 s), and a build step animates only what it
adds. The rail across the top names every part; the current part's track fills as the audio moves through it. All of it
is the renderer's: you choose the slides, the words, the steps and the cue times, never the motion.

## Steps

1. `artools run start $run_id make-podcast-slides --version 2.0.0`
2. Read both transcripts in full (`start` and `text`). Note where each part starts; each number the hosts say; each
   term they define; **each chain of cause and effect** ("tariffs make Chinese goods dearer, so buyers switch…"); each
   analogy; the opening puzzle; the recap.
3. **The library** (`storyboard.json`, one for both editions; `beats: []`). Parts: `open`, `answer`, `p1`…`pN` (kind
   `part`, as in plan.json), `recap`, `end`. Slides, in the article's order:
   - `thumb` (template `thumb`, part `end`): the YouTube thumbnail, three to six words.
   - The opening: a `flow` of the puzzle the hosts open with (two or three steps, for example "Steel and cars hit →
     yet exports set a record → how?"), then `question`, `answer`, `roadmap` (the parts, each with its question).
   - Per part: a `chapter` card (it shows the story so far on its right), the part's `number` and `compare` tiles
     (fact tokens, `facts: [F…]`), at least one `flow` for the part's mechanism, `figure` slides for its charts (with
     `builds` that highlight the series the hosts discuss; quarterly charts can't take a period highlight), `term`
     cards for every glossary term a host defines, `findings` lists, and a `quote` only when the hosts quote it.
   - `read` (our read), `story` (the recap: every part with what it found, one part per step), a `findings` "Three
     things to remember", and `end`.
   - A `flow` has two to four steps (`steps` up to the number of items) and `facts` for any value in it. Use one where
     the hosts walk through a chain; a list of parallel points is `findings`, not a flow.
   Prefer a flow, a findings list or tiles over a dense table: a table chart is unreadable at video size.
   Check each Korean fact token with `artools video render $run_id "{{F1}}" --lang ko`. A money fact that renders as
   "1,230억 5,380만 달러" doesn't belong on a slide; say it in words in a findings item instead.
4. **Wording** (`script/<lang>.json`): `meta` (`title` at most 100 characters, ending "| podcast" / "| 팟캐스트"; `summary`
   two to four sentences for the description; `thumbnail`), `story`, and `slides` with each template's fields.
   - `story`: for each part, `label` (the rail and the story line: at most 24 characters in English, 12 글자 in Korean)
     and `takeaway` (what the part found, one line: at most 70 characters, 35 글자), both in the article's words.
     The chapter cards and the recap are built from them; the chapter's `text` is the part's question.
   - `flow`: `kicker`, optional `headline`, `items` (each step at most 40 characters, 22 글자, a clause not a
     sentence), optional `values` aligned with the items (a fact token or ""), optional `label` (the closing line, shown
     with the last step: what the chain adds up to, or what the value measures).
   - `number` and `compare` may take `text`: what the number means, one short line in the article's words ("The tariff
     paid was about half the announced"). It shows under the tiles with an accent bar.
   - Write each edition from its own article: Korean as a Korean newspaper writes it (`guides/voice-ko.md`). Every
     claim on a slide is the article's, whatever the hosts said. When a host overstates or loses a hedge, the slide
     states the article's version (for example a term card that says how the article uses the term). In Korean, keep
     a pair joined by "·" short enough for one line, or the line breaks at the dot. The end card's `label` is the
     disclaimer plus `config/video/podcast.yaml` → `disclosure`.
5. `artools video slides $run_id`. It renders every slide and step, and for podcast decks each step's enter animation
   as a short clip next to its PNG (the PNG is the clip's last frame). Read both contact sheets
   (`slides/<lang>-sheet.png`) and every frame `slides/render.json` flags. Fix the wording or the template and re-render
   the slide (`--only <ids>`). The thumb's watermark sitting in the caption zone is expected.
6. **The timelines** (`podcast/<lang>.timeline.json`): `{"lang", "thumb": "thumb", "cues": [{"t", "slide", "step"}],
   "chapters": [{"t", "title"}]}`.
   - The first cue is at 0; then a cue at the `start` of the segment where the hosts reach the thing the slide shows.
     A number tile goes up at the segment that says the number; a flow's next step at the segment that says it; a
     chapter card at "Part two" / "둘째".
   - Change slides every 10–45 seconds; no hold over 60 seconds (split a long stretch with the part's next relevant
     slide, a flow's next step, or an earlier slide the hosts return to), no flash under 5 seconds. Every cue
     animates for about a second, so a cue under 5 s after the last one reads as a flicker.
   - A slide may come back, but only within its own part: the rail lights the slide's part, so a part-one card in
     part three would light the wrong label.
   - Chapters: the question, the short answer, one per part, and the recap. YouTube needs the first at 0:00.
7. **Captions in the other language** (`asr/<lang>.<other>.json`, so `asr/ko.en.json` and `asr/en.ko.json`):
   `{"from", "to", "segments": [{"i", "text"}]}`, one translation per transcript segment, `i` its index in
   `asr/<lang>.json` → `segments`. The times are the transcript's.
   - Translate what the host said, not the article: a slip stays a slip ("two-thirds of a percent" where the host said
     삼분의 이), a question stays a question. Trim fillers ("어", "뭐", "you know") and false starts.
   - Terms as the other edition's glossary words them (실효관세율 → effective tariff rate). Numbers: a number the
     transcript writes in digits stays in digits; years, percentages and amounts never change.
   - Short enough to read: about 20 characters a second in English and 12 in Korean. Korean captions in the polite
     spoken style the hosts use (해요체/합니다체), not written style.
   - `artools video podcast captions $run_id` lists every segment missing, too long to read, or with a number that
     differs. Fix them all.
8. `artools video podcast assemble $run_id` and `artools video podcast thumb $run_id`. Assembly checks every cue
   (slide exists, steps, order) and writes both caption tracks (`video/<lang>.srt` and `video/<lang>.<other>.srt`).
   Grab two frames from each video to confirm (`video/<lang>.json` → `timeline` shows what should be on screen when).
9. `artools run done $run_id make-podcast-slides --note "<slides, flows, cues per edition, minutes>"`.

## Never

- Put a number on a slide that is not a fact token or the article's words, in a flow step, a takeaway or a `text` line.
- Draw a flow the article doesn't make: each arrow is a link the article states, not one the hosts improvised.
- Change the audio or the transcript's timing. Caption text may be corrected where the transcription misheard a word
  or cut one at a piece boundary (record it in `asr/<lang>.json` → `edited`); never to make the hosts say something
  they didn't. The translation follows the corrected text.
- Tune the motion per slide or add animations: the renderer's mild set is the house style.
