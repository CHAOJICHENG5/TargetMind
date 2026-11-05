import type { CSSProperties } from "react";
import { cn } from "#/utils/utils";

export type ResearchDiscipline =
  | "biology"
  | "chemistry"
  | "clinical"
  | "bioinformatics"
  | "pharmacology"
  | "genetics"
  | "chief";

export type ResearchAgentState = "idle" | "thinking" | "active" | "discovered";

interface ResearchAgent {
  discipline: ResearchDiscipline;
  state: ResearchAgentState;
  skin: string;
  hair: string;
  accent: string;
  route: {
    start: string;
    station: string;
    handoff: string;
    duration: string;
    delay: string;
  };
}

interface MultidisciplinaryExpertRailProps {
  className?: string;
  agentStates?: Partial<Record<ResearchDiscipline, ResearchAgentState>>;
}

type ResearchEquipment = "lab-bench" | "computer";

// Route ranges are separated by station widths, so 40px avatars never overlap.
const RESEARCH_AGENTS: ResearchAgent[] = [
  {
    discipline: "biology",
    state: "active",
    skin: "#D99A72",
    hair: "#58392F",
    accent: "#2F8A76",
    route: {
      start: "1%",
      station: "12.5%",
      handoff: "6%",
      duration: "14.8s",
      delay: "-2.1s",
    },
  },
  {
    discipline: "chemistry",
    state: "thinking",
    skin: "#F0BE9B",
    hair: "#26394A",
    accent: "#6B62A5",
    route: {
      start: "35.5%",
      station: "29.5%",
      handoff: "33%",
      duration: "16.2s",
      delay: "-7.4s",
    },
  },
  {
    discipline: "clinical",
    state: "idle",
    skin: "#B97759",
    hair: "#242E35",
    accent: "#C45B68",
    route: {
      start: "44%",
      station: "49.5%",
      handoff: "47%",
      duration: "15.4s",
      delay: "-4.8s",
    },
  },
  {
    discipline: "bioinformatics",
    state: "active",
    skin: "#E4AC82",
    hair: "#55738A",
    accent: "#0E7C9B",
    route: {
      start: "75.5%",
      station: "66.5%",
      handoff: "71%",
      duration: "13.6s",
      delay: "-9.2s",
    },
  },
  {
    discipline: "pharmacology",
    state: "thinking",
    skin: "#C98970",
    hair: "#4C405E",
    accent: "#A45179",
    route: {
      start: "91.5%",
      station: "84%",
      handoff: "88%",
      duration: "17.1s",
      delay: "-5.9s",
    },
  },
];

const RESEARCH_EQUIPMENT: Array<{
  equipment: ResearchEquipment;
  left: string;
}> = [
  { equipment: "lab-bench", left: "21%" },
  { equipment: "computer", left: "58%" },
];

function BiologyPixels({ accent }: { accent: string }) {
  return (
    <g data-testid="agent-specialty-biology">
      <g className="tm-agent-signal" fill={accent}>
        <rect x="3" y="8" width="2" height="2" />
        <rect x="5" y="10" width="2" height="2" />
        <rect x="3" y="12" width="2" height="2" />
        <rect x="5" y="14" width="2" height="2" />
        <rect x="3" y="16" width="2" height="2" />
        <rect x="4" y="10" width="2" height="1" opacity="0.55" />
        <rect x="4" y="14" width="2" height="1" opacity="0.55" />
      </g>
      <rect x="31" y="21" width="2" height="8" fill="#DCE6EC" />
      <rect x="31" y="27" width="2" height="4" fill={accent} />
      <rect x="30" y="20" width="4" height="2" fill="#183044" />
    </g>
  );
}

function ChemistryPixels({ accent }: { accent: string }) {
  return (
    <g data-testid="agent-specialty-chemistry">
      <rect x="13" y="9" width="5" height="3" fill="#D8F1F2" />
      <rect x="22" y="9" width="5" height="3" fill="#D8F1F2" />
      <rect x="12" y="8" width="7" height="1" fill={accent} />
      <rect x="21" y="8" width="7" height="1" fill={accent} />
      <rect x="19" y="9" width="2" height="1" fill={accent} />
      <g className="tm-agent-signal">
        <rect x="34" y="16" width="2" height="7" fill="#183044" />
        <rect x="33" y="15" width="4" height="2" fill="#183044" />
        <rect x="32" y="23" width="6" height="2" fill="#183044" />
        <rect x="31" y="25" width="8" height="5" fill={accent} />
        <rect x="33" y="25" width="4" height="1" fill="#BFE4E7" />
        <rect x="32" y="30" width="6" height="2" fill="#183044" />
      </g>
    </g>
  );
}

