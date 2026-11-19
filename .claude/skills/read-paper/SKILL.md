---
name: read-paper
description: Read one chosen paper closely - question, data, method, findings, limits - and record verified evidence quotes and a reading note, plus up to three context documents. Sample stage of the paper-digest pipeline.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Agent
metadata:
  version: 0.1.0
  family: stage
  status: sample
---
# read-paper

## Purpose

Make the paper's own claims checkable, so the digest says what the paper says and no more. Read first:
- `search-jejualps/SKILL.md` § evidence records (the same format);
- `guides/citations.md`;
- `guides/untrusted-text.md`.

## Inputs

`selection.json` (`chosen.doc`), `brief.json`.

## Steps

1. `artools run start $run_id read-paper --version 0.1.0`
2. `artools reading get <doc>`. If there is no note yet, have the `paper-reader` agent write one, then `artools reading save`.
3. Write `evidence/jejualps.jsonl`. Include one record for each of:
   - the question;
   - the data;
   - the method;
   - each main finding;
   - the stated limits.
   Each record has a verified quote: `artools quote verify <doc> "<quote>"`.
4. Optionally add up to three `kind: "context"` records from other documents: a paper the result contradicts, or a policy note that uses it.
5. Put the paper's own key numbers (effect sizes, samples, periods) into `analysis/analysis.json` as facts with `source: "paper"` and the evidence id, so the draft can use tokens.
6. `artools run done $run_id read-paper`

## Never

- Paraphrase a finding more strongly than the paper states it.
- Turn a correlation into a cause.
