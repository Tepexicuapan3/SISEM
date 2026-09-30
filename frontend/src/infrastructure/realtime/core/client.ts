import {
  parseRealtimeEnvelope,
  type RealtimeEventEnvelope,
} from "@realtime/core/protocol";

export const REALTIME_CONNECTION_STATUS = {
  IDLE: "idle",
  CONNECTING: "connecting",
  CONNECTED: "connected",
  DISCONNECTED: "disconnected",
  ERROR: "error",
} as const;

export type RealtimeConnectionStatus =
  (typeof REALTIME_CONNECTION_STATUS)[keyof typeof REALTIME_CONNECTION_STATUS];

export interface RealtimeSequenceGap {
  expectedSequence: number;
  receivedSequence: number;
}

export interface RealtimeSocketClosedInfo {
  code: number;
  reason: string;
}

export interface RealtimeWebSocketLike {
  readyState?: number;
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent<string>) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  close: () => void;
  send?: (payload: string) => void;
}

export interface RealtimeClientState {
  connectionStatus: RealtimeConnectionStatus;
  lastSequence: number | null;
}

export type RealtimeEventHandler = (event: RealtimeEventEnvelope) => void;
export type RealtimeStateChangeHandler = (state: RealtimeClientState) => void;

export interface RealtimeClientOptions {
  url: string;
  createSocket?: (url: string) => RealtimeWebSocketLike;
  backoffBaseMs?: number;
  backoffMaxMs?: number;
  jitterRatio?: number;
  random?: () => number;
  heartbeatIntervalMs?: number;
  heartbeatTimeoutMs?: number;
  heartbeatMessage?: string;
  shouldReconnectOnClose?: (info: RealtimeSocketClosedInfo) => boolean;
  onGap?: (gap: RealtimeSequenceGap) => void;
  onSocketError?: () => void;
  onSocketClosed?: (info: RealtimeSocketClosedInfo) => void;
}

const DEFAULT_BACKOFF_BASE_MS = 1000;
const DEFAULT_BACKOFF_MAX_MS = 30000;
const DEFAULT_JITTER_RATIO = 0.1;
const DEFAULT_HEARTBEAT_INTERVAL_MS = 0;
const DEFAULT_HEARTBEAT_TIMEOUT_MS = 10000;
const DEFAULT_HEARTBEAT_MESSAGE = JSON.stringify({ type: "ping" });
const NON_RECONNECTABLE_CLOSE_CODES = new Set([1000, 1001, 4401, 4403]);

const SOCKET_READY_STATE = {
  CONNECTING: 0,
  OPEN: 1,
} as const;

interface HeartbeatMessage {
  type: string;
}

const createDefaultSocket = (url: string): RealtimeWebSocketLike => {
  if (typeof WebSocket === "undefined") {
    throw new Error("WebSocket is not available in this environment");
  }

  return new WebSocket(url);
};

export class RealtimeClient {
  private readonly url: string;
  private readonly createSocket: (url: string) => RealtimeWebSocketLike;
  private readonly backoffBaseMs: number;
  private readonly backoffMaxMs: number;
  private readonly jitterRatio: number;
  private readonly random: () => number;
  private readonly heartbeatIntervalMs: number;
  private readonly heartbeatTimeoutMs: number;
  private readonly heartbeatMessage: string;
  private readonly shouldReconnectOnClose: (
    info: RealtimeSocketClosedInfo,
  ) => boolean;
  private readonly onGap?: (gap: RealtimeSequenceGap) => void;
  private readonly onSocketError?: () => void;
  private readonly onSocketClosed?: (info: RealtimeSocketClosedInfo) => void;

  private socket: RealtimeWebSocketLike | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private awaitingPong = false;
  private isStopped = false;
  private readonly seenEventIds = new Set<string>();
  private readonly eventHandlers = new Map<string, Set<RealtimeEventHandler>>();
  private readonly stateHandlers = new Set<RealtimeStateChangeHandler>();
  private readonly gapHandlers = new Set<(gap: RealtimeSequenceGap) => void>();
  private readonly socketErrorHandlers = new Set<() => void>();
  private readonly socketClosedHandlers = new Set<
    (info: RealtimeSocketClosedInfo) => void
  >();