function ClinicalPixels({ accent }: { accent: string }) {
  return (
    <g data-testid="agent-specialty-clinical">
      <rect x="18" y="2" width="4" height="2" fill="#F7FAFC" />
      <rect x="19" y="1" width="2" height="4" fill={accent} />
      <rect x="17" y="2" width="6" height="2" fill={accent} />
      <rect x="18" y="24" width="4" height="2" fill={accent} />
      <rect x="19" y="23" width="2" height="4" fill={accent} />
      <g
        className="tm-agent-signal"
        fill="none"
        stroke={accent}
        strokeWidth="1.5"
      >
        <path d="M31 20v7h-2v3h-3v-2" />
        <rect x="24" y="26" width="3" height="3" fill={accent} stroke="none" />
      </g>
    </g>
  );
}

function BioinformaticsPixels({ accent }: { accent: string }) {
  return (
    <g data-testid="agent-specialty-bioinformatics">
      <rect x="12" y="9" width="16" height="4" fill="#BFE4E7" />
      <rect x="12" y="9" width="3" height="4" fill={accent} opacity="0.7" />
      <rect x="25" y="9" width="3" height="4" fill={accent} opacity="0.7" />
      <g className="tm-agent-signal">
        <rect x="32" y="17" width="7" height="9" fill="#183044" />
        <rect x="33" y="18" width="5" height="6" fill="#D8F1F2" />
        <rect x="34" y="19" width="1" height="1" fill={accent} />
        <rect x="36" y="19" width="1" height="1" fill={accent} />
        <rect x="35" y="21" width="2" height="1" fill={accent} />
        <rect x="31" y="26" width="9" height="2" fill={accent} />
      </g>
    </g>
  );
}

function PharmacologyPixels({ accent }: { accent: string }) {
  return (
    <g data-testid="agent-specialty-pharmacology">
      <g className="tm-agent-signal">
        <rect x="2" y="14" width="5" height="10" fill="#183044" />
        <rect x="3" y="15" width="3" height="4" fill="#F7FAFC" />
        <rect x="3" y="19" width="3" height="4" fill={accent} />
        <rect x="2" y="18" width="5" height="2" fill="#183044" />
      </g>
      <rect x="31" y="22" width="8" height="4" fill="#183044" />
      <rect x="32" y="23" width="3" height="2" fill="#F7FAFC" />
      <rect x="35" y="23" width="3" height="2" fill={accent} />
    </g>
  );
}

/** Chromosome in the left hand, gel with banding pattern in the right. */
function GeneticsPixels({ accent }: { accent: string }) {
  return (
    <g data-testid="agent-specialty-genetics">
      <g className="tm-agent-signal" fill={accent}>
        <rect x="2" y="9" width="2" height="5" />
        <rect x="6" y="9" width="2" height="5" />
        <rect x="3" y="14" width="4" height="2" />
        <rect x="2" y="16" width="2" height="6" />
        <rect x="6" y="16" width="2" height="6" />
      </g>
      <rect x="31" y="18" width="8" height="11" fill="#183044" />
      <rect x="32" y="19" width="6" height="9" fill="#E7EEF2" />
      <rect x="33" y="20" width="4" height="1" fill={accent} />
      <rect x="33" y="23" width="4" height="1" fill={accent} opacity="0.7" />
      <rect x="33" y="25" width="4" height="1" fill={accent} opacity="0.45" />
    </g>
  );
}

/** Clipboard with the integrated findings. */
function ChiefPixels({ accent }: { accent: string }) {
  return (
    <g data-testid="agent-specialty-chief">
      <rect x="30" y="18" width="9" height="12" fill="#183044" />
      <rect x="31" y="20" width="7" height="9" fill="#F7FAFC" />
      <rect x="33" y="17" width="3" height="2" fill="#8395A6" />
      <g className="tm-agent-signal" fill={accent}>
        <rect x="32" y="22" width="5" height="1" />
        <rect x="32" y="24" width="4" height="1" />
        <rect x="32" y="26" width="5" height="1" />
      </g>
      <rect x="11" y="24" width="3" height="3" fill={accent} />
    </g>
  );
}

