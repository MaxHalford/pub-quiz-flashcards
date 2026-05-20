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
