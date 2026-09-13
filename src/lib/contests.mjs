/**
 * 공모전 레코드 정규화 · 상태 판정 · 검색 색인.
 * 빌드(Node)와 브라우저 양쪽에서 같은 규칙을 쓰기 위해 순수 함수로만 작성한다.
 */

/** 상태 버킷 정의. 화면 탭 순서와 동일하다. */
export const BUCKETS = [
  { key: 'open', label: '접수중', hint: '지금 바로 낼 수 있는 공모전입니다.' },
  { key: 'upcoming', label: '곧 시작', hint: '아직 접수 전입니다. 미리 준비하세요.' },
  { key: 'closed', label: '결과 대기', hint: '접수가 끝났고 결과 발표가 확인되지 않았습니다.' },
  { key: 'published', label: '발표 완료', hint: '결과 발표가 확인된 공모전입니다. 14일간 표시합니다.' }
];

/** 발표 완료를 목록에 남겨두는 기간(일). */
export const PUBLISHED_WINDOW_DAYS = 14;

const DAY = 86400000;

/** 'YYYY-MM-DD' → UTC ms. 형식이 다르면 null. */
export function toTime(value) {
  const text = String(value ?? '').trim();
  if (!/^\d{4}-\d{2}-\d{2}/.test(text)) return null;
  const time = Date.parse(`${text.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(time) ? null : time;
}

/** 기준일(today) 대비 남은 일수. 마감일이 오늘이면 0. */
export function daysLeft(end, today) {
  const endTime = toTime(end);
  const baseTime = toTime(today);
  if (endTime === null || baseTime === null) return null;
  return Math.round((endTime - baseTime) / DAY);
}

export function bucketOf(contest, today) {
  const base = toTime(today);
  const start = toTime(contest.submission_start);
  const end = toTime(contest.submission_end);

  if (contest.results_confirmed === true) {
    const published = toTime(contest.results_published_at);
    if (published === null) return 'closed';
    return (base - published) / DAY <= PUBLISHED_WINDOW_DAYS ? 'published' : 'archived';
  }
  if (end !== null && base > end) return 'closed';
  if (start !== null && base < start) return 'upcoming';
  if (start === null && end !== null && base <= end) return 'open';
  if (start !== null && end !== null && base >= start && base <= end) return 'open';
  return 'closed';
}

/** 한글 초성 색인. "ㅇㅅㄱ" 같은 입력으로도 찾을 수 있게 한다. */
const CHO = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];

export function toChosung(text) {
  let out = '';
  for (const char of String(text ?? '')) {
    const code = char.charCodeAt(0);
    if (code >= 0xac00 && code <= 0xd7a3) out += CHO[Math.floor((code - 0xac00) / 588)];
    else out += char;
  }
  return out.toLowerCase();
}

export function isChosungQuery(query) {
  const text = String(query ?? '').replace(/\s+/g, '');
  return text.length > 0 && /^[ㄱ-ㅎ]+$/.test(text);
}

/** 설정의 categories 정의로 레코드의 분야 키 목록을 만든다. */
export function categoryKeys(contest, categories) {
  const label = String(contest.category ?? '');
  const keys = categories.filter(item => item.match.some(word => label.includes(word))).map(item => item.key);
  return keys.length ? keys : ['etc'];
}

/** 화면·검색·정렬에 필요한 파생 필드를 붙인다. */
export function decorate(contest, { today, categories }) {
  const bucket = bucketOf(contest, today);
  const left = daysLeft(contest.submission_end, today);
  const haystack = `${contest.title ?? ''} ${contest.organizer ?? ''} ${contest.summary ?? ''} ${contest.category ?? ''}`;
  return {
    ...contest,
    bucket,
    daysLeft: left,
    cats: categoryKeys(contest, categories),
    search: haystack.toLowerCase(),
    chosung: toChosung(haystack)
  };
}

export function matchesQuery(contest, query) {
  const text = String(query ?? '').trim().toLowerCase();
  if (!text) return true;
  if (isChosungQuery(text)) return contest.chosung.replace(/\s+/g, '').includes(text.replace(/\s+/g, ''));
  return contest.search.includes(text);
}

export const SORTS = [
  { key: 'deadline', label: '마감 임박순' },
  { key: 'newest', label: '최근 등록순' },
  { key: 'name', label: '이름순' },
  { key: 'organizer', label: '주최기관순' }
];

export function compare(a, b, sort) {
  if (sort === 'name') return String(a.title).localeCompare(String(b.title), 'ko');
  if (sort === 'organizer') return String(a.organizer ?? '').localeCompare(String(b.organizer ?? ''), 'ko');
  if (sort === 'newest') return String(b.submission_start ?? '').localeCompare(String(a.submission_start ?? ''));
  const left = toTime(a.submission_end) ?? Number.MAX_SAFE_INTEGER;
  const right = toTime(b.submission_end) ?? Number.MAX_SAFE_INTEGER;
  return left - right || String(a.title).localeCompare(String(b.title), 'ko');
}

/** 남은 일수에 따른 긴급도. 카드 배지 색을 결정한다. */
export function urgency(left) {
  if (left === null) return 'none';
  if (left < 0) return 'over';
  if (left <= 3) return 'critical';
  if (left <= 7) return 'soon';
  if (left <= 30) return 'normal';
  return 'far';
}

/** 공식 출처 여부. 데이터의 source_type 값을 그대로 판정한다. */
export function isOfficial(contest) {
  return String(contest.source_type ?? '').startsWith('official');
}

export const SOURCE_LABELS = {
  official_homepage: '공식 홈페이지',
  official_notice: '공식 공고',
  official_platform: '공식 접수 플랫폼',
  official_apply_page: '공식 접수 페이지',
  reference_link: '참고 링크'
};
