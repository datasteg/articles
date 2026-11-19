---
name: collect-speeches
description: Collect every central-bank speech in the archive for the roundup's period, and record each speaker's main point as a verified evidence quote. Sample stage of the speech-roundup pipeline.
argument-hint: <run-id> <from YYYY-MM-DD> <to YYYY-MM-DD>
arguments: [run_id, from, to]
allowed-tools: Bash(artools *) Read Write Edit
metadata:
  version: 0.1.0
  family: stage
  status: sample
---
# collect-speeches

## Purpose

Have the whole period's speeches in view, each with its point in the speaker's own words. Read first:
- `search-jejualps/reference/archive.md`;
- `guides/citations.md`;
- `guides/untrusted-text.md`.

## Steps

1. `artools run start $run_id collect-speeches --version 0.1.0`
2. List the speeches dated from `$from` to `$to` (`artools jejualps search` with `type` speech and the date range). Keep the governors, deputy governors and board members of the central banks in `config/sources.yaml`.
3. For each speech, read its opening and conclusion. Write one evidence record (`kind: "position"`) whose `claim` is the speaker's main point in one sentence, with a verified quote.
4. Record in `evidence/jejualps.log.json` what you skipped (ceremonial remarks, duplicates) and why.
5. `artools run done $run_id collect-speeches`

## Never

- Quote more than one sentence from a speech.
- Infer a policy signal the speaker did not state.
