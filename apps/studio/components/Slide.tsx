import { BarChart, ChartTable, DumbbellChart, LineChart, ScatterChart, StatTiles, tx, type ChartSpec } from '@articles/charts';
import type { Lang } from '@glacier/i18n';
import { chartAt, type Deck, type SlideData } from '@/lib/deck';

// One slide at 1920×1080: each template is a component of the article page (apps/web/app/article.css,
// packages/ui/glacier.css) at video size. The bottom 162 px stay empty for YouTube's captions. The podcast video's
// decks (deck.motion) add the story rail, the flow and story templates and the enter animations (studio.css § podcast).

const LABEL: Record<string, Record<Lang, string>> = {
  question: { en: 'The question', ko: '질문' },
  keyNumbers: { en: 'Key numbers', ko: '주요 수치' },
  findings: { en: 'Key findings', ko: '핵심 결과' },
  read: { en: 'Our read', ko: '우리의 판단' },
  sources: { en: 'Sources', ko: '출처' },
};

/** List items revealed by build steps: at step k of n, all but the last n − k items show. */
const shown = (count: number, steps: number, step: number) => count - (steps - Math.min(step, steps));

type Css = React.CSSProperties & Record<`--${string}`, number>;
type Enter = (kind: string, i?: number) => { 'data-a'?: string; style?: Css };

/** Motion (the podcast video, deck.motion): what enters at this step carries `data-a` (its animation, studio.css
 *  § motion) and its place in the stagger. `artools video slides` steps the animations frame by frame; without
 *  motion nothing is marked and the slide is the still it always was. */
function motion(deck: Deck, s: SlideData, step: number) {
  const on = Boolean(deck.motion);
  const enter: Enter = (kind, i = 0) => (on && step === 1 ? { 'data-a': kind, style: { '--i': i } } : {});
  /** List item i of count: shown at this step, and entering now (with its place among the newcomers). */
  const span = (count: number) => [step === 1 ? 0 : shown(count, s.steps, step - 1), shown(count, s.steps, step)];
  const mark = (kind: string, i: number) => ({ 'data-a': kind, style: { '--i': Math.max(0, i) } as Css });
  /** List item i of count: hidden until its step; entering now carries its place among the newcomers (× scale). */
  const item = (i: number, count: number, kind = 'rise', offset = 0, scale = 1) => {
    const [before, now] = span(count);
    return { later: i >= now, a: on && i < now && i >= before ? mark(kind, offset + scale * (i - before)) : {} };
  };
  /** What comes with a list's last item (a closing line): it enters after the newcomers. */
  const after = (count: number, kind = 'rise', offset = 0, scale = 1) => {
    const [before, now] = span(count);
    return { later: now < count, a: on && now >= count && before < count ? mark(kind, offset + scale * (now - before)) : {} };
  };
  return { enter, item, after };
}

/** Where the slide sits in the story: the part's index, every part done in the recap, -1 before the first part. */
function storyAt(deck: Deck, s: SlideData) {
  const parts = deck.story ?? [];
  if (s.part === 'recap' || s.part === 'end') return parts.length;
  return parts.findIndex((p) => p.id === s.part);
}

/** The podcast video's rail: every part's short label over a track. Parts before this one are filled; the current
 *  part's track is filled by the assembly as the audio moves through it (podcast.py → _rail). */
function Rail({ deck, s }: { deck: Deck; s: SlideData }) {
  if (!deck.story?.length || ['thumb', 'end', 'chapter', 'story', 'roadmap'].includes(s.template)) return null;
  const cur = storyAt(deck, s);
  return (
    <nav className="vs-rail" aria-hidden="true">
      {deck.story.map((p, i) => (
        <span key={p.id} data-part={p.id} className={i < cur ? 'is-done' : i === cur ? 'is-on' : undefined}>
          <b>{p.label}</b><i />
        </span>
      ))}
    </nav>
  );
}

/** The story line as a vertical track: parts done show what they found, the current part is lit, later ones wait.
 *  `current` is -1 for the roadmap (each part with the question it answers) and the part count for the recap. */
function Line({ deck, s, step, current, labels, big }: { deck: Deck; s: SlideData; step: number; current: number; labels?: string[]; big?: boolean }) {
  const { item } = motion(deck, s, step);
  const parts = deck.story ?? [];
  const n = parts.length;
  const reveal = s.template !== 'chapter';
  return (
    <ol className={'vs-line' + (big ? ' vs-line--big' : '')}>
      {parts.map((p, i) => {
        const it = reveal ? item(i, n) : { later: false, a: deck.motion && step === 1 ? { 'data-a': i === current ? 'pop' : 'fade', style: { '--i': i === current ? n : i } as Css } : {} };
        const state = i < current ? 'is-done' : i === current ? 'is-on' : 'is-next';
        return (
          <li key={p.id} className={state + (it.later ? ' is-later' : '') + (current < 0 && p.question ? ' is-ask' : '')} {...it.a}>
            <b>{labels?.[i] ?? p.label}</b>
            {i < current && p.takeaway ? <span>{p.takeaway}</span> : null}
            {current < 0 && p.question ? <span>{p.question}</span> : null}
          </li>
        );
      })}
    </ol>
  );
}