  private state: RealtimeClientState = {
    connectionStatus: REALTIME_CONNECTION_STATUS.IDLE,
    lastSequence: null,
  };

  constructor(options: RealtimeClientOptions) {
    this.url = options.url;
    this.createSocket = options.createSocket ?? createDefaultSocket;
    this.backoffBaseMs = options.backoffBaseMs ?? DEFAULT_BACKOFF_BASE_MS;
    this.backoffMaxMs = options.backoffMaxMs ?? DEFAULT_BACKOFF_MAX_MS;
    this.jitterRatio = options.jitterRatio ?? DEFAULT_JITTER_RATIO;
    this.random = options.random ?? Math.random;
    this.heartbeatIntervalMs =
      options.heartbeatIntervalMs ?? DEFAULT_HEARTBEAT_INTERVAL_MS;
    this.heartbeatTimeoutMs =
      options.heartbeatTimeoutMs ?? DEFAULT_HEARTBEAT_TIMEOUT_MS;
    this.heartbeatMessage =
      options.heartbeatMessage ?? DEFAULT_HEARTBEAT_MESSAGE;
    this.shouldReconnectOnClose =
      options.shouldReconnectOnClose ??
      ((info) => !NON_RECONNECTABLE_CLOSE_CODES.has(info.code));
    this.onGap = options.onGap;
    this.onSocketError = options.onSocketError;
    this.onSocketClosed = options.onSocketClosed;
  }

  connect(): void {
    if (this.socket) {
      const currentReadyState = this.socket.readyState;
      if (
        currentReadyState === SOCKET_READY_STATE.CONNECTING ||
        currentReadyState === SOCKET_READY_STATE.OPEN
      ) {
        return;
      }
    }

    this.isStopped = false;
    this.clearReconnectTimer();
    this.openSocket(false);
  }

  disconnect(): void {
    this.isStopped = true;
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();

    if (!this.socket) {
      this.setConnectionStatus(REALTIME_CONNECTION_STATUS.DISCONNECTED);
      return;
    }

    const socket = this.socket;
    this.socket = null;
    socket.onopen = null;
    socket.onmessage = null;
    socket.onerror = null;
    socket.onclose = null;
    socket.close();
    this.setConnectionStatus(REALTIME_CONNECTION_STATUS.DISCONNECTED);
  }

  subscribe(eventType: string, handler: RealtimeEventHandler): () => void {
    const handlers = this.eventHandlers.get(eventType) ?? new Set();
    handlers.add(handler);
    this.eventHandlers.set(eventType, handlers);

    return () => {
      this.unsubscribe(eventType, handler);
    };
  }

  unsubscribe(eventType: string, handler: RealtimeEventHandler): void {
    const handlers = this.eventHandlers.get(eventType);
    if (!handlers) {
      return;
    }

    handlers.delete(handler);
    if (handlers.size === 0) {
      this.eventHandlers.delete(eventType);
    }
  }

  onStateChange(handler: RealtimeStateChangeHandler): () => void {
    this.stateHandlers.add(handler);

    return () => {
      this.stateHandlers.delete(handler);
    };
  }

  getState(): RealtimeClientState {
    return { ...this.state };
  }

