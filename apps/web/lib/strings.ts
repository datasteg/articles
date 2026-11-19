import type { Lang } from '@glacier/i18n';

// Interface strings for the articles site. Glacier's shared glossary lives in @glacier/i18n (copied from
// main/, unchanged); these are the explainer's own labels, in both editions.
const S = {
  wordmark: { en: 'datasteg', ko: 'datasteg' },
  'nav.latest': { en: 'Latest', ko: '최신 글' },
  'nav.method': { en: 'How we work', ko: '작성 원칙' },
  'nav.glossary': { en: 'Glossary', ko: '용어 풀이' },
  'nav.topics': { en: 'Topics', ko: '주제' },
  'nav.about': { en: 'About', ko: '소개' },
  'nav.privacy': { en: 'Privacy', ko: '개인정보 처리방침' },
  'nav.terms': { en: 'Terms', ko: '이용 약관' },
  'social.x': { en: 'datasteg on X', ko: 'X의 datasteg' },
  'social.linkedin': { en: 'datasteg on LinkedIn', ko: '링크드인의 datasteg' },
  'social.youtube': { en: 'datasteg on YouTube', ko: 'YouTube의 datasteg' },
  'site.description': { en: 'Explainers on economics and finance, built from central-bank research and official data.', ko: '중앙은행 연구와 공식 통계로 쓴 경제·금융 해설.' },
  'home.rail': { en: 'Search and topics', ko: '검색과 주제' },
  'search.label': { en: 'Search articles', ko: '글 검색' },
  'search.placeholder': { en: 'Search articles (coming soon)', ko: '글 검색(준비 중)' },
  'search.help': { en: 'Search by title, topic or term is on its way. For now, pick a topic below.', ko: '제목·주제·용어로 찾는 검색을 준비하고 있습니다. 지금은 아래에서 주제를 고를 수 있습니다.' },
  'search.helpShort': { en: 'Search is on its way. For now, pick a topic.', ko: '검색을 준비하고 있습니다. 지금은 주제를 골라 보세요.' },
  'feed.all': { en: 'All articles', ko: '모든 글' },
  'feed.allTopics': { en: 'All topics', ko: '모든 주제 보기' },
  'feed.topic': { en: 'Topic', ko: '주제' },
  'feed.clear': { en: 'Clear filter', ko: '필터 해제' },
  'feed.pages': { en: 'Pages', ko: '페이지' },
  'feed.page': { en: 'Page {n}', ko: '{n}쪽' },
  'feed.prev': { en: 'Previous', ko: '이전' },
  'feed.next': { en: 'Next', ko: '다음' },
  'feed.range': { en: '{from}–{to} of {n} articles', ko: '글 {n}편 중 {from}–{to}' },
  'home.empty': { en: 'No articles yet', ko: '아직 게시된 글이 없습니다' },
  'home.emptyBody': { en: 'The first article is on its way.', ko: '첫 글을 준비하고 있습니다.' },
  keyNumbers: { en: 'Key numbers', ko: '주요 수치' },
  ourQuestion: { en: 'The question we answered', ko: '이 글이 답한 질문' },
  lookedAt: { en: 'What we looked at', ko: '살펴본 내용' },
  premiseNote: { en: 'A note on the question', ko: '질문에 덧붙이는 말' },
  references: { en: 'References', ko: '참고 자료' },
  'ref.research': { en: 'Research', ko: '연구' },
  'ref.speeches': { en: 'Speeches and statements', ko: '연설과 발표' },
  'ref.data': { en: 'Data', ko: '데이터' },
  'ref.other': { en: 'Other sources', ko: '기타 자료' },
  related: { en: 'Related reading', ko: '더 읽을거리' },
  citedIn: { en: 'Cited in', ko: '인용 위치' },
  usedFor: { en: 'Used here for', ko: '이 글에서 쓴 곳' },
  readSource: { en: 'Read the source', ko: '원문 보기' },
  dataSource: { en: 'Data source', ko: '데이터 출처' },
  toc: { en: 'Contents', ko: '목차' },
  'toc.findings': { en: 'The answer in a few sentences.', ko: '몇 문장으로 본 답.' },
  'toc.question': { en: 'What we set out to answer, and why.', ko: '무엇에 답하려 했고 왜 그렇게 정했는지.' },
  'toc.insight': { en: 'Our interpretation of the evidence.', ko: '근거를 바탕으로 한 편집자의 해석입니다.' },
  'toc.terms': { en: 'Plain definitions of the terms used.', ko: '본문에 쓰인 용어의 쉬운 정의.' },
  'toc.references': { en: 'Every source, with how to find it.', ko: '모든 출처와 찾는 방법.' },
  findSeries: { en: 'Finding the series', ko: '지표 찾는 법' },
  openPdf: { en: 'PDF', ko: 'PDF' },
  allRefs: { en: 'All references', ko: '전체 참고 자료' },
  fromSource: { en: 'From the source', ko: '원문에서' },
  dataset: { en: 'Dataset', ko: '데이터셋' },
  provider: { en: 'Provider', ko: '제공 기관' },
  seriesKey: { en: 'Series', ko: '시계열' },
  unit: { en: 'Unit', ko: '단위' },
  frequency: { en: 'Frequency', ko: '주기' },
  lastObservation: { en: 'Last observation', ko: '최근 관측치' },
  retrieved: { en: 'Retrieved', ko: '조회일' },
  howToRead: { en: 'How to read this chart', ko: '이 차트 읽는 법' },
  aboutChart: { en: 'About this chart', ko: '차트 정보' },
  definition: { en: 'Definition', ko: '정의' },
  calculation: { en: 'Calculation', ko: '계산' },
  span: { en: 'Period', ko: '기간' },
  licence: { en: 'Licence', ko: '이용 조건' },
  sources: { en: 'Sources', ko: '출처' },
  dataTo: { en: 'Data to {date}', ko: '{date}까지 자료' },
  figure: { en: 'Figure {n}', ko: '그림 {n}' },
  previewTitle: { en: 'Preview: not approved by the editor', ko: '편집자 승인 전 미리보기' },
  previewBody: { en: 'This article is a draft shown for review. It is not published.', ko: '검토용 초안입니다. 아직 게시되지 않았습니다.' },
  corrections: { en: 'Corrections', ko: '정정' },
  disclaimer: { en: 'Disclaimer', ko: '유의 사항' },
  glossaryTitle: { en: 'Glossary', ko: '용어 풀이' },
  glossaryDek: { en: 'The terms our articles use, in plain words. Filter them by topic or by article.', ko: '기사에 나오는 용어를 쉬운 말로 풀었습니다. 주제나 기사별로 골라 볼 수 있습니다.' },
  'term.more': { en: 'About this term', ko: '용어 자세히' },
  'gl.topic': { en: 'Topic', ko: '주제' },
  'gl.all': { en: 'All', ko: '전체' },
  'gl.inArticle': { en: 'In article', ko: '기사' },
  'gl.allArticles': { en: 'All articles', ko: '모든 기사' },
  'gl.showing': { en: '{n} of {total} terms', ko: '용어 {total}개 중 {n}개' },
  'gl.none': { en: 'No term matches these filters.', ko: '조건에 맞는 용어가 없습니다.' },
  'gl.clear': { en: 'Clear filters', ko: '필터 해제' },
  'gl.usedIn': { en: 'Used in', ko: '쓰인 글' },
  'gl.inArticles': { en: 'In these articles', ko: '이 용어가 쓰인 글' },
  'gl.related': { en: 'Related terms', ko: '관련 용어' },
  'gl.notUsed': { en: 'No published article uses this term yet.', ko: '아직 이 용어를 쓴 글이 없습니다.' },
  termsTitle: { en: 'Terms in this article', ko: '이 글의 용어' },
  'about.title': { en: 'About these articles', ko: 'datasteg 글 소개' },
  'about.dek': { en: 'Explainers on economics and finance from central-bank research and official data, prepared with AI and approved by an editor.', ko: '중앙은행 연구와 공식 통계로 쓴 경제·금융 해설입니다. AI의 도움으로 준비하고 편집자가 승인합니다.' },
  'about.method': { en: 'How each kind of article is made, step by step.', ko: '글의 형식마다 만드는 과정을 단계별로 설명합니다.' },
  'about.glossary': { en: '{n} terms in plain words, by topic and by article.', ko: '용어 {n}개를 쉬운 말로, 주제와 기사별로.' },
  'about.corrections': { en: 'If we get something wrong, we correct it and say so at the end of the article, with the date.', ko: '잘못이 있으면 바로잡고, 글 끝에 날짜와 함께 밝힙니다.' },
  'about.advice': { en: 'General information about economics and finance. Not investment advice.', ko: '경제와 금융에 관한 일반 정보입니다. 투자 권유가 아닙니다.' },
  'about.advice.h': { en: 'Not advice', ko: '투자 권유가 아닙니다' },
  'about.privacy.h': { en: 'Privacy', ko: '개인정보' },
  'about.privacy': { en: 'We count page views and downloads on our own server, without cookies and without storing anything that identifies you. The counts are never shared.', ko: '페이지 조회와 다운로드 수는 자체 서버에서 집계합니다. 쿠키를 쓰지 않고, 개인을 알아볼 수 있는 정보는 저장하지 않습니다. 이 수치는 누구와도 공유하지 않습니다.' },
  'method.dek': { en: 'Every article answers a question with published research and official data. AI prepares each step; an editor approves.', ko: '모든 글은 공개된 연구와 공식 통계로 질문에 답합니다. 단계마다 AI가 준비하고 편집자가 승인합니다.' },
  'method.principles': { en: 'Principles', ko: '원칙' },
  'method.formats': { en: 'Formats', ko: '글의 형식' },
  'method.formatsDek': { en: 'Each format has its own pipeline.', ko: '형식마다 만드는 과정이 다릅니다.' },
  'method.titleType': { en: 'How {name} are made', ko: '{name}: 만드는 과정' },
  'format.kicker': { en: 'Format', ko: '형식' },
  'format.sample': { en: 'In development', ko: '개발 중' },
  'format.sampleNote': { en: 'This format is in development. Its pipeline is a sample, and no article uses it yet.', ko: '개발 중인 형식입니다. 만드는 과정은 시안이며, 아직 이 형식으로 쓴 글은 없습니다.' },
  'format.how': { en: 'How {name} are made', ko: '{name}: 만드는 과정' },
  'format.see': { en: 'All {name}', ko: '{name} 전체 보기' },
  'format.empty': { en: 'No {name} yet', ko: '아직 게시된 글이 없습니다' },
  'format.emptyBody': { en: 'The first one is on its way.', ko: '첫 글을 준비하고 있습니다.' },
  'format.count': { en: '{n} steps · {g} editor approvals', ko: '{n}단계 · 편집자 승인 {g}회' },
  'shape.length': { en: 'Length', ko: '분량' },
  'shape.figures': { en: 'Figures', ko: '그림' },
  'shape.gates': { en: 'Editor approvals', ko: '편집자 승인' },
  'shape.steps': { en: 'Steps', ko: '단계' },
  'pl.legend': { en: 'Key', ko: '범례' },
  'pl.step': { en: 'Step', ko: '단계' },
  'pl.parallel': { en: 'Runs in parallel', ko: '동시 진행' },
  'pl.gate': { en: 'Editor approval', ko: '편집자 승인' },
  'pl.loop': { en: 'Review loop', ko: '검토 반복' },
  'pl.loopBadge': { en: 'Fixes go back · {n} automatic rounds, then the editor', ko: '수정은 해당 단계로 · 자동 {n}회, 이후 편집자 판단' },
  'pl.loopBadgeRun': { en: 'Fixes went back to the stage that made them', ko: '수정은 해당 단계로' },
  'pl.manual': { en: 'Run by the editor', ko: '편집자가 실행' },
  'pl.label': { en: '{name}: {steps} steps in {phases} phases, with {gates} editor approvals', ko: '{name}: {phases}개 과정, {steps}단계, 편집자 승인 {gates}회' },
  'topics.dek': { en: 'Articles by subject and by region. Pick a topic to see its articles.', ko: '주제와 지역별로 모은 글입니다. 주제를 고르면 해당 주제의 글만 표시합니다.' },
  'cite.title': { en: 'Cite this article', ko: '이 글 인용하기' },
  'cite.ask': { en: 'If you use this article in research, a report or the news, please cite it as follows.', ko: '이 글을 연구, 보고서, 기사에 참고하셨다면 아래와 같이 출처를 밝혀 주세요.' },
  'cite.button': { en: 'Cite', ko: '인용' },
  'cite.copy': { en: 'Copy', ko: '복사' },
  'cite.copied': { en: 'Copied', ko: '복사했습니다' },
  'cite.bibtex': { en: 'BibTeX', ko: 'BibTeX' },
  'cite.copyBibtex': { en: 'Copy BibTeX', ko: 'BibTeX 복사' },
  'toc.cite': { en: 'How to cite this article.', ko: '이 글을 인용하는 방법.' },
  'pdf.download': { en: 'Download PDF', ko: 'PDF 다운로드' },
  'pdf.button': { en: 'PDF', ko: 'PDF' },
  'pdf.size': { en: '{pages} pages, {size}', ko: '{pages}쪽, {size}' },
  'pdf.title': { en: 'PDF edition', ko: 'PDF판' },
  'pdf.ask': { en: 'A print layout of this article, with every figure, the references and this citation.', ko: '그림, 참고 자료, 인용 정보를 모두 담은 인쇄용 지면입니다.' },
  'pdf.en': { en: 'English', ko: '영문' },
  'pdf.ko': { en: 'Korean', ko: '국문' },
  'print.info': { en: 'Article information', ko: '글 정보' },
  'print.type': { en: 'Type', ko: '형식' },
  'print.published': { en: 'Published', ko: '게시' },
  'print.updated': { en: 'Updated', ko: '수정' },
  'print.topics': { en: 'Topics', ko: '주제' },
  'print.online': { en: 'Online version', ko: '온라인판' },
  'print.other': { en: 'Korean edition', ko: '영문판' },
  'print.data': { en: 'Data', ko: '데이터' },
  'print.dataText': { en: 'The data behind each chart can be downloaded as CSV from the online version.', ko: '차트마다 그 자료를 온라인판에서 CSV로 내려받을 수 있습니다.' },
  'print.made': { en: 'This PDF was made from the online version on {date}. The online version has interactive charts, the data behind them and any later corrections.', ko: '이 PDF는 {date}에 온라인판에서 만들었습니다. 대화형 차트와 그 자료, 이후의 정정은 온라인판에서 볼 수 있습니다.' },
  close: { en: 'Close', ko: '닫기' },
  source: { en: 'Source', ko: '출처' },          // a citation's popover label ("출처 3"); figure source lines use lib/text sourceLine → "자료:"
  question: { en: 'The question', ko: '질문' },
  findingsTitle: { en: 'Key findings', ko: '핵심 결과' },
} as const;

