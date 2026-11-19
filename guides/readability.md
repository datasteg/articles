# Readability

The reader should understand the answer after the title, key numbers and findings, and understand why after the sections.

- **Order.** Answer → key numbers → findings → the question → sections that each open with their point → our read → references.
- **Length.** 1,200–1,800 English words (7–9 minutes). Cut background no sub-question needs.
- **Sentences.** 15–20 words on average, none over 40. Korean: about 45 characters on average (at most 50), none over 70; translation-style Korean is flagged (`guides/voice-ko.md`).
- **Paragraphs.** One idea, at most four sentences.
- **Jargon.** Every technical term is defined where it first appears, in plain words or with a glossary mark `((spread))`. Each glossary id used needs an entry in `draft/glossary.json` with an EN and KO definition of one or two sentences.
- **Numbers.** No more than two or three numbers in a sentence; let the charts carry series.
- **Headings.** Plain statements or short noun phrases a skimming reader can follow.
- **Figures.** One per main point, placed right after the paragraph that introduces it; the paragraph tells the reader what to look at.

`artools check readability --run <run>` measures sentence and paragraph length and flags jargon without a glossary mark. Its findings are advisory; the review decides.
