---
name: draft-article
description: Write the English and Korean editions of an approved article plan in plain language for general readers - numbers only as fact tokens, every claim with a citation id and a used-for line for its source popover, technical terms with glossary marks and definitions. Writes draft/en.json, draft/ko.json and draft/glossary.json.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit
metadata:
  version: 0.1.0
  family: stage
---
# draft-article

## Purpose

Write the article the plan describes, in both editions, so that a reader with no economics training understands the answer and can check every claim. Read first:
- `guides/voice-en.md` and `guides/voice-ko.md`;
- `guides/readability.md`, `guides/numbers.md` and `guides/citations.md`;
- `contracts/content.md` (the shape of `en.json`; the draft is the same, with tokens and citation ids instead of final numbers and S-numbers).

## Inputs

`guides/templates/<type>.md` for the article type in `run.json` → `pipeline` (default `explainer`), `plan.json` (approved at gate 2; its `notes_for_draft` and `editor_edits` are the editor's instructions and override this skill's defaults), `question-review.json`, `analysis/analysis.json`, `evidence/*.jsonl`, `readings/`, `litmap.json`, `data/*/catalog.json`, `config/editorial.yaml`, and `run.json`. The byline is exactly `config/editorial.yaml` → `byline` for the edition; never add an editor's name. In fix mode, `review.json`: fix every blocking issue whose `owner` is `draft-article`, and the advisory ones where they're right.

## Steps

1. `artools run start $run_id draft-article --version 0.1.0`
2. Write `draft/en.json`, section by section, following the plan's order and its `point` for each section:
   - `kicker`, `title`, `dek` from the plan (tokens allowed; no glossary or citation marks in the dek: the site shows it as plain text); `byline` exactly as in `config/editorial.yaml`;
   - `keyNumbers`: three items `{"value": "{{F4}}", "label": "<what and when>", "cite": ["ecb-irs-fr", "ecb-irs-de"]}`;
   - `findings`: 3–5 sentences, each with a token and a citation;
   - `question`: `asked` is the refined question approved at gate 1 (`question-review.json` `refined.en`), not the reader's raw wording; `lookedAt` and `premiseNote` come from `question-review.json` too (the build fills `asked` from `refined` regardless, so the page always shows the approved question);
   - `sections[].summary`: one short plain sentence (at most about 15 words; Korean about 40 characters) saying what the section shows, ideally its answer, for the contents list readers use to keep their place. No tokens, glossary marks or citations; it must not claim more than the section does;
   - `sections[].blocks`: `p`, `figure` (`{"type": "figure", "chart": "<figure id>"}`, after the paragraph that introduces it), `table`, `list`, `quote`;
   - `insight`: `{"label": "Our read", "text": …}`, the only place for our opinion;
   - no `methodNote` or other "how this was made" text: the site does not show how an article was made;
   - `disclaimer` from `config/editorial.yaml`;
   - `citations`: for every id cited anywhere, `{"<id>": {"used_for": "<half-sentence>"}}`.
3. Write `draft/ko.json` from the same plan, facts and citations, in Korean (`guides/voice-ko.md`). It is not a translation: the same points, facts and citation ids, in sentences written for Korean readers. Its `question.asked` is `refined.ko` from `question-review.json`, each section's `summary` is a Korean sentence saying the same as the English one, its `lookedAt` the Korean line from `question-review.json`, and its `citations` hold Korean `used_for` lines.
4. Write `draft/glossary.json`: for every `((id))` mark used, `{"id": "spread", "term": {"en": "spread", "ko": "스프레드"}, "definition": {"en": "…", "ko": "…"}, "context": {"en": "…", "ko": "…"}}`.
   - Each definition is one or two plain sentences and **general**, because every article that uses the term shares it. Anything about this article (the benchmark, the country, the period) goes in `context`, one optional sentence such as "Here: France's 10-year yield minus Germany's."
   - Give each new term `topics`: 1–2 ids from `config/topics.yaml` for the field the term belongs to (VIX: `stock-markets`), which need not be this article's topics. Readers filter the glossary by them.
   - Before defining a term, look in `content/glossary/<id>.json`. If it exists, reuse the id and don't redefine it (publishing keeps the existing definition); add a `context` sentence if this article uses it in a narrower sense.
5. Run `artools check numbers style readability --run $run_id`. Fix every blocking issue, and the advisory ones that are right.
6. `artools run done $run_id draft-article`

## Inline marks

- `{{F4}}`: a fact, rendered per language (`{{F5|signed}}` gives +24bp).
- `[[jejualps-E12]]`, `[[ecb-irs-fr,ecb-irs-de]]`: citations.
- `((spread))` or `((spread|spreads))`: a glossary term.
- `*emphasis*`.

## Judgement

- Each paragraph makes one point and tells the reader why it matters. Each figure is introduced by the paragraph before it ("The chart below shows …").
- A claim is no stronger than its evidence: causal words only for causal evidence; associations as associations; scenarios with their conditions.
- When research disagrees, say so, with both sides cited.
- When a reader's premise was corrected, say it plainly and kindly in `question.premiseNote` and once in the text, never mocking the question.
- Length from the type's template (explainer: 1,200–1,800 English words).

## Never

- Type a number (dates, years and maturities excepted).
- Cite an id that isn't in the run's evidence or data.
- Quote a document except through its verified evidence quote.
- Let the Korean edition use different facts or citations from the English.
