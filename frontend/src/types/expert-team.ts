/** One expert (sub-agent) run as reported by GET /app-conversations/{id}/experts. */
export interface ExpertRunSteps {
  id: string;
  prompt: string;
  execution_status: string | null;
  step_count: number;
  steps: { title: string; tool: string | null }[];
  started_at: string | null;
  updated_at: string | null;
}
