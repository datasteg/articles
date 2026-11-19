---
name: select-paper
description: For a paper digest, shortlist recent papers in the jejualps archive and choose one whose finding general readers can use and whose method holds up - writing selection.json for the editor's selection gate. Sample stage of the paper-digest pipeline.
argument-hint: <run-id> [topic or window]
arguments: [run_id, hint]
allowed-tools: Bash(artools *) Read Write Edit
metadata:
  version: 0.1.0
  family: stage
  status: sample
---
# select-paper

## Purpose

Pick the one paper worth a digest this time. Read first:
- `guides/templates/paper-digest.md`;
- `search-jejualps/reference/archive.md`;
- `guides/untrusted-text.md`.

## Inputs

`run.json` (its `question` names a topic or "new this month"), plus the archive.

## Steps

1. `artools run start $run_id select-paper --version 0.1.0`
2. Search the archive for papers from the last 60 days (or the window in the hint). Use `artools jejualps search --q "…"`, filtering by date and by `type` paper or working paper.
3. Shortlist 3–8 candidates. For each, read the abstract and conclusion with `artools jejualps segments`. Score them on:
   - **readers:** does the finding change how a non-economist sees something?
   - **method:** identification, data and robustness, in one line each;
   - **newness:** not a re-run of a well-known result.
4. Write `selection.json` (`contracts/selection.schema.json`): every candidate with `why` and `against`, and the `chosen` one with `why_readers` and `method_check`.
5. Write `brief.json`: the chosen paper's question, in plain words, as the article's question.
6. `artools run done $run_id select-paper`

## Never

- Choose a paper you have not read beyond its abstract.
- Choose on the institution's prestige alone.
