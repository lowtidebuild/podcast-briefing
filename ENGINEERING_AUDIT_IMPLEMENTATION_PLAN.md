# Podcast Briefing 엔지니어링/디자인 감사 기반 구현 기획서

## 0. 목적

이 문서는 현재 Podcast Briefing 에이전트 파이프라인의 감사 결과를 실제 구현 가능한 개선 계획으로 전환하기 위한 기획 문서다. 목표는 단순한 코드 정리가 아니라, 같은 입력으로 더 정확하고 검증 가능한 브리핑을 만들고, 실패 산출물이 공개되지 않도록 하며, 토큰 비용과 운영 리스크를 줄이는 것이다.

이 문서의 핵심 원칙은 다음과 같다.

- 요약이 “JSON으로 파싱된다”는 이유만으로 정상 산출물로 취급하지 않는다.
- 인용문, 핵심 주장, 게스트 정보처럼 신뢰도가 중요한 필드는 근거 검증을 통과해야 한다.
- 긴 전사문 전체를 한 번에 LLM에 넣는 구조를 제거하고, 중간 주제 누락을 막는 단계형 파이프라인으로 바꾼다.
- 공개 사이트에 올릴 데이터와 개인용/검증용 데이터를 분리한다.
- 실패를 조용히 넘기지 않고, 재시도 가능한 상태로 남긴다.

## 0.1 검증 보고서 반영 후 정정 사항

`ENGINEERING_AUDIT_VERIFICATION.md` 검토 결과, 최초 기획서의 큰 방향은 유지하되 구현 순서와 일부 규칙의 강도를 수정한다. 특히 다음 사항은 반드시 반영한다.

- `pipeline/sheets.py`에는 이미 `summary_en` 길이와 `summary_ko` JSON 조각을 감지하는 최소 실패 판정 로직이 있다. P0는 완전히 새 validator를 만드는 작업이 아니라, 이 로직을 `pipeline/quality.py`로 끌어올려 `main.py`의 발행 게이트로 재사용하는 작업부터 시작한다.
- CI/CD의 `continue-on-error: true` 제거와 `npm ci` 전환은 Phase 5가 아니라 PR 1로 당겨야 한다. 코드량은 작고 실패 산출물 발행을 즉시 줄인다.
- 기존 데이터에서 key point KO/EN mismatch와 keyword 개수 위반은 발생하지 않았다. 이 규칙들은 P0의 hard fail이 아니라 warning 또는 회귀 방지 테스트로 시작한다.
- `_key_points_note` 같은 extra field는 현재 발행 데이터에는 없고, `generate_episode_json()`도 알려진 필드만 복사한다. P0에서는 warning + strip 처리로 충분하며, structured output 도입 후 hard fail로 승격한다.
- “실패 에피소드가 processed에 들어간다”는 주장은 summary fallback 실패에 대해 정확하다. 다운로드/전사 예외는 `processed` 추가 전에 빠지므로 이미 재시도 가능하다. 문서 전반에서 이 둘을 구분한다.
- quote grounding은 영어 transcript 기준으로만 직접 검증할 수 있다. 한국어 quote는 직접 인용이 아니라 영어 검증 quote의 번역으로 모델링해야 한다.
- 공개 transcript 제거는 현재 git에 이미 들어간 `data/transcripts/*.txt` 이력까지 고려해야 한다. 신규 공개 노출을 줄이는 것과 과거 이력 정리는 별도 의사결정으로 분리한다.

## 1. 현재 가장 큰 실패 지점

가장 취약한 지점은 `pipeline/summarize.py`의 단일 LLM 호출 결과를 거의 검증 없이 정상 episode JSON으로 발행하는 구조다.

현재 흐름은 다음과 같다.

```text
transcript text
  -> SUMMARY_PROMPT
  -> LLM raw text
  -> json.loads 성공 여부만 확인
  -> data/summaries/{slug}.json 생성
  -> Google Sheets 반영
  -> state["processed"] 업데이트
  -> Astro 사이트 배포
```

이 구조에서는 다음 문제가 동시에 발생한다.

- LLM이 구조적으로 불완전한 JSON을 생성해도 일부 필드가 비어 있는 상태로 발행될 수 있다.
- `summary_ko` 안에 JSON 문자열 조각이 들어가는 등 “그럴듯한 실패”가 감지되지 않는다.
- notable quote가 실제 전사문에서 온 문장인지 검증하지 않는다.
- summary 파싱 실패 fallback처럼 “필드 모양은 맞지만 내용이 빈” 결과도 `processed`에 들어가 자동 재처리가 막힌다. 반면 다운로드/전사 단계 예외는 `processed` 추가 전에 빠지므로 이미 재시도 가능하다.
- GitHub Actions가 파이프라인 실패를 무시하고 빌드/커밋/배포를 계속한다. 빌드 실패와 부분 커밋이 섞일 수 있어 실패 원인도 흐려진다.

따라서 1차 개선의 중심은 “생성 품질 향상”보다 먼저 “CI 안전장치, 검증, 발행 게이트”여야 한다.

## 2. 구현 우선순위

### P-1. 즉시 적용할 CI/런타임 안전장치

가장 먼저 적용한다. 코드량은 작지만 실패 산출물이 공개되는 경로를 즉시 줄인다.

#### 변경 대상

