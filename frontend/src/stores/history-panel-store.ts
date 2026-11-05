import { create } from "zustand";

const STORAGE_KEY = "targetmind-history-panel-open";

function readOpen(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeOpen(open: boolean) {
  try {
    window.localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
  } catch {
    // Private mode / quota: the choice just isn't remembered.
  }
}

interface HistoryPanelState {
  /** Task history column next to the rail (remembered per browser). */
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
}

export const useHistoryPanelStore = create<HistoryPanelState>((set, get) => ({
  isOpen: readOpen(),
  setOpen: (open) => {
    writeOpen(open);
    set({ isOpen: open });
  },
  toggle: () => get().setOpen(!get().isOpen),
}));
