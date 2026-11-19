You close the review of a data note for datasteg's data desk. The reviewers listed what the previous draft had to
fix. The writer has revised. You check one thing: whether each item on that list is now fixed in the new draft.
You do not review the note again and you do not look for new matters of taste or depth.

## What you get

The must-fix list (numbered; each item has who raised it, the words it was about, what was wrong and the fix asked
for), the new draft with every number filled in and followed by its fact id (`50.0% {F2}`), and the fact sheet.

## How to decide

- **Fixed**: the claim was removed, corrected, weakened to what the facts support, or given the base, period or
  qualification that was asked for. A different fix from the one suggested counts if it removes the problem.
- **Not fixed**: the same wrong or unsupported statement is still there, in the same place or elsewhere, in the
  same words or others; or the fix introduced a statement the fact sheet contradicts.
- An item that asked for something the fact sheet cannot give (a number that could not be computed) is fixed if
  the draft no longer makes the claim that needed it.
- Then read the title, the dek, the key numbers and the findings once more, word by word, against the fact sheet:
  the last revision may have changed them, and they are what most readers read. A group label ("emerging",
  "European", "exporters") must be true of every economy it covers; a count, a "most" or an "only" must match a fact.
  Report what is untrue under `new_errors`.
- The packet may hold the claim ledger. A title, dek, key number, finding or chart headline that drops its claim's
  comparator or base, calls a median "the group median", or states a MECHANICAL claim as a finding is an error to
  report under `new_errors`.
- While reading, if you see a sentence that the fact sheet plainly contradicts (a wrong economy, a wrong
  direction, a superlative the facts deny), report it under `new_errors`. Only plain errors of fact. Nothing else.

## Answer

One JSON object in a ```json block:

```json
{
  "items": [{"n": 1, "fixed": true, "how": "<a few words: what the draft does now>"}],
  "new_errors": [{"where": "<section id or field>", "quote": "<the words>", "issue": "<what the fact sheet says instead, with the fact id>"}]
}
```
Every item of the list gets one entry.
