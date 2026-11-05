import { useConversationId } from "#/hooks/use-conversation-id";
import { useWorkspaceViewerStore } from "#/stores/workspace-viewer-store";
import { useResizablePanels } from "#/hooks/use-resizable-panels";
import { ResizeHandle } from "#/components/ui/resize-handle";
import { PlanPanel } from "./plan-panel";
import { ExpertTeamPanel } from "./expert-team-panel";
import { ResultsPanel } from "./results-panel";
import { FileViewer } from "./file-viewer";

/**
 * TargetMind workspace panel .
 *
 * Default: a single column with the Planner stacked over Results.
 * When a result file is opened, a resizable file viewer appears to its left
 * (the column itself is never remounted),
 * giving the Biomni-style layout: chat | viewer | plan+results.
 *
 * The viewer and the plan/results column are both `min-w-0 overflow-hidden`, so
 * a very wide file (huge table / long code line) can never squeeze the
 * plan/results column off-screen — the close button therefore always stays
 * reachable in the viewer header.
 */
export function TargetMindWorkspacePanel() {
  const { conversationId } = useConversationId();
  const { selectedFile } = useWorkspaceViewerStore();
  const hasViewer = !!selectedFile;

  const { leftWidth, isDragging, containerRef, handleMouseDown } =
    useResizablePanels({
      defaultLeftWidth: 58,
      minLeftWidth: 35,
      maxLeftWidth: 72,
      storageKey: "targetmind-viewer-panel-width",
    });

  // One tree for both layouts: the viewer and its handle are inserted before
  // the Plan/Results column, which keeps its slot and therefore stays mounted —
  // opening the first file must not reset the browsed folder, collapsed panels
  // or scroll positions.
  return (
    <div
      ref={containerRef}
      className="flex h-full min-h-0 w-full min-w-0 overflow-hidden"
    >
      {hasViewer && (
        <div
          className="flex min-w-0 flex-col overflow-hidden"
          style={{
            width: `${leftWidth}%`,
            transition: isDragging ? "none" : "width 150ms ease",
          }}
        >
          {conversationId && <FileViewer conversationId={conversationId} />}
        </div>
      )}

      {hasViewer && (
        <ResizeHandle onMouseDown={handleMouseDown} className="mx-1" />
      )}

      {/* Plan + Results (always mounted, own min width) */}
      <div
        className="flex h-full min-h-0 min-w-0 flex-col gap-3 overflow-hidden"
        style={{
          width: hasViewer ? `${100 - leftWidth}%` : "100%",
          transition: isDragging ? "none" : "width 150ms ease",
        }}
      >
        <ExpertTeamPanel conversationId={conversationId} />
        <PlanPanel />
        <ResultsPanel conversationId={conversationId} />
      </div>
    </div>
  );
}
