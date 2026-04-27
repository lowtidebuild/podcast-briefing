# ENGINEERING_AUDIT_IMPLEMENTATION_PLAN 검증 보고서

검증일: 2026-04-27
검증 대상: [ENGINEERING_AUDIT_IMPLEMENTATION_PLAN.md](ENGINEERING_AUDIT_IMPLEMENTATION_PLAN.md) (Codex 작성)
검증 방법: 기획서의 모든 사실 주장과 코드 인용을 실제 저장소 상태와 1:1 대조

---

## 0. 한 줄 결론

**전반적으로 신뢰할 만한 기획서다.** 검증한 사실 주장 대부분이 코드와 일치하고, 우선순위(P0 = 발행 게이트)도 실제 가장 큰 위험을 정확히 짚었다. 다만 **이미 부분적으로 구현된 기능을 새로 만든다고 가정한 부분**, **데이터 분포상 영향이 작은 규칙**, **누락된 추가 결함 1~2건**이 있어 그대로 5단계를 순차 실행하기보다는 아래 정정 사항을 반영해 우선순위를 재배열하는 것을 권장한다.

신뢰도 점수: **8.5 / 10** (사실 정확성 9.5, 처방의 타당성 8, 우선순위 8.5, 누락 발견 7)

---

## 1. 사실 주장 검증 결과

### 1.1 정확한 주장 (코드와 일치)