- `.github/workflows/daily-briefing.yml`
- `.github/workflows/deploy-web.yml`
- `pipeline/main.py`

#### 구현 내용

1. `daily-briefing.yml`의 `Run pipeline` 단계에서 `continue-on-error: true`를 제거한다.
2. `npm install`을 `npm ci`로 바꾼다.
3. `main.py`에서 `audio_path`를 loop 초기에 `None`으로 초기화하고, cleanup은 값이 있을 때만 호출한다.
4. build가 실패한 상태에서 data commit/push가 실행되지 않도록 step 순서 또는 조건을 재검토한다.

#### 왜 P0보다 먼저인가

품질 validator를 작성하기 전에도 현재 워크플로우는 파이프라인 실패 후 배포를 계속할 수 있다. 이 문제는 작은 변경으로 완화할 수 있으므로 먼저 처리한다.

#### 완료 기준

- 파이프라인 실행이 예외로 끝나면 Astro build/deploy가 진행되지 않는다.
- CI 로그에서 실패 단계가 숨겨지지 않는다.
- `download_audio()` 실패 시 cleanup 단계에서 부수적인 `UnboundLocalError`/`NameError`가 발생하지 않는다.
- CI에서 lockfile 기반 설치가 수행된다.

### P0. 발행 차단용 품질 게이트

P-1 이후 즉시 구현한다. 이 단계가 없으면 이후 개선도 실패 summary artifact를 계속 정상 데이터로 취급할 수 있다.

#### 변경 대상

- `pipeline/summarize.py`
- `pipeline/generate_output.py`
- `pipeline/main.py`
- `pipeline/sheets.py`
- 신규 파일: `pipeline/schema.py`
- 신규 파일: `pipeline/quality.py`
- 신규 파일: `pipeline/failures.py`
- 신규 테스트 디렉터리: `tests/`

#### 구현 내용

1. `pipeline/sheets.py`의 기존 실패 감지 로직을 `pipeline/quality.py`로 추출한다.
2. LLM raw output, parsed output, validation result를 분리한다.
3. hard fail 규칙을 통과하지 못하면 정상 JSON을 만들지 않는다.
4. warning 규칙은 report와 failure/warning artifact에는 남기되, P0에서는 발행 차단 기준으로 쓰지 않는다.
5. 실패 결과는 `data/failures/`에 저장한다.
6. 품질 게이트를 통과한 경우에만 Google Sheets 업데이트와 `state["processed"]` 업데이트를 수행한다.
7. `summarize_episode()`의 fallback은 schema-valid처럼 보이는 빈 dict가 아니라 명시적 실패 결과를 반환하도록 바꾼다.

#### 의존성

Pydantic을 쓰는 경우 `requirements.txt`에 명시적으로 추가해야 한다. P0에서 의존성 추가를 피하고 싶다면 dataclass + 수동 validator로 시작해도 된다. 중요한 것은 “검증 위치를 `main.py` 발행 전으로 끌어올리는 것”이지 특정 라이브러리가 아니다.

#### 권장 스키마

```python
class Guest(BaseModel):
    name: str
    title: str = ""

class KeyPoint(BaseModel):
    heading: str
    body: str

class Quote(BaseModel):
    text: str
    attribution: str

class SummaryResult(BaseModel):
    guest: Guest | None
    summary_ko: str
    summary_en: str
    key_points_ko: list[KeyPoint]
    key_points_en: list[KeyPoint]
    notable_quote_ko: Quote
    notable_quote_en: Quote
    keywords_ko: list[str]
    keywords_en: list[str]

    # P0에서는 extra field를 hard fail로 막기보다 strip + warning 처리한다.
    # structured output 도입 후 extra="forbid"로 승격한다.
    model_config = ConfigDict(extra="ignore")
```

#### Hard fail 규칙

`pipeline/quality.py`에 다음 규칙을 구현한다.

- `summary_ko`, `summary_en`은 각각 최소 100자 이상이어야 한다.
- `summary_ko` 또는 `summary_en`이 `{`로 시작하거나 JSON 조각처럼 보이면 실패 처리한다.
- key point는 최소 1개 이상이어야 한다. P0에서 2개 이상을 강제하면 짧은 에피소드의 정상 결과를 과하게 막을 수 있다.
- 각 key point의 `heading`과 `body`는 비어 있으면 안 된다.
- `notable_quote_*`의 `text`, `attribution`은 비어 있으면 안 된다.
- `guest`는 `null`이거나 `{name, title}` 객체여야 한다. 단, 현재 프롬프트가 hosts-only 에피소드에 `{name: null, title: "Host monologue"}`를 만들 수 있으므로 P0에서는 이를 hard fail로 막지 말고 `guest: null`로 정규화한 뒤 warning으로 남긴다. 프롬프트 수정 후 hard fail로 승격한다.

#### Warning 규칙

다음 규칙은 P0에서는 발행 차단이 아니라 warning으로 둔다. 현재 데이터에서는 위반 사례가 거의 없기 때문에 운영 안정성을 높이면서 false positive를 줄이는 쪽이 낫다.

- `key_points_ko`와 `key_points_en`의 개수가 다르다.
- key point 개수가 2-5개 범위를 벗어난다.
- `keywords_ko`, `keywords_en`이 각각 4-6개 범위를 벗어난다.
- `_key_points_note` 같은 허용되지 않은 메타 필드가 raw parsed object에 포함되어 있다.

