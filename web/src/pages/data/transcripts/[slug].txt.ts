import type { APIRoute, GetStaticPaths } from 'astro';
import { loadTranscript, loadTranscriptSlugs } from '../../../lib/episodes';

export const prerender = true;

export const getStaticPaths: GetStaticPaths = () =>
  loadTranscriptSlugs().map((slug) => ({
    params: { slug },
  }));

export const GET: APIRoute = ({ params }) => {
  const slug = params.slug || '';
  const transcript = loadTranscript(slug);

  if (transcript === null) {
    return new Response('Transcript not found', { status: 404 });
  }

  return new Response(transcript, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