function DisciplinePixels({
  discipline,
  accent,
}: Pick<ResearchAgent, "discipline" | "accent">) {
  if (discipline === "biology") return <BiologyPixels accent={accent} />;
  if (discipline === "chemistry") return <ChemistryPixels accent={accent} />;
  if (discipline === "clinical") return <ClinicalPixels accent={accent} />;
  if (discipline === "bioinformatics") {
    return <BioinformaticsPixels accent={accent} />;
  }
  if (discipline === "genetics") return <GeneticsPixels accent={accent} />;
  if (discipline === "chief") return <ChiefPixels accent={accent} />;
  return <PharmacologyPixels accent={accent} />;
}

export type PixelPerson = Pick<
  ResearchAgent,
  "discipline" | "skin" | "hair" | "accent"
>;

export function PixelResearchAgent({
  discipline,
  skin,
  hair,
  accent,
  className,
}: PixelPerson & { className?: string }) {
  return (
    <svg
      data-testid="expert-sprite"
      data-discipline={discipline}
      viewBox="0 0 40 40"
      className={cn(
        "tm-agent-avatar h-10 w-10 drop-shadow-[0_2px_1px_rgba(19,34,56,0.14)]",
        className,
      )}
      shapeRendering="crispEdges"
      focusable="false"
    >
      <DisciplinePixels discipline={discipline} accent={accent} />

      <g className="tm-agent-portrait">
        <rect x="12" y="4" width="16" height="2" fill="#183044" />
        <rect x="10" y="6" width="20" height="11" fill="#183044" />
        <rect x="12" y="7" width="16" height="9" fill={skin} />
        <rect x="12" y="6" width="16" height="4" fill={hair} />
        <rect x="10" y="8" width="3" height="5" fill={hair} />
        <rect x="27" y="8" width="3" height="5" fill={hair} />
        <rect x="14" y="11" width="2" height="2" fill="#183044" />
        <rect x="24" y="11" width="2" height="2" fill="#183044" />
        <rect x="19" y="14" width="3" height="1" fill="#9D5E55" />
        <rect x="17" y="16" width="6" height="4" fill={skin} />

        <rect x="8" y="20" width="24" height="14" fill="#183044" />
        <rect x="6" y="23" width="4" height="9" fill="#183044" />
        <rect x="30" y="23" width="4" height="9" fill="#183044" />
        <rect x="10" y="22" width="20" height="11" fill="#F7FAFC" />
        <rect x="7" y="24" width="4" height="7" fill="#E7EEF2" />
        <rect x="29" y="24" width="4" height="7" fill="#E7EEF2" />
        <rect x="10" y="22" width="6" height="5" fill="#DCE6EC" />
        <rect x="24" y="22" width="6" height="5" fill="#DCE6EC" />
        <rect x="16" y="21" width="3" height="9" fill={accent} />
        <rect x="21" y="21" width="3" height="9" fill={accent} />
        <rect x="19" y="22" width="2" height="11" fill="#FFFFFF" />
        <rect x="12" y="32" width="16" height="2" fill={accent} />
        <g className="tm-agent-legs" fill="#183044">
          <rect x="12" y="34" width="6" height="4" />
          <rect x="22" y="34" width="6" height="4" />
          <rect
            className="tm-agent-foot tm-agent-foot-left"
            x="10"
            y="38"
            width="8"
            height="2"
          />
          <rect
            className="tm-agent-foot tm-agent-foot-right"
            x="22"
            y="38"
            width="8"
            height="2"
          />
        </g>
      </g>
    </svg>
  );
}

