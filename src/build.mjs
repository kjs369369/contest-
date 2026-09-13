#!/usr/bin/env node
/**
 * 정적 사이트 빌드.
 *   node src/build.mjs              → index.html, assets/, sitemap.xml, llms.txt 생성
 *   BOARD_DATE=2026-09-14 node src/build.mjs   → 기준일 고정(테스트용)
 *
 * 생성물은 저장소 루트에 놓여 GitHub Pages가 그대로 서빙한다.
 */
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { ROOT, readJson, seoulDate, nowSeoulIso } from './lib/util.mjs';
import { BUCKETS, decorate, compare } from './lib/contests.mjs';
import { renderPage, renderSitemap, renderLlmsTxt } from './lib/render.mjs';

const today = process.env.BOARD_DATE || seoulDate();
const config = await readJson(join(ROOT, 'config/site.json'));

/* 1) 데이터 읽기 --------------------------------------------------------- */
const payloads = [];
for (const source of config.dataSources) {
  payloads.push({ source, data: await readJson(join(ROOT, source.file)) });
}
const contests = payloads.flatMap(entry => entry.data.contests || []);
const updatedAt = payloads.map(entry => entry.data.meta?.generated_at || '').filter(Boolean).sort().pop() || nowSeoulIso();

/* 2) 상태·분야 계산 ------------------------------------------------------ */
const decorated = contests
  .map(contest => decorate(contest, { today, categories: config.categories }))
  .filter(contest => contest.bucket !== 'archived');

const stats = {
  total: decorated.length,
  domestic: decorated.filter(item => item.region === 'domestic').length,
  overseas: decorated.filter(item => item.region === 'overseas').length,
  open: decorated.filter(item => item.bucket === 'open').length,
  upcoming: decorated.filter(item => item.bucket === 'upcoming').length,
  urgent: decorated.filter(item => item.bucket === 'open' && item.daysLeft !== null && item.daysLeft >= 0 && item.daysLeft <= 7).length,
  buckets: Object.fromEntries(BUCKETS.map(bucket => [bucket.key, decorated.filter(item => item.bucket === bucket.key).length]))
};

/* 자바스크립트가 꺼져 있어도 보이는 기본 목록: 접수중 · 마감 임박순 */
const ssrList = decorated
  .filter(item => item.bucket === 'open')
  .sort((a, b) => compare(a, b, 'deadline'));

/* 3) 자산 복사 ----------------------------------------------------------- */
await mkdir(join(ROOT, 'assets'), { recursive: true });
const toBrowser = source => source.replace(/from '\.\/(\w+)\.mjs'/g, "from './$1.js'");

await writeFile(join(ROOT, 'assets/app.css'), await readFile(join(ROOT, 'src/assets/app.css'), 'utf8'));
await writeFile(join(ROOT, 'assets/app.js'), toBrowser(await readFile(join(ROOT, 'src/assets/app.js'), 'utf8')));
await writeFile(join(ROOT, 'assets/contests.js'), toBrowser(await readFile(join(ROOT, 'src/lib/contests.mjs'), 'utf8')));
await writeFile(join(ROOT, 'assets/card.js'), toBrowser(await readFile(join(ROOT, 'src/lib/card.mjs'), 'utf8')));
await writeFile(join(ROOT, 'assets/export.js'), toBrowser(await readFile(join(ROOT, 'src/lib/export.mjs'), 'utf8')));

/* 4) 페이지 생성 --------------------------------------------------------- */
const html = renderPage({ config, contests: decorated, ssrList, stats, today, updatedAt });
await writeFile(join(ROOT, 'index.html'), html, 'utf8');
await writeFile(join(ROOT, 'sitemap.xml'), renderSitemap(config, updatedAt), 'utf8');
await writeFile(join(ROOT, 'llms.txt'), renderLlmsTxt(config, stats, updatedAt), 'utf8');
await writeFile(join(ROOT, '.nojekyll'), '', 'utf8');

console.log(`빌드 완료 (기준일 ${today})`);
console.log(`  전체 ${stats.total}건 / 접수중 ${stats.open} · 곧 시작 ${stats.upcoming} · 결과 대기 ${stats.buckets.closed} · 발표 완료 ${stats.buckets.published}`);
console.log(`  index.html ${(html.length / 1024).toFixed(0)}KB`);
