import { redirect } from "react-router";

/**
 * Old settings pages (LLM, agent, MCP, secrets …) are platform-managed now;
 * bookmarks to them land on the profile page instead of a 404.
 */
export const clientLoader = () => redirect("/settings");

export default function SettingsRedirect() {
  return null;
}
