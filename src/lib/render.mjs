/** index.html 생성기. 문구를 고치려면 이 파일만 보면 된다. */
import { BUCKETS, SORTS, urgency } from './contests.mjs';
import { cardHtml, esc } from './card.mjs';
import { escapeJson, safeUrl } from './util.mjs';

const DAY_FILTERS = [
  { value: 7, label: '7일 이내 마감' },
  { value: 14, label: '14일 이내 마감' },
  { value: 30, label: '30일 이내 마감' }
];

const FAQ = [
  ['이 목록에 있는 공모전은 바로 접수할 수 있나요?', '첫 화면의 <strong>접수중</strong> 탭은 오늘 날짜 기준으로 접수 기간 안에 있는 공고입니다. 다만 마감 시각과 조기 마감 여부는 반드시 공고 원문에서 확인하세요.'],
  ['공모전 정보를 어디서 모으나요?', '주최기관의 공식 공고·공식 홈페이지·공식 접수 페이지를 우선합니다. 공식 출처가 확인되지 않은 경우 카드에 <strong>참고 링크</strong>로 표시합니다.'],
  ['관심 공모전은 어디에 저장되나요?', '사용하시는 브라우저 안에만 저장됩니다(로그인·회원가입 없음). 서버로 전송하지 않으며, 다른 기기에서는 보이지 않습니다.'],
  ['마감일 알림은 어떻게 받나요?', '카드의 <strong>📅 마감일 알림</strong>을 누르면 달력 파일(.ics)이 내려받아집니다. 파일을 열면 구글 캘린더·아이폰 달력·아웃룩에 마감 3일 전 알림과 함께 등록됩니다.'],
  ['글씨가 작아서 보기 힘듭니다.', '오른쪽 위 <strong>가 보통</strong> 버튼을 누를 때마다 보통 → 크게 → 아주 크게로 바뀝니다. 선택한 크기는 다음 방문 때도 유지됩니다.'],
  ['요약만 보고 출품해도 되나요?', '아니요. 이 보드는 <strong>찾기용</strong>입니다. 참가 자격, 참가비, 제출 규격, 저작권과 AI 사용 조건은 반드시 주최기관 원문에서 최종 확인하세요.']
];

function statsHtml(stats) {
  return `<ul class="stats">
    <li><b>${stats.open}</b><span>지금 접수중</span></li>
    <li class="hot"><b>${stats.urgent}</b><span>7일 안에 마감</span></li>
    <li><b>${stats.upcoming}</b><span>곧 시작</span></li>
    <li><b>${stats.total}</b><span>전체 등록 공고</span></li>
  </ul>`;
}

function jsonLd(config, contests, page) {
  const itemList = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: `${config.name} — 접수중 AI 공모전`,
    description: config.description,
    numberOfItems: contests.length,
    itemListElement: contests.slice(0, 30).map((contest, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      item: {
        '@type': 'Event',
        name: contest.title,
        startDate: contest.submission_start,
        endDate: contest.submission_end,
        eventAttendanceMode: 'https://schema.org/OnlineEventAttendanceMode',
        eventStatus: 'https://schema.org/EventScheduled',
        location: { '@type': 'VirtualLocation', url: safeUrl(contest.url) || config.baseUrl },
        organizer: { '@type': 'Organization', name: contest.organizer || '미확인' },
        url: safeUrl(contest.url) || config.baseUrl,
        description: contest.summary || ''
      }
    }))
  };
  const faq = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQ.map(([question, answer]) => ({
      '@type': 'Question',
      name: question,
      acceptedAnswer: { '@type': 'Answer', text: answer.replace(/<[^>]+>/g, '') }
    }))
  };
  const website = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: config.name,
    url: config.baseUrl,
    inLanguage: 'ko-KR',
    description: page.description
  };
  return [website, itemList, faq]
    .map(data => `<script type="application/ld+json">${escapeJson(data)}</script>`)
    .join('\n');
}

