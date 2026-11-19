import type { Lang } from '@glacier/i18n';

/** A reader-facing text: one entry per edition ({"en", "ko"}), or a plain string used in every edition. */
export type Txt = string | ({ en: string } & Partial<Record<Lang, string>>);

/** The text for `lang`, falling back to English. */
export function tx(v: Txt | null | undefined, lang: Lang): string {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  return v[lang] ?? v.en ?? '';
}

export interface NumberFormat { decimals?: number; prefix?: string; suffix?: string }

export interface Axis {
  type?: 'time' | 'category' | 'linear';
  label?: Txt | null;
  unit?: string;
  domain?: [number, number];
  ticks?: Array<number | string>;
  /** time axes: "year" | "month"; value axes: { decimals } */
  format?: 'year' | 'month' | NumberFormat;
}

export type SeriesColor = 'focus' | 'context' | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;  // matches @glacier/ui SeriesColor

export interface LineSeriesSpec { id: string; label: Txt; values: Array<number | null>; color?: SeriesColor; endLabel?: boolean; dashed?: boolean }
export interface BandSpec { from: string; to: string; label?: Txt }
export interface AnnotationSpec { x: string; label: Txt }
export interface ReferenceLineSpec { axis: 'x' | 'y'; value: number; label?: Txt }
export interface CategorySpec { id: string; label: Txt; value: number; highlight?: boolean }
export interface DumbbellRowSpec { id: string; label: Txt; from: number; to: number; highlight?: boolean }
export interface PointSpec { id: string; label: Txt; x: number; y: number; group?: 'focus' | 'context' }
export interface TileSpec { value: Txt; label: Txt; note?: Txt | null; cite?: string[] }

export interface ChartMeta {
  sources?: string[];
  provider?: string;
  keys?: string[];
  definition?: Txt;
  calculation?: Txt;
  span?: [string, string];
  lastObservation?: string;
  retrieved?: string;
  licence?: string;
  attribution?: Txt;
}

export interface TableSpec {
  columns: Array<{ key: string; label: Txt; align?: 'left' | 'right'; decimals?: number }>;
  rows: Array<Record<string, unknown>>;
}

export type ChartForm = 'line' | 'bars' | 'dumbbell' | 'scatter' | 'stat-tiles' | 'table';

export interface ChartSpec {
  id: string;
  form: ChartForm;
  headline?: Txt;
  title?: Txt;
  subtitle?: Txt;
  howToRead?: Txt | null;
  notes?: Txt[];
  alt?: Txt;
  meta?: ChartMeta;
  table?: TableSpec | null;
  csv?: string | null;
  axes?: { x?: Axis; y?: Axis };
  // line
  x?: string[];
  series?: LineSeriesSpec[];
  bands?: BandSpec[];
  annotations?: AnnotationSpec[];
  referenceLines?: ReferenceLineSpec[];
  // bars
  categories?: CategorySpec[];
  valueFormat?: NumberFormat;
  // dumbbell
  rows?: DumbbellRowSpec[];
  fromLabel?: Txt;
  toLabel?: Txt;
  // scatter
  points?: PointSpec[];
  // stat tiles
  tiles?: TileSpec[];
}
