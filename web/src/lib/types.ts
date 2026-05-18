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

export type DailyResult = { id: string; knew: boolean };

export type DailyState = {
  date: string;
  reviewed: number;
  extras: number;
  queue: string[];
  entities: SessionEntity[];
  results: DailyResult[];
};

export type AppState = {
  version: 2;
  deviceId: string;
  cards: Record<string, StoredCard>;
  daily: DailyState;
  history: Record<string, number>;
  settings: { dailyGoal: number };
};
