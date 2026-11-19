# FRED API: what fred.py uses

Base `https://api.stlouisfed.org/fred/`, every call with `api_key` and `file_type=json`. Documentation: https://fred.stlouisfed.org/docs/api/fred/. Checked 20 Oct 2026.

| Endpoint | fred.py command | Key parameters | Returns |
|---|---|---|---|
| `series/search` | `search` | `search_text`, `search_type` (`full_text` or `series_id` with `*` wildcards), `limit` (≤ 1000), `order_by` (`search_rank`, `popularity`), `filter_variable` + `filter_value` (one filter: `frequency`, `units` or `seasonal_adjustment`) | `count`, `seriess[]` |
| `tags/series` | `tags` | `tag_names` (`;`-separated, all must match), `order_by` | `seriess[]` |
| `series` | `info`, `validate` | `series_id` | `seriess[0]`: `title`, `frequency(_short)`, `units(_short)`, `seasonal_adjustment(_short)`, `observation_start/end`, `last_updated`, `popularity`, `notes` |
| `series/tags` | `info`, `validate` | `series_id` | `tags[]` with `group_id`: `src` (source), `geo`, `freq`, `seas`, `gen`, `rls`, **`cc` (citation and copyright)** |
| `series/release` | `info` | `series_id` | the release name and link |
| `series/observations` | `obs`, `validate`, `fetch` | `observation_start/end` (YYYY-MM-DD), `units` (transform), `frequency` + `aggregation_method` (down-sampling), `limit` (≤ 100000) | `observations[]`: `date`, `value` |

**Values and dates.** `value` is a string; `"."` means missing (daily series miss market holidays). Monthly, quarterly and annual observations are dated by the **first day of the period**: September 2026 is `2026-09-01`.

**Frequency filter.** `filter_value` takes the long names `Daily`, `Weekly`, `Biweekly`, `Monthly`, `Quarterly`, `Semiannual`, `Annual`. A short code such as `M` silently matches nothing; `fred.py` translates.

**Transforms (`units`).** `lin` (levels), `chg` (change), `ch1` (change from a year ago), `pch` (% change), `pc1` (% change from a year ago), `pca` (compounded annual rate), `cch`, `cca`, `log`. A transformed series still reports the original units in `info`; the Dataset records the transform.

**Down-sampling.** `frequency=m|q|a` with `aggregation_method=avg|sum|eop`. Only to a lower frequency.

**Licence tags (group `cc`).**

| Tag | Meaning | fred.py sets `publishable` |
|---|---|---|
| `public domain: citation requested` | Federal Reserve, BLS, BEA, EIA … | true |
| `copyrighted: citation required` | OECD, CBOE (VIX), St. Louis Fed indices … | true, with the attribution line |
| `copyrighted: pre-approval required` | ICE BofA bond indices … | false |
| no tag | unknown | none; read the notes before publishing |

**Limits and errors.** 120 requests a minute per key (`fred.py` paces at 0.6 s and backs off on 429 and 5xx). A bad parameter answers HTTP 400 with `{"error_code": 400, "error_message": "..."}`, which `fred.py` prints with the key redacted.

**Vintages.** The API serves the latest revision. For "what was known then" (ALFRED), use `realtime_start` and `realtime_end`; `fred.py` doesn't expose them yet.