| # | 기획서 주장 | 검증 결과 | 근거 |
|---|---|---|---|
| 1 | `summarize.py`가 80,000자 초과 시 앞뒤 40,000자만 남기고 중간 누락 | ✅ 일치 | [pipeline/summarize.py:112-117](pipeline/summarize.py#L112-L117) |
| 2 | `_parse_summary`가 JSON 파싱 성공 여부만 확인, 필드 검증 없음 | ✅ 일치 | [pipeline/summarize.py:195-216](pipeline/summarize.py#L195-L216) |
| 3 | retry 소진 시 빈 dict fallback을 반환해 그대로 발행됨 | ✅ 일치 | [pipeline/summarize.py:180-192](pipeline/summarize.py#L180-L192) |
| 4 | `main.py`가 요약 결과를 검증 없이 `generate_episode_json` → `append_episode` → `state["processed"]`로 전달 | ✅ 일치 | [pipeline/main.py:59-72](pipeline/main.py#L59-L72) |
| 5 | 실패 사례 `2026-03-11-lex-fridman-podcast.json`에 JSON 조각이 `summary_ko`에 들어가 있음 | ✅ 일치. `summary_ko`가 `'{\n  "guest": {...'`로 시작, 나머지 필드는 모두 빈값 | grep / json.load |
| 6 | 실패 사례 `2026-04-14-ezra-klein-show.json`에 거의 모든 필드가 비어 있음 | ✅ 일치. summary_ko/en, key_points, keywords, quote 모두 비어 있음 | json.load |
| 7 | 전사문 58개, 평균 ~59,000자, 80,000자 초과 10개 | ✅ 일치 (실측: 58개, 59,136자, 10개) | os.path.getsize |
| 8 | 정적 프롬프트 ~4,954자 | ✅ 거의 일치 (실측 4,905~4,966자) | regex 추출 후 측정 |
| 9 | GitHub Actions의 `Run pipeline` 단계에 `continue-on-error: true` | ✅ 일치 | [.github/workflows/daily-briefing.yml:37](.github/workflows/daily-briefing.yml#L37) |
| 10 | 워크플로우가 `npm install`을 사용하고 `package-lock.json`을 무시 | ✅ 일치. lock 파일은 존재 | [.github/workflows/daily-briefing.yml:57](.github/workflows/daily-briefing.yml#L57) |
| 11 | `requirements.txt`가 `>=`만 사용, 상한 없음 | ✅ 일치 | [requirements.txt](requirements.txt) |
| 12 | `index.astro`와 `archive.astro`가 동일한 데이터 로딩 코드 중복 | ✅ 일치. `readdirSync` → `JSON.parse` → `transcriptMap` 빌드까지 거의 동일 | [web/src/pages/index.astro:8-15](web/src/pages/index.astro#L8-L15), [web/src/pages/archive.astro:7-15](web/src/pages/archive.astro#L7-L15) |
| 13 | Astro가 transcript 전문을 `<script type="application/json">` 안에 inline | ✅ 일치 | [web/src/components/EpisodeCard.astro:180](web/src/components/EpisodeCard.astro#L180) |
| 14 | Obsidian Markdown 다운로드가 brief가 아니라 transcript 중심 | ✅ 일치. frontmatter + 제목 + transcript 본문이며 summary/key_points는 빠져 있음 | [web/src/components/EpisodeCard.astro:67-82](web/src/components/EpisodeCard.astro#L67-L82) |
| 15 | Google Sheets에 summary 전문(EN/KO)을 그대로 append | ✅ 일치 | [pipeline/sheets.py:88-89](pipeline/sheets.py#L88-L89) |
| 16 | `make_slug()`가 파일 존재 여부로 suffix를 부여 → 재실행 시 비결정적 | ✅ 일치. transcript 저장과 summary 저장에서 각각 `make_slug` 호출 | [pipeline/generate_output.py:18-35](pipeline/generate_output.py#L18-L35), [pipeline/main.py:52](pipeline/main.py#L52) |
| 17 | 프롬프트 예시 JSON에 `_key_points_note` 비스키마 필드 존재 | ✅ 일치 | [pipeline/summarize.py:77](pipeline/summarize.py#L77) |
| 18 | "The Economist style" 같은 브랜드 지시 사용 | ✅ 일치 (line 21: "in the style of The Economist") | [pipeline/summarize.py:21](pipeline/summarize.py#L21) |
| 19 | Gemini 호출은 `response_mime_type="application/json"`만 쓰고 schema config 미사용, Claude는 구조화 출력 모드를 쓰지 않음 | ✅ 일치 | [pipeline/summarize.py:127-150](pipeline/summarize.py#L127-L150) |

### 1.2 부분적으로 부정확하거나 뉘앙스가 다른 주장

| # | 기획서 주장 | 실제 상태 | 영향 |
|---|---|---|---|
| A | "Sheets에 전체 영어/한국어 요약을 그대로 append한다" (6.3) | 사실이지만 누락된 점: [pipeline/sheets.py:68-76](pipeline/sheets.py#L68-L76)는 **이미 SUMMARY FAILED 검출 로직을 갖고 있다**. `summary_en`이 50자 미만이거나 `summary_ko`가 `{`로 시작하면 ⚠️ 마커를 단다. | 이는 "Sheets 경량화"보다 **이미 sheets.py가 알고 있는 검증 로직을 main.py로 끌어올리기만 해도 P0의 90%가 해결된다**는 뜻. 기획서가 이 부분을 모르고 신규 `quality.py`를 새로 짓는 것처럼 서술한 것은 약점. |
| B | "_key_points_note 같은 메타 필드가 결과 JSON에 들어오면 테스트가 실패한다" (P0 완료 기준) | 현재 `data/summaries/*.json` 57개 중 `_key_points_note`가 들어 있는 파일은 **0개**. | 위험은 실재하지만 발생률은 낮다. 이 규칙을 P0 차단 사유로 두는 것은 과한 면이 있다. WARN 단계로 둬도 됨. |
| C | "key point KO/EN mismatch", "kw 4-6 위반"을 검증 규칙으로 둠 (2.4) | 현재 정상 발행 55건 중 KO/EN 키포인트 개수 mismatch 0건, 키워드 개수 4-6 위반 0건. | 규칙 자체는 옳지만 **현재 데이터에서 차단 대상이 없다**. 이 규칙이 새로 막는 케이스는 0이고, 의의는 회귀 방지뿐. P0 우선순위에서 끌어내려도 됨. |
| D | "실패한 에피소드도 `processed`에 들어가 자동 재처리가 막힌다" (1장) | 절반만 사실. **요약 파싱 실패(빈 dict fallback)** 시는 정확히 그렇다 — `state["processed"]`에 들어간다. **다운로드/전사 단계의 예외**는 [pipeline/main.py:80-87](pipeline/main.py#L80-L87) try/except 때문에 `processed` 추가 전에 빠진다(즉 자동 재시도 가능). | 둘을 분리해서 서술해야 정확함. P0 게이트는 "summary 실패 케이스"에만 추가 가치를 준다. |
| E | "평균 입력 약 14,800 tokens 추정" (4.1) | 4 chars/token 가정 기반. 영어 우세 transcript에서는 18,000-22,000 tokens가 더 정확. | 비용 절감 **잠재력**이 기획서가 말한 것보다 **더 크다**. 전사문이 길수록 chunking 효과 큼. |
| F | "GitHub Actions가 파이프라인 실패를 무시하고 배포를 계속한다" (1장) | 정확하지만 또 다른 결함도 있음: workflow가 빌드 실패 시 git commit/push까지 한 뒤 deploy를 시도 (조건문 없음). 즉 코드 빌드 실패 = 부분 commit + deploy 실패의 혼합 상태. | 5.1의 exit code 분류만으로는 부족. job step 간 실패 격리도 필요. |

### 1.3 검증되지 않은 주장 (실측 불가/외부 의존)

| # | 주장 | 비고 |
|---|---|---|
| - | "Hard Fork, All-In, Odd Lots는 다중 주제이므로 중간 누락이 특히 위험" (3.1) | 일반적 도메인 지식. 검증 불가하나 합리적. |
| - | chunk extraction 도입 시 입력 토큰 60-80% 감소 가능 (3.1, 4.4) | 미실측. 다만 80,000자 초과 transcript 10개 분포상 **상한 절감 폭이 50% 이상**임은 산수상 가능. |
| - | quote grounding pass rate 90% 가능 (11) | 데이터 없음. fuzzy match 임계값에 따라 달라짐. |

---

## 2. 처방(권장 구현)에 대한 평가

### 2.1 Phase 1 (P0 품질 게이트) — **★★★★★ 즉시 시행 권장**

- 진단과 처방 모두 정확.
- 다만 신규 `pipeline/quality.py`를 처음부터 만들기보다 **`pipeline/sheets.py`의 기존 failure 검출 로직(`has_en`, `has_ko` 체크)을 추출해 모듈화**하는 편이 더 작고 안전한 1차 PR이 된다.
- `Pydantic`은 이미 `requirements.txt`에 없음 → 의존성 추가 필요. 기획서에 명시되지 않음.
- 실패 fixture로 `2026-03-11-lex-fridman-podcast.json`, `2026-04-14-ezra-klein-show.json`을 그대로 쓰면 빠르게 시작 가능.

### 2.2 Phase 2 (quote grounding) — ★★★★ 가치 높음, 난이도 중

- `is_verbatim` flag 도입은 사용자 신뢰도 큰 효과.
- 다만 fuzzy matching 구현 시 한국어 quote는 transcript에 없음(영어 transcript). KO quote는 항상 model paraphrase가 됨 → KO만 별도 정책 필요.
- 기획서가 이 점을 명시하지 않음. **추가 필요 사항**: `notable_quote_ko.is_verbatim`은 항상 false거나, `text_en`을 grounding 대상으로 하고 `text_ko`는 번역 표시.

### 2.3 Phase 3 (chunk extraction + 캐시) — ★★★★ 가치 높음, 난이도 높

- 80,000자 초과 transcript 10건 = 총 58건의 17%. 비용 절감 효과 실재.
- 캐시 키에 `extraction_prompt_version`을 넣은 설계는 정확.
- **추가 위험**: chunk extraction 단계가 새로 추가되면 LLM 호출 횟수가 chunk 수만큼 증가. 250,066자(최대 transcript) 기준 chunk 8-12k tokens면 ~6 chunks → 호출 6회. retry 정책이 없으면 실패 확률은 합쳐서 더 높아질 수 있다. 기획서가 chunk extraction 자체의 실패 처리를 다루지 않음.

### 2.4 Phase 4 (publishing 구조) — ★★★ 가치 중, 난이도 낮

- transcript inline 제거: HTML 크기 절감 효과 정량화 권장. 빌드 산출물이 큰 이유는 거의 전적으로 이 inline 때문.
- 기획서의 P1/P2/P3 점진 단계는 합리적.
- **추가**: `data/transcripts/*.txt`가 git에 그대로 commit되고 있음. 공개 transcript 제거 정책은 git 이력까지 고려해야 한다(저작권 리스크). 기획서가 이 부분을 명시하지 않음.

### 2.5 Phase 5 (CI/CD) — ★★★★★ 가장 작은 PR로 가장 큰 안정성 향상

- `continue-on-error: true` 제거 + `npm ci` 도입 = 1줄, 1줄 변경. 즉시 효과.
- exit code 분류는 좋으나 1차 PR에서는 `set -e`만 살려도 충분.

---

## 3. 기획서가 누락한 결함

### 3.1 `audio_path` 미정의 NameError 위험

[pipeline/main.py:80-87](pipeline/main.py#L80-L87)의 `except` 블록에서 `cleanup_audio(audio_path)`를 호출하지만, `download_audio` 호출 자체가 실패하면 `audio_path`가 정의되지 않은 상태다. 두 번째 `try/except`가 잡아주긴 하지만 실제 첫 예외의 cleanup 의도는 무산된다. P0 게이트 PR에서 같이 수정 가능.

### 3.2 `make_slug()`가 동일 실행 내에서도 2회 호출

`main.py`는 transcript 저장 시 [pipeline/main.py:52](pipeline/main.py#L52) `make_slug(ep)`를 호출하고, 그 후 [pipeline/generate_output.py:42](pipeline/generate_output.py#L42)의 `generate_episode_json`이 다시 `make_slug(ep)`를 호출한다. 그 사이에 동일 podcast의 다른 에피소드가 동일 날짜로 처리되면 **transcript는 `xxx.txt`로, summary는 `xxx-2.json`으로 저장**될 수 있다. 5.3에서 deterministic slug를 다루지만 이 dual-call 패턴은 직접 언급하지 않음.

### 3.3 `rebuild_feed_index()`의 silent JSON decode error 무시

[pipeline/generate_output.py:94-95](pipeline/generate_output.py#L94-L95)는 손상된 JSON 파일을 만나면 조용히 건너뛴다. 실패 artifact 격리 정책(P0)을 도입하면 이 catch는 더 이상 필요 없으나, 그 전까지는 진단을 어렵게 만든다.

### 3.4 Sheets append 실패 후 state 동기화 문제

[pipeline/sheets.py:97-98](pipeline/sheets.py#L97-L98)는 모든 예외를 swallow한 뒤 정상 흐름이 이어진다. 그러나 [pipeline/main.py:71](pipeline/main.py#L71)의 `state["processed"].append`는 그 이후에 실행된다. 즉 **Sheets append 실패는 영구적으로 묵살된다**(다음 실행에서 재시도 안 됨). 5.4의 state 확장이 이를 다루나, "publish_failed" 상태가 Sheets 실패도 포함한다는 점을 명시하면 더 좋다.

### 3.5 SUMMARY_PROMPT의 `summary_ko` 길이 지시가 자기모순적

[pipeline/summarize.py:69](pipeline/summarize.py#L69)는 `200-300 words` (Korean), `350-450 words`, `450-600 words`로 분기한다. **한국어는 word 단위로 측정하기 곤란**(공백 없는 단어 경계). 모델이 어떻게 해석하든 일관성이 떨어진다. 7.4 "브랜드 스타일 제거"에서 함께 다루면 좋다.

### 3.6 `summarize_episode`의 fallback이 invalid한 dict를 return

기획서 1장에서 "fallback도 정상 흐름으로 들어간다"고 정확히 지적했지만, **fallback dict 자체가 schema-valid한 것처럼 보인다**(필드 개수가 같음)는 점이 더 위험하다. P0에서 fallback을 None 반환으로 바꾸는 편이 의도가 명확하다.

---

## 4. 기획서의 우선순위에 대한 재배열 권장

기획서는 P0 → P1 → P2 → P3 → P4 → P5 (CI/CD를 마지막)로 둔다. 검증 결과를 보면 다음 재배열이 더 나은 가성비를 낸다.

### 권장 순서

```
PR 1 (1일):
  - .github/workflows/daily-briefing.yml: continue-on-error 제거 + npm ci
  - main.py: audio_path NameError 수정
  - 즉시 효과: 다음 실패 사이클이 사이트에 발행되지 않음

PR 2 (P0, 3-5일):
  - sheets.py의 has_en/has_ko 검출 로직을 pipeline/quality.py로 추출
  - main.py에 validation gate 추가
  - 실패 artifact를 data/failures/로 분리
  - 기존 2건 fixture 기반 테스트
  - Pydantic 의존성 추가 (필요 시)

PR 3 (Phase 4 일부, 1-2일):
  - index.astro/archive.astro 데이터 로딩 중복 제거 (헬퍼 추출)
  - transcript inline 제거 + lazy fetch 전환

PR 4 (Phase 3 chunk extraction):
  - 비용 효과 큰 80,000자 초과 10건에만 적용해도 되는지 결정
  - cache 키 설계 + extraction prompt 분리

PR 5 (Phase 2 quote grounding):
  - KO quote는 grounding 대상에서 제외 처리 명시
  - is_verbatim flag와 UI 분기

PR 6 (Phase 5 나머지):
  - state 구조 확장
  - regression metrics report
```

요약: **기획서의 Phase 5 일부(워크플로우 1줄 수정)를 Phase 1 앞으로 끌어오고**, **기존 sheets.py의 검증 로직을 활용**하면 P0의 코드량이 절반 이하로 줄어든다.

---

## 5. 채택 권고

| 영역 | 평가 |
|---|---|
| 사실 정확성 | 매우 높음. 인용한 코드/숫자가 실제와 일치. |
| 처방 타당성 | 높음. 다만 일부는 이미 구현된 로직을 새로 짓는 것처럼 묘사. |
| 우선순위 | 대체로 정확. CI/CD를 마지막에 둔 것은 가성비상 부적절. |
| 누락 | 6건의 추가 결함을 본 보고서에서 보강. |
| 안전한 채택 방식 | **기획서의 P0를 기본으로 하되, 본 보고서 §4의 PR 분할 순서로 실행** |

**결론: Codex 기획서는 대부분 채택해도 좋다.** 본 검증 보고서의 §1.2(부정확/뉘앙스), §3(누락 결함), §4(우선순위 재배열)을 머지해 보완 기획서로 쓰면 된다.