#### 실패 artifact

정상 요약 JSON 대신 다음 위치에 실패 파일을 저장한다.

```text
data/failures/{slug}.json
```

예시:

```json
{
  "slug": "2026-04-14-ezra-klein-show",
  "episode_id": "...",
  "stage": "summary_validation",
  "provider": "claude",
  "model": "claude-sonnet-4-6",
  "errors": [
    "summary_ko is empty",
    "summary_en is empty",
    "key_points_en has 0 items"
  ],
  "raw_output_path": "data/failures/raw/2026-04-14-ezra-klein-show.txt",
  "created_at": "..."
}
```

#### `main.py` 변경

현재는 summary fallback 실패도 `generate_episode_json`, `append_episode`, `state["processed"].append(...)`로 이어진다. 이를 다음 흐름으로 바꾼다.

```text
summary_result = summarize_episode(...)
validation = validate_summary(summary_result.parsed, summary_result.raw_text, transcript)

if not validation.ok:
    write_failure(...)
    cleanup_audio(...)
    continue

generate_episode_json(...)
append_episode(...)
state["processed"].append(...)
save_state(...)
```

#### 완료 기준

- 빈 summary JSON이 더 이상 `data/summaries/`에 생성되지 않는다.
- 검증 실패 에피소드는 `data/failures/`에 남고 다음 실행에서 재처리 가능하다.
- `_key_points_note` 같은 메타 필드는 P0에서는 결과 JSON에서 제거되고 warning으로 기록된다.
- 기존 실패 사례인 `2026-03-11-lex-fridman-podcast`, `2026-04-14-ezra-klein-show`를 fixture로 넣었을 때 validation이 실패해야 한다.

## 3. Output Quality 개선 계획

### 3.1 긴 전사문 처리 구조 변경

#### 문제

`pipeline/summarize.py`는 전사문이 80,000자를 넘으면 앞 40,000자와 뒤 40,000자만 남기고 중간을 버린다.

```python
if len(transcript_text) > 80000:
    transcript_text = transcript_text[:40000] + omitted + transcript_text[-40000:]
```

이 방식은 다중 주제 팟캐스트에서 중간 세그먼트를 통째로 누락시킨다. Hard Fork, All-In, Odd Lots처럼 에피소드 안에 여러 주제가 있는 경우 특히 위험하다.

#### 구현안

단일 summarization 호출을 다음 3단계로 분리한다.

```text
1. chunk extraction
   전사문을 8k-12k token 단위로 나눠 각 chunk에서 claim/evidence/quote 후보 추출

2. episode synthesis
   chunk 결과만 모아 에피소드 전체 구조, 핵심 thesis, key points 결정

3. bilingual rendering
   확정된 구조를 한국어/영어 브리핑 문체로 렌더링
```

단, chunk extraction은 호출 횟수를 늘린다. 최대 250,000자 transcript는 chunk 크기에 따라 5-8회 이상의 LLM 호출이 필요할 수 있고, 각 chunk 중 하나만 실패해도 전체 synthesis가 흔들린다. 따라서 Phase 3에서는 모든 에피소드에 즉시 적용하지 말고, 우선 80,000자 초과 transcript에만 적용한다. chunk별 retry, partial failure, cache 재사용 정책을 함께 구현해야 한다.

#### 신규 artifact

```text
data/intermediate/{slug}/chunks.json
data/intermediate/{slug}/synthesis.json
```

`chunks.json` 예시:

```json
[
  {
    "chunk_index": 0,
    "char_start": 0,
    "char_end": 12000,
    "topics": ["AI layoffs", "Atlassian", "Block"],
    "claims": [
      {
        "claim": "Some AI layoffs are partly narrative management for investors.",
        "evidence": ["Block stock rose 17% after layoffs", "Block spent $68M on a Jay-Z event"],
        "speakers": ["Kevin Roose", "Casey Newton"]
      }
    ],
    "quote_candidates": [
      {
        "text": "...",
        "speaker": "Casey Newton",
        "char_start": 3450,
        "char_end": 3590
      }
    ]
  }
]
```

#### 완료 기준

- 80,000자 초과 전사문에서도 중간 chunk가 누락되지 않는다.
- 최종 key point가 chunk coverage 정보를 가진다.
- synthesis 단계 입력 token 수가 원문 전체보다 60% 이상 줄어드는지 실측 report로 확인한다. 70%는 목표치이지 PR merge 조건으로 고정하지 않는다.
- chunk 하나가 실패해도 전체 episode 상태가 `extraction_failed`로 남고, 다음 실행에서 cache hit chunk를 재사용해 재시도할 수 있다.

### 3.2 notable quote grounding

#### 문제

현재 `notable_quote_en.text`는 실제 전사문에서 온 직접 인용인지, 모델이 재구성한 문장인지 구분되지 않는다. 또한 transcript는 대부분 영어이므로 `notable_quote_ko.text`는 직접 검증 대상이 아니라 영어 quote의 번역으로 취급해야 한다.

#### 구현안

quote 필드를 다음과 같이 확장한다.

