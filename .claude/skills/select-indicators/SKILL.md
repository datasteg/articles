---
name: select-indicators
description: For a data brief, choose the two to five statistical series that answer "which number moved, by how much, compared with what" - each tied to the sentence it will support and validated against a published value - and write indicators.json, which routes the fetch step. Sample stage of the data-brief pipeline.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Bash(python3 *) Read Write Edit
metadata:
  version: 0.1.0
  family: stage
  status: sample
---
# select-indicators

## Purpose

A data brief is about one number that moved. This stage decides which series show it, and the one or two others a reader needs to judge it (a peer, a long average, a related measure). Read first:
- `guides/templates/data-brief.md`;
- `guides/numbers.md`;
- the provider skills' references: `fetch-public-data/reference/series.md`, `fetch-fred/reference/indicators.md` and `fetch-ecos/reference/`.

## Inputs

`brief.v1.json` (the framed question: which number, which period), and `run.json`.

## Steps

1. `artools run start $run_id select-indicators --version 0.1.0`
2. Write the brief's number as one sentence: what it is, the period, and the comparison that makes it news (its level, its change, its rank, the last time it was this high).
3. Find candidate series with the provider skills' search scripts (`fred.py search`, `ecos.py search`, the ECB keys in `series.md`). Prefer the publisher's headline series over a derived one.
4. For each series you keep, record a published `anchor`: one value from the publisher's own release or table, for `artools validate` to compare against after the fetch.
5. Write `indicators.json` (`contracts/indicators.schema.json`):
   - one `headline` series;
   - one to three `comparison` series;
   - at most one `context` series;
   - each with `serves`, the sentence of the brief it supports;
   - `context_queries`: one to three archive searches for documents that explain the move (the context step runs them).
6. Write `litmap.json` with one mechanism whose `indicators` list these series and their providers, so the driver routes the fetch skills as it does for explainers.
7. `artools run done $run_id select-indicators`

## Judgement

- Two charts' worth of series is the limit; a brief that needs more is an explainer.
- Seasonally adjusted and real (inflation-adjusted) series by default; say so in `serves` when not.

## Never

- Keep a series without a published anchor.
- Choose a series because it moves the most.
