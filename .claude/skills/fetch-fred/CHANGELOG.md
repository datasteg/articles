# fetch-fred changelog

## 0.1.0 (20 Oct 2026)

- First version: `scripts/fred.py` (search, tags, info, obs, validate, fetch; standard library only; key redacted).
- Validation: existence, discontinued, frequency, units, seasonal adjustment, freshness, coverage, missing values, range, anchors, cross-provider comparison, licence from FRED's `cc` tags.
- Reference: API notes, 22 checked series, search playbook.
- Tested live: the search frequency filter needs long names (fixed in the script); the OECD France yield matches the ECB series to within 0.06 points.
