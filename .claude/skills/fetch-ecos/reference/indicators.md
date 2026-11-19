# ECOS series already checked

Validated with `ecos.py validate` on 20 Oct 2026. Anchors come from `ecos.py keystats` (the Bank of Korea's key statistics) on 19 Oct 2026; comparisons are against FRED. Re-validate before every use (step 5 of the skill).

Give the codes exactly as listed: `ecos.py validate <table> <cycle> <item 1> [<item 2>]`.

| Table | Cycle | Item codes | What | Unit | From | Producer | Publish | Check that passed |
|---|---|---|---|---|---|---|---|---|
| `722Y001` | D | `0101000` | Bank of Korea base rate | 연% | 1999-05-06 | Bank of Korea | yes | anchor 3% on 19 Oct 2026 (also cycles A, Q, M) |
| `817Y002` | D | `010200000` | government bond yield, 3 years | 연% | 1998-11-13 | Bank of Korea | yes | anchor 3.877% on 19 Oct 2026 |
| `817Y002` | D | `010210000` | government bond yield, 10 years | 연% | 2000-12-18 | Bank of Korea | yes | range 2.563–4.6% over 2025–26; one value per day |
| `817Y002` | D | `010101000` | call rate (overnight, all trades) | 연% | 1991 | Bank of Korea | yes | anchor 3.047% on 16 Oct 2026 |
| `721Y001` | M | `5050000` | government bond yield, 10 years, monthly average | 연% | 2000-10 | Bank of Korea | yes | identical to FRED `IRLTLT01KRM156N` in all 237 months since 2007 (4.454% in Sep 2026) |
| `731Y001` | D | `0000001` | won per US dollar, Seoul fixing (매매기준율) | 원 | 1964-05-04 | Seoul Money Brokerage | check terms | vs FRED `DEXKOUS` (New York noon rate): mean difference 7.0 won, up to 50.2; a different fixing, don't mix |
| `731Y001` | D | `0000003` | won per euro | 원 | 1994-04-11 | Seoul Money Brokerage | check terms | anchor 1,505.17 on 19 Oct 2026 |
| `901Y009` | M | `0` | consumer price index, all items (총지수) | 2020=100 | 1965-01 | 국가데이터처 | check terms | anchor 120.43 for Sep 2026 |
| `902Y023` | M | `IRLT` `KOR` | Korea long-term interest rate (OECD) | % | 1991-01 | OECD | check terms | vs FRED `IRLTLT01KRM156N`: mean difference 0.0015, max 0.005 |
| `902Y023` | M | `IRLT` `FRA` | France long-term interest rate (OECD) | % | 1960-01 | OECD | check terms | vs ECB `IRS.M.FR…`: mean difference 0.004, max 0.06; 4.48% vs 4.44% in Sep 2026 |
| `732Y001` | M | `99` | foreign exchange reserves, total | 천달러 (thousand USD) | 1971 | Bank of Korea | yes | anchor 440,556,657 for Sep 2026 |

Swap the country code in `902Y023` for other countries (`USA`, `DEU`, `JPN`, `GBR`, `ITA`, `CHN` …; `ecos.py items 902Y023`). `IR3TIB` instead of `IRLT` gives 3-month rates.

## Known codes, not yet validated here

From a series list used in production elsewhere. Validate before first use, then move each row up.

| Table | Cycle | Item codes | What | Producer |
|---|---|---|---|---|
| `731Y002` | D | `0000003` | US dollars per euro | Seoul Money Brokerage |
| `802Y001` | D | `0001000`, `0030000` | KOSPI close; foreigners' net purchases on KOSPI (억원) | 한국거래소 |
| `902Y003` | M | `010101`, `010103` | WTI and Brent, monthly average | check |
| `161Y006` | M | `BBHA00` | M2, average balance, not seasonally adjusted (십억원) | Bank of Korea |
| `191Y001` | M | `0200000` `4` | government bonds outstanding (two groups) | check |
| `282Y004` | Q | `A2` `C0` | bonds held by non-residents, market value (two groups) | check |
| `301Y013` | M | `BOPF22200000` | balance of payments: portfolio investment liabilities, debt securities | Bank of Korea |
| `311Y001` | Q | `2020000` | international investment position: portfolio investment liabilities | Bank of Korea |
