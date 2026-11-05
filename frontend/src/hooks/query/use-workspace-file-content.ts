import { useQuery } from "@tanstack/react-query";
import V1ConversationService from "#/api/conversation-service/v1-conversation-service.api";

/**
 * Read a text file's content from the conversation workspace.
 * `relativePath` is relative to the workspace working_dir; `workingDir` comes
 * from the file-list response.
 */
export function useWorkspaceFileContent(
  conversationId: string | null | undefined,
  workingDir: string | null | undefined,
  relativePath: string | null | undefined,
  version: string | null | undefined,
  byteRange?: string,
  enabled = true,
) {
  const absPath =
    workingDir && relativePath ? `${workingDir}/${relativePath}` : null;
  return useQuery<string>({
    queryKey: [
      "workspace-file-content",
      conversationId,
      absPath,
      version,
      byteRange,
    ],
    queryFn: ({ signal }) =>
      V1ConversationService.readWorkspaceFileContent(
        conversationId!,
        absPath!,
        version!,
        signal,
        byteRange,
      ),
    enabled:
      enabled &&
      !!conversationId &&
      !conversationId.startsWith("task-") &&
      !!absPath &&
      !!version,
    staleTime: Infinity,
    retry: 1,
    meta: { disableToast: true },
  });
}
