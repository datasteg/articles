/** Text without its inline marks: citations dropped, glossary marks and emphasis as plain words (for decks,
 *  cards and metadata). */
export const plainText = (x: string) => x.replace(/\s*\[\[[^\]]*\]\]/g, '').replace(/\(\(([^)|]+)(?:\|([^)]*))?\)\)/g, (_m: string, id: string, text: string) => text || id).replace(/\*([^*]+)\*/g, '$1');

/** A figure's source line, headed the way statistics releases head it: "Source: ECB Data Portal" in English,
 *  "자료: ECB 데이터 포털" in Korean (the Bank of Korea's 자료:, not 출처:). Chart attributions may already carry a
 *  head ("Source: …", "출처: …", "자료: …"); it is replaced, never doubled. */
export const sourceLine = (attribution: string, lang: 'en' | 'ko') => {
  const body = attribution.replace(/^\s*(?:Sources?|출처|자료)\s*:\s*/i, '');
  return body ? `${lang === 'ko' ? '자료' : 'Source'}: ${body}` : '';
};
