---
name: analyze-data
description: Compute every number an article will use from the run's fetched data - levels, spreads, changes, peaks, ranks, ratios, then-versus-now comparisons, the indicator scorecard - in a rerunnable analysis.py, recorded as facts (analysis.json) with unrounded values, display rules, formulas, inputs and publishability, plus derived series for the charts.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit
metadata:
  version: 0.1.0
  family: stage
---
# analyze-data

## Purpose

Every number readers will see comes from here. Drafts refer to facts by id (`{{F4}}`), so a number that isn't a fact can't be printed. Read `guides/numbers.md`.

## Inputs

- `data/*/catalog.json` and the CSVs (`date,value`; empty = missing), `litmap.json`, `brief.json`, `question-review.json`
- In fix mode, `review.json`: the blocking issues whose `owner` is `analyze-data`

## Steps

1. `artools run start $run_id analyze-data --version 0.1.0`
2. List what the article will need: the litmap's `needed` and `useful` indicators, the premise checks, the comparisons in the brief. For each, the measures a reader understands: a level with its date, the change since a reference date, a peak and when, a ratio to the peak, a rank, a gap between two series, "the last time it was this high".
3. Write `/data/articles/runs/$run_id/analysis/analysis.py`:
   - pandas, no network; reads the run's CSVs by path from the catalogs;
   - writes `analysis/analysis.json`, and any derived series the charts need as CSVs in `data/derived/`, each with an entry in `data/derived/catalog.json` (same Dataset fields: `id`, `indicator`, `provider: "datasteg calculation"`, `key: "<formula>"`, `inputs: [dataset ids]`, `frequency`, `unit`, `span`, `retrieved`, `licence: "derived from <inputs>"`, `attribution: "Source: <providers>; datasteg calculation"`, `publishable`: true only if every input is, `file`, `validation: {"verdict": "pass", "checks": []}`).
4. Run it: `artools analysis run $run_id`. Fix until it runs cleanly and reproduces the same facts on a second run.
5. Sanity-check the facts with `artools data query $run_id --sql …`: units, last observations, signs, a value or two by hand.
6. `artools run done $run_id analyze-data`

## A fact

```json
{"id": "F4", "label": "France 10-year spread over Germany, Sep 2026", "value": 96.7, "unit": "bp",
 "display": {"decimals": 0}, "period": "2026-09", "formula": "(yield FR − yield DE) × 100",
 "inputs": ["ecb-irs-fr", "ecb-irs-de"], "publishable": true}
```

- `value` unrounded; `display.decimals` decides the shown precision. A date-like fact has `unit` `month`, `date`, `quarter` or `year`, and `value` "2012-07".
- A change is computed from unrounded inputs, and rounded once at display.
- `inputs` are dataset ids (fetched or derived); `publishable` is true only if all inputs are.
- Ids `F1`, `F2` … in a stable order (by section of the brief); never renumber in fix mode, only add.

Also write `scorecard`: one row per litmap indicator, `{"indicator": "I1", "then": "<value + period>", "now": "<value + period>", "reading": "<one line>"}`.

## Judgement

- Prefer measures a general reader grasps: basis points, % of GDP, "% of its 2011 peak", "the widest since July 2012".
- Monthly averages are not daily highs: say which, in the label.
- When the data contradict a draft claim (fix mode), add the fact that states what the data do show.
- No forecasts, no regressions the evidence doesn't call for.

## Never

- Type a number into analysis.json that the script didn't compute.
- Mark a fact publishable when an input isn't.