```json
{
  "notable_quote": {
    "source_text_en": "Measuring programming progress by lines of code is like measuring aircraft building progress by weight.",
    "translation_ko": "프로그래밍 진척도를 코드 줄 수로 측정하는 것은 항공기 건조 진척도를 무게로 측정하는 것과 같습니다.",
    "speaker": "Kevin Roose",
    "attribution": "Kevin Roose, citing early programming industry wisdom",
    "is_verbatim": true,
    "translation_is_verbatim": false,
    "source_char_start": 12345,
    "source_char_end": 12440,
    "match_score": 0.94
  }
}
```

검증 방식:

- chunk extraction 단계에서만 quote 후보를 뽑는다.
- 후보의 `source_char_start`, `source_char_end`를 저장한다.
- 최종 synthesis는 quote 후보 목록에서 선택만 한다.
- `source_text_en`만 전사문 fuzzy match score가 기준 이상일 때 직접 인용으로 허용한다.
- `translation_ko`는 직접 인용이 아니라 verified English quote의 번역으로 표시한다.
- 기준 미달이면 quote block을 숨기거나 “대표 해석” 필드로 별도 렌더링한다.

#### 완료 기준

- quote가 전사문에 없으면 `is_verbatim=false`가 된다.
- UI는 `is_verbatim=false`인 경우 blockquote로 렌더링하지 않는다.
- KO 화면에서는 `translation_ko`가 영어 원문에서 번역된 것임을 내부 모델에 반영하고, `translation_is_verbatim=false`로 저장한다.
- quote 후보가 없으면 빈 quote UI가 나오지 않는다.

### 3.3 게스트 식별 안정화

#### 문제

`guest`는 모델이 전체 프롬프트에서 추론한다. hosts-only 에피소드, 다중 게스트 에피소드, 패널형 에피소드에서 오류가 발생하기 쉽다.

#### 구현안

guest 식별을 요약 생성에서 분리한다.

1. RSS title/description에서 guest 후보 추출
2. 전사문 첫 5-10분에서 host introduction 탐색
3. LLM 소형 모델 또는 규칙 기반 parser로 후보 확정
4. confidence score 저장

권장 필드:

```json
{
  "guests": [
    {
      "name": "Jasmine Sun",
      "title": "Freelance journalist and writer",
      "confidence": 0.92,
      "source": "intro"
    }
  ]
}
```

기존 `guest` 단수 필드는 UI 호환을 위해 유지하되 내부 구조는 `guests[]`로 확장한다.

## 4. Token Efficiency 개선 계획

### 4.1 토큰 낭비 지점

현재 저장된 전사문 기준:

- 전사문 58개
- 평균 전사 길이 약 59,000자
- 평균 입력은 단순 4 chars/token 기준 약 14,800 tokens지만, 영어 transcript 특성상 실제 tokenizer 기준으로는 18,000-22,000 tokens에 가까울 가능성이 있다.
- 정적 프롬프트 약 4,954자, 약 1,200 tokens 추정
- 80,000자 초과 전사문 10개

가장 큰 낭비는 전사문 전체를 매번 최종 브리핑 프롬프트에 넣는 것이다. retry가 발생하면 같은 긴 입력을 반복 전송한다.

### 4.2 단계별 모델 전략

#### 현재

```text
고급 모델 1회:
guest + summary + key points + quote + keywords + bilingual rendering
```

#### 변경 후

```text
저가/빠른 모델:
chunk extraction, guest 후보, keyword 후보

고급 모델:
episode-level thesis, analytical synthesis

저가/중간 모델:
한국어/영어 렌더링, formatting repair
```

#### 작업별 권장 모델 등급

| 작업 | 품질 민감도 | 권장 모델 등급 |
|---|---:|---|
| RSS parsing | 낮음 | deterministic |
| guest 후보 추출 | 중간 | cheap LLM 또는 규칙 기반 |
| chunk claim extraction | 중간 | cheap/medium LLM |
| quote 후보 추출 | 높음 | extraction + deterministic verification |
| episode synthesis | 높음 | premium reasoning model |
| Korean/English rendering | 중간 | medium model |
| schema repair | 낮음 | deterministic 또는 cheap model |

### 4.3 캐싱

chunk extraction 결과는 transcript hash 기준으로 캐시한다.

```text
cache key = sha256(transcript_text + extraction_prompt_version + model)
```

저장 위치:

```text
data/cache/extractions/{hash}.json
```

재실행 시 transcript가 같으면 extraction을 재사용하고 synthesis/rendering만 다시 수행한다.

### 4.4 완료 기준

- 긴 에피소드 1건의 최종 synthesis 입력 token이 기존 대비 60-80% 감소한다.
- retry 시 전체 전사문을 다시 보내지 않는다.
- A/B 테스트도 raw transcript가 아니라 cached extraction 기반으로 실행 가능하다.

## 5. Architecture and Structure 개선 계획

### 5.1 오케스트레이션 분리

#### 문제

`pipeline/main.py`가 다운로드, 전사, 저장, 요약, Sheets, 상태 업데이트를 모두 순차 실행한다.

#### 구현안

단계를 명시적으로 분리한다.

```text
fetch
  -> episode manifest 생성

transcribe
  -> transcript artifact 생성

extract
  -> chunk artifact 생성

synthesize
  -> validated summary artifact 생성

publish
  -> data/summaries + feed index + Sheets
```

권장 파일 구조:

```text
pipeline/
  orchestrator.py
  models.py
  schema.py
  quality.py
  extraction.py
  synthesis.py
  publishing.py
  failures.py
```

