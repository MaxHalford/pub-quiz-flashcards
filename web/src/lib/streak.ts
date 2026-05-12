import { todayKey } from './storage';

export function streakDays(
  history: Record<string, number>,
  now: Date = new Date()
): number {
  const cursor = new Date(now);
  cursor.setHours(0, 0, 0, 0);
  if (!((history[todayKey(cursor)] ?? 0) > 0)) {
    cursor.setDate(cursor.getDate() - 1);
  }
  let count = 0;
  while ((history[todayKey(cursor)] ?? 0) > 0) {
    count++;
    cursor.setDate(cursor.getDate() - 1);
  }
  return count;
}

export type HeatmapCell = {
  date: string;
  count: number;
  weekday: number;
  isFuture: boolean;
};

export function heatmapCells(
  history: Record<string, number>,
  weeks: number = 12,
  now: Date = new Date()
): HeatmapCell[][] {
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  const todayWeekday = today.getDay();

  const leftmostSunday = new Date(today);
  leftmostSunday.setDate(today.getDate() - todayWeekday - (weeks - 1) * 7);

  const cols: HeatmapCell[][] = [];
  for (let w = 0; w < weeks; w++) {
    const col: HeatmapCell[] = [];
    for (let d = 0; d < 7; d++) {
      const date = new Date(leftmostSunday);
      date.setDate(leftmostSunday.getDate() + w * 7 + d);
      const isFuture = date.getTime() > today.getTime();
      const key = todayKey(date);
      col.push({
        date: key,
        count: history[key] ?? 0,
        weekday: d,
        isFuture
      });
    }
    cols.push(col);
  }
  return cols;
}
