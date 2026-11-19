---
name: design-model
description: For a deep dive, design - not estimate - a model of the question: outcome, drivers, data, structure, how to validate it and where it breaks, grounded in the literature map and the run's data. Writes model.json for the editor's model gate. Sample stage of the deep-dive pipeline.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Agent
metadata:
  version: 0.1.0
  family: stage
  status: sample
---
# design-model

## Purpose

Some questions end with "and how could we predict it?". Answer that honestly: a model design a reader could follow and a researcher could build, with its limits stated first. Read first:
- `guides/templates/deep-dive.md`;
- `litmap.json` (`models` and `mechanisms`);
- `analysis/analysis.json`.

## Steps

1. `artools run start $run_id design-model --version 0.1.0`
2. Define the outcome precisely, with the measure and data the run already has (for example, "a fall of 20% or more in the KOSPI within 60 trading days").
3. Choose the drivers from the litmap's mechanisms. Each needs evidence ids and a series the run has fetched or could fetch.
4. Choose the model family by comparing at least two from the literature (early-warning logit, regime-switching, log-periodic and so on), and say why.
5. Specify validation: the backtest window, the out-of-sample split, benchmarks (including "always no crash") and the failure modes.
6. Write `model.json` (`contracts/model.schema.json`) with `not_a_forecast: true`. The article presents a design and its limits, never a prediction.
7. `artools run done $run_id design-model`

## Never

- Estimate the model or report a probability of a future event.
- Choose drivers because they fit the past best.
