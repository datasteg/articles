---
name: map-literature
description: Organise a run's deep evidence by mechanism - what explains the phenomenon, what the models say, where studies agree and disagree, what is missing - and name, for each mechanism, the indicators a reader would need to see, each routed to a data provider with a priority. Writes litmap.json, which drives the data skills.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write
metadata:
  version: 0.1.0
  family: stage
---
# map-literature

## Purpose

Turn a pile of evidence into the structure of an explanation: the mechanisms behind the phenomenon, the evidence for each, where the research disagrees, and the indicators that would show each mechanism at work today. The indicator list decides which data skills run.

## Inputs

- `brief.json`, `question-review.json`
- `evidence/*.jsonl` (deep), `readings/jejualps/*.json`, `evidence/jejualps.log.json`
- `config/sources.yaml` (provider ids)

## Steps

1. `artools run start $run_id map-literature --version 0.1.0`
2. Read every evidence record and the reading notes. Group the records by the mechanism they speak to, not by paper.
3. For each mechanism write:
   - a summary of 2–4 sentences, in our words, no stronger than the evidence;
   - the evidence ids (at least two where the pool has them);
   - whether the evidence is causal or associative;
   - the **indicators** that would show the mechanism at work today.
4. Record **models** (formal frameworks: the paper and the key idea), **consensus**, **disagreements** (topic, the records on each side, why they differ: period, method, sample) and **gaps** (sub-questions the evidence can't answer).
5. Route each indicator:
   - `provider`: `ecb`, `eurostat`, `fred`, `ecos` (see `config/sources.yaml`);
   - `priority`:
     - `needed`: the answer depends on it;
     - `useful`: it makes a point clearer for readers;
     - `context`: the editor should know it; readers needn't see it;
   - `reader_value`: one sentence naming the sentence or chart it would serve.
   Be strict: an indicator is `needed` or `useful` only if a reader gains from seeing it. Korean series (`ecos`) are `useful` only if `brief.json` includes a Korea angle.
6. Write `litmap.json`, then `artools run done $run_id map-literature`.

## litmap.json

```json
{
  "mechanisms": [
    {"id": "M1", "name": "Fiscal fundamentals", "summary": "…", "evidence": ["jejualps-E3", "jejualps-E7"],
     "strength": "causal | associative | mixed",
     "indicators": [{"id": "I1", "text": "General government gross debt, % of GDP, by country, annual",
                     "reader_value": "The debt dumbbell: shows France's debt rose most among the six since 2011",
                     "priority": "needed", "provider": "eurostat"}]}
  ],
  "models": [{"name": "…", "evidence": ["…"], "idea": "…"}],
  "consensus": ["…"],
  "disagreements": [{"topic": "…", "sides": [{"view": "…", "evidence": ["…"]}], "why": "…"}],
  "gaps": ["…"]
}
```

## Never

- Name a mechanism the evidence doesn't support.
- Mark an indicator `needed` or `useful` just because data exist.
