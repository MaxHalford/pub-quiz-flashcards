export const POINTS_FIRST = 1000;
export const POINTS_SECOND = 800;
export const POINTS_OTHER_CORRECT = 500;

export function pointsForRank(rank: number): number {
  if (rank === 1) return POINTS_FIRST;
  if (rank === 2) return POINTS_SECOND;
  return POINTS_OTHER_CORRECT;
}
