import type { AppState } from './types';
import { loadState, saveState, todayKey } from './storage';

export function exportBackup(): void {
  const state = loadState();
  const payload = JSON.stringify(
    { exportedAt: new Date().toISOString(), state },
    null,
    2
  );
  const blob = new Blob([payload], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `quiz-backup-${todayKey()}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export type ImportResult = { ok: true } | { ok: false; reason: string };

export function importBackup(text: string): ImportResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { ok: false, reason: 'not valid JSON' };
  }
  const wrapper = parsed as { state?: AppState };
  const candidate = wrapper.state ?? (parsed as AppState);
  if (!candidate || typeof candidate !== 'object') {
    return { ok: false, reason: 'missing state object' };
  }
  if (candidate.version !== 3) {
    return { ok: false, reason: `unsupported schema version ${candidate.version}` };
  }
  if (
    !candidate.cards ||
    !candidate.suspended ||
    !candidate.daily ||
    !candidate.history ||
    !candidate.settings
  ) {
    return { ok: false, reason: 'state is missing required fields' };
  }
  saveState(candidate);
  return { ok: true };
}
