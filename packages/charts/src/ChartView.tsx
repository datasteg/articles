'use client';
import { useState } from 'react';
import { SegmentedControl } from '@glacier/ui';
import { t, type Lang } from '@glacier/i18n';
import { BarChart } from './BarChart';
import { ChartTable } from './ChartTable';
import { DumbbellChart } from './DumbbellChart';
import { LineChart } from './LineChart';
import { ScatterChart } from './ScatterChart';
import { tx, type ChartSpec } from './types';

/** One figure's plot with its Chart / Table toggle. Stat tiles are rendered by the page (server side). */
export function ChartView({ spec, lang }: { spec: ChartSpec; lang: Lang }) {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const caption = tx(spec.title, lang);
  if (spec.form === 'table') return <ChartTable spec={spec} lang={lang} caption={caption} />;
  const plot = spec.form === 'line' ? <LineChart spec={spec} lang={lang} />
    : spec.form === 'bars' ? <BarChart spec={spec} lang={lang} />
    : spec.form === 'dumbbell' ? <DumbbellChart spec={spec} lang={lang} />
    : spec.form === 'scatter' ? <ScatterChart spec={spec} lang={lang} />
    : null;
  return (
    <div className="ac-view" data-view={view}>
      {spec.table ? (
        <div className="ac-view__tools">
          <SegmentedControl size="sm" label={caption} value={view} onChange={(v) => setView(v as 'chart' | 'table')}
            options={[{ value: 'chart', label: t(lang, 'chart') }, { value: 'table', label: t(lang, 'table') }]} />
        </div>
      ) : null}
      {view === 'chart' ? plot : <ChartTable spec={spec} lang={lang} caption={caption} />}
    </div>
  );
}