export function renderPage({ config, contests, ssrList, stats, today, updatedAt }) {
  const page = {
    title: `${config.name} | 국내·해외 AI 공모전 모음 (${today} 기준)`,
    description: config.description
  };
  const canonical = config.baseUrl;

  const cards = ssrList.map(contest => cardHtml(contest, { today, interactive: true })).join('\n');

  const categoryChips = config.categories.map(category => {
    const count = ssrList.filter(item => item.cats.includes(category.key)).length;
    return `<button type="button" class="chip" data-cat="${esc(category.key)}" aria-pressed="false">${esc(category.label)}<span class="n">${count}</span></button>`;
  }).join('');

  const tabs = BUCKETS.map(bucket => `<button type="button" role="tab" data-bucket="${esc(bucket.key)}" aria-selected="${bucket.key === 'open'}" aria-controls="cards">${esc(bucket.label)}<span class="count">${stats.buckets[bucket.key] ?? 0}</span></button>`).join('');

  const sortOptions = SORTS.map(sort => `<option value="${esc(sort.key)}">${esc(sort.label)}</option>`).join('');

  const dayChips = DAY_FILTERS.map(filter => `<button type="button" class="chip" data-days="${filter.value}" aria-pressed="false">${esc(filter.label)}</button>`).join('');

  const faqHtml = FAQ.map(([question, answer]) => `<details><summary>${esc(question)}</summary><p>${answer}</p></details>`).join('');

  const bootData = {
    today,
    files: config.dataSources.map(source => `./${source.file}`),
    categories: config.categories,
    contests
  };

  return `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>${esc(page.title)}</title>
<meta name="description" content="${esc(page.description)}">
<meta name="author" content="${esc(config.owner.name)}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<link rel="canonical" href="${esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="${esc(config.name)}">
<meta property="og:title" content="${esc(page.title)}">
<meta property="og:description" content="${esc(page.description)}">
<meta property="og:url" content="${esc(canonical)}">
<meta property="og:locale" content="ko_KR">
<meta name="twitter:card" content="summary">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta name="theme-color" content="#1857b8">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%231857b8'/%3E%3Ctext x='50' y='68' font-size='52' font-weight='700' text-anchor='middle' fill='white' font-family='sans-serif'%3EAI%3C/text%3E%3C/svg%3E">
<link rel="stylesheet" href="./assets/app.css">
${jsonLd(config, ssrList, page)}
</head>
<body>
<a class="skip" href="#main">본문 바로가기</a>

<header class="site-header">
  <div class="wrap header-row">
    <a class="brand" href="./"><span class="brand-mark" aria-hidden="true">AI</span>${esc(config.name)}</a>
    <div class="header-tools">
      <button type="button" class="tool-btn" id="font-toggle" aria-label="글자 크기 변경">가 보통</button>
      <button type="button" class="tool-btn" id="theme-toggle" aria-pressed="false">🌙 어둡게</button>
    </div>
  </div>
</header>

<main id="main">
  <div class="wrap">
    <section class="hero">
      <h1>${esc(config.tagline)}</h1>
      <p>공고 <b>${stats.total}건</b>을 마감 임박순으로 정리했습니다. 데이터 기준일 <b><span id="updated-at">${esc(updatedAt.slice(0, 10))}</span></b> · 오늘 <b>${esc(today)}</b></p>
      ${statsHtml(stats)}
      <details class="howto">
        <summary>처음 오셨나요? 30초 사용법 보기</summary>
        <ol>
          <li><strong>1단계 · 고르기</strong> — 위쪽 <strong>접수중</strong> 탭에서 <strong>이미지·영상·디자인·음악</strong> 버튼을 눌러 원하는 분야만 봅니다.</li>
          <li><strong>2단계 · 저장하기</strong> — 마음에 드는 공고의 <strong>☆ 관심 저장</strong>을 누르면 <strong>★ 관심만 보기</strong>에서 모아 볼 수 있습니다.</li>
          <li><strong>3단계 · 잊지 않기</strong> — <strong>📅 마감일 알림</strong>을 누르면 달력 파일이 내려받아지고, 열면 마감 3일 전 알림이 등록됩니다.</li>
        </ol>
        <p class="hint">검색창에는 <strong>초성</strong>도 됩니다. 예) <strong>ㄱㅇㄷ</strong> → 경연대회 · <strong>ㅇㅅ</strong> → 영상</p>
      </details>
    </section>

    <section class="controls" aria-label="공모전 찾기">
      <div class="searchbar">
        <span class="icon" aria-hidden="true">🔍</span>
        <label class="sr-only" for="search">공모전 검색</label>
        <input id="search" type="search" placeholder="공모전 이름, 주최기관, 키워드 (초성도 가능)" autocomplete="off">
        <button type="button" class="search-clear" id="search-clear">지우기</button>
      </div>

      <div class="tabs" role="tablist" aria-label="접수 상태">${tabs}</div>

      <div class="chips">
        <span class="group-label">지역</span>
        <button type="button" class="chip" data-region="all" aria-pressed="true">전체</button>
        <button type="button" class="chip" data-region="domestic" aria-pressed="false">국내<span class="n">${stats.domestic}</span></button>
        <button type="button" class="chip" data-region="overseas" aria-pressed="false">해외<span class="n">${stats.overseas}</span></button>
      </div>
      <div class="chips">
        <span class="group-label">분야</span>${categoryChips}
      </div>
      <div class="chips">
        <span class="group-label">마감</span>${dayChips}
        <button type="button" class="chip" id="fav-only" aria-pressed="false">★ 관심만 보기 (0)</button>
      </div>

      <div class="toolbar">
        <h2 id="result-count" aria-live="polite">접수중 <em>${stats.open}건</em></h2>
        <div class="spacer"></div>
        <label class="sr-only" for="sort">정렬 기준</label>
        <select id="sort">${sortOptions}</select>
        <button type="button" class="linkish" id="export-ics">📅 달력 저장</button>
        <button type="button" class="linkish" id="export-csv">📊 엑셀 저장</button>
        <button type="button" class="linkish" id="print">🖨️ 인쇄</button>
        <button type="button" class="linkish" id="reset">필터 초기화</button>
      </div>
      <p class="hint" id="bucket-hint">${esc(BUCKETS[0].hint)}</p>
      <p class="alert" id="fetch-alert" role="status" hidden>최신 데이터를 불러오지 못했습니다. 아래 목록은 <b>${esc(updatedAt.slice(0, 10))}</b> 기준 저장본입니다.</p>
    </section>

    <ul class="cards" id="cards">
${cards}
    </ul>
    <div class="empty" id="empty" hidden><strong>조건에 맞는 공모전이 없습니다.</strong>검색어를 줄이거나 <b>필터 초기화</b>를 눌러 보세요.</div>
    <p class="list-end" id="list-end">총 ${ssrList.length}건을 모두 보여드렸습니다.</p>

    <section class="notes" aria-label="이용 안내">
      <article class="note-card">
        <h2>이 보드를 쓰는 순서</h2>
        <ol>
          <li>분야와 마감 기간으로 후보를 좁힙니다.</li>
          <li>카드의 <b>공고 원문 보기</b>로 주최기관 페이지를 엽니다.</li>
          <li>참가 자격 · 제출 규격 · AI 사용 조건 · 저작권 조항을 원문에서 확인합니다.</li>
          <li>낼 공고만 <b>관심 저장</b>하고 마감일을 달력에 넣습니다.</li>
        </ol>
      </article>
      <article class="note-card">
        <h2>출처와 편집 원칙</h2>
        <ul>
          <li>날짜·참가비·자격을 임의로 추정하지 않습니다. 확인되지 않은 값은 <b>정보 없음</b>으로 표시합니다.</li>
          <li>공식 공고·공식 홈페이지·공식 접수 페이지는 <b>공식</b> 배지로, 그 외는 <b>참고 링크</b>로 구분합니다.</li>
          <li>공고는 주최기관 사정으로 변경될 수 있습니다. 출품 직전 원문을 다시 확인하세요.</li>
          <li>정정 제안: <a href="mailto:${esc(config.owner.email)}">${esc(config.owner.email)}</a></li>
        </ul>
      </article>
      <article class="note-card full faq">
        <h2>자주 묻는 질문</h2>
        ${faqHtml}
      </article>
    </section>
  </div>
</main>

<footer class="site-footer">
  <div class="wrap">
    <p><b>${esc(config.name)}</b> · ${esc(config.owner.name)}</p>
    <p>데이터 기준 ${esc(updatedAt)} · 전체 ${stats.total}건(국내 ${stats.domestic} · 해외 ${stats.overseas})</p>
    <p>공모전 사실 정보 수집 출처: <a href="${esc(safeUrl(config.credit.url))}" target="_blank" rel="noopener noreferrer">${esc(config.credit.label)}</a></p>
    <p>이 페이지는 공모전 탐색을 돕는 안내이며 주최기관의 공고를 대신하지 않습니다. 관심 저장 정보는 이용자 브라우저에만 보관되며 서버로 전송되지 않습니다.</p>
  </div>
</footer>

<button type="button" id="to-top" aria-label="맨 위로 이동">↑</button>
<div class="toast" id="toast" role="status" hidden></div>

<script type="application/json" id="board-data">${escapeJson(bootData)}</script>
<script type="module" src="./assets/app.js"></script>
</body>
</html>
`;
}

