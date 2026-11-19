# Citations, quotes and popovers

**Mark every factual claim** with the id of what supports it: `[[jejualps-E12]]` (an evidence record), `[[ecb-irs-fr]]` (a dataset), or several: `[[jejualps-E3,jejualps-E7]]`. Put the mark at the end of the sentence, before the period is fine either way; the publisher numbers sources S1…Sn by first appearance and groups evidence from the same document into one source.

**What the reader sees.** A numbered superscript. Tapping it opens a popover with:
- the source's series and date, and its title;
- the **quote**: the evidence record's verified quote, in its original language. It must support the claim it's attached to. If it doesn't, cite a different record or none.
- **"Used here for"**: the draft's `citations.<id>.used_for`, a half-sentence in the edition's language ("which market prices sovereign risk first"). Write one for every id you cite.
- a link to the original.

**Quote policy** (Glacier): at most one quoted sentence per document across the whole article. If two claims cite the same paper, only one evidence record from it may carry a quote into the popovers; give the other a `used_for` line only.

**Verified only.** A quote reaches readers only if `artools quote verify` found it in the stored text word for word. A quote broken by a footnote at a page break (`interrupted`) is acceptable, but prefer a clean sentence from the same paper if there is one.

**Data citations** carry no quote: the popover shows provider, series key, unit, frequency, last observation and retrieval date.

**References** are generated from the sources: research (papers, policy notes, reports), speeches and statements, data; each with "cited in" back-links. Related reading (2–4 documents worth reading next, not cited) comes from `plan.related`.
