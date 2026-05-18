import { Peer, type DataConnection } from 'peerjs';
import type { Card } from '$lib/types';
import type {
  HostToPlayer,
  PlayerToHost,
  PlayerInfo,
  ScoreEntry
} from './protocol';
import { PROTOCOL_VERSION } from './protocol';
import { buildQuestion, pickGameCards, type GameQuestion } from './distractors';
import { pointsForRank } from './scoring';

export const QUESTION_DURATION_MS = 20_000;
export const REVEAL_DURATION_MS = 5_000;
export const MAX_USERNAME_LEN = 20;

type Player = {
  id: string;
  username: string;
  conn: DataConnection;
  connected: boolean;
  score: number;
  lastChoiceIndex: number | null;
  pointsThisQuestion: number;
};

export type HostMode = 'connecting' | 'question' | 'reveal' | 'paused';

export class HostController {
  peerId = $state<string | null>(null);
  mode = $state<HostMode>('connecting');
  players = $state<Player[]>([]);
  questionIndex = $state(0);
  currentQuestion = $state<GameQuestion | null>(null);
  questionDeadline = $state<number>(0);
  error = $state<string | null>(null);

  private peer: Peer | null = null;
  private cards: Card[];
  private pool: GameQuestion[] = [];
  private poolCursor = 0;
  private correctOrder: string[] = [];
  private timer: ReturnType<typeof setTimeout> | null = null;
  private pausedRemainingMs = 0;
  private modeBeforePause: 'question' | 'reveal' = 'question';

  constructor(cards: Card[]) {
    this.cards = cards;
  }

  init() {
    this.peer = new Peer();
    this.peer.on('open', (id) => {
      this.peerId = id;
      this.nextQuestion();
    });
    this.peer.on('connection', (conn) => this.handleIncoming(conn));
    this.peer.on('error', (err) => {
      this.error = err.message ?? String(err);
    });
  }

  private handleIncoming(conn: DataConnection) {
    let player: Player | null = null;
    conn.on('open', () => {
      this.sendTo(conn, { type: 'hello', version: PROTOCOL_VERSION, yourId: conn.peer });
    });
    conn.on('data', (raw) => {
      const msg = raw as PlayerToHost;
      if (msg.type === 'join') {
        const username = msg.username.trim().slice(0, MAX_USERNAME_LEN);
        if (!username) {
          this.sendTo(conn, { type: 'join-rejected', reason: 'Username required' });
          setTimeout(() => conn.close(), 200);
          return;
        }
        const taken = this.players.some(
          (p) => p.connected && p.username.toLowerCase() === username.toLowerCase()
        );
        if (taken) {
          this.sendTo(conn, { type: 'join-rejected', reason: 'Name taken' });
          setTimeout(() => conn.close(), 200);
          return;
        }
        player = {
          id: conn.peer,
          username,
          conn,
          connected: true,
          score: 0,
          lastChoiceIndex: null,
          pointsThisQuestion: 0
        };
        this.players = [...this.players, player];
        this.broadcastRoster();
        this.sendSnapshot(conn);
      } else if (msg.type === 'answer') {
        if (this.mode !== 'question' || !player || !this.currentQuestion) return;
        if (msg.questionIndex !== this.questionIndex) return;
        if (player.lastChoiceIndex !== null) return;
        player.lastChoiceIndex = msg.choiceIndex;
        if (msg.choiceIndex === this.currentQuestion.correctIndex) {
          this.correctOrder.push(player.id);
        }
        this.players = [...this.players];
        const allAnswered = this.players.every(
          (p) => !p.connected || p.lastChoiceIndex !== null
        );
        if (allAnswered) this.advanceToReveal();
      }
    });
    conn.on('close', () => {
      if (player) {
        player.connected = false;
        this.players = [...this.players];
        this.broadcastRoster();
      }
    });
  }

  private sendTo(conn: DataConnection, msg: HostToPlayer) {
    try {
      conn.send(msg);
    } catch {
      // connection might be closed
    }
  }

  private broadcast(msg: HostToPlayer) {
    for (const p of this.players) {
      if (p.connected) this.sendTo(p.conn, msg);
    }
  }

  private broadcastRoster() {
    const players: PlayerInfo[] = this.players
      .filter((p) => p.connected)
      .map((p) => ({ id: p.id, username: p.username }));
    this.broadcast({ type: 'roster', players });
  }

