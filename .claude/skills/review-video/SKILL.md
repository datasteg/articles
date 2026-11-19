---
name: review-video
description: Review a video explainer before the editor watches it - the mechanical checks, an independent video-checker against the published article, the voice's transcripts, the slide renders, and the two listening tests (eyes closed, muted) run by subagents that see only the narration or only the slides. Writes review.json with blocking and advisory issues, each owned by the stage that must fix it.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob Agent
metadata:
  version: 0.1.0
  family: stage
---
# review-video

## Purpose

The video is checked against the article it came from, not against the world: the article has passed its own review.
What can go wrong here is a beat that says more than the article, a number spoken with the wrong meaning, a slide that
doesn't match its beat, a misread take, a tone that isn't ours, or a video that fails the listener with the screen off.
Read `guides/video.md` first.

## Inputs

The video run: `source/` (the article), `storyboard.json`, `script/<lang>.json`, `slides/render.json`,
`slides/slides.json`, `slides/<lang>-sheet.png`, `audio/<lang>/voice.json` and, when assembled, `video/<lang>.json`.

## Steps

1. `artools run start $run_id review-video --version 0.1.0`
2. `artools check video-script --run $run_id`. Each blocking result is a blocking issue owned by `write-video-script`.
3. Read `slides/render.json` → `problems` and `slides/slides.json` → `accepted`. An unaccepted problem is a blocking
   issue owned by `make-slides`.
4. Read `audio/<lang>/voice.json`: every beat with a `flag` (a misread number, a high word error rate) is a blocking
   issue with owner `voice` and the fix "re-record with `artools video voice <run> --lang <lang> --beats <id>`, or add
   the misread word to `config/video/lexicon.<lang>.yaml`". If `placeholder` is true, say so as an advisory: the voice
   isn't recorded yet. Read `video/<lang>.json` if present: a length outside 9–16 minutes is advisory, owned by
   `write-video-script`.
5. Start the `video-checker` subagent with the run id. Take its issues as they are, unless one is plainly wrong; say why
   in `checked` when you drop one.
6. **Eyes closed.** Write five questions: the answer, each chapter's lesson (its wrap-up), one limit, and the number
   the script stresses most. Start a
   general-purpose subagent and give it only the output of `artools video transcript $run_id --lang en` (pasted into
   the prompt) and the questions, telling it to answer from that text alone, read no files and run no commands. Repeat
   for Korean with the Korean transcript and the questions in Korean. A wrong or missing answer is a blocking issue owned
   by `write-video-script`.
7. **Muted.** Start a general-purpose subagent that may read only `slides/en-sheet.png` (and then `slides/ko-sheet.png`):
   it states the question, the answer and the three parts, in order. A part it can't find is advisory, owned by
   `make-slides`.
8. Look at the contact sheets yourself, with each beat's text beside it: a slide that says what its beat doesn't is
   blocking, owned by `make-slides`.
9. Write `review.json` (`contracts/review.schema.json`): `status` (`pass` only with no blocking issue), `blocking`,
   `advisory`, `checks` (what each step found, with counts), `for_editor` (what to listen and look for at gate V, with
   beat and slide ids and times when known).
10. `artools run done $run_id review-video`.

## Judgement

- The article is the standard. A beat that is true but not in the article is still blocking: the video adds nothing.
- Rounding for the ear is fine until it changes a comparison ("about the same" for 89 against 97).
- Tone issues are blocking only where the style book names them; otherwise advisory.

## Never

- Edit the scripts, slides or audio yourself: issues go to their owners.
- Tell the listening-test subagents what the answers are, or let them read the scripts.
