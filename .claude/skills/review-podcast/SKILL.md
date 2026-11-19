---
name: review-podcast
description: Review the podcast video before it goes public - the mechanical checks on both transcripts, an independent fact-check of everything the NotebookLM hosts say against the article, the slides against what is said when, and the muted test from the contact sheets. Writes review.json with blocking and advisory issues, owned by make-podcast (the audio) or make-podcast-slides.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob Agent
metadata:
  version: 1.1.0
  family: stage
---
# review-podcast

## Purpose

The hosts wrote their own script from the article, so unlike the narrated video nothing they say was checked before
it was recorded. This review is that check, and the upload waits on it: a blocking issue sends the edition back to
make-podcast for a new take. Read `guides/video-podcast.md` § The review first.

## Steps

1. `artools run start $run_id review-podcast --version 1.1.0`
2. `artools video podcast check $run_id`. Read `asr/<lang>.check.json`: a number the hosts said that is not in the source
   is a candidate blocking issue. The check reads digits only, and the transcript (VibeVoice-ASR) writes some numbers in
   words ("삼분의 이 퍼센트", "fifteen percent"), so the fact-check below reads those too. Confirm each candidate against
   the source (a number the source has in words, "about seventeen per cent", is fine) and against the audio:
   `artools video podcast hear $run_id --lang <lang> --at <t>` hears those seconds again on their own, without the
   context prompt (about a minute, mostly loading the model). A key number said wrong (2.2% for 2.1%) is blocking.
   A host pointing at a screen is advisory. An edition outside `podcast.yaml` → `length` is blocking for make-podcast.
3. **Fact-check.** Start a general-purpose subagent with only the file paths (`podcast/<lang>.source.md`,
   `asr/<lang>.json`) and this brief: find every statement where the hosts give a number, date, name or ranking that
   differs from the source, whether written in digits or words, including a slip one host makes and the other
   corrects; state as fact what the source doesn't say; drop a hedge so that a scenario sounds like a
   forecast; or give investment advice. Blocking only when a typical viewer would come away believing a materially
   wrong number or a wrong answer to the article's question; otherwise advisory. It writes
   `review/podcast-check.json`. Run it in the foreground (background agents can be stopped with the session).
4. **Slides against audio.** For each edition, read `podcast/<lang>.timeline.json` with the transcript: every number tile
   is up within a sentence of the hosts saying it; every chapter card at its part; every flow step at the sentence that
   says it; no slide that says something the article doesn't (flow arrows, part takeaways and `text` lines included:
   each is a link or finding the article states). Read `slides/<lang>-sheet.png`: nothing cut off, Korean wording
   natural. Open one clip per template (`slides/<lang>/<slide>-1.mp4`) if a frame looks wrong mid-animation.
5. **Captions in the other language.** `artools video podcast captions $run_id`: no problems left. Then read
   `asr/<lang>.<other>.json` beside `asr/<lang>.json` for the stretches around every number and every candidate from
   steps 2 and 3: the translation says what the host said (a slip stays a slip, a hedge stays a hedge), with the other
   edition's terms. A number changed in translation is blocking for make-podcast-slides; wording is advisory.
6. **Muted test.** From the contact sheets alone, state the question, the answer, the parts in order and how one leads to
   the next (the rail, the flows and the chapter cards carry it). If you can't, that is an advisory issue for
   make-podcast-slides.
7. Write `review.json`: `{"blocking": [...], "advisory": [...], "checked": "..."}`, each issue `{lang, t, owner, issue,
   fix}`. Owner `make-podcast` for anything the hosts said (the fix: a new take, with the line to add to the focus
   prompt), `make-podcast-slides` for slides, timelines and both caption tracks.
8. `artools run done $run_id review-podcast --note "<blocking n, advisory n>"`.

## Judgement

- Conversation is looser than an article. "About a third of a percent" for "a third of a per cent of output" is fine; "the
  data proves" for "the models find" is advisory; a wrong year, a wrong sign or a model loss called a forecast is
  blocking.
- A take costs fifteen minutes and NotebookLM's daily quota, and an edition gets two at most (one retake): block only a
  critical error, never style. When the edition already has two takes, own a blocking issue to `make-podcast-slides`
  with a slide fix that states the article's version.
- An advisory issue the slides can answer (a hedge the hosts dropped) is fixed on the slide, not by a new take.
