import React from "react";
import { useTMText } from "#/i18n/targetmind-strings";
import { cn } from "#/utils/utils";

/** Collapsed height for long tool/command output (a few lines). */
const CLAMP_PX = 150;
/** Content longer than this (lines or chars) is considered "long". */
const MAX_LINES = 6;
const MAX_CHARS = 400;

function isLong(text?: string): boolean {
  if (!text) return false;
  const lines = text.split("\n").length;
  return lines > MAX_LINES || text.length > MAX_CHARS;
}

/**
 * Clamps long tool/command output (file_editor, bash, etc.) to a few lines
 * with a fade + "show more/less" toggle, so verbose output stays tidy.
 *
 * Whether to clamp is decided synchronously from the raw text (line count /
 * length) when provided — robust against async markdown/highlight layout.
 */
export function ClampedDetails({
  children,
  rawText,
}: {
  children: React.ReactNode;
  rawText?: string;
}) {
  const tm = useTMText();
  const [expanded, setExpanded] = React.useState(false);
  const long = isLong(rawText);
  const clamped = long && !expanded;

  return (
    <div className="relative">
      <div
        className={cn(clamped && "overflow-hidden")}
        style={clamped ? { maxHeight: CLAMP_PX } : undefined}
      >
        {children}
      </div>

      {clamped && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-tm-card to-transparent" />
      )}

      {long && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="relative mt-1 text-xs font-medium text-tm-teal transition-colors hover:text-tm-teal-deep"
        >
          {expanded ? tm("output.showLess") : tm("output.showMore")}
        </button>
      )}
    </div>
  );
}
