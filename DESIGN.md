# Glacier, as applied on articles.datasteg.com

Glacier is the design system of the articles site. Its picture is a glacier seen from inside: fresh snow as the
reading surface, light-filled ice for panels, a bright cyan where light shines through the ice for the one action
colour, and a deep blue-black, never pure black, for text. By night the page becomes night ice and the text turns
pale. A warm dawn colour (alpenglow) is kept for the editor's own voice and nothing else.

Everything visible is built from tokens. Components and pages refer to `var(--token)` only, and
`scripts/check-colors.mjs` fails the build on a hard-coded colour outside `packages/tokens` (the shared datasteg
bar at the top of every datasteg site is the one exception, because it carries the family's own colours).

| Where | What |
|---|---|
| [`packages/tokens/tokens.json`](packages/tokens/tokens.json) | The source of every token: colour (two themes), type, spacing, radius, shadow, layout, breakpoints, canvas sizes, each with its usage note |
| [`packages/tokens/build.mjs`](packages/tokens/build.mjs) | Writes `tokens.css`: the light theme on `:root`, the dark theme under `[data-theme="dark"]` and under `prefers-color-scheme: dark` when no theme is set |
| [`packages/ui/glacier.css`](packages/ui/glacier.css) | Component styles (`gl-*` classes), every value a token |
| [`packages/ui/src/`](packages/ui/src) | The React components |
| [`packages/charts/`](packages/charts) | The article charts (`ac-*` classes over Glacier's chart anatomy) |
| [`packages/fonts/`](packages/fonts) | Self-hosted fonts, split so that English pages load no Hangul files |
| [`apps/web/lib/ds-type.css`](apps/web/lib/ds-type.css) | The datasteg family type layer, loaded last: it points Glacier's font tokens at the family's typefaces |
| [`apps/web/app/site.css`](apps/web/app/site.css), [`article.css`](apps/web/app/article.css), [`print.css`](apps/web/app/print.css) | The site's own layouts: feed, article page and the A4 PDF edition |
| [`guides/charts.md`](guides/charts.md), [`guides/covers.md`](guides/covers.md) | The rules the AI agents follow when they draw charts and covers |

## Palette

### Identity colours

Fixed values, used through the theme tokens below rather than directly.

| Token | Hex | What it is |
|---|---|---|
| `snow` | `#FFFFFF` | Fresh snow: the reading surface by day |
| `frost` | `#E9FBFF` | The faintest ice tint, quiet panels by day |
| `ice` | `#C8F6FF` | Thin, light-filled ice: tinted panels and the cover tint |
| `glacier` | `#5BCEF3` | Light shining through the ice: the action fill by day, with dark text on it (8.7:1) |
| `meltwater` | `#89E0F8` | The hover state of `glacier`; the accent by night |
| `ice-wall` | `#B6F4FF` | Standing inside the ice: the fill of deep blocks by day |
| `tarn` | `#006C9B` | A glacial lake: the text-safe blue for links, kickers and focus |
| `crevasse` | `#004774` | The darkest blue in use: buttons on deep blocks, the big number on deep infographics |
| `abyss` | `#001E32` | Night ice |

### Theme tokens (light / dark)

| Token | Light | Dark | Used for |
|---|---|---|---|
| `surface` | `#FFFFFF` | `#012333` | Page background everywhere |
| `surface-frost` | `#E9FBFF` | `#0D2F41` | Quiet panels: the topic rail, tags, code blocks, notices |
| `surface-ice` | `#C8F6FF` | `#153D4F` | Tinted callouts: key findings |
| `line` | `#C4EDF7` | `#244758` | Hairlines: feed dividers, masthead edge, card borders, gridlines |
| `line-strong` | `#588EA8` | `#5288A2` | Borders that carry meaning: inputs, the secondary button |
| `ink` | `#022A41` | `#E7F9FE` | Primary text (at least 12:1) |
| `ink-secondary` | `#315B72` | `#A7D3E1` | Deks, labels, chart values |
| `ink-muted` | `#496E84` | `#81B4C6` | Metadata only: dates, read time, captions, axis ticks |
| `accent` | `#5BCEF3` | `#6EDBFC` | The one action fill: primary button, selected segment, active underline |
| `accent-hover` | `#89E0F8` | `#9FECFF` | Hover and pressed state of the accent |
| `on-accent` | `#022A41` | `#012333` | Label on an accent fill: a glowing button, never a dark one |
| `link` | `#006C9B` | `#89E0F8` | Inline links, active navigation, finding numerals |
| `focus` | `#0081B1` | `#6EDBFC` | Focus ring, 2px solid, 2px offset |
| `glacial` | `#0081B1` | `#4CC8EE` | Small marks and labels: the strata rule, the kicker above a title |
| `alpenglow` | `#A84A22` | `#F0A07E` | The editor's voice: the Insight label and the New marker only, one per screen |
| `alpenglow-soft` | `#FDEFE6` | `#3A1F14` | Reader highlights (`<mark>`) |
| `deep` | `#B6F4FF` | `#004E75` | Inside the glacier: the fill of hero and subscribe blocks |
| `deep-edge` | `#89E0F8` | `#147298` | The 1px rim around deep blocks |
| `deep-strata` | `#7ADAF8` | `#076C92` | Decorative strata lines inside deep blocks, never text |
| `on-deep` | `#022A41` | `#FFFFFF` | Titles on `deep` |
| `deep-accent` | `#004774` | `#89E0F8` | The kicker and button fill on `deep` |
| `status-good` | `#1F7A4D` | `#4CC38A` | Status, always with an icon and a word |
| `status-warning` | `#946200` | `#E8B13A` | Warning or provisional data |
| `status-critical` | `#B3261E` | `#F2A49B` | Errors; also `delta-bad` and `delta-fall` |

Market deltas follow the international convention (green up, red down). Inside `[data-market="kr"]` the two swap,
as Korean readers expect.

### Chart colours

| Token | Light | Dark | Used for |
|---|---|---|---|
| `viz-focus` | `#0072A8` | `#6EDBFC` | The one series the story is about |
| `viz-context` | `#7A97A6` | `#547080` | Comparison series, "Other", sparklines |
| `viz-1` … `viz-8` | `#2F8AE4` `#E0703C` `#17A37A` `#B8860B` `#C9659B` `#5C8F22` `#7A5CC4` `#D24B4B` | `#4A9AE8` `#CF6833` `#169A72` `#B0820F` `#C25F95` `#5C8F22` `#8A72D6` `#D65555` | Categorical slots, in order: glacier blue, alpenglow orange, glacial lake, moraine ochre, heather, lichen, dusk violet, alpenrose |
| `viz-grid` | `#C4EDF7` | `#244758` | Horizontal gridlines (the `line` token) |
| `viz-axis` | `#A3C4D1` | `#3A5D6F` | The zero baseline, darker than the grid so zero is findable |
| `viz-band` | `#E2F8FE` | `#103243` | Shaded periods: recessions, crisis windows |
| `seq-100` … `seq-700` | `#DDF6FF` → `#00426B` | `#013752` → `#CAEEFF` | Sequential ramp for magnitudes |
| `div-neg-3` … `div-pos-3` | `#A1420B` … `#EBEFF2` … `#005E98` | `#F2AB83` … `#29353C` … `#97D4F8` | Diverging ramp: an alpenglow arm below, a glacier arm above, a neutral grey midpoint |

## Type

Glacier's own stacks are Hanken Grotesk (sans), Source Serif 4 (serif) and JetBrains Mono, with Pretendard, Noto
Sans KR and Noto Serif KR for Korean. On the live site the family type layer (`apps/web/lib/ds-type.css`) points
those tokens at the typefaces every datasteg site shares, so each component keeps its sizes and spacing and changes
only its face:

| Role | Typeface | Korean |
|---|---|---|
| Headlines and big numbers (`--font-serif`, `--font-display`) | Newsreader, in its optical sizes, at a light-to-book weight | Noto Serif KR |
| Text, menus, labels and charts (`--font-sans`) | Libre Franklin | Pretendard |
| Codes, ids and paths (`--font-mono`) | JetBrains Mono | |

The type scale in `tokens.json` sets the sizes: the article title 42/52 (32/40 on phones), section headings 26/32,
the dek 22/30 in `ink-secondary`, body copy 20/32 at a measure of 680px (about 70 characters), and the Insight (the
editor's read) as a 24/36 italic quote, upright in Korean.

## Components

From `packages/ui`, styled by `glacier.css`:

- **Masthead**, **LanguageSwitch** (English / Korean) and **Footer**; a theme toggle that sets `data-theme` on the root
  (also `?theme=light|dark` in the address).
- **StoryCard**: the feed item, with the article's cover and a plate of what it is built on (indicators, papers,
  charts).
- **ArticleHeader**: kicker, title, dek, byline, tags and the action bar (PDF, Cite).
- **KeyFindings** on `surface-ice`, **StatTile** for key numbers, **PaperCard** for a cited paper, **Insight** for
  the editor's read, **Notice**, **EmptyState**, **Skeleton**.
- **StrataRule**: three short rules, Glacier's section mark; **IssueHero** and **SubscribeBox**: deep blocks with
  strata drawn inside.
- **Figure**, **ChartCard**, **Legend**, **ChartTooltip**, **DataTable**, **Sparkline**, **Delta**,
  **SegmentedControl**, **Switch**, **Button**, **Tag**.

Corners are mostly hard (`radius-none` for figures: ice has hard edges); panels use 8px, tags and buttons a pill.

## Charts

The article charts (`packages/charts`) draw the chart contract in `contracts/content.md` (§ charts): line, bars,
dumbbell, scatter, stat tiles and table. The conventions, which the chart agent follows and `artools check charts`
enforces where it can (`guides/charts.md`):

- One **focus** series in `viz-focus`, the rest in `viz-context`; at most eight series, direct end labels up to four.
- Horizontal gridlines only, a darker zero rule, linear scales, bars from zero; never two y-axes, never a broken or
  log scale.
- A headline that states the takeaway, a title for what is plotted, a subtitle with unit, frequency and span.
- At most three annotations, each a dated event backed by a piece of evidence; bands for named periods, labelled in
  text.
- Every chart has a table of the same values, alt text with its numbers, and a source line; its data can be
  downloaded as CSV.

## Covers

Each article has a small drawn cover (`guides/covers.md`). Its colours are classes, `f-` fills and `s-` strokes, each
bound to a Glacier token in `site.css` (`f-frost`, `f-ice`, `f-deep`, `f-strata`, `f-glint` …), so a cover follows
the theme. `pipeline/artools/cover.py` holds the same palette, and a test keeps the two in step.

## Print

The PDF edition of each article is the site's own page (`/print/<lang>/<slug>`, `print.css`) set as a journal page
on A4 paper in the same type and colours, printed headless from the published content.
