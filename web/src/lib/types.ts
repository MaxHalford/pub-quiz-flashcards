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
    onboarded?: boolean;
  };
};
