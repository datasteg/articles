import { isLang, type Lang } from '@glacier/i18n';
import { notFound } from 'next/navigation';

/** The page's language from its route params (the layout has already checked it). */
export async function langOf(params: Promise<{ lang: string }>): Promise<Lang> {
  const { lang } = await params;
  if (!isLang(lang)) notFound();
  return lang;
}
