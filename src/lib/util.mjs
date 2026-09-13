/** 공용 유틸. 빌드 스크립트와 동기화 스크립트가 함께 사용한다. */
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

export async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

/** 제목+마감일로 만든 결정적(deterministic) 앵커 ID. 데이터가 같으면 항상 같은 값. */
export function stableId(title, end) {
  const input = `${title || ''}|${end || ''}`;
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return `c-${hash.toString(36)}`;
}

/** Asia/Seoul 기준 YYYY-MM-DD */
export function seoulDate(date = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(date);
}

export function nowSeoulIso(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul', hour12: false,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  }).formatToParts(date).reduce((acc, part) => ({ ...acc, [part.type]: part.value }), {});
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}+09:00`;
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** JSON을 <script>에 안전하게 넣기 위한 이스케이프. */
export function escapeJson(value) {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}

/** http/https 링크만 허용한다. 그 외(javascript: 등)는 빈 문자열. */
export function safeUrl(value) {
  const raw = String(value ?? '').trim();
  if (!/^https?:\/\//i.test(raw)) return '';
  return raw;
}
