import { Check, X } from "lucide-react";
import type { ExpertId, ExpertStatus } from "#/hooks/use-expert-team";
import { cn } from "#/utils/utils";
import {
  PixelResearchAgent,
  type PixelPerson,
} from "../multidisciplinary-expert-rail";

/**
 * Pixel scientists of the expert panel. Same people as in the lab rail above
 * the workspace; each holds the instrument of its discipline. Motion only
 * mirrors real state (CSS `.tm-expert-sprite[data-status]`): working experts
 * work, finished ones stand still with a badge, idle ones are greyed out.
 */
export const TEAM_SPRITES: Record<ExpertId | "chief", PixelPerson> = {
  chief: {
    discipline: "chief",
    skin: "#B97759",
    hair: "#242E35",
    accent: "#0E7C9B",
  },
  "molecular-biology": {
    discipline: "biology",
    skin: "#D99A72",
    hair: "#58392F",
    accent: "#2F8A76",
  },
  genetics: {
    discipline: "genetics",
    skin: "#C98970",
    hair: "#4C405E",
    accent: "#3567AD",
  },
  bioinformatics: {
    discipline: "bioinformatics",
    skin: "#E4AC82",
    hair: "#55738A",
    accent: "#0E7C9B",
  },
  "medicinal-chemistry": {
    discipline: "chemistry",
    skin: "#F0BE9B",
    hair: "#26394A",
    accent: "#6B62A5",
  },
};

const BADGE: Partial<Record<ExpertStatus, string>> = {
  done: "bg-emerald-600",
  partial: "bg-amber-500",
  error: "bg-red-500",
};

export function ExpertSprite({
  member,
  status,
  size = "md",
}: {
  member: ExpertId | "chief";
  status: ExpertStatus;
  size?: "sm" | "md";
}) {
  const badge = BADGE[status];
  const person = TEAM_SPRITES[member];
  return (
    <span
      data-testid={`team-sprite-${member}`}
      data-status={status}
      className={cn(
        "tm-expert-sprite relative inline-grid shrink-0 place-items-center",
        size === "md" ? "size-11" : "size-8",
      )}
    >
      <PixelResearchAgent
        discipline={person.discipline}
        skin={person.skin}
        hair={person.hair}
        accent={person.accent}
        className={size === "md" ? "h-10 w-10" : "h-7 w-7"}
      />
      {status === "working" && (
        <span
          aria-hidden
          className="tm-expert-working-dot absolute right-0 top-0 size-2 rounded-full bg-tm-teal ring-2 ring-white"
        />
      )}
      {badge && (
        <span
          aria-hidden
          className={cn(
            "absolute -bottom-0.5 -right-0.5 grid size-3.5 place-items-center rounded-full text-white ring-2 ring-white",
            badge,
          )}
        >
          {status === "done" && <Check className="size-2.5" strokeWidth={3} />}
          {status === "partial" && (
            <span className="text-[9px] font-bold leading-none">!</span>
          )}
          {status === "error" && <X className="size-2.5" strokeWidth={3} />}
        </span>
      )}
    </span>
  );
}
