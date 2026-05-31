import type { State } from 'ts-fsrs';

export type EntitySpan = {
  start: number;
  end: number;
  title: string;
  url: string;
};

export type Card = {
  id: string;
  q: string;
  a: string;
  source: string;
  source_date: string;
  source_url: string;
  tier?: string;
  topic?: string;
  q_entities?: EntitySpan[];
  a_entities?: EntitySpan[];
};

export type StoredCard = {
  due: number;
  stability: number;
  difficulty: number;
  elapsed_days: number;
  scheduled_days: number;
  reps: number;
  lapses: number;
  state: State;
  last_review?: number;
};

export type SessionEntity = { title: string; url: string };

export type CardRating = 'knew' | 'unknown' | 'skipped';

export type DailyResult = { id: string; rating: CardRating };

export type DailyState = {
  date: string;
  reviewed: number;
  extras: number;
  queue: string[];
  results: DailyResult[];
};

export type AppState = {
  version: 3;
  deviceId: string;
  cards: Record<string, StoredCard>;
  tombstoned: Record<string, true>;
  daily: DailyState;
  history: Record<string, number>;
  settings: {
    dailyGoal: number;
    disabledSources?: Record<string, true>;
    disabledTopics?: Record<string, true>;
    onboarded?: boolean;
    // When true, FSRS uses Learning/Relearning steps with sub-day intervals,
    // so a card answered correctly can resurface the same day or the next.
    // When false (default), every rating schedules in days — no same-day or
    // next-day repeats, at the cost of losing intra-session drilling on lapses.
    shortTerm?: boolean;
  };
};
