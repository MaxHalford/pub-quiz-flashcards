export const PROTOCOL_VERSION = 2;

export type PlayerInfo = {
  id: string;
  username: string;
};

export type QuestionPayload = {
  index: number;
  q: string;
  choices: string[];
  durationMs: number;
};

export type RevealPayload = {
  correctIndex: number;
  scores: ScoreEntry[];
  yourPoints: number;
};

export type ScoreEntry = {
  id: string;
  username: string;
  score: number;
  connected: boolean;
};

export type HostToPlayer =
  | { type: 'hello'; version: number }
  | { type: 'roster'; players: PlayerInfo[] }
  | { type: 'join-rejected'; reason: string }
  | { type: 'question'; payload: QuestionPayload }
  | { type: 'reveal'; payload: RevealPayload }
  | { type: 'paused'; remainingMs: number | null }
  | { type: 'resumed'; remainingMs: number | null }
  | { type: 'host-closed' };

export type PlayerToHost =
  | { type: 'join'; username: string; version: number }
  | { type: 'answer'; questionIndex: number; choiceIndex: number };
