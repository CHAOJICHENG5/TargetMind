import React from "react";
import { Download, X, FileWarning, LoaderCircle } from "lucide-react";
import Papa from "papaparse";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useWorkspaceViewerStore } from "#/stores/workspace-viewer-store";
import { useWorkspaceFileContent } from "#/hooks/query/use-workspace-file-content";
import { useListWorkspaceFiles } from "#/hooks/query/use-list-workspace-files";
import { MarkdownRenderer } from "#/components/features/markdown/markdown-renderer";
import { useTMText } from "#/i18n/targetmind-strings";
import { MoleculeViewer, MOLECULE_EXTS } from "./molecule-viewer";

/** Map a file extension to a Prism language id for syntax highlighting. */
const EXT_TO_LANG: Record<string, string> = {
  py: "python",
  r: "r",
  js: "javascript",
  ts: "typescript",
  tsx: "tsx",
  jsx: "jsx",
  sh: "bash",
  bash: "bash",
  json: "json",
  jsonl: "json",
  ndjson: "json",
  yaml: "yaml",
  yml: "yaml",
  css: "css",
  html: "markup",
  xml: "markup",
  toml: "toml",
  ini: "ini",
  cfg: "ini",
  sql: "sql",
  java: "java",
  c: "c",
  cpp: "cpp",
};

/** Extensions rendered as plain (non-highlighted) monospace text. */
const PLAIN_EXTS = new Set(["txt", "log"]);

const TEXT_EXTS = new Set([
  "txt",
  "log",
  "json",
  "jsonl",
  "ndjson",
  "py",
  "r",
  "js",
  "ts",
  "tsx",
  "sh",
  "yaml",
  "yml",
  "css",
  "html",
  "xml",
  "toml",
  "ini",
  "cfg",
]);
const TABLE_EXTS = new Set(["csv", "tsv"]);
/** Line-oriented files that can be huge (event logs): only the head is loaded. */
const PARTIAL_EXTS = new Set([...TABLE_EXTS, "jsonl", "ndjson"]);
/** Above this size code is shown as plain text (highlighting would freeze the tab). */
const MAX_HIGHLIGHT_CHARS = 300_000;
const MAX_PRETTY_JSON_CHARS = 2_000_000;

