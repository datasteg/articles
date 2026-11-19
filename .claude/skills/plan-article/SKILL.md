---
name: plan-article
description: Plan an explainer from a run's refined question, literature map and facts - the answer in one sentence, the headline, three key numbers, the sections with the facts and evidence each uses, and the figure plan (3-6 figures in at least two forms, each with its takeaway). Writes plan.json for gate 2 (approved by the driver in unattended runs).
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write
metadata:
  version: 0.2.0
  family: stage
---
# plan-article

## Purpose

Decide what the article says before anyone writes it: the answer, the order of the argument, which facts and evidence carry each section, and which picture makes each main point. The editor approves or changes this at gate 2, cheaply.

## Inputs

`question-review.json`, `brief.json`, `litmap.json`, `analysis/analysis.json`, `data/*/catalog.json`, `evidence/*.jsonl`, `evidence/jejualps.log.json` (related reading), `guides/charts.md`, `guides/readability.md`, `config/editorial.yaml`, `config/topics.yaml`. The article type is `run.json` → `pipeline` (default `explainer`); its template, `guides/templates/<type>.md`, sets the sections, length and figures, and overrides the explainer defaults below.

## Steps

1. `artools run start $run_id plan-article --version 0.2.0`
2. Write the **answer** in one sentence, with its numbers (for the editor, not readers).
3. Write the headline, kicker and dek in English and Korean:
   - the headline states the finding, at most 90 / 40 characters, with no question and no colon subtitle;
   - all three may use fact tokens.
4. Choose **three key numbers** (fact ids) that change a reader's mind, and the **topics** from `config/topics.yaml`: one to three subject topics (groups Markets, Policy, Economy and society), the main one first, plus at most one region (group Regions) when the article is about a place. Readers filter the home page by these, so pick what the article is mainly about, not everything it touches. If none fits, propose one as `{"id": …, "label": {…}, "group": …, "new": true}`; the editor decides at gate 2. `artools validate plan-article` checks the counts.
5. Plan the **sections**, explainer order:
   - `question`;
   - 4–6 content sections, each opening with its point;
   - `insight`, `references`, `related`, `method`.
   Each content section lists the facts (F…), evidence (E…), mechanisms (M…) and datasets it uses.
6. Plan the **figures** first, then the words:
   - 3–6 figures in at least two forms (`guides/charts.md`), one per main point;
   - each with its takeaway as a sentence, the form, the data (dataset or derived ids), focus and context series, and anything left out with the reason;
   - the key numbers are a `stat-tiles` figure with id `key-numbers`.
7. Choose 2–4 **related reading** items from the search log (not cited), each with a one-line `why` in both languages.
8. Write `plan.json`, then `artools run done $run_id plan-article`. Gate 2 follows: the driver approves it itself under `config/editorial.yaml` → `gates.auto`, so nobody reads the plan before the draft. Make it right the first time.

## plan.json

```json
{
  "slug": "france-spread-2026",
  "date": "<today>",
  "answer": "…",
  "headline": {"en": "…", "ko": "…"}, "kicker": {"en": "Sovereign debt", "ko": "국가채무"}, "dek": {"en": "…", "ko": "…"},
  "type": "explainer",
  "topics": [{"id": "sovereign-debt", "label": {"en": "Sovereign debt", "ko": "국가채무"}}],
  "key_numbers": ["F4", "F5", "F10"],
  "sections": [
    {"id": "question"},
    {"id": "now", "heading": {"en": "Where things stand", "ko": "현재 상황"}, "point": "…", "uses": ["F4", "F5", "ecb-irs-fr"], "figure": "spread-history"},
    {"id": "insight"}, {"id": "references"}, {"id": "related"}, {"id": "method"}
  ],
  "figures": [
    {"id": "key-numbers", "form": "stat-tiles", "takeaway": "…", "uses": ["F4", "F5", "F10"]},
    {"id": "spread-history", "form": "line", "takeaway": "…", "data": ["derived-spread-fr", "derived-spread-it"],
     "focus": ["FR"], "context": ["IT", "ES"], "left_out": "GR, PT: their peaks would flatten the others; in the table"}
  ],
  "glossary": ["spread", "basis-point"],
  "related": [{"title": "…", "institution": "…", "date": "…", "url": "…", "why": {"en": "…", "ko": "…"}}],
  "length": {"en_words": 1500}
}
```

## Judgement

- Answer first; the title, key numbers and findings alone should tell a reader the answer.
- Every content section uses at least one fact, evidence record or mechanism. Every fact used is publishable.
- A figure every 300–400 words. Never a chart for decoration: each one's takeaway is a sentence the text relies on.
- Use only what the run has. If a planned point lacks a fact, plan for `analyze-data` to add it, and say so in the plan's `todo` list, rather than writing around it.

## Never

- Plan a claim the evidence doesn't support, or a figure from non-publishable data.
