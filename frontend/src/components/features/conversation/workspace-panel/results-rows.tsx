import React from "react";
import {
  ChevronRight,
  Download,
  File as FileIcon,
  FileCode,
  FileImage,
  FileSpreadsheet,
  FileText,
  Folder,
  Loader2,
  Trash2,
  X,
} from "lucide-react";
import type { WorkspaceFile } from "#/types/workspace-file";
import { cn } from "#/utils/utils";
import {
  type FolderEntry,
  type SelectionState,
  formatFileSize,
  formatFileTime,
  fullTime,
} from "./results-tree";

const CODE_EXTS = new Set([
  "py",
  "r",
  "js",
  "ts",
  "json",
  "jsonl",
  "ndjson",
  "sh",
  "yaml",
  "yml",
  "html",
  "css",
]);
const TABLE_EXTS = new Set(["csv", "tsv"]);

export function FileTypeIcon({ file }: { file: WorkspaceFile }) {
  const cls = "h-4 w-4 shrink-0";
  if (file.is_image) return <FileImage className={cn(cls, "text-tm-teal")} />;
  if (TABLE_EXTS.has(file.ext))
    return <FileSpreadsheet className={cn(cls, "text-emerald-600")} />;
  if (file.ext === "md")
    return <FileText className={cn(cls, "text-tm-chip-text")} />;
  if (CODE_EXTS.has(file.ext))
    return <FileCode className={cn(cls, "text-amber-600")} />;
  if (file.ext === "txt" || file.ext === "log")
    return <FileText className={cn(cls, "text-tm-slate")} />;
  return <FileIcon className={cn(cls, "text-tm-slate-soft")} />;
}

/** Checkbox with a visible "some selected" (indeterminate) state. */
export function TriCheckbox({
  state,
  onChange,
  disabled,
  label,
}: {
  state: SelectionState;
  onChange: () => void;
  disabled?: boolean;
  label: string;
}) {
  const ref = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => {
    if (ref.current) ref.current.indeterminate = state === "some";
  }, [state]);
  return (
    <input
      ref={ref}
      type="checkbox"
      checked={state === "all"}
      onChange={onChange}
      onClick={(e) => e.stopPropagation()}
      disabled={disabled}
      aria-label={label}
      aria-checked={state === "some" ? "mixed" : state === "all"}
      className="h-3.5 w-3.5 shrink-0 cursor-pointer accent-tm-teal disabled:cursor-default disabled:opacity-40"
    />
  );
}

/** "size • date" style metadata, always visible. */
function MetaLine({ parts }: { parts: { text: string; title?: string }[] }) {
  const shown = parts.filter((part) => part.text);
  return (
    <span className="flex shrink-0 items-center gap-1.5 text-[11px] tabular-nums text-tm-slate-soft">
      {shown.map((part, index) => (
        <React.Fragment key={part.text + String(index)}>
          {index > 0 && (
            <span aria-hidden className="text-tm-slate-soft/50">
              •
            </span>
          )}
          <span title={part.title}>{part.text}</span>
        </React.Fragment>
      ))}
    </span>
  );
}

const ICON_BUTTON =
  "shrink-0 rounded-md p-1 text-tm-slate-soft transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tm-teal/40";

const ROW =
  "group flex items-center gap-2 rounded-lg px-2 py-2 transition-colors";

export interface RowText {
  lang: "zh" | "en";
  fileCount: (n: number) => string;
  download: string;
  delete: string;
  deleteConfirm: string;
  deleteCancel: string;
}

