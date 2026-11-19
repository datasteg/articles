import type { Metadata } from 'next';
import type { Lang } from '@glacier/i18n';
import { Tag } from '@glacier/ui';
import { tx } from '@articles/charts';
import { Glyph, type GlyphName } from '@/components/Glyph';
import { PipelineStrip, pipelineCounts } from '@/components/PipelineDiagram';
import { PIPELINES } from '@/lib/content';
import { langOf } from '@/lib/page';
import { s } from '@/lib/strings';

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const lang = await langOf(params);
  return { title: s(lang, 'nav.method') };
}

// How we work: six principles every format shares (one line each), then the formats, each with its pipeline.
// The steps themselves are drawn on /method/<type> from config/pipelines/<type>.yaml, not written out here.
const PRINCIPLES: Record<Lang, Array<{ icon: GlyphName; h: string; p: string }>> = {
  en: [
    { icon: 'question', h: 'The question is tested first', p: 'We check what a question takes for granted before researching it, and say so if a premise is wrong.' },
    { icon: 'institution', h: 'Official sources', p: 'Research from central banks and international institutions; numbers from official statistics.' },
    { icon: 'calculator', h: 'Numbers are computed, never typed', p: 'Every number comes from the data by script, so both editions always match.' },
    { icon: 'quote', h: 'Quotes checked word for word', p: 'Each quote is matched against the stored text of its source before it is used.' },
    { icon: 'approve', h: 'An editor approves', p: 'AI prepares each step; an editor approves at every gate, and is named on the article.' },
    { icon: 'correct', h: 'Corrections, and no advice', p: 'Errors are corrected openly, with the date. Nothing here is investment advice.' },
  ],
  ko: [
    { icon: 'question', h: '질문부터 검토합니다', p: '조사에 앞서 질문의 전제를 확인하고, 틀린 전제는 글에서 밝힙니다.' },
    { icon: 'institution', h: '공식 자료만 씁니다', p: '연구는 중앙은행과 국제기구에서, 수치는 공식 통계에서 가져옵니다.' },
    { icon: 'calculator', h: '수치는 계산하고 손으로 쓰지 않습니다', p: '모든 수치는 스크립트로 자료에서 계산하므로 두 언어판이 항상 일치합니다.' },
    { icon: 'quote', h: '인용은 원문과 대조합니다', p: '모든 인용문은 쓰기 전에 저장된 원문과 한 글자씩 대조합니다.' },
    { icon: 'approve', h: '편집자가 승인합니다', p: '각 단계는 AI가 준비하고, 단계마다 편집자가 승인하며 글에 이름을 밝힙니다.' },
    { icon: 'correct', h: '정정은 공개하고, 투자 권유는 하지 않습니다', p: '잘못은 날짜와 함께 바로잡습니다. 이 사이트의 내용은 투자 권유가 아닙니다.' },
  ],
};

export default async function Method({ params }: { params: Promise<{ lang: string }> }) {
  const lang = await langOf(params);
  return (
    <>
      <header className="page-head">
        <p className="gl-kicker"><a className="page-head__up" href={`/${lang}/about`}>{s(lang, 'nav.about')}</a></p>
        <h1>{s(lang, 'nav.method')}</h1>
        <p className="dek">{s(lang, 'method.dek')}</p>
      </header>
      <section className="wide-block" aria-labelledby="pr-h">
        <h2 id="pr-h" className="gl-visually-hidden">{s(lang, 'method.principles')}</h2>
        <ul className="principles">
          {PRINCIPLES[lang].map((x) => (
            <li key={x.h} className="principle">
              <span className="principle__icon"><Glyph name={x.icon} size={22} /></span>
              <h3 className="principle__h">{x.h}</h3>
              <p className="principle__p">{x.p}</p>
            </li>
          ))}
        </ul>
      </section>
      <section className="wide-block" aria-labelledby="fm-h">
        <h2 id="fm-h" className="block-h">{s(lang, 'method.formats')}</h2>
        <p className="block-dek">{s(lang, 'method.formatsDek')}</p>
        <ul className="formats">
          {PIPELINES.map((p) => {
            const c = pipelineCounts(p);
            return (
              <li key={p.id} className="format-card" data-status={p.status}>
                <div className="format-card__head">
                  <h3 className="format-card__name"><a href={`/${lang}/method/${p.id}`}>{tx(p.name, lang)}</a></h3>
                  {p.status !== 'live' ? <Tag kind="jel">{s(lang, 'format.sample')}</Tag> : null}
                </div>
                <p className="format-card__tagline">{tx(p.tagline, lang)}</p>
                <PipelineStrip p={p} lang={lang} />
                <p className="format-card__meta">
                  {[p.shape?.words ? tx(p.shape.words, lang) : null, s(lang, 'format.count', { n: c.steps, g: c.gates })].filter(Boolean).join(' · ')}
                </p>
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}
