import { base } from '$app/paths';
import type { Card } from './types';

export type Manifest = { hash: string; count: number; generatedAt: string };

export async function loadCards(): Promise<{ cards: Card[]; manifest: Manifest }> {
  const manifestRes = await fetch(`${base}/cards-manifest.json`, { cache: 'no-cache' });
  if (!manifestRes.ok) throw new Error(`manifest ${manifestRes.status}`);
  const manifest = (await manifestRes.json()) as Manifest;
  const cardsRes = await fetch(`${base}/cards.${manifest.hash}.json`);
  if (!cardsRes.ok) throw new Error(`cards ${cardsRes.status}`);
  const cards = (await cardsRes.json()) as Card[];
  return { cards, manifest };
}

const SOURCE_LABELS: Record<string, string> = {
  the_guardian_weekly: 'The Guardian'
};

export function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] ?? source;
}
