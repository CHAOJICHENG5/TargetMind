/**
 * TargetMind disease context.
 *
 * A conversation created from the disease-search home page is scoped to one
 * target disease. We carry that context two ways so it survives the
 * task-id -> real-conversation-id swap and page reloads:
 *   1. localStorage, keyed by conversation id (fast path for the badge)
 *   2. the conversation instructions/title string (server-persisted fallback
 *      that the agent also receives as context)
 */

export interface DiseaseContext {
  name: string;
  /** Primary OpenTargets ontology id — may be EFO_, MONDO_, Orphanet_, HP_… */
  ontologyId: string;
  /** MONDO cross-reference from dbXRefs (may equal ontologyId or be null). */
  mondoId: string | null;
  description?: string | null;
}

const KEY_PREFIX = "targetmind:disease:";
const LAST_KEY = "targetmind:disease:last";

/** Human label for an ontology id: "MONDO_0000494" -> "MONDO". */
export function ontologyLabel(id: string): string {
  const prefix = id.split("_")[0] || id;
  const known: Record<string, string> = {
    EFO: "EFO",
    MONDO: "MONDO",
    ORPHANET: "Orphanet",
    HP: "HP",
    DOID: "DOID",
    MP: "MP",
    NCIT: "NCIt",
  };
  return known[prefix.toUpperCase()] ?? prefix;
}

export function saveDiseaseContext(
  conversationId: string,
  disease: DiseaseContext,
): void {
  try {
    const raw = JSON.stringify(disease);
    localStorage.setItem(KEY_PREFIX + conversationId, raw);
    localStorage.setItem(LAST_KEY, raw);
  } catch {
    // localStorage unavailable (private mode / quota) — the instructions
    // string remains as the fallback source of truth.
  }
}

/**
 * Move a stored disease context from one conversation id to another. Used when
 * the screen transitions from the transient "task-{id}" url to the real
 * conversation id (react-router replace), so the badge keeps working.
 */
export function migrateDiseaseContext(fromId: string, toId: string): void {
  if (!fromId || !toId || fromId === toId) return;
  try {
    const raw = localStorage.getItem(KEY_PREFIX + fromId);
    if (raw) {
      localStorage.setItem(KEY_PREFIX + toId, raw);
      localStorage.removeItem(KEY_PREFIX + fromId);
    }
  } catch {
    // ignore
  }
}

export function readDiseaseContext(
  conversationId: string | null | undefined,
): DiseaseContext | null {
  if (!conversationId) return null;
  try {
    const raw = localStorage.getItem(KEY_PREFIX + conversationId);
    if (raw) return JSON.parse(raw) as DiseaseContext;
  } catch {
    // ignore
  }
  return null;
}

/**
 * Build the instructions string sent as conversation context. It is written
 * so the agent reads a clear research target, and so we can parse the disease
 * back out of the conversation title if localStorage misses.
 */
export function buildDiseaseInstructions(disease: DiseaseContext): string {
  const parts = [`${ontologyLabel(disease.ontologyId)}: ${disease.ontologyId}`];
  if (disease.mondoId && disease.mondoId !== disease.ontologyId) {
    parts.push(`MONDO: ${disease.mondoId}`);
  }
  return `Target disease: ${disease.name} (${parts.join(", ")})`;
}

/** Sentinel marking the end of the injected disease-context prefix. Uses plain
 * visible ASCII so it survives transport/normalisation (an invisible unicode
 * char could be stripped, breaking the strip step). It reads naturally and is
 * removed from the displayed bubble. */
export const INJECTED_CONTEXT_END = " ===";

/** Build the disease-context prefix prepended to the first user message. */
export function buildInjectedContextPrefix(disease: DiseaseContext): string {
  return `[Research context — ${buildDiseaseInstructions(
    disease,
  )}. All work in this workspace concerns this disease.]${INJECTED_CONTEXT_END}`;
}

/** Remove the injected disease-context prefix for display in the chat bubble. */
export function stripInjectedDiseaseContext(text: string): string {
  // Primary: split on the explicit sentinel.
  const idx = text.indexOf(INJECTED_CONTEXT_END);
  if (idx !== -1) {
    return text.slice(idx + INJECTED_CONTEXT_END.length).replace(/^\s+/, "");
  }
  // Fallback: match the bracketed research-context block even if the sentinel
  // was altered in transit.
  const stripped = text.replace(
    /^\s*\[Research context —[\s\S]*?concerns this disease\.\]\s*(?:===)?\s*/,
    "",
  );
  return stripped;
}

/**
 * Recover disease context from a conversation title/instructions string built
 * by buildDiseaseInstructions. Fallback for when localStorage is empty.
 */
export function parseDiseaseInstructions(
  title: string | null | undefined,
): DiseaseContext | null {
  if (!title) return null;
  const match = title.match(/^Target disease:\s*(.+?)(?:\s*\((.*)\))?$/);
  if (!match) return null;
  const name = match[1]?.trim();
  if (!name) return null;
  const meta = match[2] ?? "";
  const ids = meta.match(/[A-Za-z]+_\d+/g) ?? [];
  const mondo = ids.find((x) => /^MONDO_/i.test(x)) ?? null;
  const ontologyId = ids[0] ?? "";
  if (!ontologyId) return { name, ontologyId: "", mondoId: mondo };
  return { name, ontologyId, mondoId: mondo };
}
