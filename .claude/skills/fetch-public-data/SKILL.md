---
name: fetch-public-data
description: Fetch and validate euro-area and EU statistics for an articles run from the ECB Data Portal and Eurostat (no key needed) - government bond yields by country, government debt and deficits, and other ECB and Eurostat series. Scout mode takes reality checks for the quantities a question names; deep mode fetches the indicators the litmap routes to ecb or eurostat.
argument-hint: <run-id> [scout|deep]
arguments: [run_id, mode]
allowed-tools: Bash(artools *) Read Write
metadata:
  version: 0.1.0
  family: source
  produces: dataset
  providers: [ecb, eurostat]
---
# fetch-public-data

## Purpose

Bring the euro-area and EU series an article needs into the run as validated Dataset records. Series keys that work are in `${CLAUDE_SKILL_DIR}/reference/series.md`; use them before searching for others.

## Scout mode (`$mode` = scout)

1. `artools run start $run_id scout:fetch-public-data --version 0.1.0`
2. From `brief.v1.json`, list the quantities the question names, and the comparators (countries, periods).
3. Fetch each with `--scout`. Example: 10-year yields for the countries named, plus Germany as the benchmark, from 2007:
   `artools data ecb get IRS.M.FR.L.L40.CI.0000.EUR.N.Z --run $run_id --scout --from 2007-01 --id ecb-irs-fr --indicator "10-year government bond yield, France"`
4. Compute the reality checks with `artools data query $run_id --sql "…"`. Tables are named `scout_<dataset id with _>`. Checks:
   - the latest observation and its date;
   - the change over the year so far;
   - the extremes and when they happened;
   - when the series was last as high as now;
   - the same for the comparators.
5. Write `/data/articles/runs/$run_id/scout/data/public-data/probe.json` as `[{"quantity", "series", "latest": {"period", "value"}, "extremes": [{"kind", "period", "value"}], "notes"}]`, and `public-data.log.json` (what was fetched and why).
6. `artools run done $run_id scout:fetch-public-data`

## Deep mode (no mode, or `deep`)

1. `artools run start $run_id fetch-public-data --version 0.1.0`
2. Read `litmap.json`. Take the indicators with `provider` `ecb` or `eurostat` and priority `needed` or `useful`. If none, write `data/public-data/public-data.log.json` with `{"skipped": "<reason>"}`, then mark done.
3. For each, choose the series (`reference/series.md`), then fetch with validation:
   - `--range` for plausible values;
   - an `--anchor` taken from a published value outside the series where you have one (for example a scout probe from another provider, or a value quoted in a verified evidence record);
   - `--id` short and readable: `ecb-irs-fr`, `eurostat-gd-fr`.
   For Eurostat:
   `artools data eurostat get gov_10dd_edpt1 --params "na_item=GD&sector=S13&unit=PC_GDP&freq=A" --geo FR,DE,IT,ES,PT,EL --since 2007 --run $run_id --indicator "General government gross debt, % of GDP" --id-prefix eurostat-gd`
4. Read each result's `verdict` and warnings. Never keep a `fail`. Explain each `warn` in the log.
5. Write `data/public-data/public-data.log.json`: indicators, series chosen and why, verdicts, skipped indicators with reasons.
6. `artools run done $run_id fetch-public-data`

## Judgement

- The ECB's convergence-criterion yields (`IRS`) are the standard monthly 10-year yields for EU countries; spreads are computed against Germany in `analyze-data`, not fetched.
- Eurostat codes Greece `EL`; the tool names the dataset `…-gr`.
- Annual debt data end a year behind (2025 values published April 2026); say so in the log.
- Never mix two providers' versions of one concept in one chart (ECB vs OECD yields differ slightly).
- Readers get a "Finding the series" note under each data source, built from the record: an ECB `url` must open the series itself; a Eurostat `key` must keep the dataset code and every filter (`nama_10_gdp?na_item=B1GQ&unit=…`) and `definition` its labels. For a provider other than ECB or Eurostat, write `locate` in the record: `{"en": "…", "ko": "…"}`, one paragraph on the clicks from the link to the exact series.

## Never

- Fetch series no indicator asks for.
- Keep a series whose validation failed.
