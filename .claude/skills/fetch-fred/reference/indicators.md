# FRED series already checked

Checked with `fred.py info` on 20 Oct 2026; "Last" is the last observation that day. Re-validate before every use (step 4 of the skill): series get discontinued and licences change.

| Series | What it measures | Freq | Units | First | Last | Source | Licence tag | Use for | Caveat |
|---|---|---|---|---|---|---|---|---|---|
| `DGS10` | US 10-year Treasury yield, constant maturity | D | Percent | 1962-01-02 | 2026-10-15 | Federal Reserve | public domain | global rates, US benchmark | daily; use `--to-freq m --aggregation avg` for monthly averages |
| `DGS2` | US 2-year Treasury yield | D | Percent | 1976-06-01 | 2026-10-15 | Federal Reserve | public domain | policy expectations | |
| `DFF` | Effective federal funds rate | D | Percent | 1954-07-01 | 2026-10-15 | Federal Reserve | public domain | US policy rate | `FEDFUNDS` is the monthly average |
| `FEDFUNDS` | Effective federal funds rate, monthly average | M | Percent | 1954-07-01 | 2026-09-01 | Federal Reserve | public domain | US policy rate in monthly charts | |
| `T10Y2Y` | 10-year minus 2-year Treasury | D | Percent | 1976-06-01 | 2026-10-16 | St. Louis Fed | citation required | yield-curve slope | |
| `VIXCLS` | CBOE Volatility Index | D | Index | 1990-01-02 | 2026-10-16 | CBOE | citation required | global risk aversion | |
| `STLFSI4` | St. Louis Fed Financial Stress Index | W | Index | 1993-12-31 | 2026-10-09 | St. Louis Fed | citation required | financial stress, US | zero = normal stress |
| `BAA10Y` | Moody's Baa corporate yield minus 10-year Treasury | D | Percent | 1986-01-02 | 2026-10-15 | St. Louis Fed | citation required | credit risk, long history | |
| `BAMLH0A0HYM2` | ICE BofA US high-yield option-adjusted spread | D | Percent | 2023-10-20 | 2026-10-16 | ICE Data Indices | **pre-approval required** | editor's context only | not publishable; FRED keeps only three years |
| `DTWEXBGS` | Nominal broad US dollar index | D | Index Jan 2006=100 | 2006-01-02 | 2026-10-09 | Federal Reserve | public domain | the dollar | |
| `DEXUSEU` | US dollars per euro | D | USD per EUR | 1999-01-04 | 2026-10-09 | Federal Reserve | public domain | euro exchange rate | |
| `DEXKOUS` | Korean won per US dollar (noon buying rate, New York) | D | KRW per USD | 1981-04-13 | 2026-10-09 | Federal Reserve | public domain | won from a US source | Korean articles use ECOS `731Y001` (Seoul fixing) |
| `CPIAUCSL` | US consumer prices, all items | M | Index 1982-84=100 | 1947-01-01 | 2026-09-01 | BLS | public domain | US inflation | SA; use `--transform pc1` for year-on-year % |
| `UNRATE` | US unemployment rate | M | Percent | 1948-01-01 | 2026-09-01 | BLS | public domain | US labour market | SA |
| `DCOILBRENTEU` | Brent crude, Europe | D | USD per barrel | 1987-05-20 | 2026-10-14 | EIA | public domain | oil prices | |
| `GFDEGDQ188S` | US federal debt, % of GDP | Q | Percent of GDP | 1966-01-01 | 2026-01-01 | Treasury, OMB | public domain | US fiscal position | |
| `IRLTLT01FRM156N` | France 10-year government bond yield (OECD) | M | Percent | 1960-01-01 | 2026-09-01 | OECD | citation required | long history before the ECB series starts | differs from the ECB's `IRS.M.FR…` by up to 0.06 points; don't mix them in one chart |
| `IRLTLT01DEM156N` | Germany 10-year yield (OECD) | M | Percent | 1956-05-01 | 2026-09-01 | OECD | citation required | as above | |
| `IRLTLT01ITM156N` | Italy 10-year yield (OECD) | M | Percent | 1991-03-01 | 2026-08-01 | OECD | citation required | as above | lags a month behind the others |
| `IRLTLT01EZM156N` | Euro-area 10-year yield (OECD) | M | Percent | 1970-01-01 | 2026-01-01 | OECD | citation required | — | **stale** (ended Jan 2026 when checked); use the ECB |
| `IRLTLT01KRM156N` | Korea 10-year yield (OECD) | M | Percent | 2000-10-01 | 2026-09-01 | OECD | citation required | Korea in an international comparison | ECOS `817Y002` is the primary source |
| `IR3TIB01KRM156N` | Korea 3-month interbank rate (OECD) | M | Percent | 1991-01-01 | 2026-09-01 | OECD | citation required | short rates across countries | |

The OECD long-term rate family is `IRLTLT01{country}M156N`, with ISO two-letter codes (`FR`, `DE`, `IT`, `ES`, `PT`, `GR`, `KR` …); `fred.py search --id "IRLTLT01*M156N"` lists all 35.
