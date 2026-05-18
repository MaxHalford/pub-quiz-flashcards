import type { Card } from '$lib/types';

export type GameQuestion = {
  cardId: string;
  q: string;
  choices: string[];
  correctIndex: number;
};

function normalize(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, ' ');
}

function shuffle<T>(arr: T[]): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function buildQuestion(card: Card, pool: Card[]): GameQuestion {
  const taken = new Set<string>([normalize(card.a)]);
  const candidates = shuffle(pool.filter((c) => c.id !== card.id));
  const distractors: string[] = [];
  for (const c of candidates) {
    if (distractors.length === 3) break;
    const key = normalize(c.a);
    if (taken.has(key)) continue;
    taken.add(key);
    distractors.push(c.a);
  }
  // Fallback for tiny pools — pad with placeholders so the UI always has 4 choices.
  while (distractors.length < 3) distractors.push('—');

  const all = shuffle([card.a, ...distractors]);
  return {
    cardId: card.id,
    q: card.q,
    choices: all,
    correctIndex: all.indexOf(card.a)
  };
}

export function pickGameCards(pool: Card[], count: number): Card[] {
  return shuffle(pool).slice(0, count);
}
