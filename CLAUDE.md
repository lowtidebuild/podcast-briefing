# Podcast Briefing

Automated bilingual (KO/EN) podcast summarization pipeline + premium editorial web app.

## Architecture

- **Web app**: Astro static site in `web/` — editorial layout (Georgia serif, 720px column, #fafaf8 bg, #b44 accents)
- **Pipeline**: Python scripts in `pipeline/` — RSS → OpenAI STT (gpt-4o-mini-transcribe) → Claude Sonnet → JSON
- **Data**: Episode summaries as JSON in `data/summaries/`
- **Config**: Podcast feeds in `config/feeds.yaml`
- **CI/CD**: GitHub Actions daily cron → pipeline → Astro build → GitHub Pages

## Key Commands

```bash
# Web app development
cd web && npm run dev

# Run pipeline locally
python pipeline/main.py

# Build for production
cd web && npm run build
```

## Design Principles

- Premium editorial aesthetic (The Economist meets Stratechery)
- Mobile responsive (720px max-width, 16px padding on mobile)
- Bilingual KO/EN with instant toggle (CSS display swap, localStorage persistence)
- Static-first: zero JS by default, Astro islands for interactivity
