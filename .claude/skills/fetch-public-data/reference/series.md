# ECB and Eurostat series that work

Checked 19–20 Oct 2026.

| What | Provider | Key / dataset | Command | Notes |
|---|---|---|---|---|
| 10-year government bond yield, by country, monthly average | ECB | `IRS.M.<CC>.L.L40.CI.0000.EUR.N.Z` (CC: FR, DE, IT, ES, PT, GR, NL, BE, AT, IE, FI …) | `artools data ecb get IRS.M.FR.L.L40.CI.0000.EUR.N.Z --run … --from 2007-01 --id ecb-irs-fr --indicator "10-year government bond yield, France"` | long-term interest rates for convergence purposes; Greece has no value for 2015-07; latest month on 19 Oct 2026: 2026-09 |
| Euro-area yield curve, daily (AAA and all issuers) | ECB | `YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y` | `artools data ecb get YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y …` | euro area as a whole only, no country split |
| General government gross debt, % of GDP, annual | Eurostat | `gov_10dd_edpt1`, params `na_item=GD&sector=S13&unit=PC_GDP&freq=A` | `artools data eurostat get gov_10dd_edpt1 --params "na_item=GD&sector=S13&unit=PC_GDP&freq=A" --geo FR,DE,IT,ES,PT,EL --since 2007 …` | latest 2025, updated 22 Apr 2026 |
| General government deficit (−) / surplus (+), % of GDP, annual | Eurostat | `gov_10dd_edpt1`, `na_item=B9&sector=S13&unit=PC_GDP&freq=A` | as above with `na_item=B9` | validate on first use |
| Government interest payable, % of GDP | Eurostat | `gov_10dd_edpt1`, `na_item=D41PAY&sector=S13&unit=PC_GDP&freq=A` | as above | validate on first use |
