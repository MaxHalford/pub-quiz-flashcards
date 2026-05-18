import { Peer, type DataConnection } from 'peerjs';
import type {
  HostToPlayer,
  PlayerToHost,
  PlayerInfo,
  QuestionPayload,
  RevealPayload
} from './protocol';
import { PROTOCOL_VERSION } from './protocol';

export type PlayerMode =
  | 'connecting'
  | 'joining'
  | 'waiting'
  | 'question'
  | 'reveal'
  | 'kicked'
  | 'error';

export class PlayerController {
  mode = $state<PlayerMode>('connecting');
  paused = $state(false);
  pausedRemainingMs = $state<number | null>(null);
  username = $state('');
  hostRoomId: string;
  players = $state<PlayerInfo[]>([]);
  currentQuestion = $state<QuestionPayload | null>(null);
  myChoice = $state<number | null>(null);
  lastReveal = $state<RevealPayload | null>(null);
  errorMsg = $state<string | null>(null);

  private peer: Peer | null = null;
  private conn: DataConnection | null = null;

  constructor(roomId: string) {
    this.hostRoomId = roomId;
  }

  init() {
    this.peer = new Peer();
    this.peer.on('open', () => {
      this.connectToHost();
    });
    this.peer.on('error', (err) => {
      if (this.mode === 'connecting') {
        this.errorMsg = err.message ?? String(err);
        this.mode = 'error';
      }
    });
  }

  private connectToHost() {
    if (!this.peer) return;
    const conn = this.peer.connect(this.hostRoomId, { reliable: true });
    this.conn = conn;
    conn.on('open', () => {
      this.mode = 'joining';
    });
    conn.on('data', (raw) => this.handleMessage(raw as HostToPlayer));
    conn.on('close', () => {
      if (this.mode !== 'kicked' && this.mode !== 'error') {
        this.errorMsg = 'Disconnected from host';
        this.mode = 'error';
      }
    });
    conn.on('error', (err) => {
      this.errorMsg = err.message ?? String(err);
      this.mode = 'error';
    });
  }

  submitJoin(username: string) {
    if (!this.conn) return;
    this.username = username;
    this.mode = 'waiting';
    this.send({ type: 'join', username, version: PROTOCOL_VERSION });
  }

  submitAnswer(choiceIndex: number) {
    if (this.mode !== 'question' || !this.currentQuestion || this.paused) return;
    if (this.myChoice !== null) return;
    this.myChoice = choiceIndex;
    this.send({
      type: 'answer',
      questionIndex: this.currentQuestion.index,
      choiceIndex
    });
  }

  private send(msg: PlayerToHost) {
    try {
      this.conn?.send(msg);
    } catch {
      // ignore
    }
  }

  private handleMessage(msg: HostToPlayer) {
    switch (msg.type) {
      case 'hello':
        break;
      case 'roster':
        this.players = msg.players;
        break;
      case 'join-rejected':
        this.errorMsg = msg.reason;
        this.mode = 'kicked';
        break;
      case 'question': {
        const isNewQuestion =
          !this.currentQuestion || this.currentQuestion.index !== msg.payload.index;
        this.currentQuestion = msg.payload;
        if (isNewQuestion) {
          this.myChoice = null;
          this.lastReveal = null;
        }
        this.mode = 'question';
        break;
      }
      case 'reveal':
        this.lastReveal = msg.payload;
        this.mode = 'reveal';
        break;
      case 'paused':
        this.paused = true;
        this.pausedRemainingMs = msg.remainingMs;
        break;
      case 'resumed':
        this.paused = false;
        this.pausedRemainingMs = null;
        if (msg.remainingMs !== null && this.currentQuestion) {
          this.currentQuestion = {
            ...this.currentQuestion,
            durationMs: msg.remainingMs
          };
        }
        break;
      case 'host-closed':
        this.errorMsg = 'Host ended the session';
        this.mode = 'error';
        break;
    }
  }

  destroy() {
    this.conn?.close();
    if (this.peer && !this.peer.destroyed) this.peer.destroy();
  }
}
