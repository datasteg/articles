import { notFound } from 'next/navigation';
import { connection } from 'next/server';
import { Slide } from '@/components/Slide';
import { loadDeck } from '@/lib/deck';

// The contact sheet: every slide at every build step, a quarter size, in order. `make-slides` reads this first.
export default async function Sheet({ params }: { params: Promise<{ run: string; lang: string }> }) {
  await connection();                       // read the run's files on every request
  const { run, lang } = await params;
  const deck = loadDeck(run, lang);
  if (!deck) notFound();
  return (
    <main className="vs-sheet">
      {deck.slides.flatMap((s) => Array.from({ length: s.steps }, (_, i) => (
        <figure key={`${s.id}-${i + 1}`}>
          <div className="vs-thumb"><Slide deck={deck} s={s} step={i + 1} /></div>
          <figcaption>{s.id}{s.steps > 1 ? `·${i + 1}` : ''} {s.template} · {s.part}</figcaption>
        </figure>
      )))}
    </main>
  );
}
