---
name: make-charts
description: Build every figure in an approved article plan as a chart file (line, bars, dumbbell, scatter, stat tiles, table) from the run's data and facts - with takeaway headline, labelled axes and units in both languages, notes, how-to-read line, full source metadata and a table view - then render them through the real site and inspect the images.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit
metadata:
  version: 0.1.0
  family: stage
---
# make-charts

## Purpose

Turn the plan's figures into charts a general reader understands at a glance, and can check. Read first:
- `guides/charts.md`;
- `contracts/content.md` § charts, the exact JSON shape per form;
- `guides/numbers.md` for units.

## Inputs

`plan.json` (`figures`), `analysis/analysis.json`, `data/*/catalog.json` and CSVs (including `data/derived/`), `draft/en.json` and `draft/ko.json` (what the text says about each figure). In fix mode, `review.json`: fix every blocking issue whose `owner` is `make-charts`.

## Steps

1. `artools run start $run_id make-charts --version 0.1.0`
2. For each figure in the plan, pull the values with `artools data query $run_id --sql "…"` (tables are named after dataset ids, with `-` → `_`). Never type values by hand.
3. Write `charts/<figure id>.json` per `contracts/content.md`, with every text field as `{"en": …, "ko": …}`. In the run:
   - `meta.sources` holds dataset ids (or evidence ids for annotations); the publisher turns them into S-numbers;
   - each line series names its `dataset` when it comes straight from one, so `check charts` can compare the values;
   - `stat-tiles` tiles use the same fact tokens as the draft's key numbers (`"value": "{{F4}}"`), and a `cite` list of dataset ids;
   - every non-tile chart has a `table` with the same data.
4. `artools check charts --run $run_id`. Fix every blocking issue.
5. Render: `artools render charts $run_id`. It writes PNGs to `charts/render/<id>.<lang>.<theme>.<width>.png` through the real site. Read every PNG: both languages, both themes, 1040 and 375 px. Look for:
   - labels that overlap, are clipped or are unreadable at 375 px;
   - ticks that are crowded or not round;
   - colours hard to tell apart, or the focus series not standing out;
   - a takeaway that doesn't show at a glance;
   - Korean labels that are too long.
   Fix the chart files and render again, at most three rounds. If rendering fails (the site isn't available), record that in `charts/charts.log.json` and rely on `check charts`.
6. Write `charts/charts.log.json`: per figure, the choices made (form, focus, domain, what was left out and why) and what the visual check changed.
7. `artools run done $run_id make-charts`

## Judgement

- One message per chart; the headline states it. The headline must not claim more than the picture shows.
- Axes: the unit in the label ("Basis points" / "bp"); round ticks; a domain that includes every value the text mentions; bars from zero.
- One series dwarfing the rest:
  - show it as a share or an index;
  - or put it in the table and say so in `notes`;
  - never a log or broken scale.
- Annotations: at most three dated events, each with an evidence id in `meta.sources`. Bands for named periods.
- Korean labels are shorter; check they still say the unit.

## Never

- Edit the site's code (`apps/`, `packages/`): it is shared by every run. If a chart form can't show what the plan needs, choose another form or record the limitation in `charts/charts.log.json` for the maintainer.
- Use non-publishable data.
- Draw a value that isn't in the data.
- Leave a chart without a table view, a source line or alt text in both languages.
