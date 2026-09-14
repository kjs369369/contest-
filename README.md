# AI 공모전 한눈에

국내·해외 **AI 공모전**을 한 페이지에서 찾고, 관심 공고를 저장하고, 마감일을 달력에 넣는 정적 웹보드입니다.
외부 패키지 **의존성 0개**(Node 20 이상 + 브라우저만 필요)라 버전 충돌이 생기지 않습니다.

- 공개 주소(배포 후): <https://kjs369369.github.io/contest-/>
- 벤치마크 원본: [AI Contest Board (junyeo217)](https://junyeo217.github.io/ai-contest-board/)

---

## 1. 핵심 요약

| 구분 | 내용 |
|---|---|
| 무엇 | 국내 179건 + 해외 55건의 AI 공모전을 **마감 임박순**으로 보여주는 1페이지 사이트 |
| 누구 | AI 공모전에 처음 도전하는 40~60대 비전공 수강생, 강의 실습용 |
| 어떻게 | JSON 파일만 고치면 화면이 바뀜. 서버·데이터베이스·로그인 없음 |
| 배포 | GitHub Pages (main 브랜치 푸시 또는 매일 00:10 자동 재빌드) |
| 비용 | 0원 |

## 2. 벤치마크 대비 개선점

| 항목 | 원본 보드 | 이 보드 |
|---|---|---|
| 국내/해외 | 페이지 2개로 분리 | **한 페이지 + 지역 버튼** |
| 접수 예정 공고 | 숨김 | **‘곧 시작’ 탭**으로 미리 준비 |
| 마감 표시 | 글자 | **D-day 색상 배지 + 진행바**(3일 이내 빨강, 7일 이내 주황) |
| 글자 크기 | 고정 15px | **17px 기본 + 보통/크게/아주 크게 3단 전환**(선택 저장) |
| 화면 모드 | 밝은 화면만 | **다크 모드**(시스템 연동 + 수동 전환) |
| 관심 공고 | 없음 | **★ 관심 저장 + 관심만 보기**(브라우저에만 저장) |
| 마감 알림 | 없음 | **달력 파일(.ics) 저장** — 마감 3일 전 알림 자동 등록 |
| 내보내기 | 없음 | **엑셀(CSV) 저장 · 인쇄용 레이아웃** |
| 검색 | 한글·영문 | **초성 검색**(예: `ㄱㅁㅈ` → 공모전) + **검색어 하이라이트** |
| 공유 | 없음 | **링크 복사 / 모바일 공유** |
| 데이터 형식 | 상태별 중첩(sections) | **평면 목록(contests 배열)** — 손으로 고치기 쉬움 |
| 검색·AI 노출 | 기본 | **구조화 데이터(Event·FAQ·WebSite) + llms.txt + sitemap** |

## 3. 3분 만에 시작하기

```sh
node src/build.mjs          # 1) 사이트 생성 (index.html, assets/)
node --test tests/run.mjs   # 2) 검사 24개 통과 확인
python3 -m http.server 8080 # 3) 미리보기 → http://localhost:8080
```

| 명령 | 하는 일 |
|---|---|
| `npm run build` | `index.html`, `assets/`, `sitemap.xml`, `llms.txt` 생성 |
| `npm test` | 상태 판정·검색·보안·데이터 형식 검사 |
| `npm run sync` | 외부 공개 데이터에서 공모전 목록 갱신 |
| `npm run check` | 갱신하면 몇 건이 되는지만 확인(파일 안 씀) |
| `BOARD_DATE=2026-10-01 npm run build` | 기준일을 고정해서 빌드(테스트용) |

## 4. 폴더 구조 (수정 지점이 분리되어 있습니다)

```
contest-/
├── config/site.json          ← ① 사이트 이름·문구·분야·주소 (여기만 고치면 전체 반영)
├── data/
│   ├── contests.json         ← ② 국내 공모전 목록
│   ├── overseas-contests.json← ② 해외 공모전 목록
│   └── README.md                데이터 입력 규칙
├── src/
│   ├── build.mjs                빌드 진입점
│   ├── lib/
│   │   ├── contests.mjs         상태·D-day·검색 규칙  (브라우저와 공유)
│   │   ├── card.mjs             공모전 카드 HTML      (브라우저와 공유)
│   │   ├── render.mjs        ← ③ 페이지 문구·FAQ·구조화 데이터
│   │   └── util.mjs             공용 유틸(날짜·이스케이프)
│   └── assets/
│       ├── app.css           ← ④ 디자인(색은 :root 변수만 고치면 됨)
│       └── app.js               화면 동작(필터·저장·내보내기)
├── scripts/sync-upstream.mjs    외부 데이터 갱신
├── tests/run.mjs                검사 24개
├── .github/workflows/pages.yml  자동 빌드·배포
└── index.html, assets/, sitemap.xml, llms.txt   ← 빌드 생성물(직접 고치지 마세요)
```

> **중요:** `index.html`과 `assets/` 는 빌드 결과물입니다. 직접 고치면 다음 빌드에서 사라집니다.
> 내용은 `data/`, 문구는 `src/lib/render.mjs`, 디자인은 `src/assets/app.css` 에서 고치세요.

## 5. 공모전 추가·수정하는 법

`data/contests.json` 의 `contests` 배열에 아래 형태로 넣고 `npm run build` 만 하면 끝입니다.

```json
{
  "id": "c-직접지정",
  "region": "domestic",
  "title": "2026 OO시 AI 영상 공모전",
  "category": "AI 영상",
  "organizer": "OO시청",
  "submission_start": "2026-10-01",
  "submission_end": "2026-10-31",
  "result_date": "2026-11 중 발표 예정",
  "url": "https://공식공고주소",
  "source_type": "official_notice",
  "summary": "한 줄 소개",
  "evidence": "공식 공고에서 확인한 근거",
  "source_checked_at": "2026-09-14T10:00:00+09:00"
}
```

필드 설명과 상태 판정 규칙은 [`data/README.md`](data/README.md) 에 있습니다.

## 6. 편집 원칙 (지키지 않으면 신뢰를 잃습니다)

- [ ] 날짜·참가비·자격을 **추정하지 않는다.** 확인되지 않으면 비워 두고 화면에는 `정보 없음` 으로 나갑니다.
- [ ] 링크는 **주최기관 공식 출처 우선**. 공식이 아니면 `source_type`을 `reference_link` 로 두어 ‘참고 링크’ 배지가 붙게 합니다.
- [ ] 결과 발표는 **실제 확인**(`results_confirmed: true` + `results_published_at`)된 것만 ‘발표 완료’로 올립니다.
- [ ] 원문의 문구·숫자·명칭을 임의로 바꾸지 않습니다.

## 7. 배포 체크리스트

| 순서 | 할 일 | 확인 |
|---|---|---|
| 1 | `npm run sync` 로 최신 데이터 반영 | 건수 출력 확인 |
| 2 | `npm run build` | 오류 없음 |
| 3 | `npm test` | 24개 전부 통과 |
| 4 | 로컬 미리보기에서 탭·검색·저장 동작 확인 | 정상 |
| 5 | main 브랜치에 푸시 | Actions 성공 |
| 6 | GitHub 저장소 → Settings → Pages → Source를 **GitHub Actions** 로 설정 | 1회만 |
| 7 | 공개 주소 접속 확인 | 목록 표시 |

## 8. 보안·개인정보

- 서버·데이터베이스·로그인·쿠키가 **없습니다.** 정적 파일만 배포합니다.
- 관심 공고는 이용자 **브라우저의 localStorage** 에만 저장되고 외부로 전송되지 않습니다.
- 모든 외부 문자열은 출력 시 HTML 이스케이프하며, 링크는 `http/https` 만 허용합니다(`javascript:` 등 차단). 관련 검사는 `tests/run.mjs` 에 포함되어 있습니다.
- 외부 링크는 `rel="noopener noreferrer"`, `referrer` 정책은 `strict-origin-when-cross-origin` 입니다.
- 저장소에 비밀키·토큰·개인정보를 넣지 마세요. 배포 워크플로는 어떤 시크릿도 사용하지 않습니다.

## 9. 부가 도구

| 도구 | 위치 | 용도 |
|---|---|---|
| 전시회 영상 자동 편집 | `tools/exhibition-video/` | 전시회 사진·영상 폴더 → 전환효과·한글자막·배경음이 들어간 완성 영상 1편 |

본체(정적 웹보드)와 **폴더·가상환경이 완전히 분리**되어 있어 의존성 충돌이 없습니다.
사용법은 [`tools/exhibition-video/README.md`](tools/exhibition-video/README.md) 를 보세요.

## 10. 출처

공모전 사실 정보(명칭·주최·접수기간·원문 링크)의 초기 수집 출처는
[AI Contest Board (junyeo217)](https://junyeo217.github.io/ai-contest-board/) 의 공개 데이터입니다.
갱신은 `scripts/sync-upstream.mjs` 가 같은 공개 JSON을 다시 읽어 수행합니다.
이 보드는 탐색을 돕는 안내이며 주최기관의 공고를 대신하지 않습니다.
