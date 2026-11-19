import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { ImageResponse } from 'next/og';
import { LANGS, type Lang } from '@glacier/i18n';
import { ARTICLES, editionOf, getArticle } from '@/lib/content';

/** The picture X, LinkedIn and messengers show for a shared article: its title beside its cover, in the light theme.
 *  Generated once per edition at build time (1200×630, the size both platforms crop least). */
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';
export const dynamicParams = false;
export function generateStaticParams() {
  return LANGS.flatMap((lang) => ARTICLES.map((a) => ({ lang, slug: a.slug })));
}

const nm = (...p: string[]) => join(process.cwd(), 'node_modules', ...p);
const fonts = Promise.all([
  readFile(nm('@fontsource/hanken-grotesk/files/hanken-grotesk-latin-700-normal.woff')),
  readFile(nm('@fontsource/hanken-grotesk/files/hanken-grotesk-latin-500-normal.woff')),
  readFile(nm('pretendard/dist/public/static/Pretendard-Bold.otf')),
  readFile(nm('pretendard/dist/public/static/Pretendard-Medium.otf')),
]);

/** Light-theme token values from tokens.css (its first :root block), with var() references resolved. */
const tokens = readFile(join(process.cwd(), '../../packages/tokens/tokens.css'), 'utf8').then((css) => {
  const raw: Record<string, string> = {};
  for (const m of (css.match(/:root\s*{([^}]*)}/)?.[1] ?? '').matchAll(/--([\w-]+):\s*([^;]+);/g)) raw[m[1]] = m[2].trim();
  const get = (k: string, depth = 0): string => {
    const v = raw[k] ?? '';
    const ref = v.match(/^var\(--([\w-]+)\)$/);
    return ref && depth < 8 ? get(ref[1], depth + 1) : v;
  };
  return get;
});

// Cover palette classes and the tokens they stand for (site.css § Covers).
const PALETTE: Record<string, string> = {
  frost: 'surface-frost', ice: 'surface-ice', paper: 'surface', line: 'line', deep: 'deep', strata: 'deep-strata',
  glint: 'deep-glint', glacier: 'accent', tarn: 'link', crevasse: 'deep-accent', focus: 'viz-focus',
  context: 'viz-context', ink: 'ink', ink2: 'ink-secondary', seq1: 'seq-100', seq2: 'seq-200', seq3: 'seq-300',
  seq4: 'seq-400', seq5: 'seq-500', seq6: 'seq-600', seq7: 'seq-700', warm: 'viz-2', lake: 'viz-3', ochre: 'viz-4',
};

/** cover.svg with its palette classes turned into fill and stroke colours, as a data URL. */
function coverUrl(cover: { viewBox: string; svg: string }, color: (k: string) => string): string {
  const svg = cover.svg.replace(/class="([^"]*)"/g, (_, cls: string) =>
    cls.split(/\s+/).map((c) => {
      const m = c.match(/^([fs])-(\w+)$/);
      const v = m && PALETTE[m[2]] ? color(PALETTE[m[2]]) : '';
      return v ? `${m![1] === 'f' ? 'fill' : 'stroke'}="${v}"` : '';
    }).join(' '));
  const doc = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${cover.viewBox}">${svg}</svg>`;
  return `data:image/svg+xml;base64,${Buffer.from(doc).toString('base64')}`;
}

export default async function Image({ params }: { params: Promise<{ lang: string; slug: string }> }) {
  const { lang: raw, slug } = await params;
  const a = getArticle(slug)!;
  const { ed, lang } = editionOf(a, raw as Lang);
  const [bold, medium, boldKo, mediumKo] = await fonts;
  const color = await tokens;
  const date = new Date(`${a.meta.date}T00:00:00Z`).toLocaleDateString(lang === 'ko' ? 'ko-KR' : 'en-GB',
    { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
  const family = lang === 'ko' ? 'Pretendard' : 'Hanken Grotesk, Pretendard';
  return new ImageResponse(
    (
      <div style={{ width: '100%', height: '100%', display: 'flex', background: color('surface'), fontFamily: family, color: color('ink') }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '56px 0 56px 64px' }}>
          <div style={{ fontSize: 30, fontWeight: 700, letterSpacing: '-0.01em' }}>datasteg</div>
          <div style={{ marginTop: 48, fontSize: 24, fontWeight: 500, color: color('ink-secondary') }}>{ed.kicker}</div>
          <div style={{ marginTop: 12, fontSize: lang === 'ko' ? 50 : 52, fontWeight: 700, lineHeight: 1.18,
            letterSpacing: lang === 'ko' ? '-0.02em' : '-0.015em', wordBreak: lang === 'ko' ? 'keep-all' : 'normal', display: 'flex', maxHeight: 248, overflow: 'hidden' }}>{ed.title}</div>
          <div style={{ marginTop: 'auto', display: 'flex', gap: 16, fontSize: 22, fontWeight: 500, color: color('ink-muted') }}>
            <span>articles.datasteg.com</span><span>·</span><span>{date}</span>
          </div>
        </div>
        <div style={{ width: 480, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 56px 0 40px' }}>
          {a.cover
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={coverUrl(a.cover, color)} width={384} height={256} style={{ borderRadius: 12 }} alt="" />
            : <div style={{ width: 384, height: 256, borderRadius: 12, background: color('surface-frost') }} />}
        </div>
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 8, background: color('accent') }} />
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: 'Hanken Grotesk', data: bold, weight: 700, style: 'normal' },
        { name: 'Hanken Grotesk', data: medium, weight: 500, style: 'normal' },
        { name: 'Pretendard', data: boldKo, weight: 700, style: 'normal' },
        { name: 'Pretendard', data: mediumKo, weight: 500, style: 'normal' },
      ],
    },
  );
}
