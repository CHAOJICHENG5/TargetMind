import React from "react";
import V1ConversationService from "#/api/conversation-service/v1-conversation-service.api";

export const VIEWING_HEARTBEAT_MS = 60_000;

/**
 * While this conversation is the visible browser tab, tell the server every
 * minute that someone is looking at it, so the idle reaper does not stop its
 * sandbox under a reader (30 min idle window). Hidden tabs send nothing.
 */
export function useConversationViewingHeartbeat(
  conversationId: string | null | undefined,
) {
  React.useEffect(() => {
    if (!conversationId || conversationId.startsWith("task-")) {
      return undefined;
    }
    const beat = () => {
      if (document.visibilityState !== "visible") return;
      V1ConversationService.markConversationViewing(conversationId).catch(
        () => {
          // Best effort: a missed beat only means the normal idle rules apply.
        },
      );
    };
    beat();
    const timer = window.setInterval(beat, VIEWING_HEARTBEAT_MS);
    document.addEventListener("visibilitychange", beat);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", beat);
    };
  }, [conversationId]);
}
