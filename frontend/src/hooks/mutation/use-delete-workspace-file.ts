import { useMutation, useQueryClient } from "@tanstack/react-query";
import V1ConversationService from "#/api/conversation-service/v1-conversation-service.api";
import { workspaceFilesQueryKey } from "#/hooks/query/use-list-workspace-files";
import { useWorkspaceViewerStore } from "#/stores/workspace-viewer-store";
import type { WorkspaceFileListResponse } from "#/types/workspace-file";

/** Delete one Results-panel file and drop it from the list and the viewer. */
export function useDeleteWorkspaceFile(
  conversationId: string | null | undefined,
) {
  const queryClient = useQueryClient();
  const queryKey = workspaceFilesQueryKey(conversationId);

  return useMutation({
    mutationFn: (path: string) =>
      V1ConversationService.deleteConversationFile(conversationId!, path),
    onSuccess: (_data, path) => {
      queryClient.setQueryData<WorkspaceFileListResponse>(queryKey, (prev) =>
        prev
          ? { ...prev, items: prev.items.filter((f) => f.path !== path) }
          : prev,
      );
      useWorkspaceViewerStore.getState().closeTab(path);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
    meta: { disableToast: true },
  });
}
