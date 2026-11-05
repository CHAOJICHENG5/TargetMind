import React from "react";
import type { AxiosError } from "axios";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronRight,
  Columns3,
  CornerLeftUp,
  Download,
  FolderArchive,
  FolderOpen,
  List,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useListWorkspaceFiles } from "#/hooks/query/use-list-workspace-files";
import { useDeleteWorkspaceFile } from "#/hooks/mutation/use-delete-workspace-file";
import { useCreateWorkspaceZip } from "#/hooks/mutation/use-create-workspace-zip";
import { useClickOutsideElement } from "#/hooks/use-click-outside-element";
import { displayErrorToast } from "#/utils/custom-toast-handlers";
import { useWorkspaceViewerStore } from "#/stores/workspace-viewer-store";
import { useConversationId } from "#/hooks/use-conversation-id";
import { useConversationStore } from "#/stores/conversation-store";
import { useTMText } from "#/i18n/targetmind-strings";
import type { WorkspaceFile } from "#/types/workspace-file";
import { cn } from "#/utils/utils";
import { rawUrl } from "./file-viewer";
import {
  DEFAULT_SORT,
  DEFAULT_SORT_DIR,
  type FolderEntry,
  type SelectionState,
  type SortKey,
  type SortOrder,
  type ViewMode,
  collapseSelection,
  folderSelection,
  formatFileSize,
  listDirectory,
  sortListing,
} from "./results-tree";
import { FileRow, FolderRow, type RowText, TriCheckbox } from "./results-rows";

export {
  collapseSelection,
  formatFileSize,
  formatFileTime,
  listDirectory,
  sortListing,
} from "./results-tree";

const VIEW_STORAGE_KEY = "targetmind-results-view";
const SORT_STORAGE_KEY = "targetmind-results-sort";
const SORT_KEYS: SortKey[] = ["time", "size", "name"];
const ZIP_LIMIT_BYTES = 200 * 1024 * 1024;

function readStored<T>(
  key: string,
  parse: (raw: string) => T | null,
): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? null : parse(raw);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private mode / quota: the choice just isn't remembered.
  }
}

const parseView = (raw: string): ViewMode | null =>
  raw === "list" || raw === "columns" ? raw : null;

const parseSort = (raw: string): SortOrder | null => {
  const [key, dir] = raw.split(":");
  if (!SORT_KEYS.includes(key as SortKey)) return null;
  if (dir !== "asc" && dir !== "desc") return null;
  return { key: key as SortKey, dir };
};

