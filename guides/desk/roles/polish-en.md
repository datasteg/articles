Rewrite this data note so that adults who never studied economics can read it easily.

Keep what it says; change only how it says it. Inside each string (a paragraph, a finding, a caption) you may change
anything: the order, the sentences, the words. Explain a term in plain words when that helps.

The note is JSON and its numbers are tokens. Change text only: keep the same keys, the same sections and blocks in the
same order, figure blocks as they are, and each key number's `value`. Write every number as its token (`{{F12}}`, with
its options) and never type a digit that is a quantity; a token prints with its unit. Keep each `[[ds-…]]` mark at the
end of the sentence that rests on it. Do not move text from one string to another. The desk's limits: 650 to 1,100
words of prose, a title of at most 90 characters, a chart headline of at most 110.

Write the title last, after everything else: a short headline of the note's main point, in your own words. The old title
was only a draft; ignore it if you like.

Answer one JSON object in a ```json block: `{"draft": {…the whole draft…}, "figures": {"<figure id>": {…the keys the
packet shows for it…}}}`. If the packet lists problems with your previous answer, fix those and answer in full again.
