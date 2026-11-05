import { create } from "zustand";
import type { WorkspaceFile } from "#/types/workspace-file";

/**
 * Upper bound on viewer tabs. Opening more evicts the least-recently opened
 * tab that isn't the active one, so a long analysis session can't accumulate
 * dozens of tabs (each holding a cached file payload).
 */
export const MAX_VIEWER_TABS = 8;

interface WorkspaceViewerState {
  /** Tab strip contents, in the order the files were opened. */
  openFiles: WorkspaceFile[];
  /** The tab currently shown in the viewer, or `null` when nothing is open. */
  selectedFile: WorkspaceFile | null;
  workingDir: string | null;
  /** Open a file in a new tab (or focus its tab if it is already open). */
  openFile: (file: WorkspaceFile, workingDir: string) => void;
  /** Focus an already-open tab. No-op for a path that isn't open. */
  selectFile: (path: string) => void;
  /** Close one tab by path, focusing a neighbour when it was the active one. */
  closeTab: (path: string) => void;
  /** Close the active tab. */
  closeFile: () => void;
  /** Close every tab — used when switching conversations. */
  closeAll: () => void;
  /** Replace open-tab metadata when the agent writes a newer file version. */
  syncFiles: (files: WorkspaceFile[]) => void;
}

/** Tracks the files open in the TargetMind file viewer (middle pane). */
export const useWorkspaceViewerStore = create<WorkspaceViewerState>(
  (set, get) => ({
    openFiles: [],
    selectedFile: null,
    workingDir: null,

    openFile: (file, workingDir) =>
      set((state) => {
        const isOpen = state.openFiles.some((f) => f.path === file.path);
        if (isOpen) {
          return { selectedFile: file, workingDir };
        }
        const openFiles = [...state.openFiles, file];
        while (openFiles.length > MAX_VIEWER_TABS) {
          // Evict the oldest tab that isn't the one we just opened.
          const evictable = openFiles.findIndex((f) => f.path !== file.path);
          openFiles.splice(evictable === -1 ? 0 : evictable, 1);
        }
        return { openFiles, selectedFile: file, workingDir };
      }),

    selectFile: (path) => {
      const file = get().openFiles.find((f) => f.path === path);
      if (file) set({ selectedFile: file });
    },

    closeTab: (path) =>
      set((state) => {
        const index = state.openFiles.findIndex((f) => f.path === path);
        const openFiles =
          index === -1
            ? state.openFiles
            : state.openFiles.filter((f) => f.path !== path);
        if (state.selectedFile?.path !== path) return { openFiles };
        // Focus the tab that slid into this slot, else the new last tab.
        const next =
          openFiles[index] ?? openFiles[openFiles.length - 1] ?? null;
        return { openFiles, selectedFile: next };
      }),

    closeFile: () => {
      const { selectedFile, closeTab } = get();
      if (selectedFile) closeTab(selectedFile.path);
    },

    closeAll: () =>
      set({ openFiles: [], selectedFile: null, workingDir: null }),

    syncFiles: (files) =>
      set((state) => {
        const latestByPath = new Map(files.map((file) => [file.path, file]));
        let changed = false;
        const openFiles = state.openFiles.map((openFile) => {
          const latest = latestByPath.get(openFile.path);
          if (
            !latest ||
            (latest.mtime === openFile.mtime &&
              latest.size === openFile.size &&
              latest.name === openFile.name &&
              latest.ext === openFile.ext &&
              latest.is_image === openFile.is_image)
          ) {
            return openFile;
          }
          changed = true;
          return latest;
        });

        if (!changed) return state;
        const selectedFile = state.selectedFile
          ? (openFiles.find((file) => file.path === state.selectedFile?.path) ??
            state.selectedFile)
          : null;
        return { openFiles, selectedFile };
      }),
  }),
);