export type StringKey = keyof typeof S;

/** A file's size for a download link: "1.2 MB", "1.2MB". */
export const fileSize = (bytes: number, lang: Lang) => `${(bytes / 1e6).toLocaleString(lang === 'ko' ? 'ko-KR' : 'en-GB', { maximumFractionDigits: 1, minimumFractionDigits: 1 })}${lang === 'ko' ? 'MB' : ' MB'}`;

/** Run counts under a pipeline step (contracts/content.md, meta.run.steps): singular and plural per language. */
const STATS: Record<string, { en: [string, string]; ko: string }> = {
  premises: { en: ['{n} premise tested', '{n} premises tested'], ko: '전제 {n}개 검토' },
  docs: { en: ['{n} document', '{n} documents'], ko: '문헌 {n}건' },
  quotes: { en: ['{n} quote checked', '{n} quotes checked'], ko: '인용 {n}건 대조' },
  series: { en: ['{n} series', '{n} series'], ko: '시계열 {n}개' },
  mechanisms: { en: ['{n} mechanism', '{n} mechanisms'], ko: '메커니즘 {n}개' },
  facts: { en: ['{n} number computed', '{n} numbers computed'], ko: '수치 {n}개 계산' },
  sections: { en: ['{n} section', '{n} sections'], ko: '{n}개 절' },
  figures: { en: ['{n} figure', '{n} figures'], ko: '그림 {n}개' },
  words: { en: ['{n} word', '{n} words'], ko: '{n}단어' },
  charts: { en: ['{n} chart', '{n} charts'], ko: '차트 {n}개' },
  rounds: { en: ['{n} round', '{n} rounds'], ko: '{n}차례' },
  papers: { en: ['{n} paper', '{n} papers'], ko: '논문 {n}편' },
  speeches: { en: ['{n} speech', '{n} speeches'], ko: '연설 {n}건' },
  themes: { en: ['{n} theme', '{n} themes'], ko: '주제 {n}개' },
  ideas: { en: ['{n} idea weighed', '{n} ideas weighed'], ko: '아이디어 {n}개 검토' },
  pages: { en: ['{n} page', '{n} pages'], ko: '{n}쪽' },
};

