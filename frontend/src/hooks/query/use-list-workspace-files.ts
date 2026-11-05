import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import V1ConversationService from "#/api/conversation-service/v1-conversation-service.api";
import type { WorkspaceFileListResponse } from "#/types/workspace-file";

const WORKSPACE_FILES_REFRESH_DELAY_MS = 400;

export const workspaceFilesQueryKey = (
  conversationId: string | null | undefined,
) => ["workspace-files", conversationId] as const;

/** List result files in the conversation workspace (polls while active). */
export function useListWorkspaceFiles(
  conversationId: string | null | undefined,
  enabled = true,
) {
  return useQuery<WorkspaceFileListResponse>({
    queryKey: workspaceFilesQueryKey(conversationId),
    queryFn: () => V1ConversationService.listConversationFiles(conversationId!),
    enabled: enabled && !!conversationId && !conversationId.startsWith("task-"),
    refetchInterval: 10000,
    refetchOnWindowFocus: true,
    staleTime: 5000,
    retry: 1,
    meta: { disableToast: true },
  });
}

/** Coalesce file-producing events into one immediate Results refresh. */
export function useWorkspaceFilesRefresh(
  conversationId: string | null | undefined,
) {
  const queryClient = useQueryClient();
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [conversationId],
  );

  return React.useCallback(() => {
    if (!conversationId || conversationId.startsWith("task-")) return;

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      queryClient.invalidateQueries({
        queryKey: workspaceFilesQueryKey(conversationId),
      });
    }, WORKSPACE_FILES_REFRESH_DELAY_MS);
  }, [conversationId, queryClient]);
}
