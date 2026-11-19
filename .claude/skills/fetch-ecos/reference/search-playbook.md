# Finding the right ECOS series

An ECOS series is `table code + cycle + one item code per item group`. The codes are opaque (`817Y002`, `010210000`), and the names you would search for usually belong to items, not tables. Work through these in order.

## 1. Say what you need before you search

Concept, cycle, unit, period, and the sentence or chart it serves. For example: "Korea, 10-year government bond yield, monthly average, percent a year, 2007–now, for the Korean edition's comparison chart."

## 2. Search four ways

| Way | When | Example |
|---|---|---|
| `find` (the item index) | Almost always first: it searches table paths, group names, item names and parent items together | `ecos.py find 국고채 10년 --cycle M` |
| `tables` | You know the area ("시장금리", "환율") and want to see the tree | `ecos.py tables 시장금리` → `817Y002` (daily) and `721Y001` (monthly, quarterly, annual) |
| `items` | You have a table and need its codes, groups, cycles, spans and units | `ecos.py items 721Y001 국고채 --cycle M` → `5050000 국고채(10년)` |
| `--lang en` | English names help, or the Korean term is unclear | `ecos.py --lang en tables "interest rate"` |

`find` needs `ecos.py index` first. It makes one call per searchable table (617 tables, 59,090 items on 20 Oct 2026), is cached for a week under `/data/articles/cache/ecos` (or `~/.cache/datasteg-articles/ecos`), and took 32 minutes to build. Build it in the background before a run that needs ECOS.

Search for the item's own words, not the concept's everyday name. Korea's growth rate is the item 국내총생산(GDP)(실질, 계절조정, 전기비) in `200Y102` (quarterly), so `find 국내총생산 실질 --cycle Q` finds it. `find 경제성장률` lists North Korea's tables first (section 9.2): read the table path.

Words are matched as substrings, so `국고채` finds 국고채(3년) … 국고채(50년). Add a second word to narrow it (`10년`). Words can match anywhere in the table path too, so `외국인 채권` also returns stock-market items from the 주식/채권 section; read the table path in each result. Item names often end in footnote markers ("외국인 순매수(유가증권시장) 1)"): the note sits in the ECOS table on the website, not in the API.

## 3. Read the candidate

From `items <table>`:
- **groups**: how many item codes the series needs. One per group, in group order.
- **cycles**: the same item may exist for D only, or for A, Q and M.
- **span** (`START_TIME..END_TIME`) and points (`DATA_CNT`).
- **unit**, in Korean: 연% is percent a year; 원 is won; 십억원 is billion won; 백만달러 is million dollars; 천달러 is thousand dollars; 2020=100 is an index.
- **parent** (`P_ITEM_NAME`): a sub-item (식료품 under 총지수) is a component, not the total.

From `tables`: the producer. An empty producer is the Bank of Korea's own table; anything else holds its own copyright.

## 4. Tables that come up often

Checked 20 Oct 2026; validated rows are in `indicators.md`.

| Table | What | Groups | Cycles | Producer | Note |
|---|---|---|---|---|---|
| `722Y001` | Bank of Korea base rate and lending rates | 1 | A, D, M, Q | Bank of Korea (empty field) | base rate item `0101000` |
| `817Y002` | market rates, daily: government bonds 1–50 years, call rate, corporate bonds | 1 | D | Bank of Korea | 10-year `010210000`, 3-year `010200000`, call `010101000` |
| `721Y001` | market rates, monthly, quarterly, annual averages | 1 | A, M, Q | Bank of Korea | 10-year `5050000`, 3-year `5020000` (different codes from `817Y002`) |
| `731Y001` | won against major currencies, daily | 1 | D | Seoul Money Brokerage | dollar `0000001` (매매기준율), euro `0000003`; copyright not the Bank's |
| `731Y004` | won against major currencies, monthly averages and end of period | check `items` | M | Bank of Korea | for monthly charts; Bank of Korea copyright, unlike `731Y001` |
| `901Y009` | consumer price index | 1 | A, M, Q | 국가데이터처 | all items `0` (총지수); 1,743 items with parents; not the Bank's copyright |
| `902Y023` | international long- and short-term interest rates | **2**: rate type (`IRLT`, `IR3TIB`), country (`FRA`, `KOR`, `DEU` …) | A, M, Q | OECD | both codes needed; same numbers as FRED's OECD copies |
| `902Y006` | central bank policy rates, major countries | check `items` | M | BIS | |
| `200Y102` | national accounts, quarterly main indicators | 1 | Q | Bank of Korea | real GDP growth q/q seasonally adjusted `10111` (key statistic: 0.6% in 2026Q2), y/y `10211`; `200Y101` is the annual table |
| `301Y013` | balance of payments | 1 | M | Bank of Korea | `BOPF…` codes; portfolio investment liabilities, debt securities `BOPF22200000` |
| `311Y001` | international investment position | 1 | Q | Bank of Korea | |
| `732Y001` | foreign exchange reserves | 1 | M | Bank of Korea | total `99`, in thousand dollars |
| `802Y001` | stock market, daily | 1 | D | 한국거래소 (Korea Exchange) | KOSPI `0001000`, foreigners' net purchases `0030000`; not the Bank's copyright |

## 5. Anchors and comparisons

- `ecos.py keystats` lists the Bank of Korea's 100 key statistics with their latest values and dates. These were the anchors on 19 Oct 2026: base rate 3%, 3-year government bond 3.877%, won per euro 1,505.17, CPI 120.43 (Sep 2026), FX reserves 440,556,657 thousand dollars (Sep 2026).
- For Korean long-term rates, FRED's OECD copy (`IRLTLT01KRM156N`) is a second provider to `--compare` against.
- For the won per dollar, FRED's `DEXKOUS` (Federal Reserve noon rate in New York) is close but not equal to the Seoul fixing: compare with a tolerance in won, to confirm the code, not to match values.

## 6. Prove it

Run `ecos.py validate <table> <cycle> <item codes…>` with:
- the expected unit;
- a plausible range (`--range=-5,5` with `=` for negatives);
- at least one anchor in the cycle's date format (`20261019=3:0.001`, `202609=120.43:0.01`);
- `--compare` where a second provider exists.

A `fail` on "all dimensions set" or "one series" means an item group is missing. A `fail` on an item with "it exists for cycles […]" means the wrong table for that cycle: look for the monthly or daily twin.
