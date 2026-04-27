import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

export interface Guest {
  name: string;
  title: string;
}

export interface KeyPoint {
  heading: string;
  body: string;
}

export interface Quote {
  text: string;
  attribution: string;
}

export interface GroundedQuote {
  source_text_en: string;
  translation_ko: string;
  speaker: string;
  attribution: string;
  is_verbatim: boolean;
  translation_is_verbatim: boolean;
  source_char_start: number | null;
  source_char_end: number | null;
  match_score: number;
}

export interface Episode {
  slug: string;
  podcast: string;
  category: string;
  title: string;
  published: string;
  link: string;
  podcast_url?: string;
  guest?: Guest | null;
  summary_ko: string;
  summary_en: string;
  key_points_ko: KeyPoint[];
  key_points_en: KeyPoint[];
  notable_quote_ko: Quote;
  notable_quote_en: Quote;
  notable_quote?: GroundedQuote | null;
  keywords_ko: string[];
  keywords_en: string[];
}

const repoDataDir = join(process.cwd(), '..', 'data');
const summariesDir = join(repoDataDir, 'summaries');
const transcriptsDir = join(repoDataDir, 'transcripts');

export function loadEpisodes(): Episode[] {
  const files = readdirSync(summariesDir)
    .filter((file) => file.endsWith('.json') && file !== 'feed.json');

  return files
    .map((file) => JSON.parse(readFileSync(join(summariesDir, file), 'utf-8')))
    .filter((episode: Partial<Episode>) => episode.slug)
    .sort(
      (a: Episode, b: Episode) =>
        new Date(b.published).getTime() - new Date(a.published).getTime(),
    );
}

export function loadTranscriptSlugs(): string[] {
  if (!existsSync(transcriptsDir)) return [];
  return readdirSync(transcriptsDir)
    .filter((file) => file.endsWith('.txt'))
    .map((file) => file.replace(/\.txt$/, ''));
}

export function loadTranscriptSlugSet(): Set<string> {
  return new Set(loadTranscriptSlugs());
}

export function loadTranscript(slug: string): string | null {
  if (!/^[\w-]+$/.test(slug)) return null;
  const path = join(transcriptsDir, `${slug}.txt`);
  if (!existsSync(path)) return null;
  return readFileSync(path, 'utf-8');
}
