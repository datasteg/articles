/** Line icons for the method pages and pipeline diagrams, in the Glacier icon style (24px grid, 1.5px stroke). */
const PATHS = {
  gate: ['M12 2.5 21.5 12 12 21.5 2.5 12z', 'M8.6 12.1l2.3 2.3 4.6-4.6'],
  loop: ['M3.5 12a8.5 8.5 0 1 0 2.6-6.1', 'M3.5 4v4.6h4.6'],
  person: ['M12 11.5a3.75 3.75 0 1 0 0-7.5 3.75 3.75 0 0 0 0 7.5z', 'M4.5 20.5a7.5 7.5 0 0 1 15 0'],
  split: ['M3.5 12h5.5', 'M9 12l6-6h5.5', 'M9 12l6 6h5.5'],
  question: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M9.3 9.2a2.8 2.8 0 0 1 5.4 1c0 1.9-2.7 2.5-2.7 2.5', 'M12 16.6v.1'],
  institution: ['M3 20.5h18', 'M5.5 20.5v-9', 'M10 20.5v-9', 'M14 20.5v-9', 'M18.5 20.5v-9', 'M2.5 10 12 4l9.5 6z'],
  calculator: ['M5.5 3h13v18h-13z', 'M8.5 6.5h7v3h-7z', 'M8.5 13h.01', 'M12 13h.01', 'M15.5 13h.01', 'M8.5 17h.01', 'M12 17h.01', 'M15.5 17h.01'],
  quote: ['M5 7h5v5c0 3-1.6 5-4.5 6', 'M14 7h5v5c0 3-1.6 5-4.5 6'],
  approve: ['M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M2.5 21a6.5 6.5 0 0 1 13 0', 'M15.5 11.5l2.2 2.2 4.3-4.3'],
  correct: ['M4 20h4L19.5 8.5l-4-4L4 16z', 'M13.5 6.5l4 4'],
  book: ['M4 4.5h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4z', 'M20 4.5h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z'],
  steps: ['M3.5 4.5h6v6h-6z', 'M14.5 13.5h6v6h-6z', 'M9.5 7.5h3a2.5 2.5 0 0 1 2.5 2.5v3.5'],
  arrow: ['M5 12h14', 'M13 6l6 6-6 6'],
} as const;
export type GlyphName = keyof typeof PATHS;

export function Glyph({ name, size = 20, className }: { name: GlyphName; size?: number; className?: string }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden focusable="false">
      {PATHS[name].map((d, i) => <path key={i} d={d} />)}
    </svg>
  );
}
