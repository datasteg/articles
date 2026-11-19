# Numbers

**Every number in reader-facing prose is a fact token.** `analyze-data` computes facts (`analysis/analysis.json`); drafts write `{{F4}}`; the publisher renders it per language. Typed digits fail `artools check numbers`, except dates and years ("September 2026", "2010–12", "2026년 9월"), maturities ("10-year", "10년물"), Q1–Q4, and digits inside a verified quote.

**Rendering** (from the fact's `unit` and `display`):

| unit | value | EN | KO |
|---|---|---|---|
| `bp` | 96.7, decimals 0 | 97bp | 97bp |
| `%` | 4.44, decimals 2 | 4.44% | 4.44% |
| `% of GDP` | 115.6 | 115.6% (write "of GDP" in the sentence) | 115.6% |
| `pp` | 0.2 | 0.2 pp | 0.2%p |
| `month` | "2012-07" | July 2012 | 2012년 7월 |
| `date` | "2026-10-16" | 16 Oct 2026 | 2026년 10월 16일 |
| `quarter` | "2026-Q2" | Q2 2026 | 2026년 2분기 |
| `months`, `years`, `countries` | 5 | five months | 5개월 |
| `times` | 5.4 | 5.4 times | 5.4배 |
| `USD bn`, `EUR bn` | 279.2, decimals 0 | USD 279bn (with an `en` template) | 2,790억 달러 |
| `USD bn` | 1,014, decimals 0 | USD 1,014bn | 1조 140억 달러 |
| `USD tn` | 1.785, decimals 2 | 1.79 USD tn (give an `en` template) | 1.79조 달러 |
| `index`, `count` | 15.8 | 15.8 | 15.8 |

Options: `{{F5|signed}}` → +24bp; `{{F5|abs}}` → 24bp for a fall written as "fell by"; `{{F13|digits}}` keeps digits for small counts. A fact may carry its own templates: `"display": {"decimals": 1, "en": "USD {v}bn", "ko": "{v}억 달러"}`.

**Korean money amounts are in 억 and 조, never in 10억** (the Bank of Korea's notation; see 「한국은행 표현 노트」, section 6). For a `USD bn`/`EUR bn` (or KRW, JPY, GBP, CNY bn) fact the renderer converts the value itself: with no `ko` template, or a `ko` template written `{v}억 …` or the older `{v}0억 …`, 279.2 bn renders 2,790억 달러 at decimals 0 and 2,792억 달러 at decimals 1 (1 bn = 10억, so 억 carry one decimal fewer), and 1,014 bn renders 1조 140억 달러. Keep the value in bn; don't scale it by hand, and don't switch a large amount to `tn` just for Korean. `tn` facts keep one 조 figure (1.79조 달러). Chart axes and table columns follow the same rule: label them 억 달러 (values × 10) or 조 달러 (values ÷ 1,000), not 10억 달러.

**Facts are computed once.** Store unrounded values; derive changes and ratios from unrounded inputs; round only at display (`display.decimals`). A change of 96.7 − 72.3 is 24bp, even though the displayed levels (97, 72) suggest 25.

**Every number has a unit, a period and a source.** The sentence names the period ("in September 2026", "monthly average"); the citation mark names the source.

**Comparisons need a base.** "97bp, up from 72bp in January" or "63% of its 2011 peak", not "97bp" alone.
