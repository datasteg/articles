import type { Metadata } from 'next';
import type { Lang } from '@glacier/i18n';
import { Policy, type PolicyDoc } from '@/components/Policy';
import { langOf } from '@/lib/page';

// The privacy policy. It is also the policy the datasteg-video OAuth app links on Google's consent screen, so
// the YouTube section must stay true to pipeline/artools/video/youtube.py and
// config/video/publish.yaml.

const DOC: Record<Lang, PolicyDoc> = {
  en: {
    title: 'Privacy',
    dek: 'What we record when you read datasteg, and what our YouTube publishing tool can reach. In short: no cookies, no accounts, no advertising, nothing sold.',
    updated: 'Last updated 26 October 2026',
    sections: [
      { id: 'who', h: 'Who we are', body: [
        'datasteg publishes the explainers on articles.datasteg.com and the videos on the datasteg YouTube channel. Write to datasteg@gmail.com with any question about this policy.',
      ] },
      { id: 'reading', h: 'Reading the site', body: [
        'You can read every article without an account. The site sets no cookies, shows no advertising and loads no third-party trackers: its fonts, scripts and charts come from our own server.',
      ] },
      { id: 'counts', h: 'Visitor counts', body: [
        'We count page views and PDF downloads with GoatCounter, which runs on our own server (stats.datasteg.com). For each view it records:',
        ['the page, and the time;', 'the site you came from, if your browser says so;', 'the type of browser and operating system, the screen size and the language;', 'the country, worked out from your IP address.'],
        'GoatCounter does not store your IP address and uses no cookies. To avoid counting one visit twice it keeps a temporary, salted hash that is regularly discarded and cannot be traced back to you. Only the editor sees the counts, and they are never shared or sold.',
      ] },
      { id: 'logs', h: 'Server logs', body: [
        'The server that hosts the site writes a log of each request: the IP address it came from, the time, the page asked for and the response. Request headers, such as your browser’s details or cookies, are left out.',
        'The log is used to keep the site running and to block abuse. It is kept for 14 days and then deleted, it is not part of our backups, and it is not shared.',
        'The API at api.datasteg.com and the MCP server at mcp.datasteg.com also log each call, to count use and apply limits. The log stores no IP addresses: a hash with a salt that changes every day counts distinct callers, and a country code is worked out from the IP address at the time of the call. Search text is kept only as its length and a hash. The rows are kept for 14 days and are not part of our backups; hourly totals are kept for 13 months.',
      ] },
      { id: 'email', h: 'If you write to us', body: [
        'We use your message and address only to reply, and keep them no longer than the conversation needs.',
      ] },
      { id: 'youtube-tool', h: 'Our YouTube publishing tool (datasteg-video)', body: [
        'datasteg turns some articles into narrated videos and publishes them on its own YouTube channel. A tool on our editor’s computer, registered with Google as “datasteg-video”, does the uploading through the YouTube Data API. It is used only by datasteg, for the datasteg channel.',
        'With the editor’s permission, Google gives the tool two kinds of access to that channel:',
        ['to upload videos (youtube.upload);', 'to manage those videos’ details, captions, thumbnails and playlists (youtube.force-ssl).'],
        'The tool reads nothing from any viewer’s or any other person’s Google account. The access token stays on our computer; it is never shared, sold, used for advertising or used to train AI models. Our use of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.',
        'Access can be withdrawn at any time in the Google account’s [third-party connections](https://myaccount.google.com/connections).',
      ] },
      { id: 'youtube', h: 'Watching on YouTube', body: [
        'When you watch our videos on YouTube, Google’s [privacy policy](https://policies.google.com/privacy) applies. We see only the totals YouTube shows every channel owner, such as views and watch time, never who watched.',
      ] },
      { id: 'children', h: 'Children', body: [
        'The site and the videos are written for adults and are not directed at children.',
      ] },
      { id: 'changes', h: 'Changes', body: [
        'If this policy changes, the new version is posted here with its date.',
      ] },
    ],
  },
  ko: {
    title: '개인정보 처리방침',
    dek: 'datasteg를 읽을 때 무엇을 기록하는지, 그리고 YouTube 게시 도구가 어디까지 접근하는지 밝힙니다. 요약하면 쿠키, 회원 가입, 광고가 없고 아무것도 팔지 않습니다.',
    updated: '2026년 10월 26일 개정',
    sections: [
      { id: 'who', h: '운영자', body: [
        'datasteg는 articles.datasteg.com에 해설 기사를, datasteg YouTube 채널에 영상을 냅니다. 이 방침에 관한 문의는 datasteg@gmail.com으로 보내 주십시오.',
      ] },
      { id: 'reading', h: '사이트를 읽을 때', body: [
        '모든 기사는 회원 가입 없이 읽을 수 있습니다. 사이트는 쿠키를 쓰지 않고, 광고를 싣지 않으며, 외부 추적 도구를 불러오지 않습니다. 글꼴과 스크립트, 차트는 모두 자체 서버에서 보냅니다.',
      ] },
      { id: 'counts', h: '방문자 수 집계', body: [
        '페이지 조회와 PDF 내려받기 수는 자체 서버에서 운영하는 GoatCounter(stats.datasteg.com)로 집계합니다. 조회 한 번마다 다음을 기록합니다.',
        ['본 페이지와 시각', '브라우저가 알려 주는 경우, 들어온 사이트', '브라우저와 운영체제 종류, 화면 크기, 언어', 'IP 주소로 판단한 국가'],
        'GoatCounter는 IP 주소를 저장하지 않고 쿠키도 쓰지 않습니다. 같은 방문을 중복 집계하지 않으려고 임시 해시값을 쓰며, 이 값은 주기적으로 삭제되고 개인을 알아내는 데 쓸 수 없습니다. 집계 결과는 편집자만 보고, 누구와도 공유하거나 팔지 않습니다.',
      ] },
      { id: 'logs', h: '서버 기록', body: [
        '사이트를 운영하는 서버는 요청마다 기록을 남깁니다. 기록하는 항목은 요청한 IP 주소, 시각, 요청한 페이지, 응답 결과입니다. 브라우저 정보나 쿠키 같은 요청 헤더는 기록하지 않습니다.',
        '이 기록은 사이트 운영과 악성 접근 차단에만 씁니다. 14일 동안 보관한 뒤 삭제하며, 백업에 포함하지 않고 공유하지 않습니다.',
        'api.datasteg.com의 API와 mcp.datasteg.com의 MCP 서버도 각 호출을 기록합니다. 기록은 사용량을 집계하고 한도를 적용하는 데 씁니다. 기록에는 IP 주소를 저장하지 않습니다. 매일 바뀌는 솔트를 포함한 해시로 호출자를 구분하고, 호출 시점에 IP 주소에서 국가 코드를 산출해 저장합니다. 검색어는 길이와 해시만 저장합니다. 기록 행은 14일간 보관하며 백업에 포함하지 않습니다. 시간별 합계는 13개월간 보관합니다.',
      ] },
      { id: 'email', h: '이메일로 연락할 때', body: [
        '보낸 메시지와 주소는 답장에만 쓰고, 대화에 필요한 기간이 지나면 보관하지 않습니다.',
      ] },
      { id: 'youtube-tool', h: 'YouTube 게시 도구(datasteg-video)', body: [
        'datasteg는 일부 기사를 내레이션 영상으로 만들어 자체 YouTube 채널에 올립니다. 업로드는 편집자의 컴퓨터에 있는 도구가 YouTube Data API로 합니다. 이 도구는 Google에 ‘datasteg-video’라는 이름으로 등록돼 있으며, datasteg가 datasteg 채널에만 씁니다.',
        '편집자가 허락하면 Google은 이 도구에 그 채널에 대한 두 가지 권한을 줍니다.',
        ['영상 올리기(youtube.upload)', '올린 영상의 정보, 자막, 썸네일, 재생목록 관리(youtube.force-ssl)'],
        '이 도구는 시청자나 다른 누구의 Google 계정 정보도 읽지 않습니다. 접근 토큰은 편집자의 컴퓨터에만 두며, 공유하거나 팔지 않고, 광고나 AI 학습에 쓰지 않습니다. Google API에서 받은 정보의 사용은 제한적 사용 요건을 포함한 [Google API 서비스 사용자 데이터 정책](https://developers.google.com/terms/api-services-user-data-policy)을 따릅니다.',
        '권한은 Google 계정의 [서드 파티 연결](https://myaccount.google.com/connections)에서 언제든 거둘 수 있습니다.',
      ] },
      { id: 'youtube', h: 'YouTube에서 볼 때', body: [
        'YouTube에서 영상을 볼 때는 Google의 [개인정보처리방침](https://policies.google.com/privacy)이 적용됩니다. datasteg는 YouTube가 모든 채널 운영자에게 제공하는 조회수, 시청 시간 같은 합계만 보며, 누가 봤는지는 알 수 없습니다.',
      ] },
      { id: 'children', h: '아동', body: [
        '사이트와 영상은 성인 독자를 위해 만들었으며, 아동을 대상으로 하지 않습니다.',
      ] },
      { id: 'changes', h: '방침의 변경', body: [
        '방침이 바뀌면 새 방침을 날짜와 함께 이 페이지에 싣습니다.',
      ] },
    ],
  },
};

export async function generateMetadata({ params }: { params: Promise<{ lang: string }> }): Promise<Metadata> {
  const lang = await langOf(params);
  return { title: DOC[lang].title, description: DOC[lang].dek };
}

export default async function Privacy({ params }: { params: Promise<{ lang: string }> }) {
  const lang = await langOf(params);
  return <Policy lang={lang} doc={DOC[lang]} />;
}
