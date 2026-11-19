---
name: frame-question
description: First stage of an articles run - turn the reader's question into a literal first brief (brief.v1.json) that lists its sub-questions, entities, periods, concepts, data needs, the sources to scout, and every premise the question takes for granted. Does not correct the question; refine-question does that after the scout pass.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write
metadata:
  version: 0.1.0
  family: stage
---
# frame-question

## Purpose

Write down, literally, what the reader asked and what the question assumes, so the scout pass can test it. Don't fix anything yet: a wrong premise must be visible to be corrected.

## Inputs

- `/data/articles/runs/$run_id/run.json`: `question`, the reader's words
- `config/sources.yaml`: the sources that exist and what they cover

## Steps

1. `artools run start $run_id frame-question --version 0.1.0`
2. Read the question and the source registry.
3. Write `/data/articles/runs/$run_id/brief.v1.json`:

```json
{
  "question": "<the reader's question, verbatim>",
  "answer_type": "assessment + historical comparison",
  "as_of": "<today, YYYY-MM-DD>",
  "premises": [
    {"id": "P1", "text": "<one checkable statement the question takes for granted>"}
  ],
  "subquestions": [
    {"id": "Q1", "text": "<as literal as the question>", "needs": ["data", "evidence"]}
  ],
  "entities": {"countries": ["FR"], "instruments": ["10-year government bond"], "institutions": ["ECB"]},
  "periods": {"<name>": ["YYYY-MM", "YYYY-MM"]},
  "concepts": ["<terms to search: mechanisms, models, policy tools>"],
  "jel": ["E62"],
  "data_needs": ["<series a reader would need, in plain words>"],
  "reader": "<who the reader is and what they likely know>",
  "sources": ["jejualps", "public-data"]
}
```

4. If the run's pipeline (`run.json` → `pipeline`; see `config/pipelines/`) has no refine-question step, also write the same content to `brief.json`: later stages read the refined brief.
5. `artools run done $run_id frame-question`

## Judgement

- **Premises** are the heart of this stage. Every adjective that judges ("severe", "crisis", "bubble"), every comparison ("the same as 2011"), every time reference ("in October 2026") and every causal link ("for the global economy") implies a premise. Write each as a statement that data or evidence could support or contradict: "France's 10-year spread over Germany is at a severe level in October 2026", "Data for October 2026 are published".
- **Sub-questions** stay literal: 2–4, in the question's own terms.
- **Sources**: `jejualps` for any economics question; `public-data` when euro-area or EU statistics are named or implied; `fred` for US or global market series; `ecos` only when Korea is named or the question asks what it means for Korea.
- **Concepts**: the vocabulary the research would use, not only the reader's words (for spreads: sovereign risk, contagion, risk aversion, fiscal fundamentals, redenomination risk, bank–sovereign loop, central bank backstop, OMT, TPI).

## Never

- Correct, narrow or reframe the question here.
- Answer the question.