### 5.2 병렬화

#### 문제

현재 에피소드 단위로 완전 순차 처리한다. 다운로드와 전사는 episode별로 병렬화 가능하다.

#### 구현안

간단한 1차 구현은 `concurrent.futures.ThreadPoolExecutor`를 사용한다.

권장 concurrency:

```text
RSS fetch: 5
audio download: 3
transcription: 2
LLM extraction: 2
LLM synthesis/rendering: 1
```

외부 API rate limit이 있으므로 LLM 최종 단계는 낮은 concurrency를 유지한다.

### 5.3 slug deterministic 처리

#### 문제

`make_slug()`가 파일 존재 여부를 보고 suffix를 붙인다. transcript 저장 시점과 summary 저장 시점에 다시 계산하기 때문에 재실행/충돌 시 slug가 어긋날 수 있다. 특히 현재 `main.py`가 transcript 저장 전에 `make_slug(ep)`를 호출하고, `generate_episode_json()` 내부에서 다시 `make_slug(ep)`를 호출한다. 동일 날짜/동일 podcast의 복수 에피소드가 한 실행 안에서 처리되면 transcript는 `xxx.txt`, summary는 `xxx-2.json`처럼 갈라질 수 있다.

#### 구현안

fetch 단계에서 slug를 한 번 생성해 episode manifest에 포함한다.

권장 형식:

```text
{published_date}-{podcast_slug}-{episode_id_hash8}
```

예:

```text
2026-03-20-hard-fork-4873f2a4
```

이 slug를 transcript, intermediate, summary, failure, Sheets 링크에 모두 사용한다.

### 5.4 state 관리

#### 문제

현재 `state["processed"]`는 처리 완료 여부만 기록한다. 실패, 부분 성공, validation 실패, publish 실패가 구분되지 않는다.

#### 구현안

state를 다음 구조로 확장한다.

```json
{
  "episodes": {
    "episode-id": {
      "slug": "...",
      "status": "published",
      "last_stage": "publish",
      "attempts": 1,
      "last_error": null,
      "updated_at": "..."
    }
  }
}
```

상태값:

```text
discovered
downloaded
transcribed
extracted
summary_failed
validation_failed
published
publish_failed
```

완료 기준:

- validation 실패 에피소드는 다음 실행에서 재시도 가능하다.
- publish 성공 전에는 `published`가 되지 않는다.
- Google Sheets append 실패도 `publish_failed` 또는 `sheets_failed`로 기록되어 재시도 가능해야 한다. 현재 `sheets.py`는 예외를 swallow하므로 state와 Sheets가 영구 불일치할 수 있다.
- 상태 전환이 테스트로 검증된다.

### 5.5 검증 보고서에서 추가로 발견된 결함

다음 항목은 최초 기획서에서 빠졌지만 구현 계획에 포함해야 한다.

#### `audio_path` 미정의 cleanup 위험

`main.py`의 `except` 블록은 `cleanup_audio(audio_path)`를 호출한다. `download_audio()` 호출 자체가 실패하면 `audio_path`가 정의되지 않을 수 있다. 현재 nested `try/except`가 추가 오류를 삼키지만 cleanup 의도는 무산된다.

수정안:

```python
audio_path = None
try:
    audio_path = download_audio(ep)
    ...
except Exception as e:
    if audio_path:
        cleanup_audio(audio_path)
```

#### `rebuild_feed_index()`의 silent skip

`generate_output.py`의 `rebuild_feed_index()`는 JSON decode error나 KeyError를 조용히 건너뛴다. 품질 게이트 도입 전까지는 손상된 summary 파일을 발견하기 어렵다.

수정안:

- 손상 파일 목록을 warning으로 출력한다.
- validation report에 `skipped_summary_files`를 기록한다.
- P0 이후에는 `data/summaries/`에 손상 파일이 들어가지 않는 것을 테스트한다.

#### 한국어 길이 지시의 word 단위 문제

`SUMMARY_PROMPT`의 `summary_ko` 길이 지시는 `200-300 words`처럼 영어식 word 단위를 사용한다. 한국어는 공백 기반 word count가 일관되지 않아 모델과 validator가 서로 다르게 해석할 수 있다.

수정안:

- 한국어 길이는 글자 수 또는 문단 수로 지시한다.
- 예: 짧은 transcript는 600-900자, 중간은 1,000-1,400자, 긴 transcript는 1,400-1,900자.

## 6. Features 개선 계획

### 6.1 공개 transcript 제거 또는 lazy access

#### 문제

현재 Astro 페이지가 transcript 전체를 읽고 `script type="application/json"` 안에 임베드한다. 공개 사이트와 repo에 전체 전사문이 노출되는 구조다.

#### 리스크

- 빌드 산출물과 HTML 크기 증가
- 공개 전사문 배포에 따른 저작권/라이선스 리스크
- 브리핑보다 원문 dump가 중심 artifact가 되는 제품 경험 문제

#### 구현안

1. 공개 사이트에서는 전체 transcript를 기본 HTML에 포함하지 않는다.
2. transcript copy/download 버튼은 별도 URL에서 lazy fetch한다.
3. 공개 배포가 부담되는 경우 transcript 파일은 private artifact로 분리한다.
4. 이미 git에 commit된 `data/transcripts/*.txt` 이력은 신규 노출 차단과 별도 트랙으로 다룬다. 이력 삭제는 `git filter-repo` 같은 파괴적 작업이므로 별도 승인과 백업 계획 없이 진행하지 않는다.

