# Charts

Glacier's data-visualisation rules, applied to explainers, plus ours. The JSON shape of a chart is in `contracts/content.md` § charts; in a run, `meta.sources` holds dataset and evidence ids (the publisher turns them into S1…Sn) and a line series may name its `dataset` so `check charts` can compare its values with the data.

## Pick the form from the data's job

| The data's job | Form |
|---|---|
| Three headline numbers | `stat-tiles` |
| One series over time is the story | `line`: focus + context |
| Compare one measure across items | `bars`: horizontal, sorted, from zero |
| Then versus now, by item | `dumbbell` |
| Two measures and their relation | `scatter`: labelled points, ≤ 3 groups |
| Exact values readers will look up | `table` |

An article has 3–6 figures in at least two forms, one per main point, a figure every 300–400 words.

## Every chart

- **headline**: the takeaway as a sentence ("France's spread is at 63% of its 2011 peak; Italy's at 17%"). The text must not contradict it.
- **title**: what is plotted; **subtitle**: unit, frequency, span ("Basis points, monthly averages, Jan 2007–Sep 2026").
- **axes**: a label with the unit on every value axis, in each language; 4–6 round ticks (0, 50, 100 …; years every 2 or 4); a domain that includes every value the text discusses.
- **howToRead**: one plain line for any form beyond a simple line or bar ("Each dot is a country; further right means more debt, higher means a wider spread").
- **notes**: data gaps, exclusions, definitions, and why a series is left out.
- **meta**: sources (dataset ids), provider, keys, definition, calculation, span, lastObservation, retrieved, licence, attribution ("Source: ECB Data Portal; datasteg calculation" / "자료: ECB 데이터 포털, datasteg 계산"). The site and the PDF head the line themselves ("Source:" / "자료:", as Bank of Korea releases do) and drop any head the attribution already carries, so `출처:` never reaches readers and nothing is doubled.
- **alt**: the takeaway with its numbers, in each language.
- **table**: the same data as rows, so every value is readable without the picture.

## Rules

- Bars start at zero. Scales are linear. Never two y-axes (Glacier), never broken or log scales (ours).
- When one series dwarfs the rest (Greece's 2,739bp in 2012), don't squash the others: show a share or index (% of peak), use a table, or leave the outlier out of the line chart and say so in `notes`.
- Focus colour for the story's series, context for the rest; at most 8 series; direct end labels for ≤ 4.
- At most three annotations, each a dated event with an evidence id behind it (`annotations[].evidence`). Bands for named periods ("Euro-area debt crisis, May 2010–Aug 2012").
- Units consistent across the article: spreads always in bp, debt always in % of GDP.
- Korean units and labels follow the Bank of Korea (「한국은행 표현 노트」, section 6): money in 억 달러 or 조 달러, never 10억 달러 (no BoK table has a billion unit); %p, not %포인트; 전년동월대비, 전년동기대비, written as one word.
- Only publishable datasets. A chart built on anything else fails `check licences`.
- Values come from the run's data or `analyze-data`'s derived CSVs, never typed by hand.

## Look at it

`artools render charts <run>` screenshots each figure through the real site in both languages, both themes, at 1040 and 375 px. Read the PNGs: labels overlapping or clipped, crowded ticks, colours hard to tell apart, a takeaway the picture doesn't show at a glance. Fix and render again.
