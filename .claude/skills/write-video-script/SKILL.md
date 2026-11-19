---
name: write-video-script
description: Write the video explainer of a published article - one storyboard both languages share (chapters of hook, example, point, evidence and wrap-up; slides; beats), then the English and Korean narration and slide wording, each from its own edition, for economists listening on the move. Few spoken numbers (the slides hold the rest), concrete examples, a wrap-up closing every chapter; one calm narrator; Korean written like a newspaper and spoken like a broadcast. Writes storyboard.json, script/en.json and script/ko.json.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob
metadata:
  version: 1.1.0
  family: stage
---
# write-video-script

## Purpose

Turn one published article into the script of a narrated slide video, in English and in Korean, for economists and
the economically literate who listen **while walking**: one ear on the video, the screen in a pocket. The narration
carries the argument as a story; the slides carry the exact figures. The article has passed its review, so the video
adds nothing to it: no research, no data, no numbers it doesn't have.

Read first, in this order: `guides/video.md` (above all § Numbers and § Chapters), then `guides/voice-en.md`,
`guides/voice-ko.md`, `guides/numbers.md`.

## Inputs

All in the video run (`/data/articles/runs/<run>/`):

- `source/en.json`, `source/ko.json`: the published editions (numbers already rendered, marks `[[S3]]`, `((term))`).
- `source/meta.json` (`terms`, `charts`), `source/sources.json`, `source/charts/<id>.json` (each chart's headline and
  takeaway in both languages), `source/related.json`.
- `source/facts.json`: the article's publishable facts with labels. Find a number's fact id with
  `artools video facts $run_id --grep "<words of its label>"`; it shows the written and spoken forms.
- The glossary: `content/glossary/<id>.json` in the repository, for the terms in `source/meta.json` → `terms`.
- `config/video/speech.yaml` (the ten-minute budget and the ear's rounding).
- In fix mode, `review.json`: fix every blocking issue whose `owner` is `write-video-script`, and the advisory ones
  where they are right.

## Steps

1. `artools run start $run_id write-video-script --version 1.1.0`
2. Read the style book and both editions in full. Write down, in one English sentence, the article's answer.
3. **Choose the numbers.** List at most eight numbers a listener should still remember at the end; find their fact ids
   with `artools video facts $run_id --grep "<words of its label>"`. Every other figure stays on slides or is said in
   words ("more than doubled", "about half").
4. **Plan the chapters** (`storyboard.json` → `parts`): `open`, `answer`, `p1`–`p3` (one finding each; record `section`
   and `finding`; `p4` only if four findings can't merge), `limits`, `recap`, `end`.
5. **Find each chapter's example**: the episode, speech or study in the article that shows the finding at work (who,
   when, what happened, what followed). An economist remembers the 2013 press conference, not the table.
6. **Plan the beats** (24–32, each 20–45 seconds): every beat has a `slide`, a `role`, the `facts` it uses and `says`,
   one English sentence of what it says. A chapter runs `hook` → `example` → `point` → `evidence` → `wrap`; a `quote`
   beat may sit inside the example. Slides: 16–24 from the templates; at most four of the article's charts, chosen for
   a shape you can tell in words; a `number` slide only for a number the beat says.
7. **Write `script/en.json` from the English edition**, beat by beat: `spoken` verbatim with at most one number as
   `{{F4:spoken}}`; `slides` with their words and numbers as `{{F4}}`; `cues` for build steps; `pause_after: 1.0` on each
   `wrap`; `meta` with the YouTube title (the edition's title or a shorter form, ≤ 100 characters), the answer in two
   sentences, and three to five words for the thumbnail.
8. **Write `script/ko.json` from the Korean edition**, on the same beats, as Korean narration (style book § 한국어
   내레이션): 하십시오체, about 30 characters a sentence, subject first, native verbs, sizes in words ("넷 중 셋",
   "두 배가 넘게"), each chapter closed with "정리하면…". Don't translate the English script.
9. `artools check video-script --run $run_id`. Fix every blocking problem (numbers over budget, a chapter without an
   example or a wrap-up, length, pointing words). Read each advisory and fix the ones that are right.
10. **Walk it.** Read each script start to finish as if aloud, imagining a street with traffic:
    - Can a listener say the answer and each chapter's lesson at the end?
    - Is any stretch a list of figures? Turn it into a size in words or move it to a slide.
    - Does each chapter have a moment worth retelling (a scene, a quote, a turn)?
    - Does any line need the screen, sound like a pitch or a podcast host, or (Korean) sound translated?

    Fix what fails, and run the check again.
11. `artools run done $run_id write-video-script`. It validates both files against `contracts/video/` and runs the check.

## Judgement

- Content is fixed by the beat; wording belongs to the language. The same facts in the same order, never the same
  sentences.
- Tell the chart: start, end, peak, comparison. If a chart can't be told in two sentences, choose another one.
- Round for the ear through the token, never by typing a rounded number.
- The answer comes within the first 75 seconds and is said three times; each chapter's lesson is said in its wrap
  and again in the recap.
- Fewer numbers, better chosen: the number that changes the listener's mind, not the one that is merely precise.
- The article's caveats are content, not small print: the `limits` part says them plainly.
- The end part says, once, that this is general information and not investment advice, and that the voice is
  synthetic (the check looks for both).

## Never

- Add a fact, number, claim, source or example the article doesn't have, or soften or strengthen its causal words.
- Point at the screen, or write a slide the narrator doesn't say.
- Type a number other than a date, year or maturity.
- Write HTML, choose colours or fonts: `make-slides` fills the article's own components.
- Write into `content/` or the article's run: the video run is the only place you write.
