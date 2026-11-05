import { ArrowRight, Loader2 } from "lucide-react";
import { DiseaseHit } from "#/api/opentargets-service/opentargets.api";
import { useDiseaseXref } from "#/hooks/query/use-disease-xref";
import { DiseaseContext } from "#/utils/disease-context";
import { cn } from "#/utils/utils";

interface DiseaseResultRowProps {
  hit: DiseaseHit;
  pending: boolean;
  onSelect: (disease: DiseaseContext) => void;
}

/**
 * A single disease row in the search dropdown: name + accession chip on one
 * line, description beneath. Matches the reference typeahead panel.
 */
export function DiseaseResultRow({
  hit,
  pending,
  onSelect,
}: DiseaseResultRowProps) {
  const { data: xref } = useDiseaseXref(hit.id);

  const disease: DiseaseContext = {
    name: hit.name,
    ontologyId: hit.id,
    mondoId: xref?.mondoId ?? null,
    description: hit.description ?? xref?.description ?? null,
  };
  // Prefer a MONDO id for the chip when available (references show MONDO).
  const chipId =
    disease.mondoId && disease.mondoId !== disease.ontologyId
      ? disease.mondoId
      : disease.ontologyId;

  return (
    <li>
      <button
        type="button"
        disabled={pending}
        onClick={() => onSelect(disease)}
        className={cn(
          "group relative flex w-full items-center gap-4 border-b border-tm-line/70 px-6 py-3.5 text-left transition-colors last:border-b-0",
          "before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-r before:bg-tm-teal before:opacity-0 before:transition-opacity",
          "hover:bg-tm-teal-soft/50 hover:before:opacity-100 focus-visible:bg-tm-teal-soft/50 focus-visible:outline-none focus-visible:before:opacity-100",
          pending && "opacity-60",
        )}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <span className="truncate text-[15px] font-semibold text-tm-ink group-hover:text-tm-teal-deep">
              {hit.name}
            </span>
            <span className="shrink-0 rounded bg-tm-chip px-1.5 py-0.5 font-mono text-[10px] font-medium text-tm-chip-text">
              {chipId}
            </span>
          </div>
          {disease.description && (
            <p className="mt-1 line-clamp-1 text-[13px] leading-relaxed text-tm-slate">
              {disease.description}
            </p>
          )}
        </div>
        {pending ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-tm-teal" />
        ) : (
          <ArrowRight className="h-4 w-4 shrink-0 -translate-x-1 text-tm-teal opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100" />
        )}
      </button>
    </li>
  );
}
