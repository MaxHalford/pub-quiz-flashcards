import type { AppState, DailyState } from './types';

const KEY = 'quiz:state:v2';
const SCHEMA = 2;

export function todayKey(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function freshDaily(): DailyState {
  return { date: todayKey(), reviewed: 0, extras: 0, queue: [], entities: [], results: [] };
}

function emptyState(): AppState {
  return {
    version: SCHEMA,
    deviceId: crypto.randomUUID(),
    cards: {},
    daily: freshDaily(),
    history: {},
    settings: { dailyGoal: 10 }
  };
}

export function loadState(): AppState {
  if (typeof localStorage === 'undefined') return emptyState();
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return emptyState();
    const parsed = JSON.parse(raw) as AppState;
    if (parsed.version !== SCHEMA) return emptyState();
    parsed.daily.entities ??= [];
    parsed.daily.results ??= [];
    return parsed;
  } catch {
    return emptyState();
  }
}

export function saveState(state: AppState): void {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // quota or disabled storage — accept the loss for now
  }
}

export function ensureToday(state: AppState): AppState {
  const today = todayKey();
  if (state.daily.date !== today) {
    state.daily = freshDaily();
  }
  return state;
}
