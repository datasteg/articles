---
name: refine-question
description: Critically review the reader's question against the scout evidence and data, before any deep research - test each premise, define vague terms, check the comparisons, add the dimensions the question misses, turn forecasts and advice into conditions, and write the refined question and brief (question-review.json, brief.json). Verdict proceed, refined, reframed or decline.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write
metadata:
  version: 0.2.0
  family: stage
---
# refine-question

## Purpose

Assume the reader's question is a first draft: often one-dimensional, sometimes resting on a false premise, occasionally unanswerable. Using the scout evidence and reality checks, write the best version of the question the sources can answer, and say exactly what changed and why. Gate 1 follows (approved by the driver in unattended runs, so no one checks it before the deep research); readers see the refined question in the article's question box ("The question we answered") beside "What we looked at", so write it for them.

## Inputs

- `run.json` (`question`), `brief.v1.json` (premises, sub-questions)
- `scout/evidence-*.jsonl`, `scout/*.log.json`, `scout/data/*/probe.json` and catalogs. Query the data with `artools data query $run_id --sql …`; scout tables are named `scout_<id>`.
- `config/sources.yaml`

## Steps

1. `artools run start $run_id refine-question --version 0.2.0`
2. **Premises.** For each premise in `brief.v1.json`, find the scout evidence and data that bear on it. Compute what you need with `artools data query`. Status: `supported`, `partly`, `contradicted` or `unverifiable`. Write a note with the numbers, and cite scout ids (`scout:jejualps-E3`, `scout:ecb-irs-fr`).
3. **Definitions.** Every vague or loaded term gets a measurable criterion. For example, "severe" means: the level against its own history and against peers, the speed of change, spillover to other markets, and the policy response.
4. **Comparisons.** Keep, qualify or replace each comparison the question makes, and add comparators the scout supports (with evidence or data ids).
5. **Missing dimensions.** Mechanisms, channels, actors or measures in the scout evidence that matter to the answer but are absent from the question.
6. **Time and data.** What "now" means in data terms: the latest observation of each key series, and what isn't published yet.
7. **Answerability.** Forecasts, price targets and advice become conditions and scenarios, or go out of scope.
8. **Framing and reader.** Neutral wording. The terms a general reader must have explained become `glossary_terms`.
9. **Coverage.** Can the registered sources answer each sub-question? Narrow, add a source (`sources`), or record a gap.
10. Write `question-review.json` and the refined `brief.json` (same shape as `brief.v1.json`, plus `refined_from: "brief.v1.json"`, at most five sub-questions, and the definitions and comparators). `needs_scout` lists anything the scout must look at before deep research (at most once, usually empty).
11. `artools run done $run_id refine-question`

## question-review.json

```json
{
  "asked": "<verbatim>",
  "verdict": "proceed | refined | reframed | decline",
  "premises": [{"id": "P1", "text": "…", "status": "partly", "note": "<with numbers>",
                "evidence": ["scout:jejualps-E3"], "data": ["scout:ecb-irs-fr"]}],
  "definitions": [{"term": "severe", "criterion": "…"}],
  "comparators": [{"name": "…", "decision": "keep | qualify | add | replace", "why": "…", "evidence": [], "data": []}],
  "added": [{"text": "<new sub-question or dimension>", "why": "…", "evidence": []}],
  "dropped": [{"text": "…", "why": "…"}],
  "data_as_of": [{"series": "…", "latest": "2026-09"}],
  "out_of_scope": ["…"],
  "refined": {"en": "<one plain sentence, at most about 40 words: readers see it as the article's question>", "ko": "<the same in Korean, one sentence, 해라체 question form is fine>"},
  "what_we_looked_at": {"en": "<one sentence readers will see>", "ko": "…"},
  "premise_note": {"en": "<one sentence if a premise was contradicted, else omit>", "ko": "…"},
  "glossary_terms": ["spread", "basis point"],
  "needs_scout": [],
  "confidence": "high | medium | low"
}
```

## Judgement

- **Sceptical but fair.** Correct the premise, keep the reader's concern. The refined question must still answer what the reader wanted to know.
- **Cite or drop.** Every change cites scout evidence or data. A change without a citation is a matter of taste: leave it out.
- **Precision before scope.** At most five sub-questions, and nothing added that doesn't serve the answer.
- **Never answer here,** beyond the premise notes.
- **Decline** only for judgments about private individuals, or a question with no answerable version. A decline stops the run, and runs are unattended (the driver approves gate 1 itself), so nobody will rescue it.
- Personal investment advice, a prediction of a specific price or date, or a topic the sources can't fully speak to: **reframe** to the answerable question (the conditions, the history, what the evidence can say) and record what was dropped and why.
- Choose `reframed` when a premise is contradicted or the period asked can't be measured; `refined` when dimensions or definitions change; `proceed` when only precision is added.

## Never

- Drop part of the reader's concern without listing it under `dropped` with a reason.
- Invent a number: compute it from scout data or quote it from verified evidence.
