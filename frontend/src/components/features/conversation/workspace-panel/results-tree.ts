import type { WorkspaceFile } from "#/types/workspace-file";

/** Results-panel helpers: directory listing, sorting, selection, formatting. */

export type SortKey = "time" | "size" | "name";
export type SortDir = "asc" | "desc";
export interface SortOrder {
  key: SortKey;
  dir: SortDir;
}
export type ViewMode = "list" | "columns";
export type SelectionState = "all" | "some" | "none";

/** Direction a sort key starts with: newest / largest first, names A→Z. */
export const DEFAULT_SORT_DIR: Record<SortKey, SortDir> = {
  time: "desc",
  size: "desc",
  name: "asc",
};
export const DEFAULT_SORT: SortOrder = { key: "time", dir: "desc" };

export interface FolderEntry {
  name: string;
  /** Workspace-relative path of the folder. */
  path: string;
  /** Number of (visible) files anywhere below the folder. */
  count: number;
  /** Total size of those files in bytes. */
  size: number;
  /** Newest file time below the folder (0 when empty). */
  mtime: number;
}

export interface DirectoryListing {
  folders: FolderEntry[];
  /** Files that live directly in the directory. */
  files: WorkspaceFile[];
}

export const joinPath = (dir: string, name: string) =>
  dir ? `${dir}/${name}` : name;

/**
 * Split a recursive flat listing into the folders and files visible at `cwd`.
 * `cwd` is a workspace-relative directory ("" for the root, "a/b" otherwise).
 */
export function listDirectory(
  items: WorkspaceFile[],
  cwd: string,
  dirs: string[] = [],
): DirectoryListing {
  const prefix = cwd ? `${cwd}/` : "";
  const files: WorkspaceFile[] = [];
  const stats = new Map<
    string,
    { count: number; size: number; mtime: number }
  >();

  items.forEach((f) => {
    if (!f.path.startsWith(prefix)) return;
    const rest = f.path.slice(prefix.length);
    const slash = rest.indexOf("/");
    if (slash === -1) {
      files.push(f);
      return;
    }
    const folder = rest.slice(0, slash);
    const s = stats.get(folder) ?? { count: 0, size: 0, mtime: 0 };
    s.count += 1;
    s.size += f.size;
    s.mtime = Math.max(s.mtime, f.mtime);
    stats.set(folder, s);
  });

  // Directories without any visible file (e.g. a fresh, empty `data/`).
  dirs.forEach((dir) => {
    if (!dir.startsWith(prefix)) return;
    const folder = dir.slice(prefix.length).split("/")[0];
    if (folder && !stats.has(folder)) {
      stats.set(folder, { count: 0, size: 0, mtime: 0 });
    }
  });

  const folders = Array.from(stats, ([name, s]) => ({
    name,
    path: joinPath(cwd, name),
    ...s,
  })).sort((a, b) => a.name.localeCompare(b.name));

  return { folders, files };
}

function compareBy<T extends { name: string; size: number; mtime: number }>(
  order: SortOrder,
) {
  const sign = order.dir === "asc" ? 1 : -1;
  return (a: T, b: T) => {
    let diff = 0;
    if (order.key === "time") diff = a.mtime - b.mtime;
    else if (order.key === "size") diff = a.size - b.size;
    else
      diff = a.name.localeCompare(b.name, undefined, {
        numeric: true,
        sensitivity: "base",
      });
    // Ties fall back to the name so the order is stable across refreshes.
    return diff !== 0
      ? sign * diff
      : a.name.localeCompare(b.name, undefined, { numeric: true });
  };
}

/** Sort folders and files by one key; folders always stay above files. */
export function sortListing(
  listing: DirectoryListing,
  order: SortOrder,
): DirectoryListing {
  return {
    folders: [...listing.folders].sort(compareBy<FolderEntry>(order)),
    files: [...listing.files].sort(compareBy<WorkspaceFile>(order)),
  };
}

/** How many files below `folderPath` are selected. */
export function folderSelection(
  items: WorkspaceFile[],
  folderPath: string,
  selected: Set<string>,
): SelectionState {
  const prefix = `${folderPath}/`;
  let total = 0;
  let hit = 0;
  items.forEach((f) => {
    if (!f.path.startsWith(prefix)) return;
    total += 1;
    if (selected.has(f.path)) hit += 1;
  });
  if (total === 0 || hit === 0) return "none";
  return hit === total ? "all" : "some";
}

/**
 * Smallest set of paths that covers the selection: a folder whose files are
 * all selected is sent as the folder (the sandbox expands it completely, even
 * when the listing was truncated), everything else file by file.
 */
export function collapseSelection(
  items: WorkspaceFile[],
  selected: Set<string>,
  dirs: string[] = [],
): string[] {
  const out: string[] = [];
  const walk = (cwd: string) => {
    const { folders, files } = listDirectory(items, cwd, dirs);
    files.forEach((f) => {
      if (selected.has(f.path)) out.push(f.path);
    });
    folders.forEach((folder) => {
      const state = folderSelection(items, folder.path, selected);
      if (state === "all") out.push(folder.path);
      else if (state === "some") walk(folder.path);
    });
  };
  walk("");
  return out;
}

const MONTHS_EN = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * Local date and time for the file list: "9月5日, 1:38" / "Sep 5, 1:38" this
 * year, with the year added otherwise. `epochSeconds` is a Unix time; 0 → "".
 */
export function formatFileTime(
  epochSeconds: number,
  lang: "zh" | "en" = "en",
  now = new Date(),
): string {
  if (!epochSeconds) return "";
  const d = new Date(epochSeconds * 1000);
  const time = `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  const sameYear = d.getFullYear() === now.getFullYear();
  if (lang === "zh") {
    const year = sameYear ? "" : `${d.getFullYear()}年`;
    return `${year}${d.getMonth() + 1}月${d.getDate()}日, ${time}`;
  }
  const year = sameYear ? "" : `, ${d.getFullYear()}`;
  return `${MONTHS_EN[d.getMonth()]} ${d.getDate()}${year}, ${time}`;
}

/** Human-readable size: "512 B", "1 KB", "110.9 KB", "2.7 MB". */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(1).replace(/\.0$/, "")} ${units[unit]}`;
}

export function fullTime(epochSeconds: number): string {
  return epochSeconds ? new Date(epochSeconds * 1000).toLocaleString() : "";
}
