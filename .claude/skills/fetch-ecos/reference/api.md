# ECOS Open API: the specification, as ecos.py uses it

Source: the Bank of Korea's developer specification (개발 명세서, https://ecos.bok.or.kr/api/#/DevGuide/DevSpeciflcation). That page is a JavaScript app, so its content was read on 20 Oct 2026 from the backend it calls (`POST /api/serviceEndpoint/httpService/request.json`, transactions `OSUOA03R01` for the service list, `OSUOA04R01` for request and output fields, `OSUOA05R01` for messages). Live behaviour noted below was tested the same day.

## Not REST: every argument is a path segment

```
https://ecos.bok.or.kr/api/{service}/{key}/{type}/{lang}/{first}/{last}/{argument 1}/{argument 2}/...
```

| Position | Name | Values |
|---|---|---|
| service | 서비스명 SVC_NM | one of the six below |
| key | 인증키 CERT_KEY | `BOK_API_KEY`; the key `sample` works for rows 1–10 only |
| type | 요청유형 DMD_TYP | `json` or `xml` |
| lang | 언어구분 LANG_DV | `kr` or `en` (names come back in that language; `en` names exist for every table checked) |
| first, last | 요청시작건수, 요청종료건수 DMD_ST_CCNT, DMD_END_CCNT | 1-based row range; integers |

Order matters and nothing is named. A Korean argument (a word or a statistic name) must be URL-encoded. The key sits in every URL, so `ecos.py` never logs URLs.

## The six services

| Service | 이름 | Arguments after the row range | Output fields | ecos.py |
|---|---|---|---|---|
| `StatisticTableList` | 서비스 통계 목록 | `[STAT_CODE]` (optional) | `P_STAT_CODE`, `STAT_CODE`, `STAT_NAME`, `CYCLE`, `SRCH_YN`, `ORG_NAME` | `tables` |
| `StatisticItemList` | 통계 세부항목 목록 | `STAT_CODE` | `STAT_CODE`, `STAT_NAME`, `GRP_CODE`, `GRP_NAME`, `ITEM_CODE`, `ITEM_NAME`, `P_ITEM_CODE`, `P_ITEM_NAME`, `CYCLE`, `START_TIME`, `END_TIME`, `DATA_CNT`, `UNIT_NAME`, `WEIGHT` | `items`, `index` |
| `StatisticSearch` | 통계 조회 조건 설정 | `STAT_CODE`, `CYCLE`, `FROM_DATE`, `TO_DATE`, `ITEM_CODE1`, `ITEM_CODE2`, `ITEM_CODE3`, `ITEM_CODE4` (items optional) | `STAT_CODE`, `STAT_NAME`, `ITEM_CODE1..4`, `ITEM_NAME1..4`, `UNIT_NAME`, `WGT`, `TIME`, `DATA_VALUE` | `obs`, `validate`, `fetch` |
| `KeyStatisticList` | 100대 통계지표 | none | `CLASS_NAME`, `KEYSTAT_NAME`, `DATA_VALUE`, `CYCLE` (the latest period), `UNIT_NAME` | `keystats` |
| `StatisticWord` | 통계용어사전 (803 terms) | `WORD` | `WORD`, `CONTENT` | `word` |
| `StatisticMeta` | 통계메타DB (15 BOK statistics) | `DATA_NAME` | `LVL`, `P_CONT_CODE`, `CONT_CODE`, `CONT_NAME`, `META_DATA` | `meta` |

The specification's own sample request: `/StatisticSearch/sample/xml/kr/1/10/200Y101/A/2020/2023/10101/?/?/?`. **Unused item positions are written `?`**; `ecos.py` does the same.

## Cycles and date formats

| CYCLE | Meaning | FROM_DATE / TO_DATE and TIME | ISO form in our CSVs |
|---|---|---|---|
| `A` | annual | `2020` | `2020` |
| `S` | half-year | `2020S1` | `2020-H1` |
| `Q` | quarter | `2020Q1` | `2020-Q1` |
| `M` | month | `202001` | `2020-01` |
| `SM` | half-month | `202001S1` | `2020-01-S1` |
| `D` | day | `20200101` | `2020-01-01` |

A date in the wrong format for the cycle answers `ERROR-101`.

## Responses

Success: `{"<service>": {"list_total_count": N, "row": [ {...}, ... ]}}`. Values are strings (`DATA_VALUE": "4.48"`); an empty string means no value.

Everything else comes back as **HTTP 200** with:

```json
{"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
```

| Code | Meaning (from the specification) | ecos.py |
|---|---|---|
| `INFO-100` | invalid key | stops |
| `INFO-200` | no data for this request | returns an empty result; `validate` fails the check |
| `ERROR-100` | a required value is missing | stops |
| `ERROR-101` | the date format doesn't match the cycle | stops; see the table above |
| `ERROR-200` | file type missing or invalid | stops |
| `ERROR-300`, `ERROR-301` | row range missing or not integers | stops |
| `ERROR-400` | the range is too large: 60-second timeout | daily requests over 8 years are split by year |
| `ERROR-500` | server error, or unknown service name | retried, then stops |
| `ERROR-600`, `ERROR-601` | database or SQL error | `600` retried |
| `ERROR-602` | too many calls: access limited for a while | waits and retries; `ecos.py` paces calls 0.35 s apart |

## What the specification doesn't tell you (tested 20 Oct 2026)

- **844 tables, 617 searchable.** Rows with `SRCH_YN = N` are category headings, not data. `P_STAT_CODE` links a table to its parent heading; `ecos.py` prints the whole path ("1. 통화/금융 > 1.3. 금리 > 1.3.2. 시장금리 > 1.3.2.1. 시장금리(일별)").
- **Concepts live in item names, not table names.** No table name contains 국채; the government bond yields are items (`국고채(10년)`) of the market-rate tables. That is why `ecos.py index` and `find` exist.
- **An item belongs to a cycle.** `817Y002` (market rates) is daily only; the monthly averages are a different table (`721Y001`). The same item code can carry different cycles in a table with several (`902Y023` has A, Q and M).
- **Multi-group tables need every group.** `902Y023` (international interest rates) has Group1 (rate type: `IRLT` long-term, `IR3TIB` 3-month) and Group2 (country: `FRA`, `KOR` …). With only the first code it returns 393 rows for 237 months, all countries mixed together. `validate` fails that ("one series").
- **The producer is not always the Bank of Korea.** `ORG_NAME` names the producer: `731Y001` daily won rates come from 서울외국환중개 (Seoul Money Brokerage), and the 902Y international tables from the IMF, OECD and BIS. Under the ECOS terms (art. 5), commercial use is allowed, but copyright stays with the producer, which may restrict it. `validate` warns for any producer other than the Bank of Korea.
- **Units are in Korean even with `lang=kr`**: 연% (percent a year), 십억원 (billion won), 백만달러 (million dollars), 천달러 (thousand dollars). Convert before charting and say so in the chart's subtitle.
- **Paging.** `list_total_count` gives the total; `ecos.py` asks 10,000 rows a call and loops.