  private sendSnapshot(conn: DataConnection) {
    if (!this.currentQuestion) return;
    const q = this.currentQuestion;
    if (this.mode === 'question') {
      const remaining = Math.max(0, this.questionDeadline - Date.now());
      this.sendTo(conn, {
        type: 'question',
        payload: { index: this.questionIndex, q: q.q, choices: q.choices, durationMs: remaining }
      });
    } else if (this.mode === 'reveal') {
      this.sendTo(conn, {
        type: 'question',
        payload: { index: this.questionIndex, q: q.q, choices: q.choices, durationMs: 0 }
      });
      this.sendTo(conn, {
        type: 'reveal',
        payload: {
          correctIndex: q.correctIndex,
          scores: this.snapshotScores(),
          yourPoints: 0
        }
      });
    } else if (this.mode === 'paused') {
      this.sendTo(conn, {
        type: 'question',
        payload: {
          index: this.questionIndex,
          q: q.q,
          choices: q.choices,
          durationMs: this.modeBeforePause === 'question' ? this.pausedRemainingMs : 0
        }
      });
      if (this.modeBeforePause === 'reveal') {
        this.sendTo(conn, {
          type: 'reveal',
          payload: {
            correctIndex: q.correctIndex,
            scores: this.snapshotScores(),
            yourPoints: 0
          }
        });
      }
      this.sendTo(conn, {
        type: 'paused',
        remainingMs: this.modeBeforePause === 'question' ? this.pausedRemainingMs : null
      });
    }
  }

  private refillPool() {
    this.pool = pickGameCards(this.cards, this.cards.length).map((c) =>
      buildQuestion(c, this.cards)
    );
    this.poolCursor = 0;
  }

  private nextQuestion() {
    if (this.poolCursor >= this.pool.length) this.refillPool();
    if (this.pool.length === 0) return; // no cards
    const q = this.pool[this.poolCursor++];
    this.questionIndex += 1;
    this.currentQuestion = q;
    this.correctOrder = [];
    for (const p of this.players) {
      p.lastChoiceIndex = null;
      p.pointsThisQuestion = 0;
    }
    this.players = [...this.players];
    this.mode = 'question';
    this.questionDeadline = Date.now() + QUESTION_DURATION_MS;
    this.broadcast({
      type: 'question',
      payload: {
        index: this.questionIndex,
        q: q.q,
        choices: q.choices,
        durationMs: QUESTION_DURATION_MS
      }
    });
    this.timer = setTimeout(() => this.advanceToReveal(), QUESTION_DURATION_MS);
  }

  private advanceToReveal() {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.mode !== 'question' || !this.currentQuestion) return;
    for (let i = 0; i < this.correctOrder.length; i++) {
      const pid = this.correctOrder[i];
      const p = this.players.find((p) => p.id === pid);
      if (!p) continue;
      const pts = pointsForRank(i + 1);
      p.pointsThisQuestion = pts;
      p.score += pts;
    }
    this.players = [...this.players];
    this.mode = 'reveal';
    this.questionDeadline = Date.now() + REVEAL_DURATION_MS;
    const scores = this.snapshotScores();
    for (const p of this.players) {
      if (!p.connected) continue;
      this.sendTo(p.conn, {
        type: 'reveal',
        payload: {
          correctIndex: this.currentQuestion.correctIndex,
          scores,
          yourPoints: p.pointsThisQuestion
        }
      });
    }
    this.timer = setTimeout(() => this.nextQuestion(), REVEAL_DURATION_MS);
  }

  pause() {
    if (this.mode !== 'question' && this.mode !== 'reveal') return;
    this.modeBeforePause = this.mode;
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    this.pausedRemainingMs = Math.max(0, this.questionDeadline - Date.now());
    this.mode = 'paused';
    this.broadcast({
      type: 'paused',
      remainingMs: this.modeBeforePause === 'question' ? this.pausedRemainingMs : null
    });
  }

  resume() {
    if (this.mode !== 'paused') return;
    const ms = this.pausedRemainingMs;
    this.mode = this.modeBeforePause;
    this.questionDeadline = Date.now() + ms;
    if (this.modeBeforePause === 'question') {
      this.timer = setTimeout(() => this.advanceToReveal(), Math.max(0, ms));
      this.broadcast({ type: 'resumed', remainingMs: ms });
    } else {
      this.timer = setTimeout(() => this.nextQuestion(), Math.max(0, ms));
      this.broadcast({ type: 'resumed', remainingMs: null });
    }
  }

  snapshotScores(): ScoreEntry[] {
    return this.players
      .map((p) => ({
        id: p.id,
        username: p.username,
        score: p.score,
        connected: p.connected
      }))
      .sort((a, b) => b.score - a.score);
  }

  destroy() {
    if (this.timer !== null) clearTimeout(this.timer);
    this.broadcast({ type: 'host-closed' });
    for (const p of this.players) {
      try {
        p.conn.close();
      } catch {
        // ignore
      }
    }
    if (this.peer && !this.peer.destroyed) this.peer.destroy();
  }
}
