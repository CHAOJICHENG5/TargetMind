import React from "react";
import { ChevronDown, Users, X } from "lucide-react";
import { cn } from "#/utils/utils";
import { AgentState } from "#/types/agent-state";
import { useAgentState } from "#/hooks/use-agent-state";
import { ExpertSprite } from "./expert-sprite";
import {
  EXPERTS,
  PHASE_LABEL,
  type ExpertId,
  type ExpertPhase,
  type ExpertRun,
  type ExpertStatus,
  useExpertTeam,
} from "#/hooks/use-expert-team";
import { useConversationExperts } from "#/hooks/query/use-conversation-experts";
import { useListWorkspaceFiles } from "#/hooks/query/use-list-workspace-files";
import { useWorkspaceViewerStore } from "#/stores/workspace-viewer-store";
import type { ExpertRunSteps } from "#/types/expert-team";

/* eslint-disable i18next/no-literal-string -- the Expert Team panel is English by design */

const STATUS: Record<
  ExpertStatus,
  { label: string; dot: string; text: string; line: string }
> = {
  working: {
    label: "Working",
    dot: "bg-tm-teal",
    text: "text-tm-teal",
    line: "#0e7c9b",
  },
  done: {
    label: "Submitted",
    dot: "bg-emerald-600",
    text: "text-emerald-700",
    line: "#2f9e6e",
  },
  partial: {
    label: "Step limit · partial",
    dot: "bg-amber-500",
    text: "text-amber-700",
    line: "#c98a1b",
  },
  error: {
    label: "Failed",
    dot: "bg-red-500",
    text: "text-red-600",
    line: "#dc2626",
  },
  standby: {
    label: "Standby",
    dot: "bg-slate-300",
    text: "text-tm-slate-soft",
    line: "#c3cfda",
  },
};

const DASH: Partial<Record<ExpertStatus, string>> = {
  working: "4 4",
  standby: "2 3",
};

const LEGEND: ExpertStatus[] = ["working", "done", "partial", "standby"];

/** Phase from the briefs' `PHASE:` line; older briefs fall back to the batch. */
const batchLabel = (batch: number, phase: ExpertPhase | null) => {
  if (phase) return PHASE_LABEL[phase];
  return batch === 1 ? "Parallel" : "Follow-up";
};

const formatDuration = (ms: number) => {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

function useNow(active: boolean) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

const matchSteps = (run: ExpertRun, steps: ExpertRunSteps[] | undefined) => {
  const head = run.prompt.trim().slice(0, 200);
  return steps
    ?.filter((s) => s.prompt.trim().startsWith(head))
    .sort((a, b) => (a.started_at ?? "").localeCompare(b.started_at ?? ""))
    .at(-1);
};

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-2.5 min-w-0">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.07em] text-tm-slate-soft">
        {title}
      </p>
      {children}
    </div>
  );
}

