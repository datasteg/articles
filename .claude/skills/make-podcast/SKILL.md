---
name: make-podcast
description: The podcast video's first step - build the NotebookLM source and focus prompt from the published article (podcast/plan.json groups its sections into five or six parts), then in the editor's signed-in Chrome make one notebook per edition, generate a two-host Deep dive Audio Overview in English and in Korean, download both and ingest them into the run. In fix mode, generate a new take for an edition whose audio the review blocked. Needs Claude in Chrome.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob ToolSearch mcp__claude-in-chrome__*
metadata:
  version: 1.1.0
  family: stage
---
# make-podcast

## Purpose

The podcast video (`config/video/podcast-pipeline.yaml`, `guides/video-podcast.md`) is NotebookLM's two-host conversation
about the article, with the article's own slides cut to it. Everything downstream is derived from this audio: the
slides follow what the hosts say, the captions are their words. So the **source and the focus prompt decide the
video**. You write them with care. Then you drive NotebookLM ("Gemini Notebook", notebook.google.com) in the editor's
Chrome, which takes about 15 minutes per edition, both in parallel.

The editor chose this over the solo Gemini TTS narrator on 29 Oct 2026, after testing open-weights TTS. The audience is **college students and young professionals**: smart, not economists,
watching on YouTube with the slides or listening on earphones while walking.

## Steps

1. `artools run start $run_id make-podcast --version 1.1.0`
2. **Plan the episode.** `artools video podcast plan $run_id` writes `podcast/plan.json` (one part per section). Read both
   editions (`source/en.json`, `source/ko.json`), then edit the plan:
   - `parts`: five or six at most, in the article's order, each `{id: p1…, title: {en, ko}, sections: [...]}`.
     Titles are short and spoken aloud ("Part one: The tariffs that actually bit"), so write them for the ear; the
     Korean ones are Korean headlines, not translations.
   - `context`: sections the hosts may draw on but should not walk through (usually the limits).
   - `drop`: sections that would derail a conversation for this audience (model design, technical appendix).
   - `answer`: `{en, ko}`, the article's answer in two plain sentences.
   Every section must be in exactly one list.
3. `artools video podcast source $run_id`. It writes `podcast/<lang>.source.md` (question, short answer, findings, key
   numbers, the parts with their sections, each chart described in words, our read, context sections, the glossary)
   and `podcast/<lang>.prompt.txt` (from `config/video/podcast.yaml` → `prompt`, at most 5,000 characters). Read
   both sources: no glossary ids leaking ("effective-tariff-rate"), no "the chart below", nothing from a dropped
   section.
4. **Chrome.** Load the tools with one ToolSearch (`select:mcp__claude-in-chrome__select_browser,…tabs_context_mcp,
   …tabs_create_mcp,…navigate,…computer,…find,…read_page,…javascript_tool,…browser_batch,…tabs_close_mcp`). Several
   browsers are connected to the account: always `select_browser` with the device in `podcast.yaml` → `notebooklm.browser`
   first. Then `tabs_context_mcp` with `createIfEmpty`, and one new tab per edition.
5. For each edition (start English, then Korean; they generate in parallel):
   1. Open `https://notebook.google.com/` → **New notebook**. A "more flexibility" announcement may cover the page:
      close it.
   2. **Add source → Copied text.** Set the textarea from `podcast/<lang>.source.md` with `javascript_tool`: build the
      string in the script, set it with the native value setter, dispatch `input`, and return `t.value.length`.
      It must equal `chars` for that edition in the output of `artools video podcast source`. Don't use `form_input` for the source:
      it echoes 35,000 characters back. There is no file input to upload to ("Upload files" opens a native picker).
      **Insert.**
   3. Rename the notebook (the title box at the top) to `datasteg · <slug> · <lang>`.
   4. Studio → **Audio Overview** opens *Customise Audio Overview*. Format **Deep dive**; language (a `mat-select`:
      click it, then `find` the option and click it; `form_input` fails on it) **English** or **한국어**; length
      **Default**; the focus prompt from `podcast/<lang>.prompt.txt`, set with `javascript_tool` the same way.
      **Generate now.**
6. **Wait.** Screenshots of this window time out (the renderer is throttled): read state with `javascript_tool`
   (`document.body.innerText.match(/Generating[^\n]*|[^\n]*\d+:\d\d ·[^\n]*/gi)`). Pause with
   `artools video podcast wait --seconds 300` between checks; a Default Deep dive of a 6,000-word source took 12–15
   minutes. Done shows as `18:01 · Deep dive · 1 source`.
7. **Download.** The item's **More** (three dots) → **Download** saves an `.m4a` into `~/Downloads`. Then
   `artools video podcast ingest $run_id --lang <lang> --file ~/Downloads/<file>.m4a --notebook <notebook url> --title "<title>"`.
   It moves the file into `audio/<lang>.m4a` and records the take in `podcast/<lang>.json`.
8. Close the tabs you opened. `artools run done $run_id make-podcast --note "<en mm:ss, ko mm:ss; notebooks>"`.

**One take per edition.** A first take is the normal case, whatever its small faults: advisory issues are answered on
the slides, never by a new take.

In **fix mode** (review.json has a blocking issue owned by `make-podcast` for an edition): make one more take of that
edition only, and only if `podcast/<lang>.json` → `takes` has fewer than `podcast.yaml` → `notebooklm.takes` (two: the
editor's limit of 29 Oct 2026). If it already has two, generate nothing: `artools run done` with a note that the take
limit is reached, and the slides answer the issue. Otherwise open that edition's notebook (`podcast/<lang>.json` →
`notebook`), delete nothing, and generate again from the same Customise dialog. Add to the focus prompt the lines that
address the blocked statements, and the review's advisories for this stage while you are at it (the retake is the only
one). Download and ingest as above: the new take replaces `audio/<lang>.m4a`, and `ingest` refuses a take past the
limit.

## Judgement

- The prompt shapes the conversation; the source shapes the facts. When the hosts get something wrong, first ask
  whether the source invited it (an ambiguous sentence, a number without its period) and fix `plan.json` or the
  builder before regenerating.
- One Deep dive per edition. Don't try Brief, Critique or Debate without the editor.
- Leave the notebooks in place: they are where the audio lives after the run deletes its local copies.

## Never

- Delete a notebook, a source or someone else's notebook.
- Type the editor's password or accept a Google prompt you weren't asked for; if NotebookLM asks for anything (sign-in,
  terms, a quota warning), stop and record it in the stage note.
- Paste anything into NotebookLM but the article's source and the prompt.
