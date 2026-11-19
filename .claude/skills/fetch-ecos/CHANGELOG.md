# fetch-ecos changelog

## 0.1.0 (20 Oct 2026)

- First version: `scripts/ecos.py` (tables, items, index, find, keystats, word, meta, obs, validate, fetch; standard library only; key redacted from every error, never logged).
- Built from the Bank of Korea's developer specification. The spec page is a JavaScript app, so its content was read from the backend the page calls. Six services; the path-segment grammar; cycles and date formats; `?` for unused item positions; error codes arrive as HTTP 200 with `RESULT`.
- Validation: table searchable; producer and licence; each item in its group and cycle; every group set; unit; one value per period; missing values; freshness; coverage (daily data may start on the first business day); range; anchors; cross-provider comparison.
- Learned by testing:
  - concepts sit in item names, not table names (hence the item index);
  - multi-group tables mix series when a group is missing (`902Y023`);
  - ECOS leaves the producer empty on 265 of its own 617 searchable tables;
  - other producers' names carry phone numbers;
  - daily requests over eight years are split by year;
  - the Seoul fixing differs from FRED's New York rate.
- Reference: the specification as tested, 11 validated series, 8 known codes to validate, search playbook.
