import type { ReactNode } from 'react';
import { minus, type Lang } from '@glacier/i18n';
import { tx, type ChartSpec, type TileSpec } from './types';

/** A row of headline numbers (Glacier StatTile anatomy). Server-rendered; `renderCite` lets the page attach
 *  its own source popovers to each tile. */
export function StatTiles({ tiles, lang, renderCite, className }: {
  tiles: TileSpec[]; lang: Lang; renderCite?: (ids: string[]) => ReactNode; className?: string;
}) {
  return (
    <ul className={'ac-tiles' + (className ? ' ' + className : '')} data-count={tiles.length}>
      {tiles.map((t, i) => (
        <li key={i} className="gl-stat ac-tile">
          <p className="gl-stat__value">{minus(tx(t.value, lang))}{t.cite?.length && renderCite ? renderCite(t.cite) : null}</p>
          <p className="gl-stat__label">{tx(t.label, lang)}</p>
          {t.note ? <p className="gl-stat__source">{tx(t.note, lang)}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export function tilesOf(spec: ChartSpec): TileSpec[] {
  return spec.tiles ?? [];
}
