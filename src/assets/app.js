/* ==========================================================================
   AI 공모전 한눈에 — 브라우저 스크립트
   서버 렌더링된 목록 위에서 동작합니다(자바스크립트가 꺼져 있어도 목록은 보입니다).
   화면 로직은 contests.mjs / card.mjs 와 공유하므로 여기서는 상태 관리만 합니다.
   ========================================================================== */
import { BUCKETS, SORTS, decorate, matchesQuery, compare } from './contests.mjs';
import { cardHtml, esc, safeHref } from './card.mjs';
import { toIcs, toCsv } from './export.mjs';

const $ = id => document.getElementById(id);
const boot = JSON.parse($('board-data').textContent);
const STORE = { fav: 'contest-board:favorites', theme: 'contest-board:theme', font: 'contest-board:font' };

const state = {
  bucket: 'open',
  region: 'all',
  cats: new Set(),
  query: '',
  sort: 'deadline',
  days: 0,
  favOnly: false,
  today: boot.today,
  raw: boot.contests
};

/* ---------- 저장소(브라우저 안에만 저장, 서버 전송 없음) ---------- */
function readStore(key, fallback) {
  try { const value = localStorage.getItem(key); return value === null ? fallback : JSON.parse(value); }
  catch { return fallback; }
}
function writeStore(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* 사생활 보호 모드 등 */ }
}
let favorites = new Set(Array.isArray(readStore(STORE.fav, [])) ? readStore(STORE.fav, []) : []);

/* ---------- 테마 · 글자 크기 ---------- */
const FONT_STEPS = [{ key: 'normal', label: '글자 보통', scale: 1 }, { key: 'large', label: '글자 크게', scale: 1.14 }, { key: 'xlarge', label: '글자 아주 크게', scale: 1.3 }];

function applyFont(key) {
  const step = FONT_STEPS.find(item => item.key === key) || FONT_STEPS[0];
  document.documentElement.style.setProperty('--font-scale', String(step.scale));
  $('font-toggle').textContent = `가 ${step.label.replace('글자 ', '')}`;
  $('font-toggle').setAttribute('aria-label', `글자 크기: ${step.label}. 눌러서 변경`);
  writeStore(STORE.font, step.key);
}
function applyTheme(mode) {
  if (mode === 'light' || mode === 'dark') document.documentElement.dataset.theme = mode;
  else delete document.documentElement.dataset.theme;
  const dark = mode === 'dark';
  $('theme-toggle').textContent = dark ? '☀️ 밝게' : '🌙 어둡게';
  $('theme-toggle').setAttribute('aria-pressed', String(dark));
  writeStore(STORE.theme, mode);
}

/* ---------- 데이터 ---------- */
function decorated() {
  return state.raw.map(item => decorate(item, { today: state.today, categories: boot.categories }));
}
let items = decorated();

function visible(ignore = {}) {
  return items.filter(item => {
    if (item.bucket === 'archived') return false;
    if (!ignore.bucket && item.bucket !== state.bucket) return false;
    if (!ignore.region && state.region !== 'all' && item.region !== state.region) return false;
    if (!ignore.cats && state.cats.size && !item.cats.some(key => state.cats.has(key))) return false;
    if (!ignore.days && state.days && state.bucket === 'open') {
      if (item.daysLeft === null || item.daysLeft < 0 || item.daysLeft > state.days) return false;
    }
    if (state.favOnly && !favorites.has(item.id)) return false;
    return matchesQuery(item, state.query);
  });
}

