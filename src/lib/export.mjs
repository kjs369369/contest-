/**
 * 내보내기(달력 .ics / 엑셀 .csv) 생성기. 순수 함수라 테스트와 브라우저가 함께 쓴다.
 */
import { toTime, BUCKETS } from './contests.mjs';
import { safeHref } from './card.mjs';

/* ---------- 달력(.ics) ---------- */
export function icsEscape(text) {
  return String(text ?? '')
    .replace(/\\/g, '\\\\')
    .replace(/[;,]/g, match => `\\${match}`)
    .replace(/\r?\n/g, '\\n');
}

export function icsDate(value, offsetDays = 0) {
  const time = toTime(value);
  if (time === null) return null;
  return new Date(time + offsetDays * 86400000).toISOString().slice(0, 10).replace(/-/g, '');
}

export function toIcs(list) {
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//AI 공모전 한눈에//KO', 'CALSCALE:GREGORIAN'];
  for (const item of list) {
    const start = icsDate(item.submission_end);
    if (!start) continue;
    lines.push(
      'BEGIN:VEVENT',
      `UID:${icsEscape(item.id)}@contest-board`,
      `DTSTART;VALUE=DATE:${start}`,
      `DTEND;VALUE=DATE:${icsDate(item.submission_end, 1)}`,
      `SUMMARY:[마감] ${icsEscape(item.title)}`,
      `DESCRIPTION:${icsEscape(`주최: ${item.organizer || '미확인'}\n원문: ${safeHref(item.url) || '링크 없음'}`)}`,
      'BEGIN:VALARM', 'TRIGGER:-P3D', 'ACTION:DISPLAY', 'DESCRIPTION:공모전 마감 3일 전', 'END:VALARM',
      'END:VEVENT'
    );
  }
  lines.push('END:VCALENDAR');
  return lines.join('\r\n');
}

/* ---------- 엑셀(.csv) ---------- */
/** 수식 주입(formula injection) 차단: =, +, -, @ 로 시작하면 엑셀이 수식으로 실행한다. */
export function csvCell(value) {
  const text = String(value ?? '');
  const safe = /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
  return `"${safe.replace(/"/g, '""')}"`;
}

export const CSV_HEAD = ['제목', '주최', '분야', '지역', '접수시작', '접수마감', '남은일수', '결과발표', '상태', '원문링크'];

export function toCsv(list) {
  const rows = list.map(item => [
    item.title, item.organizer, item.category,
    item.region === 'overseas' ? '해외' : '국내',
    item.submission_start, item.submission_end,
    item.daysLeft ?? '', item.result_date,
    BUCKETS.find(bucket => bucket.key === item.bucket)?.label || '',
    safeHref(item.url)
  ]);
  // 앞의 BOM(﻿)은 엑셀이 한글을 깨뜨리지 않게 한다.
  return `﻿${[CSV_HEAD, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n')}`;
}
