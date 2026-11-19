# Content format: what `artools publish` writes and the web app reads

The only interface between the newsroom and the site. Field names are camelCase. Every reader-facing text field is an object with one entry per edition: `{"en": "...", "ko": "..."}`; per-language files (`en.json`, `ko.json`) hold plain strings instead. There is no JSON Schema for these files: the run files they are built from are checked against `contracts/draft.schema.json`, `chart.schema.json` and `cover.schema.json`, and the site's `scripts/check-content.mjs` checks the content itself at build time.

```
content/
  articles/<slug>/
    meta.json        shared, language-neutral
    en.json          the English edition
    ko.json          the Korean edition (absent when meta.editions is ["en"])
    sources.json     every cited source, numbered S1…Sn
    related.json     related reading (not cited)
    charts/<id>.json one file per figure
    data/<id>.csv    the data behind each chart (publishable data only)
    cover.svg        the picture beside the article in every list (§ Cover below; optional)
    pdf/<lang>.pdf   the PDF edition of each language (§ PDF below)
    data/data.zip    a data note's data download (meta.download {file, bytes}; served as /data/<slug>/datasteg-<slug>-data.zip)
  glossary/<id>.json shared glossary terms, reused across articles
```

The site also reads `config/pipelines/<type>.yaml`, the article types and their pipelines (§ Pipelines below).

The web app reads `content/` by default and the folder named by `CONTENT_DIR` when set: `artools preview` writes `.preview/` (gitignored), and the shared preview site (port 3311, started by `artools render` or `artools preview-server start`) runs the app with `CONTENT_DIR=.preview`. `artools ship` writes `content/` through `artools publish`. In preview, articles without editor approval are shown with a "Preview: not approved" notice; in a production build they fail the build.

## meta.json

```json
{
  "slug": "france-spread-2026",
  "type": "explainer",
  "date": "2026-10-20",
  "updated": null,
  "editions": ["en", "ko"],
  "topics": [{"id": "sovereign-debt", "label": {"en": "Sovereign debt", "ko": "국가채무"}}],
  "jel": ["E62", "G12", "F34"],
  "countries": ["FR", "DE", "IT", "ES", "PT", "GR"],
  "readTime": {"en": 8, "ko": 9},
  "charts": ["key-numbers", "spread-history", "share-of-peak", "debt-then-now", "debt-vs-spread"],
  "facts": [{"id": "F4", "value": 96.7, "unit": "bp", "period": "2026-09"}],
  "run": {"id": "20261020-france-spread", "skills": {"draft-article": "0.1.0"}, "models": ["claude-opus-5-5", "claude-sonnet-5-5"]},
  "review": {"editor": "datasteg desk (autonomous agent)", "approved": "2026-10-20"},
  "corrections": [{"date": "2026-10-22", "text": {"en": "...", "ko": "..."}}]
}
```

`review.approved` is null until gate 3. The production build fails on any article without it. `review.editor` is whoever approved the publish gate; for the three live articles that is "datasteg desk (autonomous agent)".

Added 20 Oct 2026 (multi-article site; all optional, so older articles still build):

```json
{
  "type": "explainer",
  "pipeline": {"id": "explainer", "version": "1.1"},
  "run": {
    "id": "20261020-france-spread",
    "runtime": {"model": "claude-opus-5-5", "effort": "high"},
    "steps": {"search": {"docs": 16, "quotes": 60}, "fetch": {"series": 59, "providers": ["ECB", "Eurostat", "FRED"]},
              "analyze": {"facts": 261}, "review": {"rounds": 6}, "cover": {"ideas": 3}},
    "gates": {"question": {"at": "2026-10-20", "by": "datasteg desk"}, "plan": {"at": "2026-10-20", "by": "datasteg desk"},
              "publish": {"at": "2026-10-20", "by": "datasteg desk (autonomous agent)"}}
  },
  "terms": [{"id": "spread", "context": {"en": "Here: France's 10-year yield minus Germany's.", "ko": "이 글에서는 프랑스 10년물 금리에서 독일 금리를 뺀 값."}}]
}
```

