import React from "react";
import {
  Check,
  Circle,
  LoaderCircle,
  ListChecks,
  ChevronDown,
} from "lucide-react";
import { useTaskList, TaskListItem } from "#/hooks/use-task-list";
import { useTMText } from "#/i18n/targetmind-strings";
import { cn } from "#/utils/utils";

function StatusIcon({ status }: { status: TaskListItem["status"] }) {
  if (status === "done")
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-tm-teal text-white">
        <Check className="h-3 w-3" strokeWidth={3} />
      </span>
    );
  if (status === "in_progress")
    return (
      <span className="flex h-5 w-5 items-center justify-center text-tm-teal">
        <LoaderCircle className="h-4 w-4 animate-spin" />
      </span>
    );
  return (
    <span className="flex h-5 w-5 items-center justify-center text-tm-slate-soft">
      <Circle className="h-3.5 w-3.5" />
    </span>
  );
}

export function PlanPanel() {
  const tm = useTMText();
  const { taskList } = useTaskList();
  const [collapsed, setCollapsed] = React.useState(false);
  const total = taskList.length;
  const done = taskList.filter((t) => t.status === "done").length;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <section
      className={cn(
        "tm-panel flex flex-col rounded-xl border border-tm-line bg-tm-workspace",
        collapsed ? "flex-none" : "min-h-0 flex-[2]",
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className={cn(
          "flex items-center justify-between px-4 py-3 text-left",
          "rounded-t-[11px] bg-tm-panel-head",
          collapsed ? "rounded-b-[11px]" : "border-b border-tm-line",
        )}
      >
        <div className="flex items-center gap-2">
          <ListChecks className="h-4 w-4 text-tm-teal" />
          <h3 className="font-display text-sm font-semibold text-tm-ink">
            {tm("panel.plan")}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {total > 0 && (
            <span className="font-mono text-xs text-tm-slate">
              {done}/{total}
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 text-tm-slate-soft transition-transform",
              collapsed && "-rotate-90",
            )}
          />
        </div>
      </button>

      {!collapsed && total > 0 && (
        <div className="px-4 pt-3">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-tm-line">
            <div
              className="h-full rounded-full bg-tm-teal transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      <div
        className={cn(
          "min-h-0 flex-1 overflow-y-auto px-2 py-2",
          collapsed && "hidden",
        )}
      >
        {total === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-tm-slate-soft">
            {tm("panel.planEmpty")}
          </p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {taskList.map((task) => (
              <li
                key={task.id}
                className={cn(
                  "flex items-start gap-2.5 rounded-lg px-2 py-2",
                  task.status === "in_progress" && "bg-tm-teal-soft/60",
                )}
              >
                <span className="mt-0.5">
                  <StatusIcon status={task.status} />
                </span>
                <span
                  className={cn(
                    "text-sm leading-5",
                    task.status === "done"
                      ? "text-tm-slate-soft line-through"
                      : "text-tm-ink",
                  )}
                >
                  {task.title}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
