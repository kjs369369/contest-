#!/usr/bin/env node
/**
 * 공개 원본 데이터를 내려받아 이 저장소의 평면(flat) 스키마로 변환한다.
 *
 * 사용법
 *   node scripts/sync-upstream.mjs                 # 네트워크에서 갱신
 *   node scripts/sync-upstream.mjs --from ./tmp    # 로컬 폴더(원본 형식)에서 갱신
 *   node scripts/sync-upstream.mjs --dry-run       # 변경 건수만 확인
 *
 * 원칙: 원문의 문구·날짜·명칭을 변형하지 않는다. 없는 값은 만들지 않는다.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { ROOT, readJson, stableId, nowSeoulIso, safeUrl } from '../src/lib/util.mjs';

const args = process.argv.slice(2);
const dryRun = args.includes('--dry-run');
const fromIndex = args.indexOf('--from');
const fromDir = fromIndex >= 0 ? args[fromIndex + 1] : null;

/** 원본 레코드에서 우리가 보존하는 필드만 그대로 옮긴다. */
const CARRY = [
  'title', 'category', 'organizer', 'submission_start', 'submission_end',
  'result_date', 'url', 'source_type', 'summary', 'evidence', 'status',
  'source_checked_at', 'rules_reviewed_at',
  'results_confirmed', 'results_published_at', 'results_url', 'results_evidence'
];

function normalize(record, region) {
  const out = { id: stableId(record.title, record.submission_end), region };
  for (const key of CARRY) {
    if (record[key] === undefined || record[key] === null || record[key] === '') continue;
    // 외부 데이터를 그대로 신뢰하지 않는다. 링크는 http/https 만 통과시킨다.
    if (key === 'url' || key === 'results_url') {
      const link = safeUrl(record[key]);
      if (!link) { console.warn(`  ! 허용되지 않는 링크를 제거했습니다: ${record.title}`); continue; }
      out[key] = link;
      continue;
    }
    out[key] = record[key];
  }
  return out;
}

function flatten(payload, region) {
  const sections = payload.sections || {};
  const order = ['starting_today', 'ongoing', 'awaiting_results'];
  const seen = new Set();
  const contests = [];
  for (const name of order) {
    for (const record of sections[name] || []) {
      const key = `${record.title || ''}|${record.submission_end || ''}`;
      if (seen.has(key)) continue;
      seen.add(key);
      contests.push(normalize(record, region));
    }
  }
  contests.sort((a, b) => String(a.submission_end || '').localeCompare(String(b.submission_end || '')));
  return contests;
}

async function load(source) {
  if (fromDir) {
    const path = resolve(process.cwd(), fromDir, source.file.split('/').pop());
    return JSON.parse(await readFile(path, 'utf8'));
  }
  const response = await fetch(source.upstream);
  if (!response.ok) throw new Error(`${source.upstream} → HTTP ${response.status}`);
  return response.json();
}

const config = await readJson(join(ROOT, 'config/site.json'));

for (const source of config.dataSources) {
  const payload = await load(source);
  const contests = flatten(payload, source.region);
  const target = join(ROOT, source.file);
  let before = 0;
  try { before = (await readJson(target)).contests.length; } catch { before = 0; }

  const next = {
    meta: {
      region: source.region,
      label: source.label,
      generated_at: payload.generated_at || nowSeoulIso(),
      synced_at: nowSeoulIso(),
      notice: payload.notice || '',
      credit: config.credit
    },
    contests
  };

  console.log(`${source.label}: ${before}건 → ${contests.length}건`);
  if (!dryRun) await writeFile(target, `${JSON.stringify(next, null, 2)}\n`, 'utf8');
}

if (dryRun) console.log('(--dry-run: 파일을 쓰지 않았습니다)');