/* ---------- 렌더 ---------- */
function render() {
  const list = visible().sort((a, b) => compare(a, b, state.sort));

  BUCKETS.forEach(bucket => {
    const button = document.querySelector(`[data-bucket="${bucket.key}"]`);
    if (!button) return;
    const active = state.bucket === bucket.key;
    button.setAttribute('aria-selected', String(active));
    button.querySelector('.count').textContent = items.filter(item => item.bucket === bucket.key
      && (state.region === 'all' || item.region === state.region)
      && (!state.favOnly || favorites.has(item.id))).length;
  });

  document.querySelectorAll('[data-cat]').forEach(button => {
    const key = button.dataset.cat;
    button.setAttribute('aria-pressed', String(state.cats.has(key)));
    const counter = button.querySelector('.n');
    if (counter) counter.textContent = visible({ cats: true }).filter(item => item.cats.includes(key)).length;
  });
  document.querySelectorAll('[data-region]').forEach(button => {
    button.setAttribute('aria-pressed', String(state.region === button.dataset.region));
  });
  document.querySelectorAll('[data-days]').forEach(button => {
    button.setAttribute('aria-pressed', String(state.days === Number(button.dataset.days)));
    button.disabled = state.bucket !== 'open';
  });
  $('fav-only').setAttribute('aria-pressed', String(state.favOnly));
  $('fav-only').textContent = `★ 관심만 보기 (${favorites.size})`;

  const bucket = BUCKETS.find(item => item.key === state.bucket);
  $('result-count').innerHTML = `${esc(bucket.label)} <em>${list.length}건</em>`;
  $('bucket-hint').textContent = bucket.hint;
  $('cards').innerHTML = list.length
    ? list.map(item => cardHtml(item, { today: state.today, query: state.query, favorite: favorites.has(item.id) })).join('')
    : '';
  $('empty').hidden = list.length > 0;
  $('list-end').textContent = list.length ? `총 ${list.length}건을 모두 보여드렸습니다.` : '';
  syncUrl();
}

function syncUrl() {
  const params = new URLSearchParams();
  if (state.bucket !== 'open') params.set('status', state.bucket);
  if (state.region !== 'all') params.set('region', state.region);
  if (state.cats.size) params.set('cat', [...state.cats].join(','));
  if (state.days) params.set('days', String(state.days));
  if (state.sort !== 'deadline') params.set('sort', state.sort);
  if (state.query) params.set('q', state.query);
  if (state.favOnly) params.set('fav', '1');
  const query = params.toString();
  history.replaceState(null, '', query ? `?${query}` : location.pathname);
}

function hydrateUrl() {
  const params = new URLSearchParams(location.search);
  const status = params.get('status');
  if (BUCKETS.some(item => item.key === status)) state.bucket = status;
  const region = params.get('region');
  if (region === 'domestic' || region === 'overseas') state.region = region;
  const cats = (params.get('cat') || '').split(',').filter(Boolean);
  const allowed = new Set(boot.categories.map(item => item.key));
  cats.forEach(key => { if (allowed.has(key)) state.cats.add(key); });
  const days = Number(params.get('days'));
  if ([7, 14, 30].includes(days)) state.days = days;
  const sort = params.get('sort');
  if (SORTS.some(item => item.key === sort)) state.sort = sort;
  state.query = (params.get('q') || '').slice(0, 80);
  state.favOnly = params.get('fav') === '1';
  $('search').value = state.query;
  $('sort').value = state.sort;
}

/* ---------- 내보내기 ---------- */
function download(filename, text, mime) {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

let toastTimer = 0;
function toast(message) {
  const node = $('toast');
  node.textContent = message;
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, 2600);
}

async function copyLink(item) {
  const url = `${location.origin}${location.pathname}#${item.id}`;
  const text = `${item.title}\n마감: ${item.submission_end || '미확인'}\n${safeHref(item.url) || url}`;
  if (navigator.share) {
    try { await navigator.share({ title: item.title, text, url: safeHref(item.url) || url }); return; } catch { /* 취소 */ }
  }
  try { await navigator.clipboard.writeText(text); toast('링크를 복사했습니다'); }
  catch { toast('복사를 지원하지 않는 브라우저입니다'); }
}

/* ---------- 이벤트 ---------- */
document.querySelectorAll('[data-bucket]').forEach(button => button.addEventListener('click', () => {
  state.bucket = button.dataset.bucket;
  if (state.bucket !== 'open') state.days = 0;
  render();
}));
document.querySelectorAll('[data-region]').forEach(button => button.addEventListener('click', () => {
  state.region = button.dataset.region; render();
}));
document.querySelectorAll('[data-cat]').forEach(button => button.addEventListener('click', () => {
  const key = button.dataset.cat;
  if (state.cats.has(key)) state.cats.delete(key); else state.cats.add(key);
  render();
}));
document.querySelectorAll('[data-days]').forEach(button => button.addEventListener('click', () => {
  const value = Number(button.dataset.days);
  state.days = state.days === value ? 0 : value;
  render();
}));