  private openSocket(isReconnect: boolean): void {
    if (!isReconnect) {
      this.setConnectionStatus(REALTIME_CONNECTION_STATUS.CONNECTING);
    }

    const socket = this.createSocket(this.url);
    this.socket = socket;
    socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.setConnectionStatus(REALTIME_CONNECTION_STATUS.CONNECTED);
      this.awaitingPong = false;
      this.startHeartbeat();
    };
    socket.onmessage = (event) => {
      this.handleRawMessage(event.data);
    };
    socket.onerror = () => {
      this.setConnectionStatus(REALTIME_CONNECTION_STATUS.ERROR);
      this.notifySocketError();
    };
    socket.onclose = (event) => {
      this.clearHeartbeatTimer();
      this.setConnectionStatus(REALTIME_CONNECTION_STATUS.DISCONNECTED);
      const closedInfo = {
        code: event.code,
        reason: event.reason,
      };
      this.notifySocketClosed(closedInfo);

      if (!this.isStopped && this.shouldReconnectOnClose(closedInfo)) {
        this.scheduleReconnect();
      }
    };
  }

  private handleRawMessage(rawData: string): void {
    if (this.isHeartbeatPong(rawData)) {
      this.acknowledgeHeartbeat();
      return;
    }

    const event = parseRealtimeEnvelope(rawData);
    if (!event) {
      return;
    }

    if (this.seenEventIds.has(event.eventId)) {
      return;
    }

    if (!this.shouldAcceptBySequence(event.sequence)) {
      return;
    }

    this.seenEventIds.add(event.eventId);
    this.setState({ lastSequence: event.sequence });
    this.dispatchEvent(event);
  }

  private shouldAcceptBySequence(sequence: number): boolean {
    const { lastSequence } = this.state;
    if (lastSequence === null) {
      return true;
    }

    if (sequence <= lastSequence) {
      return false;
    }

    if (sequence > lastSequence + 1) {
      this.notifyGap({
        expectedSequence: lastSequence + 1,
        receivedSequence: sequence,
      });
    }

    return true;
  }

  private dispatchEvent(event: RealtimeEventEnvelope): void {
    const handlers = [
      ...(this.eventHandlers.get(event.eventType) ?? []),
      ...(this.eventHandlers.get("*") ?? []),
    ];

    for (const handler of handlers) {
      handler(event);
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();

    const factor = 2 ** this.reconnectAttempts;
    const unclampedBackoff = this.backoffBaseMs * factor;
    const backoff = Math.min(unclampedBackoff, this.backoffMaxMs);
    const jitter = backoff * this.jitterRatio * this.random();
    const reconnectDelayMs = Math.round(backoff + jitter);

    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => {
      this.openSocket(true);
    }, reconnectDelayMs);
  }

  private startHeartbeat(): void {
    this.clearHeartbeatTimer();

    if (this.heartbeatIntervalMs <= 0) {
      return;
    }

    const socket = this.socket;
    if (!socket?.send) {
      return;
    }

    this.heartbeatTimer = setInterval(() => {
      if (this.isStopped || !this.socket?.send) {
        return;
      }

      this.socket.send(this.heartbeatMessage);
      this.trackHeartbeatProbe();
    }, this.heartbeatIntervalMs);
  }

  private clearReconnectTimer(): void {
    if (!this.reconnectTimer) {
      return;
    }

    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  private clearHeartbeatTimer(): void {
    if (!this.heartbeatTimer) {
      this.clearHeartbeatTimeoutTimer();
      this.awaitingPong = false;
      return;
    }

    clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
    this.clearHeartbeatTimeoutTimer();
    this.awaitingPong = false;
  }

  private clearHeartbeatTimeoutTimer(): void {
    if (!this.heartbeatTimeoutTimer) {
      return;
    }

    clearTimeout(this.heartbeatTimeoutTimer);
    this.heartbeatTimeoutTimer = null;
  }

  private trackHeartbeatProbe(): void {
    if (this.heartbeatTimeoutMs <= 0) {
      return;
    }

    this.awaitingPong = true;
    this.clearHeartbeatTimeoutTimer();

    this.heartbeatTimeoutTimer = setTimeout(() => {
      if (!this.awaitingPong || this.isStopped || !this.socket) {
        return;
      }

      this.socket.close();
    }, this.heartbeatTimeoutMs);
  }

  private acknowledgeHeartbeat(): void {
    this.awaitingPong = false;
    this.clearHeartbeatTimeoutTimer();
  }

  private isHeartbeatPong(rawData: string): boolean {
    try {
      const message = JSON.parse(rawData) as HeartbeatMessage;
      return message?.type === "pong";
    } catch {
      return false;
    }
  }

  private setConnectionStatus(status: RealtimeConnectionStatus): void {
    this.setState({ connectionStatus: status });
  }

  onGapDetected(handler: (gap: RealtimeSequenceGap) => void): () => void {
    this.gapHandlers.add(handler);

    return () => {
      this.gapHandlers.delete(handler);
    };
  }

  onSocketErrorDetected(handler: () => void): () => void {
    this.socketErrorHandlers.add(handler);

    return () => {
      this.socketErrorHandlers.delete(handler);
    };
  }

  onSocketClosedDetected(
    handler: (info: RealtimeSocketClosedInfo) => void,
  ): () => void {
    this.socketClosedHandlers.add(handler);

    return () => {
      this.socketClosedHandlers.delete(handler);
    };
  }

  private notifyGap(gap: RealtimeSequenceGap): void {
    this.onGap?.(gap);
    for (const handler of this.gapHandlers) {
      handler(gap);
    }
  }

  private notifySocketError(): void {
    this.onSocketError?.();
    for (const handler of this.socketErrorHandlers) {
      handler();
    }
  }

  private notifySocketClosed(info: RealtimeSocketClosedInfo): void {
    this.onSocketClosed?.(info);
    for (const handler of this.socketClosedHandlers) {
      handler(info);
    }
  }

  private setState(next: Partial<RealtimeClientState>): void {
    this.state = {
      ...this.state,
      ...next,
    };

    const snapshot = this.getState();
    for (const handler of this.stateHandlers) {
      handler(snapshot);
    }
  }
}

