import { useMutation } from "@tanstack/react-query";
import V1ConversationService from "#/api/conversation-service/v1-conversation-service.api";

/** Build a ZIP of Results-panel paths in the sandbox; resolves to its URL. */
export function useCreateWorkspaceZip(
  conversationId: string | null | undefined,
) {
  return useMutation({
    mutationFn: async ({
      paths,
      filename,
    }: {
      paths: string[];
      filename: string;
    }) => {
      const zip = await V1ConversationService.createConversationFilesZip(
        conversationId!,
        paths,
      );
      return {
        ...zip,
        url: V1ConversationService.conversationFilesZipUrl(
          conversationId!,
          zip.id,
          filename,
        ),
      };
    },
    meta: { disableToast: true },
  });
}
