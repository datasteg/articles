import type { CSSProperties } from 'react';
import type { Lang } from '@glacier/i18n';
import { fmtPeriod, tx } from '@articles/charts';
import type { Meta, Pipeline, PipelineStep } from '@/lib/content';
import { providerName, s, statLine } from '@/lib/strings';
import { Glyph } from './Glyph';

type Run = Meta['run'];

const counts = (p: Pipeline) => ({
  phases: p.phases.filter((ph) => p.steps.some((x) => x.phase === ph.id)).length,
  steps: p.steps.filter((x) => !x.gate).length,
  gates: p.steps.filter((x) => x.gate).length,
});

/** A pipeline (config/pipelines/<id>.yaml) as a swimlane: one row per phase, its steps left to right, in columns
 *  shared by every row. Plain HTML and CSS (article.css § pipeline): in a container under 720px it stacks
 *  vertically. With `run` (an article's meta.run), each step shows what that run produced and each editor gate
 *  its approval; `details` adds each step's one-line description. */
export function PipelineDiagram({ p, lang, run, details = false, legend = true, label }: {
  p: Pipeline; lang: Lang; run?: Run; details?: boolean; legend?: boolean; label?: string;
}) {
  const phases = p.phases.map((ph) => ({ ...ph, steps: p.steps.filter((x) => x.phase === ph.id) })).filter((ph) => ph.steps.length);
  const cols = Math.max(1, ...phases.map((ph) => ph.steps.length));
  const numbers = new Map(p.steps.filter((x) => !x.gate).map((x, i) => [x.id, i + 1]));
  const c = counts(p);
  return (
    <figure className="pl" style={{ '--pl-cols': cols } as CSSProperties}>
      <figcaption className="gl-visually-hidden">{label ?? s(lang, 'pl.label', { name: tx(p.name, lang), ...c })}</figcaption>
      <ol className="pl__rows">
        {phases.map((ph) => (
          <li key={ph.id} className="pl__row">
            <p className="pl__phase">{tx(ph.label, lang)}</p>
            <ol className="pl__steps">
              {ph.steps.map((st) => <Step key={st.id} st={st} n={numbers.get(st.id)} lang={lang} run={run} details={details} />)}
            </ol>
          </li>
        ))}
      </ol>
      {legend ? <Legend p={p} lang={lang} /> : null}
    </figure>
  );
}

function Step({ st, n, lang, run, details }: { st: PipelineStep; n?: number; lang: Lang; run?: Run; details: boolean }) {
  const kind = st.gate ? 'gate' : st.branches?.length ? 'parallel' : 'step';
  const stats = run?.steps?.[st.id];
  // in a run, a parallel step lists what that run actually used (its providers), not every branch the type allows
  const used = run && Array.isArray(stats?.providers) && stats.providers.length ? (stats.providers as string[]).map((x) => providerName(x, lang)) : null;
  const branches = used ?? st.branches?.map((b) => tx(b, lang));
  const line = stats ? statLine(lang, stats, { providers: !used }) : '';
  const gate = st.gate ? run?.gates?.[st.gate] : undefined;
  const cls = ['pl__step', `pl__step--${kind}`, st.loop ? 'pl__step--loop' : '', st.manual ? 'pl__step--manual' : ''].filter(Boolean).join(' ');
  return (
    <li className={cls}>
      <p className="pl__head">
        {st.gate ? <span className="pl__icon"><Glyph name="gate" size={20} /></span> : <span className="pl__num" aria-hidden>{n}</span>}
        <span className="pl__label">{st.gate ? null : <span className="gl-visually-hidden">{s(lang, 'pl.step')} {n}: </span>}{tx(st.label, lang)}</span>
        {kind === 'parallel' ? <span className="pl__kind" title={s(lang, 'pl.parallel')}><Glyph name="split" size={16} /></span> : null}
      </p>
      {details && st.detail ? <p className="pl__detail">{tx(st.detail, lang)}</p> : null}
      {branches?.length ? (
        <ul className="pl__branches" aria-label={s(lang, 'pl.parallel')}>
          {branches.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
      ) : null}
      {/* the pipeline's rounds are automatic; the editor may ask for more at the gate, so a run shows no maximum */}
      {st.loop ? <p className="pl__badge"><Glyph name="loop" size={14} />{run ? s(lang, 'pl.loopBadgeRun') : s(lang, 'pl.loopBadge', { n: st.loop.max ?? 1 })}</p> : null}
      {st.manual ? <p className="pl__badge"><Glyph name="person" size={14} />{s(lang, 'pl.manual')}</p> : null}
      {line ? <p className="pl__stats">{line}</p> : null}
      {gate?.at ? <p className="pl__stats pl__stats--gate">✓ {fmtPeriod(String(gate.at).slice(0, 10), lang, 'auto')}{gate.by ? ` · ${gate.by}` : ''}</p> : null}
    </li>
  );
}

function Legend({ p, lang }: { p: Pipeline; lang: Lang }) {
  const has = (f: (x: PipelineStep) => unknown) => p.steps.some(f);
  return (
    <ul className="pl-legend" aria-label={s(lang, 'pl.legend')}>
      <li><span className="pl-legend__key pl-legend__key--step" aria-hidden>1</span>{s(lang, 'pl.step')}</li>
      {has((x) => x.branches?.length) ? <li><span className="pl-legend__key pl-legend__key--icon" aria-hidden><Glyph name="split" size={14} /></span>{s(lang, 'pl.parallel')}</li> : null}
      {has((x) => x.gate) ? <li><span className="pl-legend__key pl-legend__key--gate" aria-hidden><Glyph name="gate" size={16} /></span>{s(lang, 'pl.gate')}</li> : null}
      {has((x) => x.loop) ? <li><span className="pl-legend__key pl-legend__key--icon" aria-hidden><Glyph name="loop" size={14} /></span>{s(lang, 'pl.loop')}</li> : null}
    </ul>
  );
}

/** A pipeline's one-line fingerprint for cards: a segment per phase, a dot per step, a diamond per editor gate. */
export function PipelineStrip({ p, lang }: { p: Pipeline; lang: Lang }) {
  const c = counts(p);
  return (
    <div className="pl-strip" role="img" aria-label={s(lang, 'pl.label', { name: tx(p.name, lang), ...c })}>
      {p.phases.map((ph) => {
        const steps = p.steps.filter((x) => x.phase === ph.id);
        if (!steps.length) return null;
        return (
          <span key={ph.id} className="pl-strip__seg" title={tx(ph.label, lang)}>
            {steps.map((st) => <i key={st.id} className={st.gate ? 'pl-strip__gate' : 'pl-strip__dot'} />)}
          </span>
        );
      })}
    </div>
  );
}

export { counts as pipelineCounts };