function ExpertCard({
  run,
  steps,
  now,
  onOpenFile,
  onClose,
  align,
}: {
  run: ExpertRun;
  steps: ExpertRunSteps | undefined;
  now: number;
  onOpenFile: (path: string) => void;
  onClose: () => void;
  align: "left" | "right";
}) {
  const meta = EXPERTS.find((e) => e.id === run.expert)!;
  const status = STATUS[run.status];
  const recent = steps?.steps.slice(-4) ?? [];
  const earlier = (steps?.step_count ?? 0) - recent.length;
  return (
    <div
      data-testid="expert-card"
      className={cn(
        "absolute top-full z-30 mt-2 w-full min-w-0 max-w-[360px] overflow-hidden rounded-xl border border-tm-line bg-white p-3.5 text-left shadow-[0_18px_40px_-18px_rgba(19,34,56,0.45)]",
        align === "left" ? "left-0" : "right-0",
      )}
    >
      <div className="flex min-w-0 items-center gap-2">
        <span className="min-w-0 truncate text-[13.5px] font-semibold text-tm-ink">
          {meta.name}
        </span>
        <span className="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-tm-line bg-tm-paper px-2 py-px text-[11px] text-tm-slate">
          <span className={cn("h-1.5 w-1.5 rounded-full", status.dot)} />
          {status.label}
        </span>
        <span className="flex-1" />
        <span className="shrink-0 whitespace-nowrap text-[11px] text-tm-slate-soft">
          {formatDuration((run.endedAt ?? now) - run.startedAt)}
          {steps ? ` · ${steps.step_count} steps` : ""}
        </span>
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="shrink-0 text-tm-slate-soft hover:text-tm-ink"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      <Section title={run.phase ? `Task · ${PHASE_LABEL[run.phase]}` : "Task"}>
        <p
          className="line-clamp-2 break-words text-xs text-tm-ink [overflow-wrap:anywhere]"
          title={run.task}
        >
          {run.task}
        </p>
      </Section>
      {recent.length > 0 && (
        <Section title="Steps">
          {earlier > 0 && (
            <p className="text-[11px] text-tm-slate-soft">
              + {earlier} earlier
            </p>
          )}
          <ul className="flex min-w-0 flex-col gap-0.5">
            {recent.map((step, i) => (
              <li
                // eslint-disable-next-line react/no-array-index-key
                key={i}
                title={step.title}
                className={cn(
                  "min-w-0 truncate text-xs text-tm-ink",
                  run.status === "working" &&
                    i === recent.length - 1 &&
                    "font-semibold text-tm-teal-deep",
                )}
              >
                {step.title}
              </li>
            ))}
          </ul>
        </Section>
      )}
      {run.summary && (
        <Section title="Summary">
          <p className="line-clamp-4 break-words rounded-lg bg-tm-paper px-2.5 py-1.5 text-xs text-tm-ink [overflow-wrap:anywhere]">
            {run.summary}
          </p>
        </Section>
      )}
      {run.files.length > 0 && (
        <Section title="Files">
          <div className="flex min-w-0 flex-wrap gap-1">
            {run.files.slice(0, 6).map((path) => (
              <button
                key={path}
                type="button"
                onClick={() => onOpenFile(path)}
                className="max-w-full truncate rounded-md bg-tm-teal-soft px-1.5 py-0.5 font-mono text-[11px] text-tm-teal-deep hover:bg-tm-teal/15"
                title={path}
              >
                {path.split("/").pop()}
              </button>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

export function ExpertTeamPanel({
  conversationId,
}: {
  conversationId: string | null | undefined;
}) {
  const team = useExpertTeam();
  const { curAgentState } = useAgentState();
  const agentRunning = curAgentState === AgentState.RUNNING;
  const now = useNow(team.working > 0);
  const { data: expertSteps } = useConversationExperts(
    conversationId,
    team.working > 0,
  );
  const { data: files } = useListWorkspaceFiles(conversationId);
  const { openFile } = useWorkspaceViewerStore();

  // Expanded by default like the other workspace panels; the user's toggle sticks.
  const [expanded, setExpanded] = React.useState(true);
  const [selected, setSelected] = React.useState<ExpertId | null>(null);

  const called = Object.keys(team.runs).length;
  const selectedRun = selected ? team.runs[selected] : undefined;
  const runs = Object.values(team.runs);
  const lastEnd = Math.max(0, ...runs.map((r) => r.endedAt ?? 0));
  const elapsed =
    team.startedAt !== null
      ? formatDuration((team.working > 0 ? now : lastEnd) - team.startedAt)
      : null;

  // Chief sprite: works while it runs or waits on experts, else stands by.
  let chiefSprite: ExpertStatus = "standby";
  if (team.working > 0 || agentRunning) chiefSprite = "working";
  else if (called) chiefSprite = "done";

  let chiefStatus = "Ready";
  if (team.working > 0) {
    chiefStatus = `Awaiting ${team.working} expert${team.working > 1 ? "s" : ""}`;
  } else if (agentRunning) {
    chiefStatus = called ? "Integrating results" : "Working directly";
  } else if (called) {
    chiefStatus = "Done";
  }

  const summaryChip = called
    ? [
        team.working && `${team.working} working`,
        team.done && `${team.done} done`,
        4 - called && `${4 - called} standby`,
      ]
        .filter(Boolean)
        .join(" · ")
    : "No experts called";

  const openPath = (path: string) => {
    const clean = path.replace(/^\.\//, "");
    const file = files?.items.find(
      (f) => f.path === clean || f.path.endsWith(`/${clean}`),
    );
    if (file && files) openFile(file, files.working_dir);
  };

  return (
    <section
      data-testid="expert-team-panel"
      className="tm-panel flex w-full min-w-0 max-w-full flex-none flex-col rounded-xl border border-tm-line bg-tm-workspace"
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className={cn(
          "flex w-full min-w-0 items-center gap-2 px-4 py-3 text-left",
          "rounded-t-[11px] bg-tm-panel-head",
          expanded ? "border-b border-tm-line" : "rounded-b-[11px]",
        )}
      >
        <Users className="h-4 w-4 shrink-0 text-tm-teal" />
        <h3 className="shrink-0 whitespace-nowrap font-display text-sm font-semibold text-tm-ink">
          Expert Team
        </h3>
        {!expanded && called > 0 && (
          <div className="flex shrink-0 items-center gap-1">
            {EXPERTS.map((e) => (
              <span
                key={e.id}
                className={cn(
                  "h-2 w-2 rounded-full",
                  STATUS[team.runs[e.id]?.status ?? "standby"].dot,
                )}
              />
            ))}
          </div>
        )}
        <span className="flex-1" />
        <span
          className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-tm-line bg-white px-2 py-0.5 text-[11px] text-tm-slate"
          title={summaryChip}
        >
          {team.working > 0 && (
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-tm-teal" />
          )}
          <span className="min-w-0 truncate">{summaryChip}</span>
        </span>
        {elapsed && (
          <span className="shrink-0 rounded-full border border-tm-line bg-white px-2 py-0.5 font-mono text-[11px] text-tm-slate">
            {elapsed}
          </span>
        )}
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-tm-slate-soft transition-transform",
            !expanded && "-rotate-90",
          )}
        />
      </button>

      {expanded && (
        <div className="min-w-0 px-3 pb-3 pt-3">
          {/* Chief Scientist */}
          <div className="flex min-w-0 justify-center">
            <div className="flex min-w-0 max-w-full items-center gap-2.5 rounded-xl bg-tm-navy px-3.5 py-2 text-white">
              <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/90">
                <ExpertSprite member="chief" status={chiefSprite} size="sm" />
              </span>
              <div className="min-w-0 leading-tight">
                <p className="truncate text-[12.5px] font-semibold">
                  Chief Scientist
                </p>
                <p className="truncate text-[11px] text-white/70">
                  {chiefStatus}
                </p>
              </div>
            </div>
          </div>

          {/* Orthogonal connectors: trunk, neutral bus, status-coloured drops */}
          <svg
            className="block h-8 w-full"
            viewBox="0 0 400 32"
            preserveAspectRatio="none"
            aria-hidden
          >
            <path
              d="M200 0 V14"
              stroke="#1b4d6b"
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
            />
            <path
              d="M50 14 H350"
              stroke="#c3cfda"
              strokeWidth="1.3"
              vectorEffect="non-scaling-stroke"
            />
            {EXPERTS.map((e, i) => {
              const status = team.runs[e.id]?.status ?? "standby";
              return (
                <path
                  key={e.id}
                  d={`M${50 + i * 100} 14 V32`}
                  stroke={STATUS[status].line}
                  strokeWidth={status === "standby" ? 1.3 : 1.7}
                  strokeDasharray={DASH[status]}
                  className={
                    status === "working" ? "tm-expert-flow" : undefined
                  }
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
          </svg>

          {/* Expert cards; the detail card is positioned against this wrapper */}
          <div className="relative min-w-0">
            <div className="grid min-w-0 grid-cols-4 gap-2">
              {EXPERTS.map((e) => {
                const run = team.runs[e.id];
                const status = run?.status ?? "standby";
                const steps = run ? matchSteps(run, expertSteps) : undefined;
                const current =
                  status === "working"
                    ? (steps?.steps.at(-1)?.title ?? "Starting")
                    : STATUS[status].label;
                return (
                  <div key={e.id} className="min-w-0 overflow-hidden">
                    <button
                      type="button"
                      data-testid={`expert-node-${e.id}`}
                      disabled={!run}
                      onClick={() =>
                        setSelected(selected === e.id ? null : e.id)
                      }
                      className={cn(
                        "flex w-full flex-col items-center gap-1 rounded-xl border bg-white px-1.5 py-2 transition-shadow",
                        status === "working"
                          ? "border-tm-teal"
                          : "border-tm-line",
                        status === "standby" && "border-dashed cursor-default",
                        run && "hover:shadow-sm",
                        selected === e.id && "ring-2 ring-tm-teal/25",
                      )}
                    >
                      <ExpertSprite member={e.id} status={status} />
                      <span
                        className="w-full truncate text-center text-[11px] font-semibold text-tm-ink"
                        title={e.name}
                      >
                        {e.name}
                      </span>
                      <span
                        className={cn(
                          "w-full truncate text-center text-[10px]",
                          STATUS[status].text,
                        )}
                        title={current}
                      >
                        {current}
                        {run &&
                          ` · ${formatDuration((run.endedAt ?? now) - run.startedAt)}`}
                      </span>
                    </button>
                  </div>
                );
              })}
            </div>

            {selectedRun && (
              <ExpertCard
                run={selectedRun}
                steps={matchSteps(selectedRun, expertSteps)}
                now={now}
                onOpenFile={openPath}
                onClose={() => setSelected(null)}
                align={
                  EXPERTS.findIndex((x) => x.id === selectedRun.expert) < 2
                    ? "left"
                    : "right"
                }
              />
            )}
          </div>

          <div className="mt-2.5 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-tm-slate">
            {LEGEND.map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-1 whitespace-nowrap"
              >
                <span
                  className={cn("h-1.5 w-1.5 rounded-full", STATUS[s].dot)}
                />
                {STATUS[s].label}
              </span>
            ))}
            <span className="flex-1" />
            {team.batch > 0 && (
              <span
                data-testid="expert-team-phase"
                className="whitespace-nowrap text-[10px] font-semibold uppercase tracking-[0.06em] text-tm-slate-soft"
              >
                Batch {team.batch} · {batchLabel(team.batch, team.phase)}
              </span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