- `type` is the article type: the id of a pipeline in `config/pipelines/`. The site groups articles by it and links each type to its method page.
- `pipeline.version` is the pipeline version the run followed.
- `run.steps` is keyed by the pipeline's step ids. Each value holds counts from the run (run records; the article page does not show them). The stat keys are: `premises`, `docs`, `quotes`, `series`, `providers` (a list of names), `mechanisms`, `facts`, `sections`, `figures`, `words`, `charts`, `rounds`, `papers`, `speeches`, `themes`, `ideas` (the cover's ideas weighed). The site has a label for each; it ignores unknown keys.
- `run.gates` gives the date and approver of each editor gate the run passed, keyed by gate name. Dates are in the newsroom's calendar (Seoul).
- `run.runtime` is the model and effort the run was set to (`run.json` → `runtime`), and `run.models` every model its stage sessions and subagents used, from the stage logs. They are for the record and for comparing runs; the site doesn't show them.
- `facts` lists every fact the run computed (`analysis.json`), with `id`, `value` (unrounded), `unit` and `period`. Added 10 Nov 2026 for the API: `publishable` is false for a fact the analysis blocked or one computed from a series that may not be published, and the API serves only publishable facts; `sources` lists the `sources.json` ids of the series and documents it was computed from, and a fact none of whose series the article cites has `sources: []` and names them in `series` (`[{"provider", "key"}]`). The 8 articles shipped before were filled by `scripts/backfill_meta_facts.py`.
- `terms` lists the glossary terms this article uses. The order is the reading order, as the build derives it from the `((id))` marks. `context` is optional: one sentence on how the term is used in this article. The shared definition stays general (glossary below).

### What the article drew on

Added 8 Nov 2026. For the portal's Data chart (publishers → apps → articles), `artools publish` records which app the article draws on and how much data its run fetched directly, both from the article's own record, never estimated (`pipeline/artools/content.py` → `article_volume`; the 8 articles shipped before this were filled by `scripts/backfill_meta_volume.py`):

```json
"draws_on": ["open-research"],
"draws_on_evidence": {"open-research": 14},
"fetch": {"ecos": {"series": 12, "rows": 34567, "bytes": 789012}, "fred": {"series": 8, "rows": 12345, "bytes": 234567}}
```

- `draws_on` lists the apps in the order money-flow, trade-flow, global-network, open-research: open-research when `sources.json` has a research-archive document (`ref` `jejualps:<id>`, the store open-research is built from), another app when a source's `url` or `pdfUrl` is on that app's host (`family/family.json`). `[]` when none applies: a measured zero. `draws_on_evidence` counts, for each app listed, the distinct `sources.json` entries that put it there.
- `draws_on_note` is the editor's, added by hand with an app the rule doesn't find; an update keeps the note and that app.
- `fetch` is keyed by the run's provider folders, `data/<provider>/`, without `data/derived` (computed, not fetched) and the scout's `scout/data`. `series` counts the folder's `catalog.json` entries whose CSV the folder has, `rows` their data rows (header excluded) and `bytes` their sizes; CSVs no catalog entry names are not counted, and a folder with neither a catalog nor CSVs (`data/public-data` holds only its stage log) is left out. `fetch` is left out when the run's data can't be read; `artools publish` then reports `fetch_problem`.
- All three are optional; the site doesn't show them.

### Citation

Added 21 Oct 2026. How readers should cite the article, shown at its end as "Cite this article" with a copy button and BibTeX. `artools publish` stamps it into `meta.json` from `config/editorial.yaml` → `citation` (author, publisher, base URL), the edition titles (without marks), the article's date and its slug, for every article type:

```json
"citation": {
  "author": {"en": "datasteg", "ko": "datasteg"},
  "publisher": {"en": "datasteg articles", "ko": "datasteg articles"},
  "date": "2026-10-21",
  "title": {"en": "The record backs Warsh on 2021 and 2013 but not against forward guidance as such", "ko": "워시의 가이던스 비판, 2021년·2013년엔 맞고 전부는 아니다"},
  "url": {"en": "https://articles.datasteg.com/en/a/warsh-forward-guidance", "ko": "https://articles.datasteg.com/ko/a/warsh-forward-guidance"}
}
```

