# Video: writing for the ear and the eye

The style book of the video explainer (`config/video/pipeline.yaml`). Read with
`voice-en.md` and `voice-ko.md`: everything there still holds; this adds what changes when the article is heard.

## Who listens

Economists and the economically literate: an analyst, a researcher, a student of economics, a policy reader. Picture
them **walking down a street with earphones in**. They know what a yield curve or a term premium is, they care who
found what and how, and they give the video one ear: traffic, a crossing, a shop door. They cannot scroll back, and
they will not remember a table read aloud.

**The rule:** the narration tells the story; the slide holds the exact numbers. A listener with the screen off follows
every argument and keeps the few numbers that matter. A viewer who glances down gets the figure and the chart.

(Revised 26 Oct 2026 after the first pilot: its narration read out too many numbers, and the editor lost the thread.)

## The narrator

An economist friend who has read the papers and the data and is walking you through it: calm, warm, exact, a little
dry, nothing performed. They use the field's words (forward guidance, term premium, dot plot) with a one-clause
definition the first time, name the people and institutions behind each finding ("Fed staff research", "Kiley and
Mishkin"), and say plainly where the evidence is thin. One narrator per language, the same voice in every video.

Never:
- banter, a second host, or agreement noises ("exactly", "right?", "wow");
- a teaser before the question, or "let's dive in", "dive deep", "fascinating", "here's the thing", "simply put",
  "you might be thinking", "game-changer", exclamation marks;
- an upbeat tone for a grave subject, or alarm for any subject.

Contractions are fine in English ("it's", "doesn't"): this is speech. Uncertainty is said plainly: "the data cannot tell
us yet".

## Numbers: few, and only the ones to remember

The ear holds one number at a time and keeps very few. So:

- **Choose the numbers first.** Before writing, pick at most **eight** numbers the listener should still remember at the
  end, and build the script around them. Every other figure stays on the slides and in the article.
- **At most one spoken number per beat**, and at most **three per chapter**. The check counts fact tokens in `spoken`:
  more than 12 in an edition, or two in one beat, is flagged.
- **Say size and direction in words** wherever the exact figure isn't the point: "more than doubled", "about half",
  "the fastest rise since the 1980s", "a quarter of a point".
- **Name episodes by their year**, not by month and day: "the 2013 taper tantrum", "the 2021 delay". Dates of the day are
  for slides.
- **Never read a list of numbers**, a table, or a comparison of four countries. Tell the one that matters and say "the
  others moved far less".
- A number slide shows a number the narrator says in that beat; a chart can show more, and the narration tells its
  shape.

## Chapters: hook, example, point, wrap-up

Each part (`p1`–`p4`) is a chapter, and every chapter has the same rhythm, which the storyboard marks on each beat
(`beats[].role`):

1. **`hook`**: one or two sentences that open the chapter with its question, or a scene ("In June 2013, a few words at a
   press conference sent mortgage rates up by a full point.").
2. **`example`**: the chapter's concrete case, told like a story: who said what, when, what markets did, what followed.
   Draw it from the article's evidence: an episode, a speech, a study. At least one per chapter.
3. **`point`**: the mechanism in plain words: why it happened, what it means for the argument.
4. **`evidence`**: the one number, or the one study's finding, that carries the chapter.
5. **`wrap`**: the chapter's last beat, one or two sentences that say what the listener should keep: "So, the first
   lesson: a promise outlived the conditions it was made for." A pause follows (`pause_after` 1.0).

A `quote` beat (at most 20 words, verbatim from the article, the speaker named) may replace part of an example. An
analogy is allowed once per chapter when it illuminates the mechanism and adds no claim of its own; say that it is one
("Think of it as…").

The **recap** repeats the chapter wrap-ups in order, then the answer, so a listener who drifted for a minute catches up.

## The shape

| Part | `parts[].id` | English words | Korean syllables | Slides |
|---|---|---|---|---|
| Open: the question as a scene or a puzzle | `open` | 60–90 | 140–200 | 1–2 |
| The answer in two sentences, then the chapters by name | `answer` | 90–130 | 200–280 | 1–2 |
| One chapter each: hook, example, point, evidence, wrap | `p1`–`p4` | 250–380 each | 550–850 each | 3–5 each |
| What the evidence does not show; where studies disagree | `limits` | 120–180 | 270–400 | 1–2 |
| The chapter wrap-ups again, then the answer and the editor's read | `recap` | 120–170 | 270–380 | 1–2 |
| Sources, the article's address, disclaimer, synthetic voice | `end` | 40 | 90 | 1 |

About ten minutes is the aim and longer is fine when the article needs it (the editor, 26 Oct 2026): the check allows
1,300–2,200 English words and 2,450–4,100 Korean syllables, about 9 to 15 minutes at the narrators' measured rates. Use
**24–32 beats** of 20–45 seconds rather than many short ones: each beat is one voice request, and Gemini allows 100 a day.
16–24 slides, at most four charts (`config/video/speech.yaml`). If the question was refined at gate 1, the answer part
says how, from `question.premiseNote`. A fourth chapter (`p4`) only when the article has four findings that can't be
merged.

## For the ear

- **Never point at the screen.** Banned: "as you can see", "this chart", "the chart above", "here you see", "on the
  left/right", "the red/blue line". 한국어: 보시는 것처럼, 보시다시피, 이 그래프, 화면, 여기, 왼쪽, 오른쪽, 빨간 선.
- **Tell a chart by its shape:** where the line starts, where it ends, its peak or turn, and what it is compared with,
  in words and at most one number.
- **Signpost.** Name the chapters in the answer; say "first", "second", "third"; open each chapter with its question;
  close it with its wrap-up.
- **Define each term once,** in one plain clause from `content/glossary/<id>.json` and the article's `terms[].context`;
  then keep the same word.
- **Short sentences, varied rhythm.** English: average about 14 words, none over 22. Korean: § 한국어 내레이션 below.
- **Sources by name in speech** ("Fed staff research", "a study by the IMF", "Governor Waller said"). No citation
  numbers, no URLs except the site's name once at the end.
- **Claims follow the article.** Nothing the article doesn't say; its causal words and its caveats; no forecasts, only
  conditions. The disclaimer and the synthetic-voice line are said once, in `end`.

## For the eye

- **The slide is the article's own component** at 1920×1080 in the site's dark theme (templates below). Never more than
  12 words of running text; never a paragraph.
- **Nothing on screen the narrator doesn't say** in that beat or the one before.
- **One idea per slide,** changed every 15–40 seconds. A build step (highlight, a second series, an annotation) appears
  on the words that name it (`cues[].at`).
- **The bottom 15% stays empty** (captions), with 5% margins on every side.
- **Korean slides** follow the site's Korean typography (no uppercase, letter-spacing 0.02em) and newspaper wording
  ("2012년 이후 최대"), written for Korean readers, not translated from the English label.

### Templates (`storyboard.slides[].template`)

| Template | The article component | Fields in `script/<lang>.json` → `slides` |
|---|---|---|
| `question` | the question box | `kicker` (the topic), `text` (the question, read word for word) |
| `answer` | dek | `text` (one or two short lines) |
| `roadmap` | table of contents | `items` (the three parts, three to six words each) |
| `number` | a key-number tile | `kicker`, `label` (what, when, compared with what); the number comes from `facts[0]` |
| `figure` | a figure: head, chart, source line | `kicker` ("Figure 1" / "그림 1"), `headline` (the takeaway), `source`; the chart is `storyboard.chart` |
| `compare` | stat tiles side by side | `items` (one label per fact in `facts`, two or three) |
| `findings` | the key-findings box | `kicker`, `items` (up to three, headline length) |
| `term` | a glossary popover | `kicker` (the term), `text` (the plain definition) |
| `quote` | a quote with its source | `text` (verbatim, at most 20 words), `source` |
| `read` | "Our read" with the strata rule | `text` (the editor's read, one sentence) |
| `end` | references and the citation block | `items` (up to three source names), `text` (address), `label` (disclaimer and disclosure) |

Every slide but `end` carries the roadmap marker (1 · 2 · 3) for the part that is playing.

## Number tokens

The numbers that are spoken or shown are fact tokens, exactly as in `numbers.md`, from `source/facts.json` (the article's publishable facts):

- `{{F4}}` on slides and in captions renders the written form at the ear's rounding: "97bp", "4.4%", "2012년 7월".
- `{{F4:spoken}}` in `spoken` renders words for the voice: "97 basis points", "4.4 percent", "97베이시스포인트",
  "4.4퍼센트". Options combine: `{{F5:spoken|signed}}`, `{{F5|abs}}`.
- Dates, years, maturities ("10-year", "10년물") may be typed. Every other digit fails the check.

When the article's own figure is too precise for the ear (4.44%), the token's rounding handles it; don't type a rounded
number yourself. Sizes said in words need no token: "about three quarters", "more than doubled", "half"; 한국어로는
"넷 중 셋", "두 배가 넘게", "절반"처럼 숫자 없이 쓴다.

## 한국어 내레이션

신문처럼 쓰고(`voice-ko.md`), 방송처럼 말한다.

- **말투.** 하십시오체("~습니다", "~입니다")로 쓴다. 묻는 문장만 "~까요?"로 쓰고, 해요체("~해요", "~죠")와 섞지 않는다.
- **길이.** 한 문장은 평균 30자 안팎, 많아야 45자다. 한 숨에 읽을 길이로 쓴다. 듣는 사람은 앞 문장으로 돌아갈 수 없다.
- **어순.** 주어를 앞에 두고 서술어를 빨리 낸다. 명사 앞 관형절은 10자 안팎으로 줄인다. 길어지면 문장을 나눈다.
- **소리가 비슷한 한자어 대신 고유어 동사.** 인상·인하는 올렸다·내렸다, 증가·감소는 늘었다·줄었다, 상승·하락은
  올랐다·떨어졌다로 쓴다. 인상과 인하는 끝소리 하나만 다르다.
- **영어 낱말 대신 우리말.** 스프레드는 처음 한 번만 "흔히 스프레드라고 부르는 가산금리"로 소개하고 그다음부터
  "금리 차이"로 쓴다. 리스크는 위험, 펀더멘털은 기초여건이다.
- **숫자.** 꼭 기억할 숫자만 말한다. 한 구간에 하나, 한 장에 셋까지다. 나머지는 "두 배가 넘게", "절반쯤", "넷 중 셋"처럼
  말로 크기를 전하고, 정확한 값은 슬라이드에 맡긴다. 날짜는 "2013년"처럼 해까지만 말한다.
- **장을 닫는 말.** 장마다 마지막 구간에서 "정리하면", "첫째 교훈은"으로 시작해 한두 문장으로 요점을 남긴다.
- **기관.** 처음에는 이름으로 부른다(유럽중앙은행, 국제통화기금). 그다음부터 약어로 부르고, 읽는 법은
  `config/video/lexicon.ko.yaml`에 둔다.
- **접속어로 길을 낸다.** 먼저, 그런데, 그래서, 다만, 정리하면. 쓰는 글보다 자주 쓴다.
- **쓰지 않는 말.** "~에 대해 알아보겠습니다", "깊이 파고들어 보겠습니다", "흥미롭게도", "무려", "여러분", "자,".
  번역 투(`voice-ko.md` 표)도 그대로 금지다.
- **자막과 슬라이드**는 신문 표기를 따른다(97bp, 4.4%, 2026년 9월). 소리는 발음 사전을 따른다.

예: 한 장(프랑스 기사의 둘째 장)을 새 방식으로.

> (hook) 둘째, 프랑스의 차입 비용은 왜 올랐을까요?
> (example) 같은 아홉 달 동안 독일의 10년물 금리도 올랐습니다. 미국과 영국, 일본도 마찬가지였습니다.
> (point) 안전한 금리가 모두 오르면 누구나 더 비싸게 빌립니다. 프랑스만의 웃돈은 그 위에 얹힌 층입니다.
> (evidence) 프랑스 금리가 오른 폭 가운데 넷 중 셋은 독일 금리가 함께 오른 몫입니다.
> (wrap) 정리하면, 둘째 교훈은 이것입니다. 지금은 세계 금리가 높아진 시기이고, 프랑스만의 몫은 그 위의 일부입니다.

## English narration, an example

The same chapter, one number at most, the size in words:

> (hook) Second: why did France's borrowing cost rise at all?
> (example) Look at Germany, the euro area's safe borrower. Over the same nine months its ten-year yield climbed too, and
> so did America's, Britain's and Japan's.
> (point) When the safe rate rises everywhere, every borrower pays more. France's own premium is only the top layer.
> (evidence) About three quarters of France's rise was Germany's own.
> (wrap) So, the second lesson: this is mostly a world of higher rates, with a French layer on top.

## Pauses

Silence is added by `artools video voice`, not written into the text: `speech.yaml` → `pause` (0.4 s between beats,
1.0 s between parts). A beat may set `pause_after` (up to 3 s) after a key number or before the recap.

## The two tests

- **Eyes closed** (`review-video`): from the transcript alone, answer five questions: the answer, each chapter's
  wrap-up, one limit, and the one or two numbers the script chose to stress.
- **Muted:** from the slide contact sheet alone, state the question, the answer and the chapters in order.