let searchTimer = 0;
$('search').addEventListener('input', event => {
  const value = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.query = value; render(); }, 150);
});
$('search-clear').addEventListener('click', () => {
  $('search').value = ''; state.query = ''; $('search').focus(); render();
});
$('sort').addEventListener('change', event => { state.sort = event.target.value; render(); });
$('fav-only').addEventListener('click', () => { state.favOnly = !state.favOnly; render(); });
$('reset').addEventListener('click', () => {
  Object.assign(state, { bucket: 'open', region: 'all', query: '', sort: 'deadline', days: 0, favOnly: false });
  state.cats.clear();
  $('search').value = ''; $('sort').value = 'deadline';
  render();
  toast('필터를 초기화했습니다');
});

$('export-csv').addEventListener('click', () => {
  const list = visible().sort((a, b) => compare(a, b, state.sort));
  if (!list.length) return toast('내보낼 공고가 없습니다');
  download(`ai-공모전-${state.today}.csv`, toCsv(list), 'text/csv');
  toast(`${list.length}건을 엑셀 파일로 저장했습니다`);
});
$('export-ics').addEventListener('click', () => {
  const list = visible().sort((a, b) => compare(a, b, state.sort));
  if (!list.length) return toast('저장할 공고가 없습니다');
  download(`ai-공모전-마감일-${state.today}.ics`, toIcs(list), 'text/calendar');
  toast(`${list.length}건의 마감일을 달력 파일로 저장했습니다`);
});
$('print').addEventListener('click', () => window.print());

$('cards').addEventListener('click', event => {
  const button = event.target.closest('[data-action]');
  if (!button) return;
  const item = items.find(entry => entry.id === button.dataset.id);
  if (!item) return;
  const action = button.dataset.action;
  if (action === 'fav') {
    if (favorites.has(item.id)) { favorites.delete(item.id); toast('관심 목록에서 뺐습니다'); }
    else { favorites.add(item.id); toast('관심 목록에 저장했습니다'); }
    writeStore(STORE.fav, [...favorites]);
    render();
  } else if (action === 'ics') {
    download(`${item.id}.ics`, toIcs([item]), 'text/calendar');
    toast('달력 파일을 저장했습니다. 파일을 열면 일정이 등록됩니다');
  } else if (action === 'share') {
    copyLink(item);
  }
});

$('theme-toggle').addEventListener('click', () => {
  const dark = document.documentElement.dataset.theme === 'dark'
    || (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
  applyTheme(dark ? 'light' : 'dark');
});
$('font-toggle').addEventListener('click', () => {
  const current = readStore(STORE.font, 'normal');
  const index = FONT_STEPS.findIndex(step => step.key === current);
  applyFont(FONT_STEPS[(index + 1) % FONT_STEPS.length].key);
});

const topButton = $('to-top');
addEventListener('scroll', () => topButton.classList.toggle('on', scrollY > 400), { passive: true });
topButton.addEventListener('click', () => scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }));

/* ---------- 최신 데이터 새로고침 ---------- */
async function refresh() {
  try {
    const payloads = await Promise.all(boot.files.map(async file => {
      const response = await fetch(`${file}?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(String(response.status));
      return response.json();
    }));
    const merged = payloads.flatMap(payload => payload.contests || []);
    if (!merged.length) throw new Error('empty');
    state.raw = merged;
    items = decorated();
    const latest = payloads.map(payload => payload.meta?.generated_at || '').sort().pop();
    if (latest) $('updated-at').textContent = latest.slice(0, 10);
    render();
  } catch {
    $('fetch-alert').hidden = false;
  }
}

/* ---------- 시작 ---------- */
applyTheme(readStore(STORE.theme, 'auto'));
applyFont(readStore(STORE.font, 'normal'));
hydrateUrl();
render();
refresh();
if (location.hash) {
  const target = document.getElementById(location.hash.slice(1));
  if (target) target.scrollIntoView({ block: 'center' });
}