- Stamped, not read from the config at build time: when the config's author changes (a person now, an organisation later), published articles keep the author they were published under.
- The site writes it as `author (year), “title”, publisher, date, URL.` (Korean: `「title」`) and as a biblatex `@online` entry keyed `datasteg:<slug>`; an author without a comma is an organisation and is braced.
- `scripts/check-content.mjs` fails a production build on an article without `citation`, or whose `title` or `url` doesn't match its edition (in a preview, a missing citation is a warning).

### PDF

Added 22 Oct 2026. Each edition has a PDF edition, a journal-style A4 layout of the same article for readers who print, file or cite it. The site links it from the article header ("PDF", downloading `datasteg-<slug>-<lang>.pdf`), from "Cite this article" (both languages, with pages and size) and as `<link rel="alternate" type="application/pdf">`. `meta.json` records each file:

```json
"pdf": {
  "en": {"file": "pdf/en.pdf", "pages": 12, "bytes": 1141880, "made": "2026-10-22", "source": "d9e30b36562e5786"},
  "ko": {"file": "pdf/ko.pdf", "pages": 11, "bytes": 1711006, "made": "2026-10-22", "source": "fabcd7f433a02911"}
}
```

- **Printed, not written.** `artools pdf <slug>` (run by `artools ship` for the article it publishes) prints `/print/<lang>/<slug>`, the site's print page (`apps/web/app/print/`, `app/print.css`), with Chromium from the published files, so the PDF has the site's own type, charts and Glacier colours. The print page loads static faces of the Glacier families (Hanken Grotesk, Source Serif 4, JetBrains Mono, Pretendard; Noto Serif KR is static already), which Chromium embeds as TrueType subsets; it would embed the site's variable faces as Type 3 glyphs. It is a tagged PDF with bookmarks from the headings and the article's title as its title.
- **The layout.** A4, one serif column (Source Serif 4 / Noto Serif KR) 156 mm wide. Page 1: the masthead with a strata rule, kicker, title, dek and byline, the key numbers in a row, the article information (type, date, topics, both editions' addresses) beside the key findings. Then the question, numbered sections with indented paragraphs, numbered figures across the column (takeaway above, notes and source under, no chart/table switch) and the editor's read. Then terms, numbered references with their addresses (how to find each data series is left to the online version), related reading, the citation with BibTeX, and how the article was made (method, the steps table with what each step produced, editor, approval, corrections, the print date). From page 2, a running head (publication, title) and foot (address, page n / N).
- **Figures float.** Before printing, `pipeline/artools/pdf.py` paginates the page in page-high columns and, where a figure or table didn't fit at the foot of a page and left a gap of 45 mm or more, lets it float past up to five following paragraphs, lists, quotes and headings (the last figure also past the editor's read), never past another figure, a table or text that points back at it ("the chart above"), and never to just under a heading.
- `source` is a hash of the edition, `sources.json` and `charts/*.json` the PDF was printed from. `scripts/check-content.mjs` fails a production build on an approved article without a PDF of each edition, with a missing file, or whose `source` no longer matches (a correction that wasn't printed again); in a preview these are warnings.
- The page count also goes into `meta.run.steps.<the type's PDF step>.pages`, which the steps table prints: when the count changes, `artools pdf` prints once more so the PDF states its own length.
- The index copies each file to `apps/web/public/pdf/<slug>-<lang>.pdf` (served at `/pdf/<slug>-<lang>.pdf`) and adds its `url`. In a preview, `meta.pdf` points at the make-pdf stage's proofs (`<run>/pdf/`).

## en.json, ko.json

```json
{
  "kicker": "Sovereign debt",
  "title": "France's bond spread tops Italy's but stays far below 2011's crisis levels",
  "dek": "One sentence that adds the who and how.",
  "byline": "datasteg desk · AI-assisted",
  "keyNumbers": [
    {"value": "97bp", "label": "France's 10-year spread over Germany, Sep 2026", "cite": ["S1", "S2"]}
  ],
  "findings": ["Sentence with a number. [[S1]]"],
  "question": {
    "asked": "The refined question approved at gate 1 (question-review.json refined.<lang>).",
    "lookedAt": "What the article answers.",
    "premiseNote": "One sentence if a premise was corrected, else null."
  },
  "sections": [
    {"id": "now", "heading": "Where things stand", "blocks": [
      {"type": "p", "text": "Plain text with inline marks."},
      {"type": "figure", "chart": "spread-history"},
      {"type": "table", "caption": "…", "columns": [{"key": "country", "label": "Country", "align": "left"},
                                                    {"key": "peak", "label": "Peak 2010–12, bp", "align": "right"}],
       "rows": [{"country": "France", "peak": "154"}], "source": "S1"},
      {"type": "list", "items": ["…", "…"]},
      {"type": "quote", "text": "Verbatim quote.", "cite": "S7"}
    ]}
  ],
  "insight": {"label": "Our read", "text": "…"},
  "disclaimer": "General information, not investment advice."
}
```

Inline marks inside `text`, `findings[]`, `items[]`, `dek`:

| Mark | Meaning | Rendered as |
|---|---|---|
| `[[S3]]` or `[[S3,S5]]` | citation(s) into `sources.json` | numbered superscript(s), each opening a source popover; without JavaScript, a link to `#ref-S3` |
| `((spread))` or `((spread\|spreads))` | glossary term id, optional display text | dotted-underlined text opening the definition from `content/glossary/spread.json` |
| `*text*` | emphasis | italic in English, weight 600 in Korean (Glacier) |
| `[text](https://…)` | link | link |

Numbers are already final (the publisher rendered the fact tokens).

## sources.json

```json
[
  {"id": "S1", "kind": "dataset",
   "title": "Long-term interest rates for convergence purposes: France",
   "institution": "ECB Data Portal", "date": "2026-10-19",
   "url": "https://data.ecb.europa.eu/data/datasets/IRS/IRS.M.FR.L.L40.CI.0000.EUR.N.Z",
   "dataset": {"provider": "ECB Data Portal", "key": "IRS.M.FR.L.L40.CI.0000.EUR.N.Z", "unit": "% per year",
               "frequency": "monthly", "lastObservation": "2026-09", "retrieved": "2026-10-19",
               "attribution": "Source: ECB Data Portal",
               "locate": {"en": "The link opens the series IRS.M.FR.L.L40.CI.0000.EUR.N.Z directly in the ECB Data Portal …", "ko": "…"}},
   "cite": {"en": "ECB Data Portal. Long-term interest rates for convergence purposes, France (IRS.M.FR.L.L40.CI.0000.EUR.N.Z). Retrieved 19 Oct 2026.",
            "ko": "…"},
   "usedFor": {"en": "France's 10-year yield, monthly averages", "ko": "…"},
   // dataset.locate: one paragraph on finding the exact series on the provider's site, built by
   // pipeline/artools/locate.py from the Dataset records (or the record's own `locate`). The references show it as
   // "Finding the series" under a "Data source" link, because most links open a home page or a whole dataset.
   "citedIn": ["key-numbers", "now"]},
  {"id": "S7", "kind": "paper",
   "title": "Intraday dynamics of euro area sovereign CDS and bonds", "titleTranslated": {"ko": "…"},
   "authors": "…", "institution": "BIS", "series": "BIS Working Papers", "number": "423", "date": "2013-09-04",
   "url": "https://www.bis.org/publ/work423.htm", "pdfUrl": null, "doi": null,
   "quote": {"text": "Our main finding is that …", "lang": "en", "locator": null},
   "cite": {"en": "BIS (2013). Intraday dynamics of euro area sovereign CDS and bonds. BIS Working Papers 423.", "ko": "…"},
   "usedFor": {"en": "which market prices sovereign risk first", "ko": "…"},
   "citedIn": ["research"]}
]
```

`kind`: `paper` · `speech` · `policy-note` · `report` · `dataset` · `web`. The References section groups research (paper, policy-note, report), speeches and statements (speech, web), and data (dataset). The cover's plate counts `dataset` sources as indicators and `paper`, `policy-note` and `report` sources as papers (§ Cover).

The publisher also writes `ref` on archive sources (`jejualps:<id>`) and `dataset.publishable` on data sources, for the newsroom; the site doesn't read them. A dataset source groups one provider's series family, so a yield for eleven countries is one source.

## related.json

```json
[{"title": "…", "institution": "IMF", "date": "2014-01-28", "url": "…", "why": {"en": "…", "ko": "…"}}]
```

## charts/<id>.json

Common fields:

```json
{
  "id": "share-of-peak",
  "form": "line | bars | dumbbell | scatter | stat-tiles | table",
  "headline": {"en": "The takeaway, one sentence", "ko": "…"},
  "title": {"en": "What is plotted", "ko": "…"},
  "subtitle": {"en": "Unit, frequency, span", "ko": "…"},
  "howToRead": {"en": "…", "ko": "…"},
  "notes": [{"en": "…", "ko": "…"}],
  "alt": {"en": "…", "ko": "…"},
  "meta": {
    "sources": ["S1", "S2"],
    "provider": "ECB Data Portal",
    "keys": ["IRS.M.FR.L.L40.CI.0000.EUR.N.Z"],
    "definition": {"en": "…", "ko": "…"},
    "calculation": {"en": "…", "ko": "…"},
    "span": ["2007-01", "2026-09"], "lastObservation": "2026-09", "retrieved": "2026-10-19",
    "licence": "ECB: reuse with attribution",
    "attribution": {"en": "Source: ECB Data Portal; datasteg calculation", "ko": "출처: ECB 데이터 포털; datasteg 계산"}
  },
  "table": {"columns": [{"key": "x", "label": {"en": "Month", "ko": "월"}}, {"key": "FR", "label": {"en": "France, bp", "ko": "프랑스, bp"}, "align": "right"}],
            "rows": [{"x": "2026-09", "FR": 96.7}]},
  "csv": "data/share-of-peak.csv"
}
```

Per form:

| form | Fields |
|---|---|
| `line` | `axes.x` `{type: "time", label, format: "year" \| "month", ticks: ["2008-01", …]}`; `axes.y` `{label, unit, domain: [lo, hi], ticks: [..], format: {decimals}}`; `x: ["2007-01", …]`; `series: [{id, label, values: [..] (null = gap), color: "focus" \| "context" \| 1–8, endLabel: true}]`; `bands: [{from, to, label}]`; `annotations: [{x, label}]` (≤ 3); `referenceLines: [{axis: "y", value, label}]` |
| `bars` | horizontal bars. `axes.x` `{label, unit, domain: [0, hi], ticks}` (always from 0); `categories: [{id, label, value, highlight: bool}]` in display order; `valueFormat: {decimals, suffix}`; `referenceLines: [{axis: "x", value, label}]` |
| `dumbbell` | `axes.x` `{label, unit, domain, ticks}`; `rows: [{id, label, from, to, highlight}]`; `fromLabel`, `toLabel` (e.g. "2011", "2025") |
| `scatter` | `axes.x`, `axes.y` `{label, unit, domain, ticks}`; `points: [{id, label, x, y, group: "focus" \| "context"}]` |
| `stat-tiles` | `tiles: [{value, label, note, cite: ["S1"]}]` (text fields per language) |
| `table` | only `table` (rendered as the figure itself) |

Every axis has a label with its unit in the page's language; bars start at zero; scales are linear; never two y-axes.

Also accepted by the site (20 Oct 2026):
- Cells in `table.rows` may be plain values or `{"en": …, "ko": …}` objects (a country name, a month).
- `tiles[].value` may be a string or `{"en": …, "ko": …}`.
- `csv` is a path relative to the article folder (`data/<id>.csv`); the site serves it at `/data/<slug>/<file name>`.
- Figure width follows the form: `line` and `scatter` break out to the wide width (1040px), the others sit in the text column (680px). There is no width field.

## Cover

Added 20 Oct 2026. `cover.svg` is the picture the site shows beside the article in every list (Latest, a topic, a format): 160 × 107 px on a desktop, 80 × 54 on a phone. `make-cover` draws it after the review (`guides/covers.md`). `meta.json` names it:

```json
"cover": {"file": "cover.svg", "alt": {"en": "Two bond certificates, the French one sitting a little lower than the German one", "ko": "…"}}
```

- The drawing is `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 320">` holding only `g`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon` and `path`. Allowed attributes are geometry, `transform`, `class`, opacities and stroke settings. No ids, styles, links, text or images.
- Colours are classes, never values: `f-<name>` fills and `s-<name>` strokes, from the palette in `guides/covers.md`. `fill` and `stroke` attributes may only be `"none"`.
- The site inlines the markup inside `<svg>` in each story card, and `site.css` maps each class to a Glacier token, so the cover follows the light and dark themes. In the card it is decorative (`aria-hidden`), since the title beside it says what the article is. `alt` is kept for uses where the picture stands alone.
- `artools check cover` enforces this before publishing. The index guards it again (`readCover`): `pnpm check` fails on a cover with anything else, and the index leaves such a cover out.
- An article without `cover` shows its card without a picture.
- **The plate.** Under a cover the site attaches a plate with three counts:
  - indicators: sources of kind `dataset` in `sources.json`, one per indicator as the reference list groups it;
  - papers: sources of kinds `paper`, `policy-note` and `report`;
  - charts: `meta.charts` whose form is neither `stat-tiles` nor `table`.

  A count of zero is left out. Beside a desktop card each count is a small stat, number over label; on a phone there is one count per line, label first in Korean ("지표 11"). The plate is derived, so it needs no field, and it stays true when an article is corrected.

## glossary/<id>.json

```json
{"id": "spread", "term": {"en": "spread", "ko": "가산금리"},
 "definition": {"en": "The extra interest one borrower pays over a benchmark borrower on debt of the same maturity, usually in basis points.", "ko": "…"},
 "topics": ["bond-markets"], "see": ["basis-point", "bond-yield"],
 "approvedBy": null}
```

One file per term, shared by every article that uses it. The definition must be **general**: whatever is specific to one article (the benchmark, the period, the country) goes in that article's `meta.terms[].context`. `topics` is optional; when it is absent, the term takes the topics of the articles that use it. `see` lists related terms and is optional.

The site's index derives, for each term, the articles that use it (from their `((id))` marks), and for each article, its terms. Readers find terms in four ways:
- the term's popover in the text;
- "Terms in this article" at the end of each article;
- the glossary, which they can filter by topic or by article;
- the term's own page at `/<lang>/glossary/<id>`, which lists every article that uses it, with each article's context.

## Pipelines

`config/pipelines/<type>.yaml` defines an article type and the steps that make it. The driver (`artools drive`) runs those steps, and the site draws them as diagrams. The fields the site uses are:

| Field | Meaning |
|---|---|
| `id`, `version`, `status` | the type id (an article's `meta.type`); `status` is `live` or `sample` (the site marks samples "In development") |
| `name`, `tagline` | `{en, ko}`: "Explainer", one line on what it is for |
| `shape` | `words` `{en, ko}`, `figures` (text), `gates` (count of editor approvals) |
| `phases[]` | `{id, label}`, the diagram's rows, in order |
| `steps[]` | `{id, phase, label, detail?}`; also `skill`, or `sources: scout` / `fetch: routed` for a parallel step (with `branches[]`, labels of what runs in parallel); `gate: <name>` for an editor approval; `loop: {owners, max}` for a step that sends fixes back; `manual: true` for a step the editor runs |

