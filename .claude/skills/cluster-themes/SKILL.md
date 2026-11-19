---
name: cluster-themes
description: Group the period's speeches into three to five themes - who said what, where they agree and where they differ - and write themes.json for the editor's themes gate. Sample stage of the speech-roundup pipeline.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit
metadata:
  version: 0.1.0
  family: stage
  status: sample
---
# cluster-themes

## Purpose

Turn a pile of speeches into the few conversations readers should know about. Read first:
- `guides/templates/speech-roundup.md`.

## Inputs

`evidence/jejualps.jsonl` from collect-speeches.

## Steps

1. `artools run start $run_id cluster-themes --version 0.1.0`
2. Group the records by what they are about (inflation, financial stability, AI and productivity, and so on), not by institution.
3. Keep three to five themes with at least two speakers each. Write each theme's `summary` in one sentence. Fill `disagreement` when speakers differ.
4. Write `themes.json` (`contracts/themes.schema.json`). Write `plan.json` only after the themes gate (plan-article does it).
5. `artools run done $run_id cluster-themes`

## Never

- Invent a disagreement by setting quotes against each other out of context.
