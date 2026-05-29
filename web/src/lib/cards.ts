import { base } from '$app/paths';
import type { Card, EntitySpan } from './types';

export type Manifest = { hash: string; count: number; generatedAt: string };

type SpanTuple = [number, number, number];
type TitleEntry = [string, string]; // [lang, title]
type WireCard = Omit<Card, 'q_entities' | 'a_entities'> & {
  qe?: SpanTuple[];
  ae?: SpanTuple[];
};
type WireCardsFile = { titles: TitleEntry[]; cards: WireCard[] };

const WIKI_HOSTS: Record<string, string> = {
  en: 'en.wikipedia.org',
  fr: 'fr.wikipedia.org'
};

function titleToUrl(lang: string, title: string): string {
  const host = WIKI_HOSTS[lang] ?? 'en.wikipedia.org';
  return `https://${host}/wiki/${encodeURIComponent(title.replace(/ /g, '_'))}`;
}

function hydrate(file: WireCardsFile): Card[] {
  // Precompute URLs and bare titles once per index — strings are then shared
  // across all spans that reference the same entity.
  const titles = file.titles.map(([, title]) => title);
  const urls = file.titles.map(([lang, title]) => titleToUrl(lang, title));
  const materialise = (spans: SpanTuple[]): EntitySpan[] =>
    spans.map(([start, end, i]) => ({ start, end, title: titles[i], url: urls[i] }));
  return file.cards.map((c) => {
    const card: Card = {
      id: c.id,
      q: c.q,
      a: c.a,
      source: c.source,
      source_date: c.source_date,
      source_url: c.source_url
    };
    if (c.tier) card.tier = c.tier;
    if (c.topic) card.topic = c.topic;
    if (c.qe?.length) card.q_entities = materialise(c.qe);
    if (c.ae?.length) card.a_entities = materialise(c.ae);
    return card;
  });
}

export async function loadCards(): Promise<{ cards: Card[]; manifest: Manifest }> {
  const manifestRes = await fetch(`${base}/cards-manifest.json`, { cache: 'no-cache' });
  if (!manifestRes.ok) throw new Error(`manifest ${manifestRes.status}`);
  const manifest = (await manifestRes.json()) as Manifest;
  const cardsRes = await fetch(`${base}/cards.${manifest.hash}.json`);
  if (!cardsRes.ok) throw new Error(`cards ${cardsRes.status}`);
  const file = (await cardsRes.json()) as WireCardsFile;
  return { cards: hydrate(file), manifest };
}

const SOURCE_LABELS: Record<string, string> = {
  the_guardian_weekly: 'The Guardian',
  le_jeu_des_1000_euros: 'Le jeu des 1000 euros'
};

const SOURCE_FLAGS: Record<string, string> = {
  the_guardian_weekly: '🇬🇧',
  le_jeu_des_1000_euros: '🇫🇷'
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}

export function sourceFlag(source: string): string {
  return SOURCE_FLAGS[source] ?? '';
}