권장 단계:

```text
P1: HTML inline transcript 제거
P2: transcript 파일을 public data에서 lazy fetch
P3: 신규 transcript의 public commit 중단, 내부용 storage로 이동
P4: 과거 git 이력 정리 여부 별도 결정
```

### 6.2 Obsidian Markdown 다운로드 개선

#### 문제

현재 `.md` 다운로드는 브리핑이 아니라 transcript 중심이다.

#### 구현안

다운로드 Markdown을 다음 구조로 바꾼다.

```markdown
---
podcast: "Hard Fork"
title: "..."
date: 2026-03-20
category: "AI / Tech"
guest: "Jasmine Sun"
slug: "..."
---

# Title

## Briefing

한국어 요약

## Key Points

### 핵심 주장

본문

## Quote

> 검증된 인용문

## Keywords

...

## Transcript

전사문 또는 링크
```

### 6.3 Google Sheets 경량화

#### 문제

Sheets에 전체 영어/한국어 요약을 그대로 append한다. 다만 `sheets.py`에는 이미 `summary_en` 길이와 `summary_ko` JSON 조각을 감지해 `SUMMARY FAILED`를 표시하는 로직이 있으므로, 이 코드는 버릴 것이 아니라 P0 품질 게이트의 출발점으로 재사용해야 한다.

#### 구현안

Sheets는 대시보드 역할만 하도록 축소한다.

권장 컬럼:

```text
Date
Podcast
Title
Guest
Category
Status
Briefing URL
Transcript URL or Internal Path
Thesis
Keywords
Validation
Notes
```

전체 summary는 JSON/웹 링크로 연결한다.

구현 순서:

1. 기존 `has_en`, `has_ko` 판정을 `pipeline/quality.py`로 이동한다.
2. `main.py`가 이 판정을 발행 전에 사용한다.
3. Sheets는 발행 후 dashboard 기록만 담당한다.
4. Sheets append 실패는 non-fatal로 삼키더라도 state에는 `sheets_failed`를 남긴다.

## 7. Prompt Engineering 개선 계획

### 7.1 프롬프트 역할 분리

#### 문제

현재 `SUMMARY_PROMPT`는 분석 기준, 문체, 금지어, 한국어 표기, JSON 구조, key point 개수, quote 선택까지 모두 포함한다.

#### 구현안

프롬프트를 3개로 나눈다.

```text
EXTRACTION_PROMPT:
  transcript chunk에서 claim/evidence/speaker/quote 후보만 추출

SYNTHESIS_PROMPT:
  chunk 결과를 바탕으로 episode thesis와 key point 구조 결정

RENDER_PROMPT:
  확정된 구조를 KO/EN 브리핑으로 렌더링
```

형식 규칙은 프롬프트가 아니라 schema validator가 강제한다.

### 7.2 JSON 출력 강제

#### 문제

Claude 호출은 “valid JSON object”를 프롬프트로 요구할 뿐 구조화 출력 모드를 쓰지 않는다.

#### 구현안

- Gemini는 `response_mime_type="application/json"` 외에 schema config까지 사용한다.
- Claude는 tool-use style schema 또는 JSON repair 후 Pydantic 검증을 사용한다.
- repair는 한 번만 수행하고, repair 후에도 실패하면 failure artifact로 보낸다.

### 7.3 예시 JSON에서 비필드 제거

#### 문제

프롬프트 예시에 `_key_points_note`가 들어 있어 실제 출력에 포함될 수 있다.

#### 구현안

예시 JSON에는 실제 허용 필드만 둔다. 설명은 JSON 밖으로 뺀다.

잘못된 예:

```json
{
  "_key_points_note": "Generate 2-3 key points..."
}
```

권장:

```text
Rules:
- Generate 2-3 key points for short transcripts.
- Generate 3-4 key points for medium transcripts.
- Generate 4-5 key points for long transcripts.

Output fields:
{ ...actual schema only... }
```

### 7.4 브랜드 스타일 지시 제거

#### 문제

“The Economist style”은 모델에 따라 모방 위험과 불명확한 해석을 만든다.

#### 구현안

브랜드명 대신 관찰 가능한 스타일 속성으로 바꾼다.

권장 문구:

```text
Write in a concise analytical editorial tone:
- lead with the consequence, not the setup
- state the central claim before background
- include specific numbers and named actors
- distinguish evidence from interpretation
- avoid generic transitions and filler
```

## 8. CI/CD 및 운영 안정성 개선

### 8.1 GitHub Actions 실패 처리

#### 문제

`daily-briefing.yml`에서 `Run pipeline`이 `continue-on-error: true`다. 파이프라인이 실패해도 빌드와 배포가 이어진다. 또한 workflow는 data commit/push와 deploy가 같은 job 안에 있어, build 실패와 부분 commit이 섞이는 운영 상태를 만들 수 있다.

#### 구현안

1차 PR에서는 먼저 단순하게 실패를 숨기지 않도록 만든다.

```text
- continue-on-error: true 제거
- npm install -> npm ci
- build 실패 시 commit/push/deploy가 실행되지 않도록 step 조건 확인
```

