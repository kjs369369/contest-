/**
 * 의존성 없는 테스트. 실행: node --test tests/
 * 데이터나 로직을 고친 뒤 반드시 한 번 돌려 주세요.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { ROOT, stableId, safeUrl, escapeJson, seoulDate } from '../src/lib/util.mjs';
import { bucketOf, daysLeft, decorate, matchesQuery, toChosung, compare, categoryKeys, urgency } from '../src/lib/contests.mjs';
import { cardHtml, esc, safeHref, progress } from '../src/lib/card.mjs';

const config = JSON.parse(readFileSync(join(ROOT, 'config/site.json'), 'utf8'));
const categories = config.categories;
const TODAY = '2026-09-14';

const base = {
  id: 'test-1', region: 'domestic', title: '테스트 AI 영상 공모전', organizer: '메이랜드',
  category: 'AI 영상', submission_start: '2026-09-01', submission_end: '2026-09-30',
  result_date: '2026-10 중 예정', url: 'https://example.com/notice', source_type: 'official_notice',
  summary: '요약', evidence: '근거', status: '진행중', source_checked_at: '2026-09-13T19:00:00+09:00'
};

test('상태: 접수 기간 안이면 접수중', () => {
  assert.equal(bucketOf(base, TODAY), 'open');
});

test('상태: 시작 전이면 곧 시작', () => {
  assert.equal(bucketOf({ ...base, submission_start: '2026-10-01', submission_end: '2026-10-31' }, TODAY), 'upcoming');
});

test('상태: 마감 후이고 결과 미확인이면 결과 대기', () => {
  assert.equal(bucketOf({ ...base, submission_start: '2026-07-01', submission_end: '2026-08-01' }, TODAY), 'closed');
});

test('상태: 발표 확인 14일 이내는 발표 완료, 그 뒤는 목록에서 제외', () => {
  const published = { ...base, results_confirmed: true, results_published_at: '2026-09-10' };
  assert.equal(bucketOf(published, TODAY), 'published');
  assert.equal(bucketOf({ ...published, results_published_at: '2026-08-01' }, TODAY), 'archived');
});

test('상태: 발표 확인 표시만 있고 날짜가 없으면 발표 완료로 올리지 않는다', () => {
  assert.equal(bucketOf({ ...base, results_confirmed: true, submission_end: '2026-08-01' }, TODAY), 'closed');
});

test('D-day 계산', () => {
  assert.equal(daysLeft('2026-09-30', TODAY), 16);
  assert.equal(daysLeft('2026-09-14', TODAY), 0);
  assert.equal(daysLeft('미정', TODAY), null);
});

test('긴급도 단계', () => {
  assert.equal(urgency(0), 'critical');
  assert.equal(urgency(3), 'critical');
  assert.equal(urgency(7), 'soon');
  assert.equal(urgency(31), 'far');
  assert.equal(urgency(null), 'none');
});

test('분야 분류: 복합 분야는 두 필터에 모두 들어간다', () => {
  assert.deepEqual(categoryKeys({ category: 'AI 이미지·영상' }, categories), ['image', 'video']);
  assert.deepEqual(categoryKeys({ category: '생성형 AI' }, categories), ['etc']);
  assert.deepEqual(categoryKeys({ category: '알 수 없음' }, categories), ['etc']);
});

test('검색: 한글·영문·초성 모두 찾는다', () => {
  const item = decorate(base, { today: TODAY, categories });
  assert.ok(matchesQuery(item, '영상'));
  assert.ok(matchesQuery(item, '메이랜드'));
  assert.ok(matchesQuery(item, 'ㅌㅅㅌ'));
  assert.ok(!matchesQuery(item, '없는단어'));
});

test('초성 변환', () => {
  assert.equal(toChosung('공모전'), 'ㄱㅁㅈ');
  assert.equal(toChosung('AI 영상'), 'ai ㅇㅅ');
});

test('정렬: 마감 임박순이 기본', () => {
  const a = decorate({ ...base, submission_end: '2026-09-20' }, { today: TODAY, categories });
  const b = decorate({ ...base, submission_end: '2026-09-18' }, { today: TODAY, categories });
  assert.ok(compare(a, b, 'deadline') > 0);
  assert.ok(compare(b, a, 'deadline') < 0);
});

test('보안: 링크는 http/https만 통과한다', () => {
  assert.equal(safeUrl('javascript:alert(1)'), '');
  assert.equal(safeHref('data:text/html,<script>'), '');
  assert.equal(safeHref('https://example.com'), 'https://example.com');
});

test('보안: 카드 렌더링은 HTML을 이스케이프한다', () => {
  const evil = decorate({
    ...base,
    title: '<img src=x onerror=alert(1)>',
    organizer: '"><script>alert(2)</script>',
    url: 'javascript:alert(3)'
  }, { today: TODAY, categories });
  const html = cardHtml(evil, { today: TODAY });
  assert.ok(!html.includes('<img src=x'));
  assert.ok(!html.includes('<script>'));
  assert.ok(!html.includes('javascript:'));
  assert.ok(html.includes('&lt;img'));
});

test('보안: JSON 임베딩은 </script> 를 깨뜨리지 않는다', () => {
  assert.ok(!escapeJson({ x: '</script>' }).includes('</script>'));
});

test('카드: 값이 없으면 추측하지 않고 정보 없음으로 표기', () => {
  const bare = decorate({ id: 'x', title: '무제', category: '', organizer: '', submission_start: '', submission_end: '', result_date: '', url: '' }, { today: TODAY, categories });
  const html = cardHtml(bare, { today: TODAY });
  assert.ok(html.includes('정보 없음'));
  assert.ok(html.includes('주최기관 미확인'));
  assert.ok(html.includes('원문 링크 없음'));
});

test('진행바: 접수 기간의 경과 비율', () => {
  assert.equal(progress({ submission_start: '2026-09-01', submission_end: '2026-09-11' }, '2026-09-06'), 50);
  assert.equal(progress({ submission_start: '미정', submission_end: '2026-09-11' }, '2026-09-06'), null);
});

test('ID는 같은 입력에 항상 같은 값', () => {
  assert.equal(stableId('가', '2026-01-01'), stableId('가', '2026-01-01'));
  assert.notEqual(stableId('가', '2026-01-01'), stableId('나', '2026-01-01'));
});

test('이스케이프 기본 동작', () => {
  assert.equal(esc('<a>&"\''), '&lt;a&gt;&amp;&quot;&#39;');
});

test('오늘 날짜는 서울 기준 YYYY-MM-DD', () => {
  assert.match(seoulDate(), /^\d{4}-\d{2}-\d{2}$/);
});

/* ---------- 실제 데이터 검증 ---------- */
for (const source of config.dataSources) {
  const payload = JSON.parse(readFileSync(join(ROOT, source.file), 'utf8'));

  test(`데이터(${source.label}): 필수 필드와 날짜 형식`, () => {
    assert.ok(Array.isArray(payload.contests) && payload.contests.length > 0);
    const ids = new Set();
    for (const contest of payload.contests) {
      assert.ok(contest.id, `id 없음: ${contest.title}`);
      assert.ok(!ids.has(contest.id), `id 중복: ${contest.id}`);
      ids.add(contest.id);
      assert.ok(contest.title, 'title 없음');
      assert.equal(contest.region, source.region);
      for (const key of ['submission_start', 'submission_end']) {
        if (contest[key]) assert.match(contest[key], /^\d{4}-\d{2}-\d{2}$/, `${key} 형식 오류: ${contest.title}`);
      }
      if (contest.url) assert.ok(safeUrl(contest.url), `허용되지 않는 링크: ${contest.url}`);
    }
  });

  test(`데이터(${source.label}): 접수 시작이 마감보다 늦지 않다`, () => {
    for (const contest of payload.contests) {
      if (contest.submission_start && contest.submission_end) {
        assert.ok(contest.submission_start <= contest.submission_end, `기간 역전: ${contest.title}`);
      }
    }
  });
}

test('생성된 index.html 검증', () => {
  const html = readFileSync(join(ROOT, 'index.html'), 'utf8');
  assert.ok(html.includes('<html lang="ko">'));
  assert.ok(html.includes('id="board-data"'));
  assert.ok(html.includes('assets/app.js'));
  assert.ok(html.includes('application/ld+json'));
  assert.ok(!/href="javascript:/i.test(html));
  const data = JSON.parse(html.split('id="board-data">')[1].split('</script>')[0]);
  assert.ok(data.contests.length > 100);
  assert.match(data.today, /^\d{4}-\d{2}-\d{2}$/);
});