export function renderSitemap(config, updatedAt) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>${config.baseUrl}</loc>
    <lastmod>${updatedAt.slice(0, 10)}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
`;
}

export function renderLlmsTxt(config, stats, updatedAt) {
  return `# ${config.name}

> ${config.description}

기준일: ${updatedAt}
수록 건수: 전체 ${stats.total}건 (국내 ${stats.domestic} · 해외 ${stats.overseas}) / 접수중 ${stats.open}건

정식 페이지:
- ${config.baseUrl}

원본 데이터(JSON, 이 파일들이 기준입니다):
${config.dataSources.map(source => `- ${config.baseUrl}${source.file}`).join('\n')}

읽는 방법:
- 각 레코드의 submission_start / submission_end 는 YYYY-MM-DD 형식입니다.
- source_type 이 official_ 로 시작하면 주최기관이 통제하는 공식 출처, reference_link 는 참고 링크입니다.
- result_date 는 공고 원문 표기를 그대로 옮긴 자유 문자열이며 날짜로 단정할 수 없습니다.
- 요약(summary)은 탐색용 안내이며 주최기관 공고를 대신하지 않습니다.

llms.txt 는 표준이 아닌 안내 파일이며 권리·허가·robots 지시를 변경하지 않습니다.
`;
}

export { urgency };
