# 데이터 입력 규칙

이 폴더의 JSON이 **원본(source of truth)** 입니다. `index.html` 은 여기서 만들어집니다.

## 파일

| 파일 | 대상 | region 값 |
|---|---|---|
| `contests.json` | 국내 공모전 | `domestic` |
| `overseas-contests.json` | 해외 공모전 | `overseas` |

## 구조

```json
{
  "meta": { "region": "domestic", "label": "국내", "generated_at": "...", "synced_at": "...", "notice": "...", "credit": { } },
  "contests": [ { "id": "...", "title": "..." } ]
}
```

## 필드

| 필드 | 필수 | 형식 | 설명 |
|---|---|---|---|
| `id` | ✅ | 문자열 | 카드 주소(#앵커). 중복 금지 |
| `region` | ✅ | `domestic` \| `overseas` | 파일의 `meta.region` 과 같아야 함 |
| `title` | ✅ | 문자열 | 공고 제목. **원문 그대로** |
| `category` | ✅ | 문자열 | 예: `AI 영상`, `AI 이미지·영상`, `AI 디자인`, `생성형 AI` |
| `organizer` | ✅ | 문자열 | 주최기관 |
| `submission_start` | 권장 | `YYYY-MM-DD` | 접수 시작 |
| `submission_end` | 권장 | `YYYY-MM-DD` | 접수 마감 |
| `result_date` | 선택 | 자유 문자열 | **원문 표기 그대로**(예: `2026-11 중 예정`, `미정`) |
| `url` | 권장 | `https://...` | 공고 원문. http/https 만 허용 |
| `source_type` | 권장 | 아래 표 참고 | 배지 색이 달라짐 |
| `summary` | 선택 | 한 줄 | 탐색용 소개 |
| `evidence` | 선택 | 문자열 | 어디서 확인했는지 |
| `source_checked_at` | 선택 | ISO 날짜시각 | 출처 확인 시각 |
| `results_confirmed` | 선택 | `true` | 결과 발표를 **실제 확인**한 경우만 |
| `results_published_at` | 선택 | `YYYY-MM-DD` | 발표 확인일. `results_confirmed` 와 **함께** 있어야 함 |
| `results_url` | 선택 | `https://...` | 발표 페이지 |

### `source_type` 값

| 값 | 화면 배지 | 의미 |
|---|---|---|
| `official_notice` | 공식 공고 (초록) | 주최기관 공고문 |
| `official_homepage` | 공식 홈페이지 (초록) | 주최기관 홈페이지 |
| `official_apply_page` | 공식 접수 페이지 (초록) | 접수 페이지 |
| `official_platform` | 공식 접수 플랫폼 (초록) | 지정 접수 플랫폼 |
| `reference_link` | 참고 링크 (주황) | 공식 확인이 안 된 링크 |

## 상태(탭)는 자동 계산됩니다 — 직접 쓰지 마세요

| 탭 | 조건 (오늘 = Asia/Seoul 기준) |
|---|---|
| 접수중 | `submission_start` ≤ 오늘 ≤ `submission_end` |
| 곧 시작 | 오늘 < `submission_start` |
| 결과 대기 | `submission_end` < 오늘 이고 발표 미확인 |
| 발표 완료 | `results_confirmed: true` **그리고** `results_published_at` 이 14일 이내 |
| (목록 제외) | 발표 확인 후 14일이 지난 공고 |

## 지켜야 할 것

- [ ] 없는 정보를 **추측해서 채우지 않습니다.** 비워 두면 화면에 `정보 없음` 으로 표시됩니다.
- [ ] 날짜는 `YYYY-MM-DD` 형식만 사용합니다(검사에서 걸러집니다).
- [ ] `submission_start` 는 `submission_end` 보다 뒤일 수 없습니다.
- [ ] 고친 뒤 반드시 `node --test tests/run.mjs` 를 실행합니다.
