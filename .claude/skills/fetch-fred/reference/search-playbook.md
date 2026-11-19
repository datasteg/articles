# Finding the right FRED series

FRED has hundreds of thousands of series and many near-duplicates, so the first hit is often wrong. Work through these in order.

## 1. Say what you need before you search

Write it down: concept, country, frequency, unit, period, and the sentence or chart it serves. For example: "France, 10-year government bond yield, monthly average, percent, 2007–now, for the spread chart." The check at the end tests the series against this, not against the search result.

## 2. Search in three ways

| Way | When | Example |
|---|---|---|
| Full text, with a frequency filter | You know the concept | `fred.py search france long-term interest rate --freq M` → `IRLTLT01FRM156N` |
| Id pattern | You know one member of a family and want another country or frequency | `fred.py search --id "IRLTLT01*M156N"` → all 35 countries |
| Tags | The words in titles vary; FRED's tags don't | `fred.py tags "korea;interest rate;monthly"` |

What helps:
- Use 2–4 content words. Words like "rate", "index" or "the" match everything.
- Rank by `--order popularity` when the results are noisy; the series people actually use rise to the top.
- `--freq` takes `D`, `W`, `M`, `Q`, `A`; the script converts them to the long names FRED needs. A raw `M` silently matched nothing.
- Discontinued series are hidden unless you pass `--include-discontinued`.

## 3. Read the candidate, not just its title

`fred.py info <ID>` shows:
- the **notes** (how the series is built, breaks, definitions);
- the **source** (the original publisher; prefer the agency itself);
- **units** and **seasonal adjustment** (`SA`, `NSA`, `SAAR`);
- **observation_end** (is it current?);
- the **licence tag**.

## 4. Known families and traps

| Family or series | What to know |
|---|---|
| `DGS*`, `DFF`, `FEDFUNDS` | Federal Reserve H.15 rates; daily constant maturities are the standard US yields |
| `IRLTLT01{CC}M156N` | OECD 10-year yields by country (monthly, also `A156N`, `Q156N`). Some lag (Italy a month); the euro-area aggregate ended Jan 2026 |
| `IR3TIB01{CC}M156N` | OECD 3-month interbank rates by country |
| `BAML*` | ICE BofA bond indices: pre-approval required to publish, and FRED keeps only three years of history |
| `DEX**US`, `DEXUS**` | Federal Reserve noon rates in New York; check the direction (`DEXKOUS` is won per dollar, `DEXUSEU` is dollars per euro) |
| `CPIAUCSL` vs `CPIAUCNS` | seasonally adjusted vs not; year-on-year inflation is the same either way, month-on-month isn't |
| Titles ending "(DISCONTINUED)" | never use; the validator fails them |

## 5. Prove it with a check

Run `fred.py validate` with:
- expected frequency, units and seasonal adjustment;
- a plausible range (`--range=-1,20`; the `=` lets the range start with a minus);
- at least one **anchor**: a value you know from a trusted publication, such as the ECB's 4.44% for France in Sep 2026, a Fed release, or ECOS `keystats`. Never take the anchor from the series under test;
- where possible, `--compare` with the same concept from another provider. FRED's OECD France yield matched the ECB series to 0.005 points on average and 0.06 at most over 237 months: close enough to confirm the ticker, different enough not to mix in one chart.

A `warn` verdict isn't a pass. Write down why each warning is acceptable for this article, or pick another series.
