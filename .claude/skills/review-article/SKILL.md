---
name: review-article
description: Review a drafted article before the editor sees it - run the mechanical checks (numbers, style, readability, licences, charts), have the fact-checker subagent test every claim, quote and popover against the evidence and data with fresh eyes, look at the rendered page, and write review.json with blocking and advisory issues, each owned by the stage that must fix it.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Agent
metadata:
  version: 0.2.0
  family: stage
---
# review-article

## Purpose

Catch what a reader would catch, and what they couldn't: untraced numbers, claims stronger than their sources, quotes that don't support their popovers, charts that mislead, jargon, the two editions drifting apart. The driver sends blocking issues back to their owners (at most twice), then the editor sees the article at gate 3.

## Inputs

The whole run: `plan.json`, `draft/*.json`, `charts/*.json` and `charts/render/`, `analysis/analysis.json`, `evidence/*.jsonl`, `readings/`, `question-review.json`, `litmap.json`, data catalogs.

## Steps

1. `artools run start $run_id review-article --version 0.2.0`
2. `artools check numbers style readability licences charts glossary --run $run_id`. Each blocking result becomes a blocking issue, owned by the stage that produced the offending file.
3. Start the `fact-checker` subagent (Agent tool, `subagent_type: fact-checker`) with the run id. Don't give it the plan's reasoning or your opinion: it checks with fresh eyes. It returns issues.
4. Render the page: `artools render page $run_id --lang en` and `--lang ko`. Read the PNGs and the chart renders, as a reader: is the answer clear from the top? Does each chart show what its paragraph says? Anything confusing, cramped or wrong? Near the end, the "Cite this article" block (from the preview's `meta.json` → `citation`) must give the edition's own title and URL (`/en/a/<slug>`, `/ko/a/<slug>`).
5. Merge everything into `review.json`, with duplicates removed and each issue concrete (where, what, the fix):

```json
{"status": "changes_required",
 "blocking": [{"where": "en.now.p[0]", "issue": "…", "fix": "…", "owner": "draft-article"}],
 "advisory": [{"where": "…", "issue": "…", "fix": "…", "owner": "make-charts"}],
 "checks": {"numbers": "ok", "quotes": "14 verified", "parity": "ok", "style": "1 issue", "readability": "EN avg 18.2 words",
            "licences": "ok", "charts": "ok", "fact_check": "3 issues"},
 "summary": "<three sentences for the editor: is it ready, what's left>"}
```

   `status` is `pass` only when there are no blocking issues.
6. `artools run done $run_id review-article`

## Rubric

- **Blocking:**
  - an unresolved token, a typed number, or an unverified quote;
  - a claim stronger than its source, or one the data contradict;
  - a popover quote that doesn't support its claim;
  - EN and KO saying different things;
  - a chart whose takeaway the text contradicts, an unlabelled axis, or a misleading scale;
  - non-publishable data;
  - a premise correction missing from the article.
- **Advisory:** a "Cite this article" block that is missing or names another title or URL (owner `draft-article` when the title is wrong; otherwise say so in the summary for the editor), jargon without a definition, a long paragraph, a weak headline or dek, a chart that could be clearer, a missing how-to-read line, a data source whose "Finding the series" note (`dataset.locate` in the preview's `sources.json`) would not lead a reader to the cited series, a section `summary` (the contents list) missing or saying something its section doesn't.
- **Owners:**
  - `analyze-data` when a fact is missing or wrong;
  - `draft-article` for words, citations and glossary;
  - `make-charts` for charts.

## Never

- Fix the files yourself: the owners do, so the trail stays clear.
- Give an issue an owner outside the run's pipeline (`config/pipelines/<run.json pipeline>.yaml`). In a deep dive, issues with the model design belong to `design-model`.
- Pass an article with any blocking issue.
- Prescribe a `fix` sentence that says more than its quote or fact. Unattended runs publish whatever the last round leaves (`config/editorial.yaml` → `gates.on_blocking: publish`), and an over-reaching fix becomes the next round's blocker.

## The last round

The publish gate no longer waits for a clean review: after the loop's last round the article goes live with the blocking issues left, and `publish.json` → `review_left` hands them to the editor, who reviews the live article and asks for an update. So write every blocking issue for that reader too: `where` names the section heading and the sentence's first words, as on the site; `issue` says what is wrong in one or two sentences; `fix` gives replacement wording in both languages.
