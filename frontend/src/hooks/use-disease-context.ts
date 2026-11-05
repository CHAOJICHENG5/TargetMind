import React from "react";
import { useConversationId } from "#/hooks/use-conversation-id";
import {
  DiseaseContext,
  readDiseaseContext,
  saveDiseaseContext,
} from "#/utils/disease-context";

const LAST_KEY = "targetmind:disease:last";

/**
 * Resolve the disease context for the current conversation.
 * Prefers the entry keyed by conversation id; on a fresh entry into the
 * workspace (id just swapped) falls back to the last-selected disease and
 * re-keys it under the current id so reloads keep working.
 */
export function useDiseaseContext(): DiseaseContext | null {
  const { conversationId } = useConversationId();

  return React.useMemo(() => {
    if (!conversationId || conversationId.startsWith("task-")) {
      // still on the transient task id — use the last selection for display
      try {
        const raw = localStorage.getItem(LAST_KEY);
        return raw ? (JSON.parse(raw) as DiseaseContext) : null;
      } catch {
        return null;
      }
    }
    const byId = readDiseaseContext(conversationId);
    if (byId) return byId;
    // Fallback: adopt the last-selected disease for this id (best-effort).
    try {
      const raw = localStorage.getItem(LAST_KEY);
      if (raw) {
        const disease = JSON.parse(raw) as DiseaseContext;
        saveDiseaseContext(conversationId, disease);
        return disease;
      }
    } catch {
      // ignore
    }
    return null;
  }, [conversationId]);
}