const COUNTS: Record<string, { en: [string, string]; ko: string }> = {
  articles: { en: ['{n} article', '{n} articles'], ko: '글 {n}편' },
  terms: { en: ['{n} term', '{n} terms'], ko: '용어 {n}개' },
};

/** count()'s singular and plural forms ("{n} article", "{n} articles"), for client components that count on their own. */
export const countForms = (lang: Lang, key: 'articles' | 'terms'): [string, string] => (lang === 'ko' ? [COUNTS[key].ko, COUNTS[key].ko] : COUNTS[key].en);

/** "1 article", "10 terms", "글 1편". */
export function count(lang: Lang, key: 'articles' | 'terms', n: number): string {
  const f = COUNTS[key];
  return (lang === 'ko' ? f.ko : f.en[n === 1 ? 0 : 1]).replace('{n}', n.toLocaleString(lang === 'ko' ? 'ko-KR' : 'en-GB'));
}

/** The cover plate's labels, beside or under their numbers: "11 indicators", "지표 11". */
const PLATE: Record<string, { en: [string, string]; ko: string }> = {
  indicators: { en: ['indicator', 'indicators'], ko: '지표' },
  papers: { en: ['paper', 'papers'], ko: '논문' },
  charts: { en: ['chart', 'charts'], ko: '차트' },
};
export const plateLabel = (lang: Lang, key: 'indicators' | 'papers' | 'charts', n: number) =>
  lang === 'ko' ? PLATE[key].ko : PLATE[key].en[n === 1 ? 0 : 1];

