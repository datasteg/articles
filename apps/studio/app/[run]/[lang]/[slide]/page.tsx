import { notFound } from 'next/navigation';
import { connection } from 'next/server';
import { Slide } from '@/components/Slide';
import { loadDeck } from '@/lib/deck';

// One slide at one build step, for `artools video slides` to screenshot at 1920×1080: /<run>/<lang>/<slide>?step=2
type Params = Promise<{ run: string; lang: string; slide: string }>;

export default async function SlidePage({ params, searchParams }: { params: Params; searchParams: Promise<{ step?: string }> }) {
  await connection();                       // read the run's files on every request
  const { run, lang, slide } = await params;
  const step = Math.max(1, Number((await searchParams).step ?? 1) || 1);
  const deck = loadDeck(run, lang);
  const s = deck?.slides.find((x) => x.id === slide);
  if (!deck || !s) notFound();
  return <Slide deck={deck} s={s} step={step} />;
}
