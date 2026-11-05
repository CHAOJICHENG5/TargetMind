/** A single result file in a conversation's sandbox workspace. */
export interface WorkspaceFile {
  name: string;
  /** Path relative to the workspace working_dir (e.g. "results/plot.png"). */
  path: string;
  size: number;
  /** Unix epoch seconds. */
  mtime: number;
  ext: string;
  is_image: boolean;
}

export interface WorkspaceFileListResponse {
  working_dir: string;
  items: WorkspaceFile[];
  /** Every visible directory (workspace-relative), including empty ones. */
  dirs?: string[];
  truncated: boolean;
}