function PixelResearchEquipment({
  equipment,
}: {
  equipment: ResearchEquipment;
}) {
  if (equipment === "lab-bench") {
    return (
      <svg
        data-testid="research-equipment-lab-bench"
        viewBox="0 0 40 40"
        className="h-10 w-10 drop-shadow-[0_2px_1px_rgba(19,34,56,0.12)]"
        shapeRendering="crispEdges"
        focusable="false"
      >
        <g className="tm-equipment-signal">
          <rect x="8" y="13" width="4" height="8" fill="#183044" />
          <rect x="9" y="14" width="2" height="5" fill="#D8F1F2" />
          <rect x="9" y="18" width="2" height="2" fill="#2F8A76" />
          <rect x="7" y="12" width="6" height="2" fill="#183044" />
          <rect x="17" y="15" width="3" height="7" fill="#183044" />
          <rect x="18" y="16" width="1" height="5" fill="#6B62A5" />
          <rect x="23" y="10" width="3" height="12" fill="#183044" />
          <rect x="24" y="11" width="1" height="10" fill="#0E7C9B" />
          <rect x="29" y="14" width="3" height="8" fill="#183044" />
          <rect x="30" y="15" width="1" height="6" fill="#C45B68" />
        </g>
        <rect x="4" y="22" width="32" height="4" fill="#183044" />
        <rect x="6" y="23" width="28" height="2" fill="#DCE6EC" />
        <rect x="7" y="26" width="4" height="10" fill="#183044" />
        <rect x="29" y="26" width="4" height="10" fill="#183044" />
        <rect x="13" y="27" width="14" height="7" fill="#55738A" />
        <rect x="15" y="29" width="10" height="2" fill="#E7EEF2" />
        <rect x="6" y="36" width="6" height="2" fill="#183044" />
        <rect x="28" y="36" width="6" height="2" fill="#183044" />
      </svg>
    );
  }

  return (
    <svg
      data-testid="research-equipment-computer"
      viewBox="0 0 40 40"
      className="h-10 w-10 drop-shadow-[0_2px_1px_rgba(19,34,56,0.12)]"
      shapeRendering="crispEdges"
      focusable="false"
    >
      <rect x="6" y="7" width="28" height="21" fill="#183044" />
      <rect x="9" y="10" width="22" height="15" fill="#D8F1F2" />
      <g className="tm-equipment-signal" fill="#0E7C9B">
        <rect x="12" y="13" width="3" height="3" />
        <rect x="17" y="13" width="7" height="2" />
        <rect x="17" y="17" width="11" height="2" />
        <rect x="12" y="21" width="6" height="2" />
        <rect x="20" y="21" width="8" height="2" fill="#6B62A5" />
      </g>
      <rect x="17" y="28" width="6" height="4" fill="#183044" />
      <rect x="12" y="32" width="16" height="3" fill="#183044" />
      <rect x="7" y="35" width="26" height="3" fill="#55738A" />
      <rect x="10" y="35" width="20" height="1" fill="#E7EEF2" />
    </svg>
  );
}

export function MultidisciplinaryExpertRail({
  className,
  agentStates,
}: MultidisciplinaryExpertRailProps) {
  return (
    <div
      data-testid="multidisciplinary-expert-rail"
      aria-hidden="true"
      className={cn(
        "pointer-events-none relative h-11 min-w-0 overflow-hidden px-3",
        className,
      )}
    >
      <div
        data-testid="expert-collaboration-line"
        className="absolute inset-x-2 top-[39px] border-t border-dashed border-tm-teal/35"
      />
      <span className="tm-collaboration-packet absolute top-[37px] h-1 w-1 bg-tm-teal" />
      <span className="tm-collaboration-packet tm-collaboration-packet-reverse absolute top-[37px] h-1 w-1 bg-[#6B62A5]" />

      <div className="relative z-[1] h-full">
        {RESEARCH_EQUIPMENT.map((station) => (
          <div
            key={station.equipment}
            data-testid="research-equipment"
            data-equipment={station.equipment}
            className="tm-research-equipment absolute top-0 flex w-10 justify-center"
            style={{ left: station.left }}
          >
            <PixelResearchEquipment equipment={station.equipment} />
          </div>
        ))}

        {RESEARCH_AGENTS.map((agent) => {
          const state = agentStates?.[agent.discipline] ?? agent.state;
          return (
            <div
              key={agent.discipline}
              data-testid="research-agent"
              data-state={state}
              data-discipline={agent.discipline}
              className="tm-research-agent absolute top-0 flex w-10 justify-center"
              style={
                {
                  left: agent.route.station,
                  "--agent-delay": agent.route.delay,
                  "--route-start": agent.route.start,
                  "--route-station": agent.route.station,
                  "--route-handoff": agent.route.handoff,
                  "--route-duration": agent.route.duration,
                } as CSSProperties
              }
            >
              <PixelResearchAgent
                discipline={agent.discipline}
                skin={agent.skin}
                hair={agent.hair}
                accent={agent.accent}
              />
              <span
                className="tm-agent-node absolute top-[37px] h-[5px] w-[5px] border border-tm-teal/70 bg-tm-paper"
                style={{ borderColor: agent.accent } as CSSProperties}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
