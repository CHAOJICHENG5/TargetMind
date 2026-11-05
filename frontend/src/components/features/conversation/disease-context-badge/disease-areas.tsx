import React from "react";
import {
  Baby,
  Bone,
  Brain,
  Bug,
  Dna,
  Droplets,
  Ear,
  Eye,
  FlaskConical,
  Hand,
  HeartPulse,
  Ribbon,
  ShieldPlus,
  type LucideProps,
} from "lucide-react";
import type { OntologyTerm } from "#/api/opentargets-service/opentargets.api";

/**
 * Body-system styling for the workspace disease card, keyed off the Open
 * Targets therapeutic areas. Every hue stays in the teal–blue family of the
 * interface (cyan/teal ↔ sky ↔ steel and indigo blue) so systems differ only
 * by shade; unknown areas fall back to the brand teal + DNA glyph.
 */

type GlyphProps = Pick<LucideProps, "className" | "strokeWidth">;
type Glyph = React.ComponentType<GlyphProps>;

function OrganGlyph({
  className,
  strokeWidth = 1.75,
  children,
}: GlyphProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      {children}
    </svg>
  );
}

// Organs lucide has no icon for, drawn on the same 24px / round-stroke grid.
export function KidneyGlyph({ className, strokeWidth }: GlyphProps) {
  return (
    <OrganGlyph className={className} strokeWidth={strokeWidth}>
      <path d="M15.6 6.6C14.4 3.6 9.8 2.8 7 5 4 7.4 3.8 12.7 5.6 16.4c1.8 3.7 6.2 5 8.8 3 1.7-1.3 1.7-3.5.4-4.8-1-1-1.3-2-.9-3.1.4-1.1 1.3-1.6 1.7-2.6.3-.8.3-1.6 0-2.3Z" />
      <path d="M14.2 12.4h2.3c1.4 0 2.5 1.1 2.5 2.5V21" />
      <path d="M8.8 8.6c-1 1.9-1 4.4 0 6.4" />
    </OrganGlyph>
  );
}

export function LungsGlyph({ className, strokeWidth }: GlyphProps) {
  return (
    <OrganGlyph className={className} strokeWidth={strokeWidth}>
      <path d="M12 3v7.5" />
      <path d="M12 10.5 9.5 13M12 10.5l2.5 2.5" />
      <path d="M8.6 6.2C6.1 6.6 3.5 11 3.5 16.2c0 2.4 1.1 3.8 3 3.8 1.7 0 3-.9 3-2.9V8c0-1.1-.3-1.9-.9-1.8Z" />
      <path d="M15.4 6.2c2.5.4 5.1 4.8 5.1 10 0 2.4-1.1 3.8-3 3.8-1.7 0-3-.9-3-2.9V8c0-1.1.3-1.9.9-1.8Z" />
    </OrganGlyph>
  );
}

export function StomachGlyph({ className, strokeWidth }: GlyphProps) {
  return (
    <OrganGlyph className={className} strokeWidth={strokeWidth}>
      <path d="M9.5 3v3c0 1.7-1 2.8-2.2 3.8-1.7 1.5-2.8 3.4-2.8 5.6 0 3.4 2.9 5.6 6.8 5.6 5.1 0 8.2-3.4 8.2-7.4 0-3.3-2.1-5.4-4.5-5.4-2 0-3.2 1.4-3.8 3" />
    </OrganGlyph>
  );
}

export type AreaKey =
  | "oncology"
  | "urinary"
  | "cardiovascular"
  | "respiratory"
  | "digestive"
  | "nervous"
  | "immune"
  | "infectious"
  | "metabolic"
  | "musculoskeletal"
  | "hematologic"
  | "skin"
  | "eye"
  | "ear"
  | "pregnancy"
  | "genetic";

export interface DiseaseArea {
  key: AreaKey;
  glyph: Glyph;
  /** Accent hue (icon, area pill, watermark). */
  hue: string;
}

// Order matters: the first matching rule wins for a term name.
const RULES: { key: AreaKey; match: RegExp; glyph: Glyph; hue: string }[] = [
  {
    key: "oncology",
    match: /cancer|neoplasm|tumou?r/,
    glyph: Ribbon,
    hue: "#2f6aa8",
  },
  {
    key: "urinary",
    match: /urinary|kidney|renal/,
    glyph: KidneyGlyph,
    hue: "#0f7f8c",
  },
  {
    key: "cardiovascular",
    match: /cardio|heart|vascular/,
    glyph: HeartPulse,
    hue: "#1f6f9f",
  },
  {
    key: "respiratory",
    match: /respiratory|thoracic|lung/,
    glyph: LungsGlyph,
    hue: "#2b86b3",
  },
  {
    key: "digestive",
    match: /digestive|liver|hepat|gastro/,
    glyph: StomachGlyph,
    hue: "#13806f",
  },
  {
    key: "nervous",
    match: /nervous|psychiatric|mental|neuro/,
    glyph: Brain,
    hue: "#3d5fa8",
  },
  { key: "immune", match: /immune/, glyph: ShieldPlus, hue: "#0f8a84" },
  { key: "infectious", match: /infectious/, glyph: Bug, hue: "#277a6c" },
  {
    key: "metabolic",
    match: /metabolic|nutritional|endocrine/,
    glyph: FlaskConical,
    hue: "#1d7d9e",
  },
  {
    key: "musculoskeletal",
    match: /musculoskeletal|connective/,
    glyph: Bone,
    hue: "#45708c",
  },
  {
    key: "hematologic",
    match: /hematolog|haematolog|blood/,
    glyph: Droplets,
    hue: "#2c5e94",
  },
  { key: "skin", match: /integumentary|skin/, glyph: Hand, hue: "#3a87a3" },
  { key: "eye", match: /visual|eye/, glyph: Eye, hue: "#3567ad" },
  { key: "ear", match: /\bear\b/, glyph: Ear, hue: "#3567ad" },
  { key: "pregnancy", match: /pregnan|perinatal/, glyph: Baby, hue: "#4672ad" },
  {
    key: "genetic",
    match: /genetic|familial|congenital/,
    glyph: Dna,
    hue: "#0e7c9b",
  },
];

// Cross-cutting Open Targets areas that say nothing about the body system.
const GENERIC_AREA = /^(phenotype|measurement|biological process|injury)/i;

export const FALLBACK_AREA: DiseaseArea = {
  key: "genetic",
  glyph: Dna,
  hue: "#0e7c9b",
};

/** Primary body-system area of a disease, or null when none is recognised. */
export function resolveDiseaseArea(
  areas: OntologyTerm[] | undefined,
): DiseaseArea | null {
  for (const term of areas ?? []) {
    if (!GENERIC_AREA.test(term.name)) {
      const name = term.name.toLowerCase();
      const rule = RULES.find((r) => r.match.test(name));
      if (rule) return { key: rule.key, glyph: rule.glyph, hue: rule.hue };
    }
  }
  return null;
}

/** Areas worth listing in the tooltip (generic ones dropped). */
export function specificAreas(areas: OntologyTerm[] | undefined): string[] {
  return (areas ?? [])
    .map((term) => term.name)
    .filter((name) => !GENERIC_AREA.test(name));
}
