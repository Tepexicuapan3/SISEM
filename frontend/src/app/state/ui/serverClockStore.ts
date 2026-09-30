import { create } from "zustand";

interface ServerClockState {
  /** Diferencia en ms entre la hora del servidor y la hora local (Date.now()) */
  offsetMs: number;
  isSynced: boolean;
  setOffset: (serverTimeMs: number) => void;
}

export const useServerClockStore = create<ServerClockState>()((set) => ({
  offsetMs: 0,
  isSynced: false,
  setOffset: (serverTimeMs) =>
    set({ offsetMs: serverTimeMs - Date.now(), isSynced: true }),
}));
