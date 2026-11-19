import type { Metadata } from 'next';
import type { Lang } from '@glacier/i18n';
import { Policy, type PolicyDoc } from '@/components/Policy';
import { langOf } from '@/lib/page';

// The terms of use, for the site and the datasteg YouTube channel. Also linked on the datasteg-video OAuth app's
// consent screen.

const DOC: Record<Lang, PolicyDoc> = {
  en: {
    title: 'Terms of use',
    dek: 'How you may read, cite and reuse datasteg articles and videos, and what we do and don’t promise.',
    updated: 'Last updated 26 October 2026',
    sections: [
      { id: 'what', h: 'What datasteg is', body: [
        'datasteg publishes explainers on economics and finance, built from central-bank research and official statistics. Each is prepared with AI and approved by an editor before it is published. Some articles are also published as narrated videos on the datasteg YouTube channel; their narrator is a synthetic voice, and each video says so.',
      ] },
      { id: 'advice', h: 'Not advice', body: [
        'Everything here is general information about the economy and financial markets. It is not investment, legal, tax or any other professional advice, and it does not take your circumstances into account. Decisions you make with it are your own.',
      ] },
      { id: 'accuracy', h: 'Accuracy and corrections', body: [
        'Every number comes from a named source and every quote is checked against its original, but mistakes can still happen. When we find one, we correct the article openly and record the date. The content is provided as it is, without any warranty that it is complete, current or free of error.',
      ] },
      { id: 'reuse', h: 'Citing and reusing', body: [
        'You are welcome to link to any article or video, and to quote short passages with a link back and the attribution in the article’s “Cite this article” block.',
        'Republishing an article, a chart or a video in full, or using them commercially, needs our permission: write to datasteg@gmail.com.',
        'The data behind each chart belongs to the source named under it, and that source’s own terms apply to the data.',
        'The API at api.datasteg.com and the MCP server at mcp.datasteg.com return the same articles and data for reading and citing, and these terms apply to them as they do to the site. Every answer links these terms and carries the article’s citation: quoting short passages with that attribution is welcome, while republishing an article in full, or using the answers commercially, needs our permission.',
      ] },
      { id: 'links', h: 'Links and other services', body: [
        'Articles link to papers, statistics and other websites that we don’t control. YouTube’s own [terms of service](https://www.youtube.com/t/terms) apply when you watch our videos there.',
      ] },
      { id: 'liability', h: 'Liability', body: [
        'To the extent the law allows, datasteg is not liable for any loss that arises from using the site, the videos or the information in them.',
      ] },
      { id: 'changes', h: 'Changes', body: [
        'If these terms change, the new version is posted here with its date. Questions: datasteg@gmail.com.',
      ] },
    ],
  },
  ko: {
    title: '이용 약관',
    dek: 'datasteg 기사와 영상을 읽고, 인용하고, 다시 쓰는 방법과 함께 datasteg가 약속하는 것과 약속하지 않는 것을 밝힙니다.',
    updated: '2026년 10월 26일 개정',
    sections: [
      { id: 'what', h: 'datasteg가 하는 일', body: [
        'datasteg는 중앙은행 연구와 공식 통계를 바탕으로 경제·금융 해설을 냅니다. 모든 글은 AI의 도움으로 준비하고, 편집자가 승인한 뒤 게시합니다. 일부 기사는 datasteg YouTube 채널에 내레이션 영상으로도 냅니다. 영상의 목소리는 합성 음성이며, 영상마다 이를 밝힙니다.',
      ] },
      { id: 'advice', h: '조언이 아닙니다', body: [
        '여기 실린 모든 내용은 경제와 금융시장에 관한 일반 정보입니다. 투자, 법률, 세무 등 어떤 전문 조언도 아니며 개인의 사정을 고려하지 않습니다. 이를 바탕으로 한 결정의 책임은 각자에게 있습니다.',
      ] },
      { id: 'accuracy', h: '정확성과 정정', body: [
        '모든 수치는 출처를 밝히고 모든 인용은 원문과 대조하지만, 잘못은 생길 수 있습니다. 잘못을 찾으면 기사에서 공개적으로 바로잡고 날짜를 남깁니다. 내용은 있는 그대로 제공하며, 완전하거나 최신이거나 오류가 없다고 보증하지 않습니다.',
      ] },
      { id: 'reuse', h: '인용과 재사용', body: [
        '기사와 영상에는 자유롭게 링크를 걸 수 있습니다. 짧은 대목은 원문 링크와 기사의 ‘이 글 인용하기’에 있는 출처 표기를 붙여 인용할 수 있습니다.',
        '기사, 차트, 영상을 통째로 다시 싣거나 상업적으로 쓰려면 허락을 받아야 합니다. datasteg@gmail.com으로 연락하면 됩니다.',
        '각 차트의 데이터는 차트 아래 밝힌 출처의 것이며, 데이터에는 그 출처의 이용 조건이 적용됩니다.',
        'api.datasteg.com의 API와 mcp.datasteg.com의 MCP 서버는 읽고 인용할 수 있도록 사이트와 동일한 기사와 데이터를 제공합니다. 이 약관은 이 서비스에도 사이트와 동일하게 적용됩니다. 모든 응답에는 이 약관 링크와 기사의 인용 정보가 포함됩니다. 이 인용 정보와 함께 짧은 부분을 인용하는 것은 허용합니다. 기사를 전체적으로 재게시하거나 응답을 상업적으로 사용하려면 허가를 받아야 합니다.',
      ] },
      { id: 'links', h: '링크와 다른 서비스', body: [
        '기사는 datasteg가 관리하지 않는 논문, 통계, 웹사이트로 연결됩니다. YouTube에서 영상을 볼 때는 YouTube의 [서비스 약관](https://www.youtube.com/t/terms)이 적용됩니다.',
      ] },
      { id: 'liability', h: '책임의 한계', body: [
        '법이 허용하는 범위에서 datasteg는 사이트와 영상, 그 안의 정보를 이용해 생긴 손실에 책임지지 않습니다.',
      ] },
      { id: 'changes', h: '약관 변경', body: [
        '약관이 바뀌면 새 약관을 날짜와 함께 이 페이지에 싣습니다. 문의는 datasteg@gmail.com으로 보내면 됩니다.',
      ] },
    ],
  },
};

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const lang = await langOf(params);
  return { title: DOC[lang].title, description: DOC[lang].dek };
}

export default async function Terms({ params }: { params: Promise<{ lang: string }> }) {
  const lang = await langOf(params);
  return <Policy lang={lang} doc={DOC[lang]} />;
}
