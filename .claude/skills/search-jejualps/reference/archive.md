# The jejualps archive, for searching

96,743 documents (1973 – mid-October 2026) from 17 units: `nber_wpapers` (28k), `bis_cbspeeches` (21.6k central-bank speeches), `cb_reshub` (17.8k central-bank papers via the BIS Research Hub), `worldbank_prwp` (11.4k), `imf_wpapers` (8.9k), `suerf_policy` (2k policy notes, very current), `oecd_eco_wpapers`, `bis_wpapers`, `bis_quarterly`, `fsb_publications`, `bis_mgmtspeeches`, `bis_committee_research`, `bis_fsi`, `bis_papers`, `fsb_speeches`, `bis_aer`, `bis_bulletins`.

## The index

- Full-text search with Postgres's **`simple` configuration: no stemming, no stop words.** Write word forms yourself: `spread:*` (prefix), `(france | french)`, `(yield:* | rate:*)`.
- `--fields meta` searches title + abstract (precise; good for scout). `--fields body` searches the ~4,000-character text chunks and ranks documents by best chunk and number of matching chunks (recall; good for deep).
- Operators: `&` and, `|` or, `!` not, `<->` followed by (`whatever <-> it <-> takes`), `:*` prefix. Group with parentheses.
- Short bodies (< 3,000 characters) are excluded: those were mostly junk pages in `cb_reshub`.
- Dates in the future (one document is dated 2035) are excluded.

## Queries that worked for sovereign spreads (19–20 Oct 2026)

| Query | Fields | Matches |
|---|---|---|
| `sovereign & spread:* & (euro:* \| france \| italy)` | meta | 48 |
| `(france \| french) & (sovereign \| oat \| bond:*) & (spread:* \| yield:*)` since 2024 | body | 276 |
| `sovereign & debt & crisis & (italy \| spain \| greece \| portugal)` | body | 2,819 |
| `redenomination \| ((doom \| diabolic) & loop) \| (multiple & equilibria & sovereign)` | body | 817 |

Very broad body queries return thousands; add a mechanism word or a period.

## Search output

`artools jejualps search` prints a header line, `{"query", "fields", "total", "shown"}`, then one JSON line per document, best first:

| Field | What it is |
|---|---|
| `id`, `date`, `kind`, `inst`, `title` | the document; its ref is `jejualps:<id>`; `kind` is paper · speech · policy-note · report |
| `text` | the abstract's first 300 characters. When there is no abstract: `summary: ` + a 220-character summary written by a model |
| `in_title` | the query words that appear in the title |
| `hits`, `best.chunk` | body searches: how many chunks match, and the number of the best one (`chunks --start <n> --count 1` reads it) |
| `card` | `true` when a research card exists |

- **A `text` that starts with `summary:` is model output, never the document.** Use it to decide what to open; never quote it or take a finding from it.
- Quotes come only from the abstract or the chunks, checked with `artools quote verify`. When 300 characters are not enough, `artools jejualps doc <id>` gives the whole abstract.
- `--no-snippet` drops `text`. `--detail why` adds `kw` (a verified sentence where a query concept appears) and the best chunk's headline with the match in «»; it returns 50–80% more characters than lean, so keep it for the searches whose hits you cannot tell apart. `--detail min` prints only id, date, kind, inst and title.
- Links, authors and `text_sha1` are not in the search lines: `artools jejualps cite <id> …` gives them for the documents you use.

## Reading a document

- `artools jejualps doc <id>`: metadata, abstract, chunk count, whether it has a card.
- `artools jejualps card <id>`: a research card (findings, methods, sample, data, limitations, policy implications). Each item carries an evidence quote, but **card quotes were matched fuzzily**: re-verify any you keep, and expect footnotes spliced into sentences at page breaks.
- `artools jejualps chunks <id> --start 0 --count 3`: the opening (abstract, introduction). `--around "risk aversion contagion"`: the chunks that match.
- `artools quote verify jejualps:<id> "<quote>"`: verbatim check against the whole stored text.
- `artools jejualps cite <id> <id> …`: the citation fields for Evidence `doc` blocks (`url`, `pdf_url`, `authors_text`, `text_sha1`, `kind`, `series`, `number` …), in the order given. There is no `doc_url`: use `url`.

## Unit hints

- Current views: `bis_cbspeeches` (speeches are often the only source for 2026 events), `suerf_policy`, `bis_bulletins`, `bis_quarterly`.
- Mechanisms and models: `imf_wpapers`, `bis_wpapers`, `nber_wpapers`, `cb_reshub` (ECB, Banque de France, Banca d'Italia papers are here).
- Speeches name their speaker in the title ("Christine Lagarde: …"); a speech is the speaker's view, cite it as such.
