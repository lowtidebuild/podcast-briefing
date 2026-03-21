<div align="center">

# Podcast Briefing

**AI-curated bilingual intelligence from the world's best podcasts**

[Live Site](https://lowtidebuild.github.io/podcast-briefing/) | [한국어](#한국어)

<br>

*What 10 of the smartest podcast hosts discussed this week — distilled into*
*analytical briefings you can read in 2 minutes, in both Korean and English.*

</div>

---

## What This Is

An automated pipeline that monitors 10 curated podcast sources, transcribes new episodes via OpenAI Whisper, generates bilingual (Korean/English) analytical summaries via Claude, and publishes them to a premium editorial web app — twice a week, fully unattended.

The reading experience is designed to feel like **The Economist meets Stratechery**: authoritative, scannable, and opinionated. Not AI slop — structured analysis with "So what?" framing.

## Sources

| Podcast | Domain | Frequency |
|---------|--------|-----------|
| **Odd Lots** (Bloomberg) | Macro / Markets | 2-3x/week |
| **Dwarkesh Podcast** | AI / Tech Deep Dive | Biweekly |
| **Lex Fridman Podcast** | AI / Science / Philosophy | Biweekly |
| **Fareed Zakaria GPS** (CNN) | Geopolitics / Foreign Affairs | Weekly |
| **Hard Fork** (NYT) | Tech / AI Current Affairs | Weekly |
| **a16z Podcast** | VC / Tech Business | 2-3x/week |
| **Ezra Klein Show** (NYT) | Politics / Policy / Philosophy | 1-2x/week |
| **All-In Podcast** | Tech x Politics x Economics | 1-2x/week |
| **Exponential View** | AI x Energy x Geopolitics | Weekly |
| **Making Sense** (Sam Harris) | Philosophy / AI Ethics | Biweekly |

## How It Works

```
RSS Feeds ──→ New Episode Detection ──→ Audio Download
                                            │
                                            ▼
                                    Whisper API (STT)
                                            │
                                            ▼
                                   Claude Sonnet (LLM)
                                     │            │
                                     ▼            ▼
                              Korean Brief   English Brief
                                     │            │
                                     ▼            ▼
                    ┌─────────────────────────────────────┐
                    │  Astro Static Site (GitHub Pages)    │
                    │  Google Sheets Dashboard             │
                    │  Transcript Archive (GitHub Repo)    │
                    └─────────────────────────────────────┘
```

**Pipeline** runs Mon/Thu at 06:00 UTC via GitHub Actions. Each episode goes through:

1. **RSS Detection** — checks 10 feeds for new episodes
2. **Audio Download** — fetches MP3, converts to mono 16kHz via ffmpeg
3. **Transcription** — OpenAI Whisper API (with chunking for long episodes)
4. **Analysis** — Claude generates Economist-style bilingual briefings with structured key points, notable quotes, and guest identification
5. **Output** — JSON summaries, transcript files, Google Sheets row, Astro rebuild, GitHub Pages deploy

## Architecture

```
podcast-briefing/
├── pipeline/              # Python: RSS → Whisper → Claude → JSON
│   ├── fetch_feeds.py     # RSS parsing + episode detection
│   ├── download_audio.py  # Audio download + ffmpeg preprocessing
│   ├── transcribe.py      # Whisper API + Substack fallback
│   ├── summarize.py       # Claude analytical briefing prompt
│   ├── generate_output.py # JSON + feed index generation
│   ├── sheets.py          # Google Sheets dashboard integration
│   └── main.py            # Orchestrator
├── web/                   # Astro: editorial static site
│   └── src/
│       ├── pages/         # index (latest 7 days) + archive (all)
│       ├── components/    # EpisodeCard, LangToggle, CategoryFilter
│       ├── layouts/       # BaseLayout with OG tags
│       └── styles/        # Editorial design system (Georgia, 720px, #b44)
├── config/feeds.yaml      # Podcast source configuration
├── data/
│   ├── summaries/         # Episode JSON files
│   └── transcripts/       # Full transcript text files
└── .github/workflows/     # CI/CD: pipeline + deploy
```

## Design Decisions

- **Typography**: Georgia serif for body, system sans-serif for UI — The Economist editorial feel
- **Layout**: 720px reading column, generous whitespace (56px between episodes)
- **Color**: Near-white background (#fafaf8), single red accent (#b44) for category labels and quotes
- **Interactivity**: KO/EN instant toggle (CSS swap, no reload), category filter pills, `<details>` source disclosure
- **Action bar**: Episode link + transcript copy + Obsidian .md download — unified at card bottom, never interrupts reading flow
- **Mobile**: Responsive with stacked action bar, 44px touch targets, horizontally scrollable filters

## Features

- **Bilingual** — Korean (formal register) and English, instant toggle
- **Analytical** — "So what?" framing, claim-based headings, evidence → implication flow
- **Guest identification** — automatic extraction of guest name + affiliation
- **Transcript access** — copy to clipboard (for NotebookLM) or download as Obsidian .md
- **Google Sheets dashboard** — personal episode management with star ratings, read tracking, notes
- **Archive** — all episodes grouped by week, compact list view
- **10 Sources disclosure** — expandable in-page list, no modal

## Cost

| Component | Monthly Cost |
|-----------|-------------|
| Whisper API (transcription) | ~$15-18 |
| Claude Sonnet (summaries) | ~$8 |
| GitHub Actions | Free |
| GitHub Pages hosting | Free |
| **Total** | **~$23-26/mo** |

## Setup

1. Clone the repo
2. Set GitHub Secrets: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
3. Optional: `GOOGLE_SHEETS_CREDENTIALS`, `GOOGLE_SHEET_ID` for Sheets dashboard
4. Edit `config/feeds.yaml` to customize sources
5. Push — GitHub Actions handles the rest

## Local Development

```bash
# Web app
cd web && npm install && npm run dev

# Pipeline (requires API keys as env vars)
pip install -r requirements.txt
python pipeline/main.py
```

---

## 한국어

### 이게 뭔가요?

세계 최고의 팟캐스트 10개를 자동으로 모니터링하고, AI가 한국어/영어 양방향 분석 브리핑을 생성하는 시스템입니다. 매주 월/목 자동 실행됩니다.

### 특징

- **이코노미스트 스타일 분석** — 단순 요약이 아니라 "So what?" 프레이밍의 분석적 브리핑
- **한국어/영어 즉시 전환** — 버튼 하나로 언어 전환 (리로드 없음)
- **게스트 자동 식별** — 게스트 이름 + 소속/직함 자동 추출
- **트랜스크립트 접근** — 클립보드 복사 (NotebookLM용) 또는 Obsidian .md 다운로드
- **Google Sheets 대시보드** — 별점, 읽음 체크, 메모 등 개인 관리
- **주간 아카이브** — 전체 에피소드를 주 단위로 정리

### 한국어 텍스트 규칙

한국어 브리핑에서 고유명사는 영어를 유지합니다:
- 인명: "Torsten Sløk" (토르스텐 슬뢰크 ✗)
- 기업명: "Apollo", "Federal Reserve" (아폴로 ✗, 연방준비제도 ✗)
- 기술 용어: 표준 한국어 번역이 없는 경우 영어 유지

### 비용

Whisper(전사) ~$15-18/월 + Claude(요약) ~$8/월 = **월 ~$23-26**. 호스팅 무료.

---

<div align="center">

Built with [Astro](https://astro.build), [Claude](https://anthropic.com), and [Whisper](https://openai.com) — designed in the spirit of The Economist

</div>
