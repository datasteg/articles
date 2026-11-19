---
name: fetch-fred
description: Find, validate and fetch economic series from FRED (Federal Reserve Bank of St. Louis) for an article run - US rates and Treasury yields, inflation, jobs, the dollar, oil, the VIX, credit spreads, and OECD cross-country series. Use only for indicators the run routes to FRED because readers need them; not for euro-area sovereign yields (ECB) or Korean statistics (ECOS).
argument-hint: <run-id> [scout|deep]
arguments: [run_id, mode]
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/fred.py *) Bash(artools *) Read Write
metadata:
  version: 0.1.0
  family: source
  produces: dataset
  provider: FRED
---
# fetch-fred

## Purpose

Turn the indicators a run needs into validated FRED series, saved in the run as Dataset records (`data/fred/catalog.json` plus one CSV per series). FRED holds over 800,000 series, many near-duplicates, some discontinued and some under a third party's copyright, so the work is mostly choosing the right one and proving it is right. The script `${CLAUDE_SKILL_DIR}/scripts/fred.py` does the calls; this skill decides.

## When to use, and when not

This skill is optional. The driver runs it only when the run routes at least one indicator to it, and each indicator must pass all three tests:

1. **A reader needs it.** The number supports a sentence, a key number or a chart in the plan (or, in scout mode, a premise of the question). "Nice context" is not enough.
2. **FRED is the right home.** Use it for US series published by the Federal Reserve, BLS, BEA, Treasury or EIA; for global market series (VIX, Brent, the broad dollar); and for OECD cross-country series when no closer official source exists. Euro-area sovereign yields come from the ECB (`fetch-public-data`), Korean statistics from `fetch-ecos`.
3. **It can be shown.** The licence tag allows publication, or the number is meant only for the editor's context and is marked so.

If no indicator passes, write `data/fred/fred.log.json` (scout: `scout/data/fred/fred.log.json`) with `{"skipped": "<reason>"}`, then mark the stage done.

## Inputs

- `/data/articles/runs/$run_id/brief.json` (scout mode: `brief.v1.json` and its premises)
- `/data/articles/runs/$run_id/litmap.json`: indicators with `provider: fred` and their `reader_value` (deep mode)
- `/data/articles/runs/$run_id/plan.json`, when present: which figures and key numbers use each indicator
- `${CLAUDE_SKILL_DIR}/reference/indicators.md`: series already validated, with their caveats

## Steps

0. `artools run start $run_id fetch-fred --version 0.1.0` (scout mode: stage `scout:fetch-fred`). In scout mode, write with `--out /data/articles/runs/$run_id/scout/data/fred` instead of `--run`, and add `probe.json` there; in deep mode use `--run /data/articles/runs/$run_id`.
1. **List the indicators** routed to FRED, each with what it must measure (concept, country, frequency, unit, period) and why a reader needs it. Drop any that fails the three tests above, and log the reason.
2. **Look up `reference/indicators.md` first.** A listed series still gets validated (step 4), because series get discontinued and licences change.
3. **Otherwise search** (`reference/search-playbook.md` explains how):
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/fred.py search <words> --freq M --limit 25      # full text, ranked
   python3 ${CLAUDE_SKILL_DIR}/scripts/fred.py search --id "IRLTLT01*M156N"            # a family by id pattern
   python3 ${CLAUDE_SKILL_DIR}/scripts/fred.py tags "france;interest rate;monthly"      # FRED's own tags
   python3 ${CLAUDE_SKILL_DIR}/scripts/fred.py info <ID>                               # notes, source, licence tag
   ```
   Shortlist 2–5 candidates. For each, read `info`: the title says what it is, the notes say how it's built, `source` names the original publisher, `licence` says whether it can be shown.
4. **Validate the choice** before using it, with an anchor from outside the series itself:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/fred.py validate <ID> --start 2007-01-01 --freq M --units percent \
       --range=-1,20 --anchor 2026-09-01=4.44:0.1 [--compare other.csv --compare-tol 0.05]
   ```
   - `--anchor` is a value you know from a trusted publication: the provider's release, ECOS `keystats`, the ECB. It must never come from the series being tested.
   - `--compare` checks against the same concept from another provider, where one exists (a CSV with `date,value`).
   - Verdict `fail`: choose another candidate. Verdict `warn`: read every warning, and record why it's acceptable or choose another.
5. **Fetch** with the same checks, plus the plain-words indicator name the charts and the "About this chart" panel will show:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/fred.py fetch <ID> --run /data/articles/runs/$run_id --start 2007-01-01 \
       --indicator "US 10-year Treasury yield" --freq D --units percent --range 0,20
   ```
   It writes the CSV, the raw response, and the catalog entry with licence, attribution and validation, and refuses on a failed validation unless given `--force` (then the log must say why).
6. **Log the choice** in `data/fred/fred.log.json`: for each indicator, the candidates considered, the one chosen and why, the validation verdict and warnings, and anything skipped.
7. **Suggest a reference update.** For a new series that validated cleanly, add a row proposal to the log under `reference_additions`; the editor adds it to `reference/indicators.md`.

## Judgement

- **The plainest series that answers the reader's question.** Prefer the headline measure (10-year constant maturity, headline CPI) over an exotic variant, unless the text needs the variant.
- **Primary source over aggregator.** Prefer FRED series published by the original agency (Federal Reserve, BLS, BEA, EIA) to re-hosted copies. For a euro-area country, the ECB beats the OECD copy on FRED.
- **One provider per concept per chart.** FRED's OECD France 10-year yield and the ECB's differ by up to 0.06 points (4.48% against 4.44% in Sep 2026). Each is right on its own terms, so never mix the two in one chart.
- **Frequency matches the claim.** Monthly averages for "in September", daily data for "on 14 October". Don't quote a daily close as a monthly level.
- **Freshness matters for "now".** Some OECD series on FRED lag by months (the euro-area long-term rate ended in January 2026 when checked). A stale series can't carry a "now" sentence.
- **Licence decides what readers see.** `copyrighted: pre-approval required` (the ICE BofA spreads, which FRED also limits to three years of history) may inform the editor but never appear in text or charts.

## Output

- `data/fred/<dataset-id>.csv` (`date,value`; empty value = missing), `data/fred/raw/`, `data/fred/catalog.json` (Dataset contract: `id`, `indicator`, `provider`, `source`, `key`, `url`, `definition`, `unit`, `frequency`, `span`, `retrieved`, `sha256`, `licence`, `attribution`, `publishable`, `validation`)
- `data/fred/fred.log.json`
- `url` must be the series page (`https://fred.stlouisfed.org/series/<ID>`): readers' "Data source" link opens it directly, and the "Finding the series" note under it is built from `key`.
- Scout mode: the same files under `scout/data/fred/`, plus `probe.json` with the latest value, its date and the history's extremes for each quantity the question names

## Done when

Every routed indicator has a fetched series with a `pass` or explained `warn` verdict, or a logged reason for skipping it. Then `artools run done $run_id fetch-fred` (scout: `scout:fetch-fred`); it validates the catalog or the logged skip. Without a run (a one-off lookup), use `--out <folder>` instead of `--run`.

## Never

- Print, log or write the API key (the script redacts it; don't work around that).
- Use a series that failed validation without `--force` and a logged reason.
- Anchor a validation on the series itself.
- Mark a series publishable that FRED tags `copyrighted: pre-approval required`.
- Fetch "just in case": every series must serve a planned sentence, key number, chart or premise check.