/** Trigger a browser download of a same-origin URL. */
function triggerDownload(href: string, filename: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function downloadFile(
  conversationId: string,
  workingDir: string,
  file: WorkspaceFile,
) {
  triggerDownload(
    rawUrl(conversationId, workingDir, file.path, `${file.mtime}-${file.size}`),
    file.name,
  );
}

function zipName(paths: string[], items: WorkspaceFile[]): string {
  const onlyFolder =
    paths.length === 1 && !items.some((f) => f.path === paths[0]);
  if (onlyFolder) return paths[0].split("/").pop() || "results";
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `results-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(
    d.getHours(),
  )}${p(d.getMinutes())}`;
}

const SEGMENT_BUTTON =
  "rounded p-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tm-teal/40";

export function ResultsPanel({
  conversationId,
}: {
  conversationId: string | null | undefined;
}) {
  const tm = useTMText();
  const { i18n } = useTranslation();
  const lang = (i18n?.language || "en").toLowerCase().startsWith("zh")
    ? "zh"
    : "en";
  const { conversationId: routeCid } = useConversationId();
  const cid = conversationId || routeCid;
  const [filter, setFilter] = React.useState("");
  const [collapsed, setCollapsed] = React.useState(false);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  /** Workspace-relative directory currently being browsed ("" = root). */
  const [cwd, setCwd] = React.useState("");
  const [view, setView] = React.useState<ViewMode>(
    () => readStored(VIEW_STORAGE_KEY, parseView) ?? "list",
  );
  const [sort, setSort] = React.useState<SortOrder>(
    () => readStored(SORT_STORAGE_KEY, parseSort) ?? DEFAULT_SORT,
  );
  const [sortMenuOpen, setSortMenuOpen] = React.useState(false);
  const closeSortMenu = React.useCallback(() => setSortMenuOpen(false), []);
  const sortMenuRef = useClickOutsideElement<HTMLDivElement>(closeSortMenu);
  const columnsRef = React.useRef<HTMLDivElement>(null);

  const { data, isLoading, isFetching, refetch } = useListWorkspaceFiles(cid);
  // The sandbox is (re)starting: files cannot be listed yet. Keep any files
  // already shown, otherwise say so instead of "no result files".
  const { shouldShownAgentLoading } = useConversationStore();
  const isWaking = shouldShownAgentLoading && !data?.items?.length;
  const wasWaking = React.useRef(shouldShownAgentLoading);
  React.useEffect(() => {
    if (wasWaking.current && !shouldShownAgentLoading) refetch();
    wasWaking.current = shouldShownAgentLoading;
  }, [shouldShownAgentLoading, refetch]);
  const { openFile, selectedFile, syncFiles } = useWorkspaceViewerStore();
  const deleteFile = useDeleteWorkspaceFile(cid);
  const createZip = useCreateWorkspaceZip(cid);
  /** File whose delete button was clicked once and awaits confirmation. */
  const [confirmingDelete, setConfirmingDelete] = React.useState<string | null>(
    null,
  );

  const items = data?.items ?? [];
  const dirs = data?.dirs ?? [];
  const query = filter.trim().toLowerCase();
  const isSearching = query.length > 0;
  const showColumns = view === "columns" && !isSearching;

  const changeView = (next: ViewMode) => {
    setView(next);
    writeStored(VIEW_STORAGE_KEY, next);
  };

  const chooseSort = (key: SortKey) => {
    const next: SortOrder =
      sort.key === key
        ? { key, dir: sort.dir === "asc" ? "desc" : "asc" }
        : { key, dir: DEFAULT_SORT_DIR[key] };
    setSort(next);
    writeStored(SORT_STORAGE_KEY, `${next.key}:${next.dir}`);
  };

  // A filter searches the whole workspace, so it ignores the current folder.
  const listing = React.useMemo(
    () =>
      sortListing(
        isSearching
          ? {
              folders: [],
              files: items.filter((f) => f.path.toLowerCase().includes(query)),
            }
          : listDirectory(items, cwd, dirs),
        sort,
      ),
    [items, dirs, cwd, isSearching, query, sort],
  );
  const { folders, files } = listing;

  const segments = cwd ? cwd.split("/") : [];

  /** One listing per open level for the column view: root, then each folder. */
  const columns = React.useMemo(() => {
    if (!showColumns) return [];
    const paths = [""].concat(
      segments.map((_, i) => segments.slice(0, i + 1).join("/")),
    );
    return paths.map((path, i) => ({
      path,
      active: segments[i],
      ...sortListing(listDirectory(items, path, dirs), sort),
    }));
    // `segments` is derived from `cwd`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showColumns, items, dirs, cwd, sort]);

  // The agent can delete or replace directories between refetches — never
  // strand the user inside a folder that no longer exists.
  React.useEffect(() => {
    if (
      cwd &&
      data &&
      !dirs.includes(cwd) &&
      !items.some((f) => f.path.startsWith(`${cwd}/`))
    ) {
      setCwd("");
    }
  }, [data, items, dirs, cwd]);

  React.useEffect(() => {
    if (data) syncFiles(data.items);
  }, [data, syncFiles]);

  // Drop selections of files that disappeared (deleted by the agent or user).
  React.useEffect(() => {
    if (!data) return;
    setSelected((prev) => {
      const present = new Set(data.items.map((f) => f.path));
      const next = new Set([...prev].filter((p) => present.has(p)));
      return next.size === prev.size ? prev : next;
    });
  }, [data]);

  // Keep the newest column in view.
  React.useEffect(() => {
    const el = columnsRef.current;
    if (showColumns && el)
      el.scrollTo?.({ left: el.scrollWidth, behavior: "smooth" });
  }, [showColumns, cwd]);

  React.useEffect(() => {
    if (!confirmingDelete) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setConfirmingDelete(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirmingDelete]);

  const setPaths = (paths: string[], on: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      paths.forEach((p) => (on ? next.add(p) : next.delete(p)));
      return next;
    });

  const toggleFile = (path: string) => setPaths([path], !selected.has(path));

  /** Select/deselect every file below a folder. */
  const toggleFolder = (folderPath: string) => {
    const paths = items
      .filter((f) => f.path.startsWith(`${folderPath}/`))
      .map((f) => f.path);
    setPaths(paths, folderSelection(items, folderPath, selected) !== "all");
  };

  /** Everything the "select all" box covers: the matches, or all below cwd. */
  const scopePaths = React.useMemo(() => {
    if (isSearching) return files.map((f) => f.path);
    const prefix = cwd ? `${cwd}/` : "";
    return items.filter((f) => f.path.startsWith(prefix)).map((f) => f.path);
  }, [isSearching, files, items, cwd]);

  const scopeHits = scopePaths.filter((p) => selected.has(p)).length;
  let scopeState: SelectionState = "none";
  if (scopeHits > 0) {
    scopeState = scopeHits === scopePaths.length ? "all" : "some";
  }
  const toggleScope = () => setPaths(scopePaths, scopeState !== "all");

  const confirmDelete = (path: string) =>
    deleteFile.mutate(path, {
      onSuccess: () => setPaths([path], false),
      onError: () => displayErrorToast(tm("panel.deleteFailed")),
      onSettled: () => setConfirmingDelete(null),
    });

  const downloadSelected = () => {
    if (!cid || !data || selected.size === 0) return;
    if (selected.size === 1) {
      const only = items.find((f) => selected.has(f.path));
      if (only) downloadFile(cid, data.working_dir, only);
      return;
    }
    const paths = collapseSelection(items, selected, dirs);
    const filename = zipName(paths, items);
    createZip.mutate(
      { paths, filename },
      {
        onSuccess: ({ url }) => triggerDownload(url, `${filename}.zip`),
        onError: (error) => {
          const detail = (error as AxiosError<{ detail?: { size?: number } }>)
            .response?.data?.detail;
          if ((error as AxiosError).response?.status === 413) {
            displayErrorToast(
              tm("panel.zipTooLarge")
                .replace("{size}", formatFileSize(detail?.size ?? 0))
                .replace("{limit}", formatFileSize(ZIP_LIMIT_BYTES)),
            );
          } else {
            displayErrorToast(tm("panel.zipFailed"));
          }
        },
      },
    );
  };

  const rowText: RowText = {
    lang,
    fileCount: (n) => tm("panel.fileCount").replace("{n}", String(n)),
    download: tm("viewer.download"),
    delete: tm("panel.delete"),
    deleteConfirm: tm("panel.deleteConfirm"),
    deleteCancel: tm("panel.deleteCancel"),
  };

  const renderFolder = (
    folder: FolderEntry,
    opts: { active?: boolean; compact?: boolean } = {},
  ) => (
    <FolderRow
      key={`dir:${folder.path}`}
      folder={folder}
      selection={folderSelection(items, folder.path, selected)}
      onToggle={() => toggleFolder(folder.path)}
      onOpen={() => setCwd(folder.path)}
      active={opts.active}
      compact={opts.compact}
      text={rowText}
    />
  );

  const renderFile = (
    file: WorkspaceFile,
    opts: { compact?: boolean } = {},
  ) => (
    <FileRow
      key={file.path}
      file={file}
      checked={selected.has(file.path)}
      onToggle={() => toggleFile(file.path)}
      onOpen={() => data && openFile(file, data.working_dir)}
      onDownload={() =>
        cid && data && downloadFile(cid, data.working_dir, file)
      }
      isOpen={selectedFile?.path === file.path}
      showPath={isSearching}
      compact={opts.compact}
      confirming={confirmingDelete === file.path}
      deleting={deleteFile.isPending && confirmingDelete === file.path}
      onAskDelete={() => setConfirmingDelete(file.path)}
      onConfirmDelete={() => confirmDelete(file.path)}
      onCancelDelete={() => setConfirmingDelete(null)}
      text={rowText}
    />
  );

  const sortLabel: Record<SortKey, string> = {
    time: tm("panel.sortTime"),
    size: tm("panel.sortSize"),
    name: tm("panel.sortName"),
  };
  const DirIcon = sort.dir === "asc" ? ArrowUp : ArrowDown;
  const hasEntries = files.length > 0 || folders.length > 0;
  const zipping = createZip.isPending;

  return (
    <section
      className={cn(
        "tm-panel flex flex-col rounded-xl border border-tm-line bg-tm-workspace",
        collapsed ? "flex-none" : "min-h-0 flex-[3]",
      )}
    >
      <header
        className={cn(
          "flex items-center justify-between gap-2 rounded-t-[11px] bg-tm-panel-head px-4 py-3",
          collapsed ? "rounded-b-[11px]" : "border-b border-tm-line",
        )}
      >
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="flex min-w-0 items-center gap-2"
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-tm-slate-soft transition-transform",
              collapsed && "-rotate-90",
            )}
          />
          <FolderOpen className="h-4 w-4 shrink-0 text-tm-teal" />
          <h3 className="font-display text-sm font-semibold text-tm-ink">
            {tm("panel.results")}
          </h3>
          {items.length > 0 && (
            <span className="font-mono text-xs text-tm-slate-soft">
              {items.length}
            </span>
          )}
        </button>
        <div className={cn("flex items-center gap-1.5", collapsed && "hidden")}>
          <button
            type="button"
            onClick={() => refetch()}
            aria-label="refresh"
            className="rounded-md p-1 text-tm-slate-soft transition-colors hover:text-tm-teal"
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", isFetching && "animate-spin")}
            />
          </button>

          <div
            role="group"
            className="flex items-center rounded-md border border-tm-line bg-tm-card p-0.5"
          >
            {(
              [
                ["list", List, tm("panel.viewList")],
                ["columns", Columns3, tm("panel.viewColumns")],
              ] as const
            ).map(([mode, Icon, label]) => (
              <button
                key={mode}
                type="button"
                onClick={() => changeView(mode)}
                aria-label={label}
                aria-pressed={view === mode}
                title={label}
                className={cn(
                  SEGMENT_BUTTON,
                  view === mode
                    ? "bg-tm-teal-soft text-tm-teal shadow-sm"
                    : "text-tm-slate-soft hover:text-tm-ink",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
              </button>
            ))}
          </div>

          <div ref={sortMenuRef} className="relative">
            <button
              type="button"
              onClick={() => setSortMenuOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={sortMenuOpen}
              aria-label={tm("panel.sortBy")}
              title={tm("panel.sortBy")}
              className={cn(
                "flex items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium transition-colors",
                sortMenuOpen
                  ? "bg-tm-card text-tm-ink"
                  : "text-tm-slate hover:text-tm-ink",
              )}
            >
              <ArrowUpDown className="h-3.5 w-3.5" />
              {sortLabel[sort.key]}
            </button>
            {sortMenuOpen && (
              <div
                role="menu"
                className="absolute right-0 top-full z-20 mt-1 w-36 overflow-hidden rounded-lg border border-tm-line bg-tm-card py-1 shadow-lg"
              >
                {SORT_KEYS.map((key) => {
                  const active = sort.key === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      role="menuitemradio"
                      aria-checked={active}
                      onClick={() => chooseSort(key)}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors hover:bg-tm-teal-soft/60",
                        active ? "font-medium text-tm-ink" : "text-tm-slate",
                      )}
                    >
                      <Check
                        className={cn(
                          "h-3.5 w-3.5 text-tm-teal",
                          !active && "invisible",
                        )}
                      />
                      <span className="flex-1">{sortLabel[key]}</span>
                      {active && (
                        <DirIcon className="h-3.5 w-3.5 text-tm-slate-soft" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </header>

      <div className={cn("px-3 pt-3", collapsed && "hidden")}>
        <div className="flex items-center gap-2 rounded-lg border border-tm-line bg-tm-card px-3 py-1.5">
          <Search className="h-3.5 w-3.5 text-tm-slate-soft" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={tm("panel.filter")}
            className="w-full bg-transparent text-sm text-tm-ink outline-none placeholder:text-tm-slate-soft"
          />
        </div>

        {/* Selection bar: select-all for the current scope + bulk actions. */}
        {scopePaths.length > 0 && (
          <div
            data-testid="results-selection-bar"
            className="mt-2 flex min-h-7 items-center gap-2 px-1"
          >
            <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-xs text-tm-slate-soft">
              <TriCheckbox
                state={scopeState}
                onChange={toggleScope}
                label={tm("panel.selectAll")}
              />
              <span
                className={cn(
                  "truncate",
                  selected.size > 0 && "font-medium text-tm-ink",
                )}
              >
                {selected.size > 0
                  ? tm("panel.selectedCount").replace(
                      "{n}",
                      String(selected.size),
                    )
                  : tm("panel.selectAll")}
              </span>
            </label>
            {selected.size > 0 && (
              <>
                <button
                  type="button"
                  onClick={downloadSelected}
                  disabled={zipping}
                  className="flex shrink-0 items-center gap-1.5 rounded-md bg-tm-teal px-2.5 py-1 text-xs font-medium text-white shadow-sm transition-colors hover:bg-tm-teal-deep disabled:cursor-wait disabled:opacity-80"
                >
                  {zipping && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  {!zipping && selected.size === 1 && (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  {!zipping && selected.size > 1 && (
                    <FolderArchive className="h-3.5 w-3.5" />
                  )}
                  {zipping && tm("panel.zipping")}
                  {!zipping &&
                    (selected.size === 1
                      ? tm("panel.download")
                      : tm("panel.downloadZip"))}
                </button>
                <button
                  type="button"
                  onClick={() => setSelected(new Set())}
                  disabled={zipping}
                  className="shrink-0 rounded-md px-2 py-1 text-xs text-tm-slate transition-colors hover:bg-white hover:text-tm-ink disabled:opacity-60"
                >
                  {tm("panel.clearSelection")}
                </button>
              </>
            )}
          </div>
        )}

        {/* Breadcrumb — only meaningful while browsing a folder tree. */}
        {!isSearching && (segments.length > 0 || folders.length > 0) && (
          <nav
            aria-label={tm("panel.breadcrumb")}
            data-testid="results-breadcrumb"
            className="mt-2 flex flex-wrap items-center gap-0.5 border-t border-tm-line/70 px-1 pt-2 text-xs text-tm-slate-soft"
          >
            {segments.length > 0 && (
              <button
                type="button"
                onClick={() => setCwd(segments.slice(0, -1).join("/"))}
                aria-label={tm("panel.up")}
                title={tm("panel.up")}
                className="mr-1 rounded-md border border-tm-line bg-tm-card p-0.5 text-tm-slate transition-colors hover:border-tm-teal hover:text-tm-teal"
              >
                <CornerLeftUp className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={() => setCwd("")}
              className={cn(
                "rounded px-1 py-0.5 transition-colors hover:text-tm-teal",
                segments.length === 0 && "font-medium text-tm-ink",
              )}
            >
              {tm("panel.root")}
            </button>
            {segments.map((segment, index) => (
              <React.Fragment key={segments.slice(0, index + 1).join("/")}>
                <ChevronRight className="h-3 w-3 shrink-0" />
                <button
                  type="button"
                  onClick={() => setCwd(segments.slice(0, index + 1).join("/"))}
                  className={cn(
                    "rounded px-1 py-0.5 transition-colors hover:text-tm-teal",
                    index === segments.length - 1 && "font-medium text-tm-ink",
                  )}
                >
                  {segment}
                </button>
              </React.Fragment>
            ))}
          </nav>
        )}
      </div>

      <div
        className={cn(
          "min-h-0 flex-1",
          showColumns && hasEntries
            ? "flex flex-col px-3 pb-3 pt-2"
            : "overflow-y-auto px-2 py-2",
          collapsed && "hidden",
        )}
      >
        {(isLoading || isWaking) && (
          <p
            data-testid="results-waking"
            className="flex items-center justify-center gap-2 px-2 py-6 text-center text-sm text-tm-slate-soft"
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            {isWaking
              ? tm("panel.workspaceWaking")
              : tm("panel.workspaceLoading")}
          </p>
        )}

        {!isLoading && !isWaking && !hasEntries && (
          <p className="px-2 py-6 text-center text-sm text-tm-slate-soft">
            {items.length === 0
              ? tm("panel.resultsEmpty")
              : tm("panel.noMatch")}
          </p>
        )}

        {!isLoading && hasEntries && !showColumns && (
          <ul className="flex flex-col gap-0.5">
            {folders.map((folder) => renderFolder(folder))}
            {files.map((file) => renderFile(file))}
          </ul>
        )}

        {!isLoading && hasEntries && showColumns && (
          <div
            ref={columnsRef}
            data-testid="results-columns"
            className="flex min-h-0 flex-1 overflow-x-auto rounded-lg border border-tm-line/70 bg-white/40"
          >
            {columns.map((column) => (
              <ul
                key={column.path || "/"}
                aria-label={column.path || tm("panel.root")}
                className="flex w-64 shrink-0 flex-col gap-0.5 overflow-y-auto border-r border-tm-line/70 p-1.5 last:border-r-0"
              >
                {column.folders.map((folder) =>
                  renderFolder(folder, {
                    active: folder.name === column.active,
                    compact: true,
                  }),
                )}
                {column.files.map((file) =>
                  renderFile(file, { compact: true }),
                )}
                {column.folders.length === 0 && column.files.length === 0 && (
                  <li className="px-2 py-4 text-center text-xs text-tm-slate-soft">
                    —
                  </li>
                )}
              </ul>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
