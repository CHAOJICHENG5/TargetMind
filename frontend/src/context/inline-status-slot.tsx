import React from "react";

/**
 * Where the agent's "running" pill renders: a slot at the end of the chat
 * transcript, so the indicator follows the latest output. `AgentStatus` stays
 * mounted in the composer (it owns notifications and the workspace loading
 * flag) and portals the pill here; without a slot it renders in place.
 */
export const InlineStatusSlotContext = React.createContext<HTMLElement | null>(
  null,
);

export const useInlineStatusSlot = () =>
  React.useContext(InlineStatusSlotContext);
