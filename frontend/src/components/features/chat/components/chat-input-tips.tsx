import React from "react";
import { Lightbulb } from "lucide-react";
import { useTMText } from "#/i18n/targetmind-strings";

/** How long each tip stays on screen. */
const ROTATE_MS = 6000;

const TIP_KEYS = [
  "tip.disease",
  "tip.files",
  "tip.plan",
  "tip.structure",
  "tip.cite",
] as const;

/**
 * Rotating usage hint above the composer.
 *
 * Cycles one short tip at a time so the hint costs a single line of height.
 * Uses a keyed fade so each tip animates in without a layout shift, and pauses
 * while the tab is hidden (a background timer would burn renders for nothing).
 */
export function ChatInputTips() {
  const tm = useTMText();
  const [index, setIndex] = React.useState(0);

  React.useEffect(() => {
    const id = window.setInterval(() => {
      if (document.hidden) return;
      setIndex((i) => (i + 1) % TIP_KEYS.length);
    }, ROTATE_MS);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div
      data-testid="chat-input-tips"
      aria-live="polite"
      className="flex items-center justify-center gap-1.5 px-2 text-xs text-tm-slate-soft"
    >
      <Lightbulb className="h-3.5 w-3.5 shrink-0 text-tm-teal/70" />
      <span key={index} className="tm-fade-up truncate">
        {tm(TIP_KEYS[index])}
      </span>
    </div>
  );
}
