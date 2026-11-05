import { useQuery } from "@tanstack/react-query";
import V1ConversationService from "#/api/conversation-service/v1-conversation-service.api";
import type { ExpertRunSteps } from "#/types/expert-team";

/** Steps of each expert run; polls while experts are working. */
export function useConversationExperts(
  conversationId: string | null | undefined,
  active: boolean,
) {
  return useQuery<ExpertRunSteps[]>({
    queryKey: ["conversation-experts", conversationId],
    queryFn: () =>
      V1ConversationService.listConversationExperts(conversationId!),
    enabled: !!conversationId && !conversationId.startsWith("task-"),
    refetchInterval: active ? 4000 : false,
    staleTime: 3000,
    retry: 1,
    meta: { disableToast: true },
  });
}
