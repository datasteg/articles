# The podcast video: NotebookLM's conversation, the article's slides

The style book of the podcast video (`config/video/podcast-pipeline.yaml`, `config/video/podcast.yaml`). Since
29 Oct 2026 it is the default video (`podcast.yaml` → `default_mode`); the narrated video (`guides/video.md`) stays
available with `artools video start <slug> --mode narrated`.

## Who it is for

College students and young professionals: curious and smart, not economists. They watch on YouTube with the
summary slides, or listen on earphones while walking. Two hosts talking suit them better than one narrator: the
second voice asks the question the listener would ask ("And what does that mean, exactly?").

## How it is made

1. **make-podcast** plans the episode (`podcast/plan.json`: five or six parts from the article's sections), builds the
   source and the focus prompt, and drives NotebookLM ("Gemini Notebook") in the editor's Chrome through Claude in
   Chrome: one notebook per edition, a Deep dive Audio Overview at Default length, downloaded as `.m4a`.
2. **transcribe** (a command): VibeVoice-ASR, an open-weights model running on dev-host, hears the audio in pieces
   of about five minutes cut at pauses and returns who spoke, when and what (`asr/<lang>.json`: one sentence per
   segment, boundaries at pauses, speaker A the lower voice); `check` lists numbers not in the source and any
   pointing at a screen.
3. **make-podcast-slides** builds one slide library from the article, words it in both languages, renders it with its
   enter animations, writes each edition's timeline from the transcript, and translates each transcript into the other
   language's captions.
4. **assemble-podcast** lays the slides over the audio (−14 LUFS): each cue cross-fades in and plays its animation, the
   rail tracks the part. Captions in both languages, chapters.
5. **review-podcast**: an independent fact-check of what the hosts say. A blocking issue sends the edition back to
   make-podcast for one new take: two takes per edition at most, the second only for a blocking error. Nothing waits for a person: what is still blocking after the loop is
   published anyway and listed in `youtube/<lang>.json` → `steps.review` (`podcast.yaml` → `on_blocking`).
6. **upload** (public, both editions, each with captions in its own language and the other's), **finish** (waits for
   YouTube's processing, then the thumbnails and the links between the editions, which fail while it runs), then **clean**:
   the audio, frames, clips and video are deleted from the run.
   The audio lives on in the notebook, the video on YouTube; the run keeps the JSON, transcripts and captions.

## The source and the prompt

Everything downstream comes from the audio, so these two decide the video.

- **The source** is the edition itself, reorganised: the question, the short answer, the findings and key numbers,
  then the parts in order (each with its sections), every chart described in words (title, takeaway, how to read
  it), our read, the limits as context, and the glossary with this article's sense of each term. Model design and
  technical appendices are dropped: two hosts can't discuss an estimation strategy for a general audience. "The chart
  below" sentences are removed, so the hosts don't point at charts.
- **The prompt** (`podcast.yaml` → `prompt`) names the audience, holds the hosts to the source's facts and hedges,
  gives the shape (question, short answer, the parts announced by name, our read, three things to remember, the
  site's address), and the rules for the ear (terms defined once, one number per sentence, sizes in words).
- What the 29 Oct 2026 pilot taught: the hosts keep numbers well (every number in both editions matched the source)
  but loosen causal language ("the data proves", "a vivid case of uncertainty damaging the economy", "the only
  response") and use textbook senses of terms the article hedges ("small open economy"). The prompt now asks for the
  source's causal care explicitly.

## The slides

- The article's own components at 1920×1080 in the site's dark theme (`guides/video.md` § For the eye), in a podcast
  look (`apps/studio/app/studio.css` § podcast): cards for tiles, findings, terms and flow steps, a soft light in the top
  corner. Four templates are this video's own: `chapter` (the part, its question, and the story so far), `flow` (two to
  four steps with arrows: what leads to what), `story` (the recap: every part with what it found) and `thumb`.
- **The slides tell the story, not just the facts.** The editor's review of the pilot (29 Oct 2026): static text cards
  that repeat the audio are "not attractive and useless". So every slide adds something the ear can't hold: the exact
  figure, the mechanism as a chain, or where the story stands. The rail across the top names the parts and fills as
  each one plays; each chapter card lists what the parts before it found; the recap builds the whole line.
- **The slide shows what is being said, as the article says it.** A number tile goes up when a host says the number;
  a flow step when they reach it; a term card when they define the term; a chapter card at "Part two". When a host
  overstates, the slide holds the article's version (the term card for "small open economy" says the article uses it
  in the everyday sense).
- **Motion is mild** (§ motion): things rise a little and fade in one after another, a chart is drawn left to right, an
  arrow before the step it leads to; each slide cross-fades in over 0.4 s. Nothing moves for longer than 1.4 s, nothing
  bounces or zooms. The renderer steps the animations frame by frame into a short clip per slide step.
- Change every 10–45 seconds, never hold over a minute, never flash under five seconds.
- No table charts: at video size a scenario table is unreadable. A three-item findings list carries the same ladder.
- Captions are the transcript. Words cut at a piece boundary or plainly misheard may be corrected
  (`asr/<lang>.json` → `edited`); the hosts' words are never changed.
- **Captions in the other language** (since 29 Oct 2026): the Korean video carries English captions and the English
  video Korean, translated per segment with the transcript's times (`asr/<lang>.<other>.json`). They translate what the
  host said, slips included, with the other edition's terms; `artools video podcast captions` checks coverage,
  reading speed and numbers.

## The review

What counts as blocking: a wrong number, year, sign or country; a model scenario presented as a forecast; a causal
claim the article explicitly declines ("not proof of it"); investment advice. Advisory: paraphrase that leans
stronger than the article, analogies, small rounding. Advisory issues the slides can answer are fixed on the slides.

## Known limits

- NotebookLM has no public API for personal accounts: the step needs the editor's Chrome open and signed in, with the
  Claude in Chrome extension connected. When Google's Podcast API (Gemini Enterprise, allow-listed) is available, it
  replaces the browser step: same source, same prompt, an MP3 back.
- Each take takes 12–15 minutes; usage limits refresh every five hours.
- YouTube takes videos over 15 minutes only from a verified account (`longUploadsStatus: allowed`). Before the
  channel was verified, the 18-minute English pilot was accepted by the API and then silently removed, twice;
  the upload now checks first. Verification also unlocked custom thumbnails (the 403s of the pilot).
- The transcript is made on dev-host: about 25 minutes of
  GPU time for both editions. Whole files fail on this GPU (out of memory, or a loop to the token cap), so the audio
  is cut at pauses and each piece's tokens are capped; a piece that still breaks off is heard again in two halves.
- Gemini transcribed the pilot (29 Oct 2026) and made two hosts' lines agree: a host said "삼분의 이 퍼센트" where the
  article says one third, the other host echoed "삼분의 일쯤이요?", and Gemini wrote 3분의 1 for both, so the review
  missed it. VibeVoice writes what was said; it may drop a short "okay" or "네" from the other host and writes some
  numbers in words.
