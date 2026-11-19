---
name: make-cover
description: Make an article's cover - the small picture next to it in every list on the site, above a plate where the site counts the article's indicators, papers and charts - after the review passes. Read the final article, weigh three ideas (object, mechanism, data echo), draw one as a flat SVG in Glacier's colour classes, check it, render it through the real site in both themes and sizes, and look at it before finishing.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob
metadata:
  version: 1.2.0
  family: stage
---
# make-cover

## Purpose

Give the article a picture that tells a reader scanning the list what it is about. Some readers are the public, some are professionals: the cover must be clear to the first and correct to the second. Read `guides/covers.md` first. It holds the rules, the palette and the technical limits.

Under the picture the site adds a plate with the article's counts: 11 indicators, 14 papers, 4 charts. You don't draw it, but the picture and the plate must read as one tile (guide § The plate).

## Inputs

- The final article: `draft/en.json` (title, dek, findings, insight), `draft/ko.json` and `plan.json` (`answer`, `figures`).
- `review.json`: the review has passed, so the text is settled.
- `charts/*.json`: the key chart's shape, for a data echo.
- The other covers on the site: `content/articles/*/cover.svg` and `.preview/articles/*/cover.svg`.

## Steps

1. `artools run start $run_id make-cover --version 1.2.0`
2. Read the inputs. Write down the article's answer in one sentence, in your own words.
3. Write three ideas, one of each kind (object, mechanism, data echo; see the guide). Score each on fit, legibility at 80 × 54 px, distinctness from the other covers, and tone. Choose one.
4. Draw it in `cover/cover.svg`, following the guide:
   - `viewBox="0 0 480 320"`, a full-frame background rect first;
   - colour by `f-`/`s-` classes only;
   - strokes at least 8 wide;
   - no text, people, flags, maps or clichés.
5. `artools check cover --run $run_id`. Fix every blocking problem, and the advisory ones unless you have a reason to keep them.
6. `artools render cover $run_id`, then read every PNG in `cover/render/`. Look for:
   - a subject that doesn't read on the phone card;
   - shapes that vanish in the dark theme;
   - a cover too close to a neighbour's;
   - a drawing that doesn't sit well with the plate under it (a `frost` band running into it, an edge that looks cut off);
   - counts on the plate that look wrong against `sources.json` and the charts (0 papers in a research-heavy article). You can't change them: say so in `checked`, for the editor;
   - anything alarmist, or anything that claims more than the answer.

   Fix the SVG and render again, three rounds at most. If rendering fails (the site isn't available), say so in `cover/cover.json` `checked` and rely on the check.
7. Write `cover/cover.json` as in the guide: `concept` and `alt` in both languages, the three ideas `considered` with verdicts, `chosen`, `rounds`, and `checked` (what each look changed).
8. `artools run done $run_id make-cover`. It validates the record and the SVG.

## Judgement

- The cover follows the answer, not the question's keywords. "Is France the next Greece?" answered "no" is not a picture of Greece.
- One idea, drawn with few shapes. When in doubt, take a shape away.
- A cover is not a chart: no axes, no values, nothing a reader could read as data.
- Alt text describes the picture ("Two bond certificates, the French one sitting slightly lower than the German one"), not the article's conclusion.

## Never

- Edit the site's code (`apps/`, `packages/`) or the palette: it is shared by every article. If the palette can't draw what you need, choose another idea and note it in `cover/cover.json`.
- Copy another article's cover, or trace a logo, flag, map, banknote or photograph.
- Put words or numbers in the picture, including the plate's counts: the site writes those.