interface RealtimeClientRegistryEntry {
  client: RealtimeClient;
  refCount: number;
  disconnectTimer: ReturnType<typeof setTimeout> | null;
}

interface AcquireRealtimeClientOptions {
  disconnectGraceMs?: number;
}

export interface RealtimeClientLease {
  client: RealtimeClient;
  release: () => void;
}

const DEFAULT_DISCONNECT_GRACE_MS = 1_500;
const realtimeClientSingletons = new Map<string, RealtimeClientRegistryEntry>();

const clearDisconnectTimer = (entry: RealtimeClientRegistryEntry): void => {
  if (!entry.disconnectTimer) {
    return;
  }

  clearTimeout(entry.disconnectTimer);
  entry.disconnectTimer = null;
};

const getOrCreateRegistryEntry = (
  options: RealtimeClientOptions,
): RealtimeClientRegistryEntry => {
  const existing = realtimeClientSingletons.get(options.url);
  if (existing) {
    return existing;
  }

  const entry: RealtimeClientRegistryEntry = {
    client: createRealtimeClient(options),
    refCount: 0,
    disconnectTimer: null,
  };

  realtimeClientSingletons.set(options.url, entry);
  return entry;
};

export const createRealtimeClient = (
  options: RealtimeClientOptions,
): RealtimeClient => {
  return new RealtimeClient(options);
};

export const acquireRealtimeClient = (
  options: RealtimeClientOptions,
  acquireOptions: AcquireRealtimeClientOptions = {},
): RealtimeClientLease => {
  const entry = getOrCreateRegistryEntry(options);
  const disconnectGraceMs = Math.max(
    0,
    acquireOptions.disconnectGraceMs ?? DEFAULT_DISCONNECT_GRACE_MS,
  );

  entry.refCount += 1;
  clearDisconnectTimer(entry);
  entry.client.connect();

  let released = false;
  return {
    client: entry.client,
    release: () => {
      if (released) {
        return;
      }
      released = true;

      const current = realtimeClientSingletons.get(options.url);
      if (!current || current.client !== entry.client) {
        return;
      }

      current.refCount = Math.max(0, current.refCount - 1);
      if (current.refCount > 0) {
        return;
      }

      clearDisconnectTimer(current);
      current.disconnectTimer = setTimeout(() => {
        const latest = realtimeClientSingletons.get(options.url);
        if (!latest || latest !== current || latest.refCount > 0) {
          return;
        }

        latest.client.disconnect();
        realtimeClientSingletons.delete(options.url);
      }, disconnectGraceMs);
    },
  };
};

export const resetRealtimeClientSingletonsForTests = (): void => {
  for (const entry of realtimeClientSingletons.values()) {
    clearDisconnectTimer(entry);
    entry.client.disconnect();
  }
  realtimeClientSingletons.clear();
};
