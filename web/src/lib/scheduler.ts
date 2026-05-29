import { fsrs, createEmptyCard, Rating, type Card as FSRSCard } from 'ts-fsrs';
import type { Card, StoredCard, AppState } from './types';

const f = fsrs();

export function toFSRSCard(stored: StoredCard | undefined, now: Date = new Date()): FSRSCard {
  if (!stored) return createEmptyCard(now);
  return {
    due: new Date(stored.due),
    stability: stored.stability,
    difficulty: stored.difficulty,
    elapsed_days: stored.elapsed_days,
    scheduled_days: stored.scheduled_days,
    reps: stored.reps,
    lapses: stored.lapses,
    state: stored.state,
    last_review: stored.last_review ? new Date(stored.last_review) : undefined
  };
}

export function fromFSRSCard(card: FSRSCard): StoredCard {
  return {
    due: card.due.getTime(),
    stability: card.stability,
    difficulty: card.difficulty,
    elapsed_days: card.elapsed_days,
    scheduled_days: card.scheduled_days,
    reps: card.reps,
    lapses: card.lapses,
    state: card.state,
    last_review: card.last_review?.getTime()
  };
}

export function applyRating(
  stored: StoredCard | undefined,
  knew: boolean,
  now: Date = new Date()
): StoredCard {
  const card = toFSRSCard(stored, now);
  const rating = knew ? Rating.Good : Rating.Again;
  const next = f.next(card, now, rating);
  return fromFSRSCard(next.card);
}

const REVIEW_RATIO = 0.7;

export function planSession(
  allCards: Card[],
  state: AppState,
  size: number,
  now: number = Date.now(),
  exclude: ReadonlySet<string> = new Set()
): Card[] {
  if (size <= 0) return [];

  const disabledSources = state.settings.disabledSources ?? {};
  const disabledTopics = state.settings.disabledTopics ?? {};
  const due: { card: Card; due: number }[] = [];
  const unseen: Card[] = [];
  for (const c of allCards) {
    if (exclude.has(c.id)) continue;
    if (state.tombstoned[c.id]) continue;
    if (disabledSources[c.source]) continue;
    // Untagged cards are keyed by '' in disabledTopics, matching the
    // "Untagged" pill in settings.
    if (disabledTopics[c.topic ?? '']) continue;
    const s = state.cards[c.id];
    if (!s) {
      unseen.push(c);
    } else if (s.due <= now) {
      due.push({ card: c, due: s.due });
    }
  }

  due.sort((a, b) => a.due - b.due);
  const dueSlots = Math.min(due.length, Math.max(1, Math.floor(size * REVIEW_RATIO)));
  const reviewCards = due.slice(0, dueSlots).map((x) => x.card);

  const remaining = size - reviewCards.length;
  const newCards: Card[] = [];
  const pool = [...unseen];
  for (let i = 0; i < remaining && pool.length > 0; i++) {
    const idx = Math.floor(Math.random() * pool.length);
    newCards.push(pool[idx]);
    pool.splice(idx, 1);
  }

  const session = [...reviewCards, ...newCards];
  for (let i = session.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [session[i], session[j]] = [session[j], session[i]];
  }
  return session;
}
