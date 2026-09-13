/**
 * 공모전 카드 HTML 생성기.
 * 빌드(Node)와 브라우저가 **같은 함수**를 사용하므로 화면이 어긋나지 않는다.
 * 순수 ESM이며 Node 전용 API를 쓰지 않는다.
 */
import { urgency, isOfficial, SOURCE_LABELS, toTime } from './contests.js';

export function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/** http/https 링크만 허용(스크립트 주입 방지). */
export function safeHref(value) {
  const raw = String(value ?? '').trim();
  return /^https?:\/\//i.test(raw) ? raw : '';
}

function ddayText(contest) {
  const left = contest.daysLeft;
  if (left === null) return { big: '?', small: '마감 미확인' };
  if (contest.bucket === 'upcoming') return { big: '접수전', small: '시작 예정' };
  if (left < 0) return { big: '마감', small: `${Math.abs(left)}일 지남` };
  if (left === 0) return { big: '오늘', small: '마감일' };
  return { big: `D-${left}`, small: '마감까지' };
}

/** 접수 기간 중 지난 비율(0~100). 진행바에 사용. */
export function progress(contest, today) {
  const start = toTime(contest.submission_start);
  const end = toTime(contest.submission_end);
  const base = toTime(today);
  if (start === null || end === null || base === null || end <= start) return null;
  const ratio = ((base - start) / (end - start)) * 100;
  return Math.max(0, Math.min(100, Math.round(ratio)));
}

function highlight(text, query) {
  const safe = esc(text);
  const needle = String(query ?? '').trim();
  if (!needle || /^[ㄱ-ㅎ]+$/.test(needle)) return safe;
  const escaped = esc(needle).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return safe.replace(new RegExp(escaped, 'gi'), match => `<mark>${match}</mark>`);
}

const DASH = '정보 없음';

export function cardHtml(contest, options = {}) {
  const { today, query = '', favorite = false, interactive = true } = options;
  const level = contest.bucket === 'upcoming' ? 'none' : urgency(contest.daysLeft);
  const dday = ddayText(contest);
  const href = safeHref(contest.url);
  const official = isOfficial(contest);
  const sourceLabel = SOURCE_LABELS[contest.source_type] || '출처 미확인';
  const ratio = progress(contest, today);

  const titleInner = highlight(contest.title, query);
  const title = href
    ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${titleInner}</a>`
    : titleInner;

  const badges = [
    `<span class="badge region">${contest.region === 'overseas' ? '해외' : '국내'}</span>`,
    `<span class="badge">${esc(contest.category || '분야 미확인')}</span>`,
    `<span class="badge ${official ? 'official' : 'reference'}">${esc(sourceLabel)}</span>`
  ].join('');

  const actions = interactive ? `<div class="actions">
    ${href ? `<a class="primary" href="${esc(href)}" target="_blank" rel="noopener noreferrer">공고 원문 보기 <span aria-hidden="true">↗</span></a>` : '<span class="badge">원문 링크 없음</span>'}
    <button type="button" class="fav" data-action="fav" data-id="${esc(contest.id)}" aria-pressed="${favorite}">${favorite ? '★ 저장됨' : '☆ 관심 저장'}</button>
    <button type="button" data-action="ics" data-id="${esc(contest.id)}">📅 마감일 알림</button>
    <button type="button" data-action="share" data-id="${esc(contest.id)}">🔗 링크 복사</button>
  </div>` : '';

  const detail = `<details class="more"><summary>자세히 보기</summary><dl>
    <dt>접수 기간</dt><dd>${esc(contest.submission_start || DASH)} ~ ${esc(contest.submission_end || DASH)}</dd>
    <dt>결과 발표</dt><dd>${esc(contest.result_date || DASH)}</dd>
    <dt>확인 근거</dt><dd>${esc(contest.evidence || DASH)}</dd>
    <dt>출처 확인일</dt><dd>${esc((contest.source_checked_at || DASH).slice(0, 10))}</dd>
    ${contest.results_url ? `<dt>결과 발표</dt><dd><a href="${esc(safeHref(contest.results_url))}" target="_blank" rel="noopener noreferrer">발표 페이지 열기</a></dd>` : ''}
  </dl></details>`;

  return `<li class="card" id="${esc(contest.id)}" data-id="${esc(contest.id)}">
  <div class="card-top">
    <div class="dday ${level}"><b>${esc(dday.big)}</b><small>${esc(dday.small)}</small></div>
    <div class="card-head">
      <div class="badges">${badges}</div>
      <h3>${title}</h3>
      <p class="org">${esc(contest.organizer || '주최기관 미확인')}</p>
    </div>
  </div>
  <p class="desc">${highlight(contest.summary || '', query)}</p>
  <div class="dates">
    <span>접수 <b>${esc(contest.submission_start || DASH)}</b> ~ <b>${esc(contest.submission_end || DASH)}</b></span>
    <span>발표 <b>${esc(contest.result_date || DASH)}</b></span>
  </div>
  ${ratio === null ? '' : `<div class="bar ${level}"><i style="width:${ratio}%"></i></div>`}
  ${actions}
  ${detail}
</li>`;
}