export function FolderRow({
  folder,
  selection,
  onToggle,
  onOpen,
  active,
  compact,
  text,
}: {
  folder: FolderEntry;
  selection: SelectionState;
  onToggle: () => void;
  onOpen: () => void;
  /** Folder is on the open path (column view). */
  active?: boolean;
  /** Column view: count only; the date moves into the tooltip. */
  compact?: boolean;
  text: RowText;
}) {
  const time = formatFileTime(folder.mtime, text.lang);
  return (
    <li
      className={cn(
        ROW,
        active
          ? "bg-tm-teal-soft/80 shadow-[inset_2px_0_0] shadow-tm-teal"
          : "hover:bg-white/70",
      )}
    >
      <TriCheckbox
        state={selection}
        onChange={onToggle}
        disabled={folder.count === 0}
        label={folder.name}
      />
      <button
        type="button"
        onClick={onOpen}
        title={
          compact ? `${folder.path}\n${fullTime(folder.mtime)}` : undefined
        }
        className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
      >
        <Folder
          className={cn(
            "h-4 w-4 shrink-0",
            active ? "fill-tm-teal/15 text-tm-teal" : "text-tm-teal",
          )}
        />
        <span
          className={cn(
            "min-w-0 flex-1 truncate text-sm text-tm-ink",
            active ? "font-semibold" : "font-medium",
          )}
        >
          {folder.name}
        </span>
        <MetaLine
          parts={[
            ...(compact ? [] : [{ text: time, title: fullTime(folder.mtime) }]),
            {
              text: String(folder.count),
              title: text.fileCount(folder.count),
            },
          ]}
        />
      </button>
      <ChevronRight
        className={cn(
          "h-3.5 w-3.5 shrink-0",
          active ? "text-tm-teal" : "text-tm-slate-soft",
        )}
      />
    </li>
  );
}

export function FileRow({
  file,
  checked,
  onToggle,
  onOpen,
  onDownload,
  isOpen,
  showPath,
  compact,
  confirming,
  deleting,
  onAskDelete,
  onConfirmDelete,
  onCancelDelete,
  text,
}: {
  file: WorkspaceFile;
  checked: boolean;
  onToggle: () => void;
  onOpen: () => void;
  onDownload: () => void;
  /** File is shown in the viewer. */
  isOpen: boolean;
  /** Search results: show the folder path under the name. */
  showPath?: boolean;
  /** Column view: size and date move into the tooltip. */
  compact?: boolean;
  confirming: boolean;
  deleting: boolean;
  onAskDelete: () => void;
  onConfirmDelete: () => void;
  onCancelDelete: () => void;
  text: RowText;
}) {
  const size = formatFileSize(file.size);
  const time = formatFileTime(file.mtime, text.lang);
  return (
    <li
      className={cn(
        ROW,
        "hover:bg-white/70",
        isOpen && "bg-tm-teal-soft/70",
        confirming && "bg-red-50/80 hover:bg-red-50/80",
      )}
    >
      <TriCheckbox
        state={checked ? "all" : "none"}
        onChange={onToggle}
        label={file.name}
      />
      <button
        type="button"
        onClick={onOpen}
        title={compact ? `${file.name}\n${size} • ${time}` : undefined}
        className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
      >
        <FileTypeIcon file={file} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm text-tm-ink">
            {file.name}
          </span>
          {showPath && file.path.includes("/") && (
            <span className="block truncate font-mono text-[10px] text-tm-slate-soft">
              {file.path}
            </span>
          )}
        </span>
        {!compact && (
          <MetaLine
            parts={[
              { text: size },
              { text: time, title: fullTime(file.mtime) },
            ]}
          />
        )}
      </button>
      {confirming ? (
        <span className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={onConfirmDelete}
            disabled={deleting}
            aria-label="confirm delete"
            className="flex items-center gap-1 rounded-md bg-red-600 px-2 py-0.5 text-[11px] font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-70"
          >
            {deleting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
            {text.deleteConfirm}
          </button>
          <button
            type="button"
            onClick={onCancelDelete}
            disabled={deleting}
            aria-label="cancel delete"
            title={text.deleteCancel}
            className={cn(ICON_BUTTON, "hover:bg-white hover:text-tm-ink")}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </span>
      ) : (
        <span className="flex shrink-0 items-center">
          <button
            type="button"
            onClick={onDownload}
            aria-label="download"
            title={text.download}
            className={cn(ICON_BUTTON, "hover:bg-white hover:text-tm-teal")}
          >
            <Download className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={onAskDelete}
            aria-label="delete"
            title={text.delete}
            className={cn(ICON_BUTTON, "hover:bg-red-50 hover:text-red-600")}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </span>
      )}
    </li>
  );
}
