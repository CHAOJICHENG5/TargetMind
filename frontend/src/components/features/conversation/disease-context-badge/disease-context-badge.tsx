import React from "react";
import { Check, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useDiseaseContext } from "#/hooks/use-disease-context";
import { useDiseaseXref } from "#/hooks/query/use-disease-xref";
import { useDiseaseProfile } from "#/hooks/query/use-disease-profile";
import { useTMText } from "#/i18n/targetmind-strings";
import { ontologyLabel } from "#/utils/disease-context";
import { cn } from "#/utils/utils";
import { copyToClipboard } from "#/utils/copy-to-clipboard";
import {
  FALLBACK_AREA,
  resolveDiseaseArea,
  specificAreas,
} from "./disease-areas";

function CopyableId({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = React.useState(false);
  const copy = async () => {
    try {
      await copyToClipboard(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // clipboard unavailable
    }
  };
  return (
    <button
      type="button"
      onClick={copy}
      title={`${label}: ${value}`}
      aria-label={`${label}: ${value}`}
      className="group hidden h-[22px] shrink-0 items-center gap-1.5 sm:inline-flex rounded-md border border-tm-line bg-tm-card px-2 font-mono text-[11px] text-tm-slate transition-colors hover:border-tm-teal/40 hover:bg-tm-teal-soft hover:text-tm-teal-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tm-teal/30"
    >
      {value}
      {copied ? (
        <Check className="h-3 w-3 text-tm-teal" />
      ) : (
        <Copy className="h-3 w-3 opacity-40 transition-opacity group-hover:opacity-90" />
      )}
    </button>
  );
}

/**
 * Target-disease card at the top of the workspace. Name, body-system pill and
 * ontology ids on the first line, the OpenTargets description on the second;
 * the icon, pill and a faint organ watermark take the hue of the disease's
 * therapeutic area, and the associated-target count shows on all but the
 * narrowest cards (it outranks the pill when space is short). All of
 * that comes from OpenTargets and is decorative: without it the card falls
 * back to the plain teal DNA form.
 */
export function DiseaseContextBadge({ className }: { className?: string }) {
  const tm = useTMText();
  const { i18n } = useTranslation();
  const disease = useDiseaseContext();
  // Older workspaces stored no description — fetch it from OpenTargets.
  const { data: xref, isLoading: isLoadingXref } = useDiseaseXref(
    disease?.ontologyId ?? "",
    !!disease?.ontologyId && !disease?.description,
  );
  const { data: profile } = useDiseaseProfile(disease?.ontologyId);
  if (!disease) return null;

  const showMondo = !!disease.mondoId && disease.mondoId !== disease.ontologyId;
  const description = disease.description || xref?.description || null;
  const area = resolveDiseaseArea(profile?.therapeuticAreas);
  const { glyph: Glyph, hue } = area ?? FALLBACK_AREA;
  const areaHint = [
    specificAreas(profile?.therapeuticAreas).join(" · "),
    profile?.parents.length
      ? `${tm("badge.isA")}: ${profile.parents.map((p) => p.name).join(", ")}`
      : "",
  ]
    .filter(Boolean)
    .join("\n");
  const targets = profile?.associatedTargets ?? null;
  const tint = (pct: number) =>
    `color-mix(in srgb, ${hue} ${pct}%, transparent)`;

  return (
    <div
      data-testid="disease-context-badge"
      data-area={area?.key ?? "none"}
      aria-label={tm("badge.targetDisease")}
      className={cn(
        "@container flex min-w-0 flex-1 items-center gap-3.5",
        className,
      )}
    >
      {/* Borderless card: a faint organ watermark on the right, inside the
          box and feathered so the card's overflow clip never shows. */}
      {area && (
        <span
          aria-hidden
          className="pointer-events-none absolute right-10 top-1/2 -translate-y-1/2 opacity-[0.09]"
          style={{
            color: hue,
            maskImage: "radial-gradient(closest-side, black 55%, transparent)",
            WebkitMaskImage:
              "radial-gradient(closest-side, black 55%, transparent)",
          }}
        >
          <Glyph className="h-16 w-16" strokeWidth={1.25} />
        </span>
      )}

      <span
        data-testid="disease-area-icon"
        className="relative grid size-10 shrink-0 place-items-center rounded-lg ring-1 transition-colors"
        style={{
          color: hue,
          backgroundColor: `color-mix(in srgb, ${hue} 11%, white)`,
          ["--tw-ring-color" as string]: tint(18),
        }}
      >
        <Glyph className="h-5 w-5" strokeWidth={1.75} />
      </span>

      <div className="relative flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex min-w-0 items-center gap-2">
          <h2 className="min-w-0 truncate text-base font-semibold leading-6 text-tm-ink first-letter:uppercase">
            {disease.name}
          </h2>
          {area && (
            <span
              data-testid="disease-area"
              title={areaHint || undefined}
              className="hidden h-[22px] shrink-0 items-center gap-1.5 rounded-full px-2 text-[11px] font-medium @xl:inline-flex"
              style={{ color: hue, backgroundColor: tint(9) }}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: hue }}
              />
              {tm(`area.${area.key}`)}
            </span>
          )}
          {disease.ontologyId && (
            <CopyableId
              label={ontologyLabel(disease.ontologyId)}
              value={disease.ontologyId}
            />
          )}
          {showMondo && (
            <CopyableId label="MONDO" value={disease.mondoId as string} />
          )}
        </div>
        {description && (
          <p
            data-testid="disease-description"
            title={description}
            className="truncate text-[13px] leading-5 text-tm-slate"
          >
            {description}
          </p>
        )}
        {!description && isLoadingXref && (
          <span className="h-3 w-2/3 animate-pulse rounded bg-tm-line/70" />
        )}
      </div>

      {targets !== null && (
        <div
          data-testid="disease-targets"
          title={tm("badge.targetsHint")}
          className="relative hidden shrink-0 flex-col items-end border-l border-tm-line/80 pl-4 pr-1 leading-tight @sm:flex"
        >
          <span className="text-[15px] font-semibold tabular-nums text-tm-ink">
            {targets.toLocaleString(i18n?.language || "en")}
          </span>
          <span className="text-[11px] text-tm-slate-soft">
            {tm("badge.associatedTargets")}
          </span>
        </div>
      )}
    </div>
  );
}