/** "14 documents · 31 quotes checked · ECB, Eurostat": the known keys in the order above, then `providers`;
 *  unknown keys are ignored. A per-language value ({en: 1650, ko: 5200}) shows the page's language. */
const PROVIDERS_KO: Record<string, string> = { 'Bank of Korea': '한국은행' };
/** A data provider's name as meta.run.steps lists it (English), in the page's language. */
export const providerName = (x: string, lang: Lang) => (lang === 'ko' ? PROVIDERS_KO[x] ?? x : x);

export function statLine(lang: Lang, stats: Record<string, unknown>, opts: { providers?: boolean } = {}): string {
  const parts: string[] = [];
  for (const [key, f] of Object.entries(STATS)) {
    const raw = stats[key];
    const n = typeof raw === 'number' ? raw : raw && typeof raw === 'object' && !Array.isArray(raw) ? (raw as Record<string, number>)[lang] : undefined;
    if (typeof n !== 'number') continue;
    const num = n.toLocaleString(lang === 'ko' ? 'ko-KR' : 'en-GB');
    parts.push((lang === 'ko' ? f.ko : f.en[n === 1 ? 0 : 1]).replace('{n}', num));
  }
  if (opts.providers !== false && Array.isArray(stats.providers) && stats.providers.length) parts.push(stats.providers.map((x) => providerName(String(x), lang)).join(', '));
  return parts.join(' · ');
}

export function s(lang: Lang, key: StringKey, vars?: Record<string, string | number>): string {
  const v: string = S[key][lang] ?? S[key].en;
  return vars ? v.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? '')) : v;
}
