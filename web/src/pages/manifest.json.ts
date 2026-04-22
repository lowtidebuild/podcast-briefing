/**
 * /manifest.json — published for briefing-hub aggregator.
 *
 * Schema follows DESIGN.md §4 of the briefing-hub repo:
 *   { name, category, accent, description, url, updated_at, latest, items[] }
 *
 * items[].url points to each episode's original podcast audio (link field) —
 * what KP wants to share with friends so they can listen directly.
 *
 * Reads from ../data/summaries/*.json (project-root data dir, outside web/).
 */
import type { APIRoute } from "astro";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

interface EpisodeData {
  slug: string;
  podcast: string;
  category: string;
  title: string;
  published: string; // ISO 8601 with TZ
  link: string;
}

const SITE_URL = "https://lowtidebuild.github.io/podcast-briefing/";
const MAX_ITEMS = 10;

export const GET: APIRoute = async () => {
  const dataDir = join(process.cwd(), "..", "data", "summaries");
  const files = readdirSync(dataDir).filter(
    (f) => f.endsWith(".json") && f !== "feed.json",
  );

  const episodes: EpisodeData[] = files.map((f) =>
    JSON.parse(readFileSync(join(dataDir, f), "utf-8")),
  );

  // Newest first
  episodes.sort(
    (a, b) => new Date(b.published).getTime() - new Date(a.published).getTime(),
  );

  const items = episodes.slice(0, MAX_ITEMS).map((ep) => ({
    title: ep.title,
    source: ep.podcast,
    url: ep.link,
    published_at: new Date(ep.published).toISOString(),
  }));

  const latest = items[0];

  const manifest = {
    name: "Podcast Briefing",
    category: "Podcast",
    accent: "#bb4444",
    description: "10개 영어 팟캐스트 · 한·영 이중언어 큐레이션",
    url: SITE_URL,
    updated_at: latest?.published_at ?? new Date().toISOString(),
    latest,
    items,
  };

  return new Response(JSON.stringify(manifest, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=300",
    },
  });
};
