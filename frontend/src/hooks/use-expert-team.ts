import { useMemo } from "react";
import { useEventStore } from "#/stores/use-event-store";
import { isActionEvent, isObservationEvent } from "#/types/v1/type-guards";
import type { AgentEvent } from "#/types/v1/core";
import type { TaskAction } from "#/types/v1/core/base/action";
import type { TaskObservation } from "#/types/v1/core/base/observation";
import type { ActionEvent } from "#/types/v1/core/events/action-event";
import type { ObservationEvent } from "#/types/v1/core/events/observation-event";

export const EXPERTS = [
  { id: "molecular-biology", name: "Molecular Biology", short: "MB" },
  { id: "genetics", name: "Genetics", short: "GE" },
  { id: "bioinformatics", name: "Bioinformatics", short: "BI" },
  { id: "medicinal-chemistry", name: "Medicinal Chemistry", short: "MC" },
] as const;

export type ExpertId = (typeof EXPERTS)[number]["id"];
export type ExpertStatus = "standby" | "working" | "done" | "partial" | "error";
export type ExpertPhase = "discovery" | "evaluation" | "follow-up";

export const PHASE_LABEL: Record<ExpertPhase, string> = {
  discovery: "Discovery",
  evaluation: "Evaluation",
  "follow-up": "Follow-up",
};

export interface ExpertRun {
  expert: ExpertId;
  status: ExpertStatus;
  task: string;
  prompt: string;
  /** From the brief's `PHASE: …` line; null for briefs without one. */
  phase: ExpertPhase | null;
  batch: number;
  startedAt: number;
  endedAt: number | null;
  summary: string | null;
  files: string[];
}

export interface ExpertTeamState {
  /** Latest run per expert (absent = never called in this conversation). */
  runs: Partial<Record<ExpertId, ExpertRun>>;
  batch: number;
  /** Phase of the latest batch (null when its briefs carry no PHASE line). */
  phase: ExpertPhase | null;
  working: number;
  done: number;
  /** When the first expert of the conversation was dispatched. */
  startedAt: number | null;
}

/** Event timestamps are UTC without a zone suffix. */
export const parseEventTime = (value: string) =>
  Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);

const observationText = (obs: TaskObservation) =>
  obs.content
    .map((c) => ("text" in c ? c.text : ""))
    .join("\n")
    .trim();

/** Body of a "## <title>" section of an expert report. */
export function reportSection(text: string, title: string): string | null {
  const match = text.match(
    new RegExp(`^##\\s*${title}\\s*$([\\s\\S]*?)(?=^##\\s|(?![\\s\\S]))`, "im"),
  );
  const body = match?.[1].trim();
  return body || null;
}

export function reportFiles(text: string): string[] {
  const body = reportSection(text, "Files");
  if (!body) return [];
  return body
    .split("\n")
    .map((line) =>
      line
        .replace(/^[-*]\s*/, "")
        .replace(/`/g, "")
        .split(/\s+[—–-]\s+/)[0]
        .trim(),
    )
    .filter((line) => /\.[a-z0-9]{1,6}$/i.test(line));
}

const PHASE_LINE = /^\s*PHASE:\s*(discovery|evaluation|follow-?up)\b/im;

/** The Chief Scientist starts every brief with `PHASE: <name>`. */
export function briefPhase(prompt: string): ExpertPhase | null {
  const match = prompt.match(PHASE_LINE);
  if (!match) return null;
  const phase = match[1].toLowerCase();
  return phase === "discovery" || phase === "evaluation" ? phase : "follow-up";
}

const briefTitle = (prompt: string) =>
  (
    prompt
      .split("\n")
      .map((line) => line.trim())
      .find((line) => line && !PHASE_LINE.test(line)) ?? ""
  ).slice(0, 160);

function statusFor(obs: TaskObservation | undefined): ExpertStatus {
  if (!obs) return "working";
  if (!obs.is_error) return "done";
  // Hitting the step cap still leaves usable work (summary.md, files).
  return /partial result|maximum iterations/i.test(observationText(obs))
    ? "partial"
    : "error";
}

const isKnownExpert = (value: string): value is ExpertId =>
  EXPERTS.some((e) => e.id === value);

/** Derive the expert team state from the conversation's task tool calls. */
export function buildExpertTeam(events: AgentEvent[]): ExpertTeamState {
  const observations = new Map<string, ObservationEvent<TaskObservation>>();
  const actions: ActionEvent<TaskAction>[] = [];
  events.forEach((event) => {
    if (isActionEvent(event) && event.action.kind === "TaskAction") {
      actions.push(event as ActionEvent<TaskAction>);
    } else if (
      isObservationEvent(event) &&
      event.observation.kind === "TaskObservation"
    ) {
      observations.set(
        event.action_id,
        event as ObservationEvent<TaskObservation>,
      );
    }
  });

  const batchIds: string[] = [];
  let phase: ExpertPhase | null = null;
  const runs: Partial<Record<ExpertId, ExpertRun>> = {};
  actions.forEach((event) => {
    const { action } = event;
    if (!isKnownExpert(action.subagent_type)) return;
    if (!batchIds.includes(event.llm_response_id)) {
      batchIds.push(event.llm_response_id);
      phase = null;
    }
    const runPhase = briefPhase(action.prompt);
    phase = phase ?? runPhase;
    const obsEvent = observations.get(event.id);
    const obs = obsEvent?.observation;
    const text = obs ? observationText(obs) : "";
    runs[action.subagent_type] = {
      expert: action.subagent_type,
      status: statusFor(obs),
      task: action.description || briefTitle(action.prompt),
      prompt: action.prompt,
      phase: runPhase,
      batch: batchIds.indexOf(event.llm_response_id) + 1,
      startedAt: parseEventTime(event.timestamp),
      endedAt: obsEvent ? parseEventTime(obsEvent.timestamp) : null,
      summary: text
        ? (reportSection(text, "Conclusion") ?? text.slice(0, 400))
        : null,
      files: text ? reportFiles(text) : [],
    };
  });

  const list = Object.values(runs);
  return {
    runs,
    batch: batchIds.length,
    phase,
    working: list.filter((r) => r.status === "working").length,
    done: list.filter((r) => r.status !== "working").length,
    startedAt: actions.length ? parseEventTime(actions[0].timestamp) : null,
  };
}

export function useExpertTeam(): ExpertTeamState {
  const events = useEventStore((state) => state.events);
  return useMemo(() => buildExpertTeam(events as AgentEvent[]), [events]);
}