그 다음 단계에서 실패 유형을 구분한다.

```text
0: 성공 또는 새 에피소드 없음
1: 인프라/코드 실패
2: 일부 에피소드 validation 실패, 발행 없음
```

정책:

- 새 에피소드 없음: deploy 가능
- 일부 에피소드 validation 실패: 기존 사이트 재배포는 가능하나 새 실패 산출물 발행은 금지
- 코드/빌드 실패: deploy 중단
- data commit/push는 validation과 build가 성공한 뒤에만 실행

### 8.2 `npm install` 대신 `npm ci`

#### 문제

workflow가 매번 `npm install`을 사용한다.

#### 구현안

`web/package-lock.json`이 있으므로 CI에서는 `npm ci`를 사용한다.

### 8.3 dependency pinning

#### 문제

`requirements.txt`가 `>=` 범위만 사용한다.

#### 구현안

다음 중 하나를 적용한다.

- `requirements.lock` 생성
- `pip-tools`로 `requirements.txt` compile
- 최소한 provider SDK major version 상한 추가

예:

```text
anthropic>=0.30,<1.0
openai>=1.0,<2.0
google-genai>=1.0,<2.0
```

## 9. 테스트 계획

### 9.1 Unit tests

신규 테스트:

```text
tests/test_schema.py
tests/test_quality.py
tests/test_slug.py
tests/test_parse_summary.py
tests/test_state.py
```

필수 fixture:

```text
tests/fixtures/valid_summary.json
tests/fixtures/summary_with_extra_field.json
tests/fixtures/summary_empty.json
tests/fixtures/summary_json_fragment_in_field.json
tests/fixtures/transcript_hard_fork_excerpt.txt
tests/fixtures/2026-03-11-lex-fridman-podcast.failed.json
tests/fixtures/2026-04-14-ezra-klein-show.failed.json
```

`summary_with_extra_field.json`은 P0에서는 hard fail이 아니라 warning + strip 동작을 검증한다. hard fail 전환은 structured output/schema enforcement 단계에서 별도 테스트로 승격한다.

### 9.2 Integration tests

샘플 transcript 1개를 기준으로 다음을 검증한다.

- chunk extraction artifact 생성
- synthesis artifact 생성
- summary schema validation 통과
- quote grounding 통과 또는 `is_verbatim=false` 처리
- `data/summaries/` 발행
- `feed.json` rebuild

### 9.3 Regression metrics

각 실행마다 다음 report를 생성한다.

```text
data/reports/{run_id}.json
```

필드:

```json
{
  "episodes_discovered": 8,
  "episodes_published": 7,
  "episodes_failed": 1,
  "summary_validation_pass_rate": 0.875,
  "quote_grounding_pass_rate": 0.92,
  "avg_input_tokens_per_episode": 6200,
  "avg_output_tokens_per_episode": 1800,
  "total_estimated_cost_usd": 4.12,
  "wall_time_seconds": 2380
}
```

## 10. 단계별 구현 로드맵

### PR 1: CI 안전장치와 작은 런타임 결함 수정

목표: 실패를 숨기지 않고, 즉시 고칠 수 있는 운영 결함을 먼저 제거한다.

작업:

- `daily-briefing.yml`의 `continue-on-error: true` 제거
- CI의 `npm install`을 `npm ci`로 변경
- `main.py`에서 `audio_path = None` 초기화 및 conditional cleanup 적용
- build 실패 시 commit/push/deploy가 실행되지 않는지 확인

완료 기준:

- 파이프라인 실패가 GitHub Actions에서 성공으로 보이지 않는다.
- lockfile 기반 설치가 수행된다.
- download 실패 시 cleanup에서 2차 예외가 발생하지 않는다.

### PR 2: 품질 게이트와 실패 격리

목표: 잘못된 summary 산출물이 공개 데이터로 발행되지 않게 한다.

작업:

- `pipeline/sheets.py`의 기존 `has_en`, `has_ko` 실패 판정을 `pipeline/quality.py`로 추출
- `pipeline/schema.py` 추가 또는 수동 schema validator 구현
- `pipeline/failures.py` 추가
- `summarize_episode()`가 raw output과 parsed output을 모두 반환하도록 변경
- `main.py`에서 hard fail validation 실패 시 발행 중단
- warning 규칙은 report에 기록하되 P0에서는 발행 차단하지 않음
- 기존 실패 JSON 2건을 fixture로 테스트 추가

완료 기준:

- 빈 summary가 `data/summaries/`에 새로 생성되지 않는다.
- validation 실패가 `data/failures/`에 남는다.
- summary fallback 실패 에피소드가 `state["processed"]`에 들어가지 않는다.
- extra field는 strip + warning 처리된다.

### PR 3: 공개 payload와 publishing 구조 정리

목표: HTML payload를 줄이고 공개 데이터와 내부 데이터를 분리하기 시작한다.

작업:

- `index.astro`, `archive.astro`의 data loading 중복 제거
- transcript inline embedding 제거
- transcript copy/download를 lazy fetch로 전환
- Obsidian markdown 다운로드를 summary-first 구조로 변경
- Sheets 컬럼 경량화 설계 반영

완료 기준:

- HTML에 transcript 전문이 포함되지 않는다.
- Markdown 다운로드가 summary-first 구조가 된다.
- Sheets에 전체 summary 전문을 계속 넣을지 여부가 명시적 설정으로 분리된다.