function Road({ deck, s }: { deck: Deck; s: SlideData }) {
  if (s.template === 'end' || s.template === 'thumb' || deck.parts < 2) return null;
  return (
    <p className="vs-road" aria-hidden="true">
      {Array.from({ length: deck.parts }, (_, i) => (
        <span key={i} className={s.road === i + 1 ? 'is-on' : undefined}>{i + 1}</span>
      ))}
    </p>
  );
}

function Plot({ spec, lang }: { spec: ChartSpec; lang: Lang }) {
  if (spec.form === 'line') return <LineChart spec={spec} lang={lang} height={236} />;
  if (spec.form === 'bars') return <BarChart spec={spec} lang={lang} />;
  if (spec.form === 'dumbbell') return <DumbbellChart spec={spec} lang={lang} />;
  if (spec.form === 'scatter') return <ScatterChart spec={spec} lang={lang} />;
  if (spec.form === 'stat-tiles') return <StatTiles spec={spec} lang={lang} />;
  return <ChartTable spec={spec} lang={lang} caption={tx(spec.title, lang)} />;
}

export function Slide({ deck, s, step }: { deck: Deck; s: SlideData; step: number }) {
  const lang = deck.lang;
  const f = s.fields;
  const { enter, item, after } = motion(deck, s, step);
  const story = Boolean(deck.motion && deck.story?.length);
  let body: React.ReactNode = null;
  switch (s.template) {
    case 'question':
      body = (<>
        {f.kicker ? <p className="vs-kicker" {...enter('fade')}>{f.kicker}</p> : null}
        <p className="vs-label" {...enter('fade')}>{LABEL.question[lang]}</p>
        <p className="vs-asked" {...enter('rise', 1)}>{f.text}</p>
      </>);
      break;
    case 'answer':
      body = (<>
        {f.kicker ? <p className="vs-kicker" {...enter('fade')}>{f.kicker}</p> : null}
        <p className="vs-answer" {...enter('rise', 1)}>{f.text}</p>
      </>);
      break;
    case 'roadmap':
      if (story) {
        body = (<>
          {f.kicker ? <p className="vs-kicker" {...enter('fade')}>{f.kicker}</p> : null}
          <Line deck={deck} s={s} step={step} current={-1} labels={f.items} big />
        </>);
        break;
      }
      body = (<>
        {f.kicker ? <p className="vs-kicker">{f.kicker}</p> : null}
        <ol className="vs-roadmap">
          {(f.items ?? []).map((t, i) => <li key={i} className={i < shown(f.items?.length ?? 0, s.steps, step) ? undefined : 'is-later'}><span>{String(i + 1).padStart(2, '0')}</span>{t}</li>)}
        </ol>
      </>);
      break;
    case 'number':
      body = (<>
        <p className="vs-label" {...enter('fade')}>{f.kicker ?? LABEL.keyNumbers[lang]}</p>
        <div className="vs-rule" {...enter('grow')} />
        <p className="vs-big" {...enter('pop', 1)}>{s.facts[0]?.written}</p>
        <p className="vs-biglabel" {...enter('rise', 3)}>{f.label}</p>
        {story && f.text ? <p className="vs-so" {...enter('rise', 5)}>{f.text}</p> : null}
      </>);
      break;
    case 'compare':
      body = (<>
        <p className="vs-label" {...enter('fade')}>{f.kicker ?? LABEL.keyNumbers[lang]}</p>
        <div className="vs-rule" {...enter('grow')} />
        <div className="vs-tiles">
          {s.facts.map((x, i) => {
            const it = item(i, s.facts.length, 'rise', 1);
            return (
              <div key={x.id} className={'vs-tile' + (it.later ? ' is-later' : '')} {...it.a}>
                <p className="vs-tile__value">{x.written}</p>
                <p className="vs-tile__label">{f.items?.[i] ?? x.label}</p>
              </div>
            );
          })}
        </div>
        {story && f.text ? (() => { const it = after(s.facts.length, 'rise', 2); return <p className={'vs-so' + (it.later ? ' is-later' : '')} {...it.a}>{f.text}</p>; })() : null}
      </>);
      break;
    case 'figure': {
      const spec = s.chart ? chartAt(s.chart, s.builds, step) : null;
      body = (<>
        <p className="vs-label" {...enter('fade')}>{f.kicker}</p>
        <p className="vs-headline" {...enter('rise')}>{f.headline}</p>
        {spec ? <div className="vs-chart" {...enter('wipe', 2)}><Plot spec={spec} lang={lang} /></div> : null}
        {f.source ? <p className="vs-source" {...enter('fade', 6)}>{f.source}</p> : null}
      </>);
      break;
    }
    case 'findings':
      body = (<>
        <p className="vs-label" {...enter('fade')}>{f.kicker ?? LABEL.findings[lang]}</p>
        <ol className="vs-findings">
          {(f.items ?? []).map((t, i) => {
            const it = item(i, f.items?.length ?? 0, 'rise', 1);
            return <li key={i} className={it.later ? 'is-later' : undefined} {...it.a}><span>{String(i + 1).padStart(2, '0')}</span>{t}</li>;
          })}
        </ol>
      </>);
      break;
    case 'term':
      body = (<>
        <p className="vs-term" {...enter('rise')}>{f.kicker}</p>
        <p className="vs-define" {...enter('rise', 2)}>{f.text}</p>
      </>);
      break;
    case 'quote':
      body = (<blockquote className="vs-quote" {...enter('fade')}><p {...enter('rise', 1)}>{f.text}</p><footer {...enter('fade', 4)}>{f.source}</footer></blockquote>);
      break;
    case 'read':
      body = (<>
        <div className="vs-strata" aria-hidden="true" {...enter('grow')}><i /><i /><i /></div>
        <p className="vs-readlabel" {...enter('fade', 1)}>{f.kicker ?? LABEL.read[lang]}</p>
        <p className="vs-read" {...enter('rise', 2)}>{f.text}</p>
      </>);
      break;
    case 'chapter':
      if (story) {
        body = (
          <div className="vs-chap2">
            <div className="vs-chap2__head">
              <p className="vs-chapnum" {...enter('fade')}>{f.kicker}</p>
              <p className="vs-chaptitle" {...enter('rise', 1)}>{f.headline}</p>
              {f.text ? <p className="vs-chapq" {...enter('rise', 3)}>{f.text}</p> : null}
            </div>
            <Line deck={deck} s={s} step={step} current={storyAt(deck, s)} />
          </div>
        );
        break;
      }
      body = (<>
        <p className="vs-chapnum">{f.kicker}</p>
        <p className="vs-chaptitle">{f.headline}</p>
        {f.text ? <p className="vs-chapq">{f.text}</p> : null}
      </>);
      break;
    case 'thumb':
      body = (<>
        <p className="vs-kicker">{f.kicker}</p>
        <p className="vs-thumbtitle">{f.headline}</p>
        {f.text ? <p className="vs-thumbsub">{f.text}</p> : null}
        <p className="vs-thumbmark">datasteg</p>
      </>);
      break;
    case 'flow': {
      // a chain of two to four steps: what leads to what, an arrow drawn before each next step
      const n = f.items?.length ?? 0;
      const so = after(n, 'rise', 1, 2);
      body = (<>
        {f.kicker ? <p className="vs-label" {...enter('fade')}>{f.kicker}</p> : null}
        {f.headline ? <p className="vs-headline" {...enter('rise')}>{f.headline}</p> : null}
        <ol className="vs-flow" style={{ '--n': n } as Css}>
          {(f.items ?? []).map((t, i) => {
            const card = item(i, n, 'rise', 1, 2), arrow = item(i, n, 'draw', 0, 2);
            return (
              <li key={i} className={(card.later ? 'is-later' : '') + (i === n - 1 ? ' is-end' : '')} {...card.a}>
                {i > 0 ? <i className="vs-flow__arrow" {...arrow.a} /> : null}
                <p className="vs-flow__text">{t}</p>
                {f.values?.[i] ? <p className="vs-flow__value">{f.values[i]}</p> : null}
              </li>
            );
          })}
        </ol>
        {f.label ? <p className={'vs-so' + (so.later ? ' is-later' : '')} {...so.a}>{f.label}</p> : null}
      </>);
      break;
    }
    case 'story':
      // the recap: every part with what it found, one per step
      body = (<>
        <p className="vs-label" {...enter('fade')}>{f.kicker}</p>
        <Line deck={deck} s={s} step={step} current={(deck.story ?? []).length} big />
      </>);
      break;
    case 'end':
      body = (<>
        <p className="vs-label" {...enter('fade')}>{f.kicker ?? LABEL.sources[lang]}</p>
        <ol className="vs-refs">{(f.items ?? []).map((t, i) => <li key={i} {...enter('rise', i)}><span>{i + 1}</span>{t}</li>)}</ol>
        <p className="vs-addr" {...enter('rise', (f.items?.length ?? 0) + 1)}>{f.text}</p>
        <p className="vs-fine" {...enter('fade', (f.items?.length ?? 0) + 3)}>{f.label}</p>
      </>);
      break;
  }
  return (
    <section className={`vs vs--${s.template}` + (deck.motion ? ' vs-pod' : '') + (story && s.template !== 'thumb' && s.template !== 'end' ? ' has-rail' : '')}
      lang={lang} data-slide={s.id} data-step={step}>
      {story ? <Rail deck={deck} s={s} /> : <Road deck={deck} s={s} />}
      <div className="vs-in">{body}</div>
    </section>
  );
}
