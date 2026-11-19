---
name: make-pdf
description: Proof the article's PDF edition - each edition set as a journal-style A4 page from the site's print layout (Glacier type, numbered sections and figures, references, the citation) and printed by Chromium - after the cover and before the editor's final approval. Print the proof, run its checks, look at every page, and record what you found for the editor. Publishing prints the final PDFs again from the published article.
argument-hint: <run-id>
arguments: [run_id]
allowed-tools: Bash(artools *) Read Write Edit Glob
metadata:
  version: 1.0.0
  family: stage
---
# make-pdf

## Purpose

Every article has a PDF edition per language, linked from its page ("PDF" in the header, and under "Cite this article"). Readers print it, file it and cite it, so it must read like a journal article: a masthead, the title block, the key numbers, the article information beside the key findings, one serif column with numbered sections, numbered figures with their sources, then the terms, the references, the citation and how the article was made. The layout is the site's (`/print/<lang>/<slug>`, `apps/web/app/print.css`); you don't design it. You check that this article prints well in it, so the editor approves the PDF with the article at gate 3.

## Inputs

- The final article in `.preview/` (the review has passed and the cover is done).
- `artools render pdf $run_id`, which:
  - prints each edition to `pdf/<lang>.pdf`, after a layout pass that floats a figure past a few paragraphs when it would leave a large gap at the bottom of a page;
  - writes `pdf/proof.json` (pages, size, the paragraphs moved, gaps left, problems);
  - draws each page in `pdf/render/<lang>-<n>.png` and a contact sheet in `pdf/render/<lang>-sheet.png`;
  - puts the proofs on the preview site's download button.

## Steps

1. `artools run start $run_id make-pdf --version 1.0.0`
2. `artools render pdf $run_id`. If it fails because the preview site isn't available, say so in `pdf/pdf.json` `checked` and stop with `artools run fail`.
3. `artools check pdf --run $run_id`. A blocking problem is either stale input (print again) or a fault in the site's layout, such as a figure wider than the column, a chart that didn't draw or a missing font. You can't fix the layout: record it as `verdict: "issues"` with the page and what is wrong, for the editor.
4. Look at each edition. Read the contact sheet first, then every page image, in order. Look for:
   - a figure or table cut across two pages, or one that overflows the column or the page;
   - a heading alone at the foot of a page, or a single line of a paragraph alone at the top or foot of a page;
   - a page that ends far too early (`proof.json` lists the gaps the layout pass could not close);
   - chart labels that overlap or run outside the plot, a legend that hides data, an empty chart;
   - text in the wrong language, missing Hangul (boxes or blanks), Korean words broken in the middle;
   - the running head, page numbers and the address at the foot of every page but the first;
   - the end matter: terms, references with their addresses, the citation box and the steps table.
5. If something can be fixed by printing again (an input changed after the proof), print again, at most twice. Anything else goes to the editor.
6. Write `pdf/pdf.json` (`contracts/pdf.schema.json`):
   - `editions`: one entry per edition with `lang`, `pages`, `verdict` (`ok` or `issues`) and `notes` (page by page, what you saw);
   - `rounds`: how many times you printed;
   - `checked`: what each look covered and found;
   - `for_editor`: what the editor should see at gate 3, with page numbers (for example "EN p. 4 ends 40 mm early: figure 3 is taller than the space left").
7. `artools run done $run_id make-pdf`. It validates the record and runs the checks.

## Judgement

- A gap at the foot of a page before a tall figure is normal in print; it is an issue only when it is most of a page.
- Judge the page as a reader holding paper would: can they follow the text, find each figure's source and cite the article?
- Small differences between the proof and the published PDF are expected: publishing prints again from the published files, and the steps table then shows the final page count.

## Never

- Edit the site's code (`apps/`, `packages/`), the print stylesheet or the draft: the layout is shared by every article, and the text has passed its review. Report what prints wrong instead.
- Write into `content/`: `artools ship` prints the published PDFs.