### PR 4: 긴 transcript용 chunk extraction

목표: 긴 전사문의 중간 누락과 토큰 낭비를 줄인다. 우선 80,000자 초과 transcript에만 적용한다.

작업:

- `pipeline/extraction.py` 추가
- transcript chunker 구현
- chunk별 claim/evidence/quote 후보 추출
- extraction cache 구현
- chunk partial failure 처리
- `pipeline/synthesis.py` 추가

완료 기준:

- 80,000자 초과 transcript에서 중간 chunk가 모두 처리된다.
- final synthesis 입력 token이 기존 대비 60% 이상 감소하는지 report로 확인한다.
- 실패 chunk 재시도 시 성공 chunk cache를 재사용한다.

### PR 5: quote grounding

목표: 직접 인용과 모델 재구성 문장을 분리한다.

작업:

- quote schema 확장
- 영어 transcript 기준 fuzzy matching 구현
- `source_text_en`, `translation_ko`, `is_verbatim`, `translation_is_verbatim`, `match_score` 저장
- UI에서 ungrounded quote block 숨김 또는 paraphrase로 표시

완료 기준:

- 영어 quote가 전사문에서 검증되지 않으면 blockquote로 렌더링하지 않는다.
- 한국어 quote는 verified English quote의 번역으로 저장된다.
- quote 검증률이 report에 기록된다.

### PR 6: state 확장과 regression metrics

목표: 실패/부분 성공/Sheets 실패를 재시도 가능한 운영 상태로 만든다.

작업:

- `state["processed"]`를 episode 상태 map으로 확장
- `summary_failed`, `validation_failed`, `sheets_failed`, `published` 상태 구분
- validation report를 artifact로 업로드
- dependency pinning 적용
- `rebuild_feed_index()`의 silent skip을 report에 기록

완료 기준:

- validation 실패 시 GitHub Actions 로그에서 실패 원인이 명확히 보인다.
- Sheets 실패가 영구 묵살되지 않는다.
- 상태 전환과 report 생성이 테스트로 검증된다.

## 11. 구현 후 성공 지표

### 품질 지표

- summary validation pass rate: 95% 이상
- quote grounding pass rate: 90% 이상
- 빈 summary 발행: 0건
- key point KO/EN mismatch: 0건
- schema extra field warning: 추적 가능해야 하며, structured output 도입 후 0건을 목표로 한다.

### 비용/효율 지표

- 긴 에피소드 final synthesis input tokens: 60% 이상 감소
- retry 시 raw transcript 재전송: 0건
- chunk extraction cache hit rate: 50% 이상

### 운영 지표

- 실패 에피소드 자동 재처리 가능
- GitHub Actions 실패 원인 분류 가능
- 공개 HTML에서 transcript inline payload 제거
- 테스트 없이 provider SDK 변경이 merge되지 않음

## 12. 구현 시 주의사항

- 기존 `data/summaries/`의 과거 실패 JSON은 바로 삭제하지 말고 migration 또는 quarantine 대상으로 분리한다.
- schema를 너무 엄격하게 시작하면 정상 에피소드까지 막을 수 있으므로 P0에서는 최소 품질 규칙부터 적용한다.
- P0의 목표는 완벽한 schema enforcement가 아니라 “빈 요약과 JSON 조각 요약의 발행 차단”이다. 낮은 빈도 규칙은 warning부터 시작한다.
- `sheets.py`에 이미 있는 summary failure 감지 로직은 폐기하지 말고 `quality.py`로 이동해 재사용한다.
- quote grounding은 처음부터 100% 직접 인용만 강제하지 말고 `is_verbatim` 플래그를 도입해 UI 표현을 분리한다.
- 한국어 quote는 영어 transcript에서 직접 검증할 수 없으므로, verified English quote의 번역으로 저장한다.
- chunking은 문장 중간 절단을 피해야 한다. 가능하면 문단/타임스탬프/화자 전환 기준을 우선한다.
- 공개 transcript 제거는 제품 기능에 영향을 주므로, 먼저 inline 제거와 lazy fetch부터 적용한 뒤 private 분리를 결정한다.
- git 이력의 transcript 제거는 별도 승인과 백업 없이는 진행하지 않는다.

## 13. 권장 첫 PR 범위

검증 보고서 반영 후 첫 PR은 품질 게이트가 아니라 CI/런타임 안전장치로 잡는다. 품질 게이트는 두 번째 PR이 맞다.

```text
PR 1: CI safety and cleanup guardrails
```

포함 작업:

- `.github/workflows/daily-briefing.yml`에서 `continue-on-error: true` 제거
- `.github/workflows/daily-briefing.yml`에서 `npm install`을 `npm ci`로 변경
- `.github/workflows/deploy-web.yml`도 `npm ci`로 변경
- `pipeline/main.py`에서 `audio_path = None` 초기화 및 conditional cleanup 적용

포함하지 않을 작업:

- schema validator
- failure artifact
- chunk extraction
- quote grounding
- web transcript 구조 변경
- state 구조 확장

이 PR이 병합되면 실패가 성공처럼 보이는 문제를 먼저 줄일 수 있다. 이후 PR 2에서 `pipeline/quality.py`와 failure quarantine을 구현한다.
