'use client';
import { DataTable, type DataColumn } from '@glacier/ui';
import { formatNumber, type Lang } from '@glacier/i18n';
import { tx, type ChartSpec, type Txt } from './types';

const isTxt = (v: unknown): v is Txt => typeof v === 'object' && v !== null && 'en' in (v as Record<string, unknown>);

/** The same data as the chart, as a table (Glacier: every chart has a table view). */
export function ChartTable({ spec, lang, caption }: { spec: ChartSpec; lang: Lang; caption: string }) {
  const t = spec.table;
  if (!t) return null;
  const columns: DataColumn<Record<string, unknown>>[] = t.columns.map((c) => ({
    key: c.key,
    label: tx(c.label, lang),
    align: c.align,
    render: (v: unknown) => (v == null ? '–' : typeof v === 'number' ? formatNumber(v, { lang, decimals: c.decimals ?? (Number.isInteger(v) ? 0 : 1) }) : isTxt(v) ? tx(v, lang) : String(v)),
  }));
  const rows = t.rows.map((r, i) => ({ id: i, ...r }));
  return <div className="ac-table"><DataTable lang={lang} caption={caption} columns={columns} rows={rows} dense /></div>;
}
