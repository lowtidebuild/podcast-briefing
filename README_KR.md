<div align="center">

# Podcast Briefing

**세계 최고의 팟캐스트에서 AI가 큐레이팅한 이중언어 인텔리전스**

[라이브 사이트](https://lowtidebuild.github.io/podcast-briefing/) | [English README](README.md)

<br>

*이번 주 가장 영향력 있는 팟캐스트 호스트 10명이 무슨 이야기를 했는지 —*
*2분 안에 읽을 수 있는 분석적 브리핑으로 정리합니다. 한국어와 영어 동시 제공.*

</div>

---

## 프로젝트 소개

거시경제, AI, 지정학, 벤처캐피탈, 공공정책을 아우르는 10개의 엄선된 팟캐스트를 자동으로 모니터링하는 인텔리전스 파이프라인입니다. 매주 2회, 새로운 에피소드를 감지하면 음성을 전사하고, AI가 이중언어 분석 브리핑을 생성하여 에디토리얼 웹앱에 자동 발행합니다.

읽기 경험은 **The Economist와 Stratechery의 교차점**을 지향합니다. 권위 있고, 한눈에 스캔 가능하며, 관점이 있는 글. 모든 브리핑은 "So what?" — 바쁜 독자가 왜 이 에피소드에 관심을 가져야 하는지부터 시작하고, 구조화된 분석과 근거, 시사점으로 이어집니다.

AI가 뱉어내는 피상적 요약이 아닙니다. 구조화된 사고입니다.

## 큐레이팅 소스

10개 소스는 각 분야의 최고 품질 팟캐스트를 기준으로 선정했습니다. 토픽이 겹치지 않으면서도 세계를 이해하는 데 필요한 핵심 영역을 커버합니다.

| 팟캐스트 | 영역 | 발행 주기 |
|---------|------|----------|
| **Odd Lots** (Bloomberg) | 거시경제 / 금융시장 | 주 2-3회 |
| **Dwarkesh Podcast** | AI / 기술 심층 분석 | 격주 |
| **Lex Fridman Podcast** | AI / 과학 / 철학 | 격주 |
| **Fareed Zakaria GPS** (CNN) | 지정학 / 국제관계 | 주 1회 |
| **Hard Fork** (NYT) | 테크 / AI 시사 | 주 1회 |
| **a16z Podcast** | VC / 테크 비즈니스 | 주 2-3회 |
| **Ezra Klein Show** (NYT) | 정치 / 정책 / 철학 | 주 1-2회 |
| **All-In Podcast** | 테크 × 정치 × 경제 | 주 1-2회 |
| **Exponential View** | AI × 에너지 × 지정학 | 주 1회 |
| **Making Sense** (Sam Harris) | 철학 / AI 윤리 | 격주 |

## 작동 원리

```
RSS 피드 ──→ 신규 에피소드 감지 ──→ 오디오 다운로드
                                         │
                                         ▼
                                  Whisper API (음성→텍스트)
                                         │
                                         ▼
                                  Claude Sonnet (분석)
                                    │           │
                                    ▼           ▼
                             한국어 브리핑   영어 브리핑
                                    │           │
                                    ▼           ▼
                   ┌──────────────────────────────────────┐
                   │  Astro 정적 사이트 (GitHub Pages)      │
                   │  Google Sheets 대시보드                │
                   │  트랜스크립트 아카이브 (GitHub Repo)     │
                   └──────────────────────────────────────┘
```

파이프라인은 **매주 월요일/목요일 15:00 KST**에 GitHub Actions로 자동 실행됩니다:

1. **감지** — 10개 RSS 피드를 파싱하여 마지막 실행 이후 새로운 에피소드 식별
2. **전사** — 오디오 다운로드, ffmpeg로 모노 16kHz 변환, Whisper API로 텍스트 전사
3. **분석** — Claude가 Economist 스타일의 이중언어 브리핑 생성. 주장 기반 키포인트, 인용문, 게스트 정보 자동 추출
4. **발행** — JSON을 리포에 저장, Google Sheets에 행 추가, Astro 빌드, GitHub Pages 배포

## 아키텍처

```
podcast-briefing/
├── pipeline/              # Python: RSS → Whisper → Claude → JSON
│   ├── fetch_feeds.py     # RSS 파싱 + 신규 에피소드 감지
│   ├── download_audio.py  # 오디오 다운로드 + ffmpeg 전처리
│   ├── transcribe.py      # Whisper API (청크 분할) + Substack 텍스트 폴백
│   ├── summarize.py       # Claude Economist 스타일 분석 프롬프트
│   ├── generate_output.py # 구조화된 JSON + 피드 인덱스 생성
│   ├── sheets.py          # Google Sheets 대시보드 연동
│   └── main.py            # 순차 실행 오케스트레이터
├── web/                   # Astro 정적 사이트: 에디토리얼 읽기 경험
│   └── src/
│       ├── pages/         # index.astro (최근 7일) + archive.astro (전체, 주 단위)
│       ├── components/    # EpisodeCard, QuoteBlock, LangToggle, CategoryFilter
│       ├── layouts/       # BaseLayout (OG 메타 태그 포함)
│       └── styles/        # 에디토리얼 디자인 시스템
├── config/feeds.yaml      # 소스 설정 (이름, RSS URL, 홈페이지, 카테고리)
├── data/
│   ├── summaries/         # 에피소드별 구조화된 JSON (이중언어)
│   ├── transcripts/       # 전체 트랜스크립트 텍스트 파일
│   └── state.json         # 처리된 에피소드 ID 추적 (중복 방지)
└── .github/workflows/     # CI/CD 파이프라인
```

## 디자인 철학

에디토리얼 디자인 시스템은 인쇄 저널리즘의 전통에서 가져왔습니다.

### 타이포그래피
Georgia 세리프를 본문에, 시스템 산세리프를 UI 요소에 사용합니다. 외부 폰트를 로드하지 않으면서도 에디토리얼 권위를 전달하는 조합입니다.

### 레이아웃
720px 읽기 컬럼, 중앙 정렬. 넉넉한 수직 리듬(에피소드 간 56px, 패딩 40px). 콘텐츠가 숨 쉴 공간을 확보합니다.

### 색상
거의 흰색에 가까운 배경(#fafaf8), 진한 텍스트(#1a1a1a), 빨간 액센트(#b44) 단 하나. 카테고리 라벨과 인용문 테두리에만 사용합니다. 장식보다 절제를 택했습니다.

### 정보 위계
`카테고리 → 제목 → 출처/날짜 → 게스트 → 요약 → 키포인트 → 인용문 → 키워드 → 액션 바`

모든 요소가 자기 위치를 얻어야 합니다. 에디토리얼 읽기 흐름(요약 → 분석 → 인용문)을 유틸리티 액션이 절대 방해하지 않도록 액션 바를 카드 최하단에 배치했습니다.

### 이중언어 토글
한국어와 영어 모두 HTML에 미리 렌더링되어 있습니다. 토글은 CSS `display` 속성만 교체하므로 네트워크 요청 없이 즉시 전환됩니다. 언어 선택은 `localStorage`에 저장됩니다.

### 모바일
"데스크톱을 세로로 쌓기"가 아닙니다. 액션 바는 수직으로 재배치되고, 터치 타겟은 44px을 보장하며, 필터 필은 가로 스크롤됩니다. 엄지손가락 도달 범위를 고려한 의도적 재설계입니다.

## 주요 기능

### 이중언어 분석 브리핑
한국어(합니다 체)와 영어, 버튼 하나로 즉시 전환. 리로드 없음.

### Economist 스타일 분석
단순 나열이 아닌 분석적 프레이밍. "So what?"으로 시작하여 핵심 주장, 근거, 시사점 순서로 구조화합니다. 키포인트 제목은 토픽이 아니라 **주장**입니다.

> 나쁜 예: "AI 에이전트 시장"
> 좋은 예: "기업 AI 파일럿의 90%가 실패한다 — 기술이 아니라 조직이 병목"

### 게스트 자동 식별
트랜스크립트에서 게스트 이름과 소속/직함을 자동 추출하여 에피소드 카드에 표시합니다.

### 트랜스크립트 접근
- **클립보드 복사** — NotebookLM 등에 바로 붙여넣기
- **Obsidian .md 다운로드** — frontmatter(팟캐스트, 제목, 날짜, 카테고리) 포함

### Google Sheets 대시보드
파이프라인이 처리한 에피소드를 자동으로 Google Sheet에 기록합니다. 별점(⭐), 읽음 체크(✔), 메모(Notes) 열은 직접 편집하여 개인 큐레이션이 가능합니다.

### 주간 아카이브
메인 페이지는 최근 7일 브리핑만 표시합니다. 전체 에피소드는 아카이브 페이지에서 주 단위로 정리되어 있으며, 컴팩트한 리스트 형태로 빠르게 스캔할 수 있습니다.

### 카테고리 필터링
Macro / Markets, AI / Tech, Geopolitics, VC / Business, Politics / Policy — 필 버튼으로 즉시 필터링.

### 소스 목록
헤더의 "10 Sources ▾"를 클릭하면 전체 소스가 인라인으로 펼쳐집니다. 모달이 아닌 `<details>` 요소를 사용하여 JavaScript 없이 동작합니다.

## 한국어 텍스트 규칙

한국어 브리핑에서 고유명사는 정확성을 위해 영어를 유지합니다:

| 유형 | 올바른 표기 | 잘못된 표기 |
|------|-----------|-----------|
| 인명 | Torsten Sløk | ~~토르스텐 슬뢰크~~ |
| 기업명 | Apollo, Federal Reserve | ~~아폴로~~, ~~연방준비제도~~ |
| 기술 용어 | term premium, NIMBYism | 표준 번역이 없는 경우 |
| 인용 출처 | Jenny Schuetz, Brookings Institution | 항상 영어 |

## 설정 방법

1. 리포 클론
2. GitHub Secrets 설정: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
3. 선택: `GOOGLE_SHEETS_CREDENTIALS` + `GOOGLE_SHEET_ID` (Sheets 대시보드용)
4. `config/feeds.yaml`에서 소스 커스터마이즈
5. Push — GitHub Actions가 나머지를 처리합니다

## 로컬 개발

```bash
# 웹앱 — localhost:4321에서 개발 서버 시작
cd web && npm install && npm run dev

# 파이프라인 — OPENAI_API_KEY, ANTHROPIC_API_KEY 환경변수 필요
pip install -r requirements.txt
python pipeline/main.py
```

## 소스 추가/변경

`config/feeds.yaml`에 항목을 추가하면 코드 수정 없이 다음 파이프라인 실행부터 자동 반영됩니다:

```yaml
  - name: "새 팟캐스트"
    display_category: "카테고리"
    homepage: "https://example.com"
    rss: "https://example.com/feed.rss"
    frequency: "weekly"
    transcript_source: "whisper"
```

---

<div align="center">

[Astro](https://astro.build) · [Claude](https://anthropic.com) · [Whisper](https://openai.com)로 구축

The Economist의 정신으로 디자인

</div>
