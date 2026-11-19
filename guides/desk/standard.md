# The data note standard

A data note is a short article the desk writes from datasteg's own apps: money-flow (BIS, IMF and central-bank
statistics), trade-flow (UN Comtrade and Korea Customs Service records), global-network (the two joined) and
open-research (the research archive's catalogue). Readers are economists and university students of economics. They
know what a current account is. They do not know our scores, our codes or our page names.

A note earns its place by **consolidation**: it puts two or more sources side by side and reports what only the
combination shows. A summary of one page is not a note.

## What a note must do

1. **State one finding first, and why today.** The title and the first two sentences give the finding with its
   numbers and period. A reader who stops there has the note. A "Why this note" line under the dek says what is new
   (a data release, an economy at an extreme of its own past, an event, a paper received this month) and why the
   note is about these economies. A note with no such reason is not written that day.
2. **Join sources.** At least two apps and two publishers, and at least one number that needs both (a cross-tab, a
   ratio, a count of economies meeting a condition on each side). Say what each source measures before joining them.
3. **Show the comparison base.** Every level comes with what it is compared against: the group median, the
   economy's own past, a rank out of how many, a threshold and where it comes from.
4. **Reason like an economist.** Name the mechanism that would make the pattern matter (who lends, who buys, what
   breaks first), and say what the data can and cannot show about it. Observed together is not caused by.
5. **State the limits where the claim is made.** Each source's period, coverage and known gaps (different periods
   on the two sides, mirror gaps in trade, residence versus nationality in banking, scores that are counts, not
   forecasts) appear next to the claim they qualify, and again in a short "What this cannot tell us" section.
6. **Show it.** The finding is visible in at least three charts in at least two forms, each form chosen for its
   point: a line for an economy's own past, a dumbbell for two measures or then and now, bars for a ranking or a
   first-round loss, at most one scatter for a relationship across the group. One sets the funding side against the
   trade side. Tables are small summaries (six rows at most), never the place a comparison is made.
7. **Let the reader check it.** Every number is a fact computed by code from a cited page, with unit and period.
   A "How we counted" line says how the join was made in one or two sentences.
   A "Get the data" section, built by code, lists each datasteg page the note read and the API call that
   returns the same table, and offers one ZIP of CSV files (every table as the desk read it, each chart's data,
   every number with its formula), so a reader can open, fetch and reuse it.
8. **Teach one thing.** A student should finish knowing one concept better (what a chokepoint share is, why net
   reserves matter, what a mirror ratio is), defined in plain words where it first appears.
9. **Read the same in English and in Korean.** A note is published in both languages. The English is the text the
   desk writes and reviews. The Korean edition is drafted from it, string by string, by qkr, datasteg's Korean
   language model, and then refined in its expression by a Korean editor (Fable, since 19 Nov 2026) under the
   desk's checks (see "The Korean edition" below). So the English must be text a translator
   cannot misread: say who owes, who lends, who buys and who sells ("the bank loans Canada owes", not "Canada's
   bank loans"); one claim per sentence; no idiom.

## What a note never does

- Forecast, recommend, or rank economies as safe or unsafe. Scores are described as what they count. A note may
  say which release to look at next and which result would change its finding ("if the next quarter's bond
  redemptions are again larger than the goods surplus, the cover reading fails"). It may not say what will happen,
  what anyone should do, or that one economy is "the one to worry about".
- Use a causal verb ("caused", "drove", "because of", "led to") for a pattern in the data. Use "went together
  with", "at the same time as", "is consistent with".
- Quote a number the code did not compute. No typed digits except years, dates and quarters.
- Describe a score or signal without saying what it is made of.
- Use our internal codes as if readers knew them (V, F, A2, J3, R24, HHI): write the plain name first, the code
  once in brackets if at all. The same holds for our own pages and apps ("the Signal Board", "country sheets",
  "money-flow"): the argument names the statistics (BIS, IMF, UN Comtrade); the method section says which datasteg
  pages they were read from.
- Pad. No background section that the finding does not need, no closing summary that repeats the opening.

## How a note is judged

Eight dimensions, each scored 1 to 5 by a judge that sees only the text and its charts' data. The same judge scores
a benchmark set of short analytical pieces from the IMF, the BIS, central banks and research institutes, so a note's
score is read against theirs.

| | Dimension | 5 looks like | 1 looks like |
|---|---|---|---|
| D1 | Finding | One specific, non-obvious finding, stated in the first two sentences with its numbers | A tour of data with no claim |
| D2 | Consolidation | The finding exists only because sources were joined; the join is explained | One source restated; others decorate |
| D3 | Evidence | Every claim has its base, period and source; magnitudes are put in proportion | Bare numbers; cherry-picked comparisons |
| D4 | Reasoning | The mechanism is named and correct; rival readings are weighed | Pattern-spotting with no economics, or wrong economics |
| D5 | Limits | Limits sit beside the claims they qualify and change how the finding is worded | Boilerplate caveats or none |
| D6 | Clarity | A second-year student follows every sentence; terms defined once; no internal codes | Jargon, long sentences, undefined scores |
| D7 | Charts | Each chart makes one point its headline states; text and chart agree; forms fit the data | Charts repeat the table or contradict the text |
| D8 | Use | A reader learns something they can use or check today: why now, what to watch, where the data is | No reason to have read it |

**Pass:** every hard check green, no dimension below 3, and the mean at or above the upper quartile of the
benchmark set (where its best quarter starts).
A note that does not pass after its review rounds is held back, not published: no note is better than a weak one.
The editor sees a held-back note with the reasons and may still approve it.

## The Korean edition

Korean wording on every datasteg site comes from qkr (the repository's rule), with one exception for these
notes (the owner, 19 Nov 2026): after qkr has drafted the edition, a Korean editor (Fable, the polish-ko role) refines
its expression, under the desk's checks. The other desk models write English only, and no person edits the Korean by
hand. For a note this means:

- **qkr drafts every string** (title, dek, key-number labels, findings, paragraphs, figure words, source lines)
  from its English with the numbers filled in, so the Korean has the right particle and counter for each number.
  Economy names in figures come from the sites' own table; the byline and disclaimer from `config/editorial.yaml`.
- **Code checks every answer** beside qkr's own checks: the same source marks, no number the English lacks, none
  of two digits or more lost, a headline of at most 40 characters in one line. The check runs again on the files
  before publishing, and a Korean string that is not qkr's recorded answer is refused.
- **A second reader compares the editions.** A model that knows both languages reads each Korean string beside its
  English and reports where the meaning differs (who owes and who lends swapped, a qualification lost, a claim made
  stronger) and where one term came out in two Korean forms. It writes English only: a rewording for qkr to draft
  from again, or which of qkr's own forms to keep. qkr then drafts or refines the string again.
- **What is left is shown to the editor.** The Korean edition is always there to read once qkr has answered. A
  string qkr could not draft to the checks shows qkr's own draft as it came, flagged beside the note with the check
  it failed and what qkr should learn from it; a place where the Korean may still differ from the English is listed
  there too. qkr's article prose is its weakest
  register, so the editor reads the Korean edition before approving, as qkr's own guide asks.
- The judge's score is for the English edition. The Korean edition is not scored.