/** Pretty-print a JSON document; anything unparsable is shown as is. */
function prettyJson(text: string): string {
  if (text.length > MAX_PRETTY_JSON_CHARS) return text;
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

/** Directory part of a workspace-relative path ("" for top-level files). */
function dirOf(relPath: string): string {
  const i = relPath.lastIndexOf("/");
  return i === -1 ? "" : relPath.slice(0, i);
}

/** Resolve a relative link (`../x/y.png`, `./y.png`) against a directory. */
export function resolveRelative(baseDir: string, link: string): string | null {
  const parts = baseDir ? baseDir.split("/") : [];
  for (const seg of link.split("/")) {
    if (seg === "..") {
      if (parts.length === 0) return null; // escapes the workspace
      parts.pop();
    } else if (seg && seg !== ".") {
      parts.push(seg);
    }
  }
  return parts.join("/");
}

export function rawUrl(
  conversationId: string,
  workingDir: string,
  relPath: string,
  version?: string,
) {
  const abs = `${workingDir}/${relPath}`;
  const versionParam = version ? `&v=${encodeURIComponent(version)}` : "";
  return `/api/v1/app-conversations/${conversationId}/file-raw?file_path=${encodeURIComponent(
    abs,
  )}${versionParam}`;
}

const MAX_TABLE_ROWS = 100;
const TABLE_PREVIEW_BYTES = 512 * 1024;

function CsvTable({ text, ext }: { text: string; ext: string }) {
  const tm = useTMText();
  const delim = ext === "tsv" ? "\t" : ",";
  const allRows = React.useMemo(
    () =>
      Papa.parse<string[]>(text, {
        delimiter: delim,
        preview: MAX_TABLE_ROWS + 2,
        skipEmptyLines: "greedy",
      }).data,
    [delim, text],
  );
  if (allRows.length === 0) return null;
  const [head, ...allBody] = allRows;
  const body = allBody.slice(0, MAX_TABLE_ROWS);
  const truncated = allBody.length > MAX_TABLE_ROWS;

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              {head.map((cell, i) => (
                <th
                  key={i}
                  className="sticky top-0 border-b border-tm-line bg-tm-paper px-3 py-2 text-left font-display font-semibold text-tm-ink"
                >
                  {cell}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, r) => (
              <tr key={r} className={r % 2 ? "bg-tm-paper/50" : ""}>
                {row.map((cell, c) => (
                  <td
                    key={c}
                    className="border-b border-tm-line px-3 py-1.5 font-mono text-xs text-tm-slate"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {truncated && (
        <div className="shrink-0 border-t border-tm-line bg-tm-paper px-3 py-2 text-center text-xs text-tm-slate-soft">
          {tm("viewer.rowLimit")}
        </div>
      )}
    </div>
  );
}

function TextContent({
  conversationId,
  workingDir,
  relPath,
  ext,
  version,
}: {
  conversationId: string;
  workingDir: string;
  relPath: string;
  ext: string;
  version: string;
}) {
  const tm = useTMText();
  const { data, isLoading, isError } = useWorkspaceFileContent(
    conversationId,
    workingDir,
    relPath,
    version,
    PARTIAL_EXTS.has(ext) ? `bytes=0-${TABLE_PREVIEW_BYTES - 1}` : undefined,
  );
  // Versions of the workspace files, so images embedded in a Markdown report
  // load through the same cache-busting raw URL as the Results panel uses.
  const { data: listing } = useListWorkspaceFiles(conversationId);
  const mdComponents = React.useMemo(() => {
    const versions = new Map(
      (listing?.items ?? []).map((f) => [f.path, `${f.mtime}-${f.size}`]),
    );
    const img = ({ src, alt }: { src?: string | Blob; alt?: string }) => {
      const link = typeof src === "string" ? src : "";
      const external = /^(https?:|data:|\/)/i.test(link);
      const rel = external ? null : resolveRelative(dirOf(relPath), link);
      const url = external
        ? link
        : rel && rawUrl(conversationId, workingDir, rel, versions.get(rel));
      if (!url) return <span>{alt}</span>;
      return (
        <img
          src={url}
          alt={alt ?? ""}
          loading="lazy"
          className="my-2 max-w-full rounded-lg border border-tm-line bg-white"
        />
      );
    };
    return { img };
  }, [listing, conversationId, workingDir, relPath]);

  if (isLoading)
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-tm-slate-soft">
        <LoaderCircle className="h-4 w-4 animate-spin" />
        {tm("viewer.loading")}
      </div>
    );
  if (isError || data == null)
    return (
      <div className="py-16 text-center text-sm text-tm-slate-soft">
        {tm("viewer.error")}
      </div>
    );

  if (ext === "md")
    return (
      <div className="markdown-body p-4 text-sm text-tm-ink">
        <MarkdownRenderer includeStandard components={mdComponents}>
          {data}
        </MarkdownRenderer>
      </div>
    );

  if (TABLE_EXTS.has(ext)) return <CsvTable text={data} ext={ext} />;

  const text = ext === "json" ? prettyJson(data) : data;
  const partial = PARTIAL_EXTS.has(ext) && data.length >= TABLE_PREVIEW_BYTES;
  const lang = EXT_TO_LANG[ext];
  let content: React.ReactNode;
  if (lang && !PLAIN_EXTS.has(ext) && text.length <= MAX_HIGHLIGHT_CHARS) {
    content = (
      <SyntaxHighlighter
        language={lang}
        style={oneLight}
        showLineNumbers
        wrapLongLines
        customStyle={{
          margin: 0,
          padding: "1rem",
          background: "transparent",
          fontSize: "12px",
          lineHeight: "1.6",
        }}
        lineNumberStyle={{ color: "#8395a6", minWidth: "2.5em" }}
      >
        {text}
      </SyntaxHighlighter>
    );
  } else {
    content = (
      <pre className="whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-tm-ink">
        {text}
      </pre>
    );
  }
  if (!partial) return content;
  return (
    <>
      {content}
      <div className="border-t border-tm-line bg-tm-paper px-3 py-2 text-center text-xs text-tm-slate-soft">
        {tm("viewer.previewLimit")}
      </div>
    </>
  );
}

function ImageContent({ src, name }: { src: string; name: string }) {
  const tm = useTMText();
  const [state, setState] = React.useState<"loading" | "loaded" | "error">(
    "loading",
  );

  return (
    <div
      className="relative flex h-full min-h-48 items-center justify-center p-4"
      aria-busy={state === "loading"}
    >
      {state === "loading" && (
        <div className="absolute inset-0 flex items-center justify-center gap-2 text-sm text-tm-slate-soft">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          {tm("viewer.loading")}
        </div>
      )}
      {state === "error" && (
        <div className="flex flex-col items-center gap-2 text-sm text-tm-slate-soft">
          <FileWarning className="h-7 w-7" />
          {tm("viewer.error")}
        </div>
      )}
      <img
        src={src}
        alt={name}
        onLoad={() => setState("loaded")}
        onError={() => setState("error")}
        className={`max-h-full max-w-full rounded-lg border border-tm-line bg-white transition-opacity ${
          state === "loaded" ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
    </div>
  );
}

/**
 * Tab strip for the files currently open in the viewer. Hidden while a single
 * file is open, since the header already names it.
 *
 * The tab and its close button are siblings inside a plain `div` — nesting a
 * button inside a button is invalid HTML and breaks click targeting.
 */
function ViewerTabs() {
  const tm = useTMText();
  const { openFiles, selectedFile, selectFile, closeTab } =
    useWorkspaceViewerStore();

  if (openFiles.length < 2) return null;

  return (
    <div
      role="tablist"
      aria-label={tm("viewer.tabs")}
      data-testid="viewer-tabs"
      className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-tm-line px-2 pt-2"
    >
      {openFiles.map((file) => {
        const active = selectedFile?.path === file.path;
        return (
          <div
            key={file.path}
            className={`flex max-w-[180px] shrink-0 items-center gap-1 rounded-t-lg border border-b-0 px-2 py-1.5 text-xs transition-colors ${
              active
                ? "border-tm-line bg-tm-card text-tm-ink"
                : "border-transparent text-tm-slate-soft hover:bg-white/60"
            }`}
          >
            <button
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => selectFile(file.path)}
              className="min-w-0 flex-1 truncate text-left"
              title={file.path}
            >
              {file.name}
            </button>
            <button
              type="button"
              onClick={() => closeTab(file.path)}
              aria-label={`${tm("viewer.closeTab")}: ${file.name}`}
              className="shrink-0 rounded p-0.5 text-tm-slate-soft transition-colors hover:bg-tm-paper hover:text-tm-ink"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function FileViewer({ conversationId }: { conversationId: string }) {
  const tm = useTMText();
  const { selectedFile, workingDir, closeFile } = useWorkspaceViewerStore();

  if (!selectedFile || !workingDir) return null;

  const { ext, path, name, mtime, size } = selectedFile;
  const version = `${mtime}-${size}`;
  const src = rawUrl(conversationId, workingDir, path, version);
  const isText = TEXT_EXTS.has(ext) || TABLE_EXTS.has(ext) || ext === "md";
  const isMolecule = MOLECULE_EXTS.has(ext);
  const isHtml = ext === "html" || ext === "htm";

  let body: React.ReactNode;
  if (selectedFile.is_image) {
    body = <ImageContent key={src} src={src} name={name} />;
  } else if (isMolecule) {
    body = <MoleculeViewer src={src} ext={ext} />;
  } else if (isHtml) {
    // Render agent-generated HTML reports directly in a sandboxed iframe.
    body = (
      <iframe
        src={src}
        title={name}
        className="h-full w-full border-0 bg-white"
        sandbox="allow-scripts allow-same-origin"
      />
    );
  } else if (ext === "pdf") {
    body = <iframe src={src} title={name} className="h-full w-full border-0" />;
  } else if (isText) {
    body = (
      <TextContent
        conversationId={conversationId}
        workingDir={workingDir}
        relPath={path}
        ext={ext}
        version={version}
      />
    );
  } else {
    body = (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-sm text-tm-slate-soft">
        <FileWarning className="h-8 w-8" />
        <span>{tm("viewer.unsupported")}</span>
        <a
          href={src}
          download={name}
          className="rounded-lg bg-tm-teal px-3 py-1.5 text-white transition-colors hover:bg-tm-teal-deep"
        >
          {tm("viewer.download")}
        </a>
      </div>
    );
  }

  return (
    // overflow-hidden clips the tinted header to the rounded corners.
    <div className="tm-panel flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-tm-line bg-tm-workspace">
      {/* Tinted header (tabs + file title) over the white content area. */}
      <div className="shrink-0 bg-tm-panel-head">
        <ViewerTabs />
      </div>
      <header className="flex items-center justify-between gap-3 border-b border-tm-line bg-tm-panel-head px-4 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-display text-sm font-semibold text-tm-ink">
            {name}
          </span>
          {path.includes("/") && (
            <span className="hidden truncate font-mono text-[11px] text-tm-slate-soft sm:inline">
              {path}
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <a
            href={src}
            download={name}
            title={tm("viewer.download")}
            className="rounded-md p-1.5 text-tm-slate transition-colors hover:bg-white/70 hover:text-tm-teal"
          >
            <Download className="h-4 w-4" />
          </a>
          <button
            type="button"
            onClick={closeFile}
            title={tm("viewer.close")}
            className="rounded-md p-1.5 text-tm-slate transition-colors hover:bg-white/70 hover:text-tm-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </header>
      <div className="relative min-h-0 flex-1">
        <div className="absolute inset-0 overflow-auto">{body}</div>
      </div>
    </div>
  );
}
