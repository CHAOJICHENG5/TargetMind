import type { AgentEvent } from "#/types/v1/core";
import { V1ExecutionStatus } from "#/types/v1/core/base/common";
import {
  isAgentStatusConversationStateUpdateEvent,
  isConversationStateUpdateEvent,
  isExecuteBashObservationEvent,
  isFullStateConversationStateUpdateEvent,
  isObservationEvent,
} from "#/types/v1/type-guards";

const FILE_EDIT_OBSERVATIONS = new Set([
  "FileEditorObservation",
  "StrReplaceEditorObservation",
]);

/** Whether a live agent event may have changed the Results file listing. */
export function eventMayChangeWorkspaceFiles(event: AgentEvent): boolean {
  if (isExecuteBashObservationEvent(event)) {
    const { exit_code: exitCode } = event.observation;
    return exitCode !== null && exitCode !== -1;
  }

  if (
    isObservationEvent(event) &&
    FILE_EDIT_OBSERVATIONS.has(event.observation.kind)
  ) {
    const observation = event.observation as {
      command?: string;
      error?: string | null;
    };
    return observation.command !== "view" && !observation.error;
  }

  if (!isConversationStateUpdateEvent(event)) return false;

  let executionStatus: V1ExecutionStatus | null = null;
  if (isAgentStatusConversationStateUpdateEvent(event)) {
    executionStatus = event.value;
  } else if (isFullStateConversationStateUpdateEvent(event)) {
    executionStatus = event.value.execution_status;
  }

  return executionStatus
    ? executionStatus !== V1ExecutionStatus.RUNNING
    : false;
}
