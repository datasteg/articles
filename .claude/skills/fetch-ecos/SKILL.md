---
name: fetch-ecos
description: Find, validate and fetch Korean economic statistics from the Bank of Korea's ECOS Open API for an article run - the base rate, government bond yields, the won, prices, growth, money, the balance of payments, foreign holdings, and ECOS's international tables. Use only when the article needs Korean data or a Korea angle readers will value; ECOS is not a REST API, so always go through scripts/ecos.py.
argument-hint: <run-id> [scout|deep]
arguments: [run_id, mode]
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py *) Bash(artools *) Read Write
metadata:
  version: 0.1.0
  family: source
  produces: dataset
  provider: ECOS
---
# fetch-ecos

## Purpose

Turn the indicators a run needs into validated ECOS series, saved in the run as Dataset records (`data/ecos/catalog.json` plus one CSV per series). In ECOS, a series is a table code, a cycle and up to four item codes, passed as bare path segments in a fixed order. Codes are hard to find: a concept is usually an item name, not a table name, and a table may need two item codes. So most of the work is finding the right codes and proving them. `${CLAUDE_SKILL_DIR}/scripts/ecos.py` does the calls; `reference/api.md` is the specification.

## When to use, and when not

This skill is optional. The driver runs it only when the run routes at least one indicator to it, and each indicator must pass all three tests:

1. **A reader needs it.** The number supports a sentence, a key number or a chart in the plan, or a premise check in scout mode. For a non-Korean topic that means the plan has an approved Korea angle (for example "what it means for Korea", for the Korean edition), not a Korean series added for colour.
2. **ECOS is the right home.** Korean statistics (the Bank of Korea's own, and others ECOS republishes) and, when no closer primary source exists, ECOS's international tables (`902Y…`, from the IMF, OECD and BIS). For euro-area yields prefer the ECB; for US data, FRED.
3. **It can be shown.** The producer (`ORG_NAME`) is the Bank of Korea, or another producer's terms have been checked (`--publishable`). Otherwise it is for the editor's context only.

If no indicator passes, write `data/ecos/ecos.log.json` (scout: `scout/data/ecos/ecos.log.json`) with `{"skipped": "<reason>"}`, then mark the stage done.

## Inputs

- `/data/articles/runs/$run_id/brief.json` (scout mode: `brief.v1.json` and its premises)
- `/data/articles/runs/$run_id/litmap.json`: indicators with `provider: ecos` and their `reader_value` (deep mode)
- `/data/articles/runs/$run_id/plan.json`, when present
- `${CLAUDE_SKILL_DIR}/reference/indicators.md`: series already validated, with their codes

## Steps

0. `artools run start $run_id fetch-ecos --version 0.1.0` (scout mode: stage `scout:fetch-ecos`). In scout mode, write with `--out /data/articles/runs/$run_id/scout/data/ecos` instead of `--run`, and add `probe.json` there; in deep mode use `--run /data/articles/runs/$run_id`.
1. **List the indicators** routed to ECOS: concept, cycle, unit, period, and why a reader needs it. Drop any that fails the three tests above, and log the reason.
2. **Look up `reference/indicators.md` first.** A listed series still gets validated (step 5).
3. **Otherwise find the codes** (`reference/search-playbook.md` explains how):
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py index                     # weekly: all items of all 617 tables (cached; ~30 min to build)
   python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py find 국고채 10년 --cycle D    # words in table + group + item names
   python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py tables 시장금리              # table names, with their place in the tree
   python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py --lang en tables "interest rate"
   python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py items 902Y023 프랑스         # a table's groups, items, cycles, spans, units
   ```
   Shortlist candidates. For each, note the table's place in the tree, every item group (one code per group), the cycles the item exists in, its span, unit and producer.
4. **Get an anchor** from outside the series: `ecos.py keystats <word>` (the Bank of Korea's 100 key statistics with their latest values), a Bank of Korea press release, or the same concept from another provider.
5. **Validate**, giving one item code per group, in group order:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py validate 817Y002 D 010210000 --from 20070101 --unit % \
       --range 0,10 --anchor 20261016=<value>:0.05 [--compare other.csv --compare-tol 0.05]
   ```
   The checks: table searchable, producer and licence, each item in its group and cycle, every group set, unit, exactly one value per period, missing values, freshness, coverage, range, anchors, comparison. Verdict `fail`: fix the codes or choose another table. Verdict `warn`: read every warning, and record why it's acceptable or choose another.
6. **Fetch** with the same arguments plus the plain-words indicator name:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/ecos.py fetch 817Y002 D 010210000 --from 20070101 \
       --run /data/articles/runs/$run_id --indicator "Korea 10-year government bond yield" --unit % --range 0,10
   ```
   It writes the CSV (ISO dates), the raw responses, the request without the key, and the catalog entry with producer, licence, attribution and validation. It refuses on a failed validation unless given `--force` (then the log must say why).
7. **Log the choice** in `data/ecos/ecos.log.json`: for each indicator, the candidates considered, the codes chosen and why, the verdict and warnings, and anything skipped. Propose new rows for `reference/indicators.md` under `reference_additions`.
8. **Definitions for readers.** If a term in the plan's glossary is in the Bank of Korea's statistics glossary, take it with `ecos.py word <term>` and record it in the log as a glossary source (the editor approves the wording).

## Judgement

- **Daily or monthly is a choice of table.** Market rates are daily in `817Y002` and monthly averages in `721Y001`; exchange rates are daily in `731Y001` and monthly averages in `731Y004`. Pick the table whose cycle matches the claim.
- **Every group, every time.** If a table has two item groups, give both codes. The validator fails a series with duplicated periods, because it is several series mixed together.
- **Parent and child items.** `P_ITEM_NAME` shows where an item sits. Don't take a component (a sub-item) for the total, or the reverse.
- **Units are in Korean, and scaled.** 연% is percent a year; 십억원 is billion won; 백만달러 is million dollars. Convert once, in `analyze-data`, and say so in the chart's subtitle.
- **Producer decides what readers see.** A Bank of Korea statistic is publishable with "Source: Bank of Korea, ECOS". A statistic from another producer (Seoul Money Brokerage, IMF, OECD, BIS, Statistics Korea) carries that producer's copyright: publish only after its terms are checked, with "Source: <producer>, via Bank of Korea ECOS".
- **One provider per concept per chart.** ECOS's international long-term rate for France (OECD, 4.48% in Sep 2026) and the ECB's (4.44%) differ slightly; don't mix them in one chart.

## Output

- `data/ecos/<dataset-id>.csv` (`date,value`, ISO dates by cycle: `2026-09`, `2026-Q3`, `2026-10-16`), `data/ecos/raw/`, `data/ecos/catalog.json` (Dataset contract, including `source` = producer, `licence`, `attribution`, `publishable`, `validation`)
- `data/ecos/ecos.log.json`
- Readers see a "Finding the series" note under each data source, built from the record's `table` check (the menu path) and `item` checks (the item names) and the cycle in `key`. ECOS links open only the home page, so keep those checks as the script writes them.
- Scout mode: the same files under `scout/data/ecos/`, plus `probe.json` with the latest value, its date and the history's extremes for each quantity the question names

## Done when

Every routed indicator has a fetched series with a `pass` or explained `warn` verdict, or a logged reason for skipping it. Then `artools run done $run_id fetch-ecos` (scout: `scout:fetch-ecos`); it validates the catalog or the logged skip. Without a run (a one-off lookup), use `--out <folder>` instead of `--run`.

## Never

- Build ECOS URLs by hand, or print, log or write the key (it sits in every URL; the script redacts it).
- Call `StatisticSearch` with fewer item codes than the table has groups.
- Anchor a validation on the series itself.
- Mark a non-Bank of Korea statistic publishable without checking its producer's terms.
- Fetch "just in case": every series must serve a planned sentence, key number, chart or premise check.
