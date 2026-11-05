import { cn } from "#/utils/utils";

interface AccessionChipProps {
  label: string; // "EFO" | "MONDO"
  value: string; // "EFO_1001517"
  tone?: "chip" | "teal";
  className?: string;
}

/**
 * TargetMind signature element: an ontology accession rendered as monospace
 * data. Recurs from the home result card to the conversation disease badge.
 */
export function AccessionChip({
  label,
  value,
  tone = "chip",
  className,
}: AccessionChipProps) {
  const tones = {
    chip: "bg-tm-chip text-tm-chip-text",
    teal: "bg-tm-teal-soft text-tm-teal-deep",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-mono text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      <span className="opacity-60">{label}</span>
      <span className="tracking-tight">{value}</span>
    </span>
  );
}
