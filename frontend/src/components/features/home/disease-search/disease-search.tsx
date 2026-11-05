import React from "react";
import { useNavigate } from "react-router";
import { Search, AlertCircle, Loader2, Crosshair } from "lucide-react";
import { useOpenTargetsDiseaseSearch } from "#/hooks/query/use-opentargets-disease-search";
import { useCreateConversation } from "#/hooks/mutation/use-create-conversation";
import { useTMText } from "#/i18n/targetmind-strings";
import {
  DiseaseContext,
  buildDiseaseInstructions,
  saveDiseaseContext,
} from "#/utils/disease-context";
import { DiseaseResultRow } from "./disease-result-card";

export function DiseaseSearch() {
  const tm = useTMText();
  const navigate = useNavigate();
  const [query, setQuery] = React.useState("");
  const [pendingId, setPendingId] = React.useState<string | null>(null);

  const {
    data: hits,
    isFetching,
    isError,
  } = useOpenTargetsDiseaseSearch(query);
  const { mutate: createConversation } = useCreateConversation();

  const handleSelect = (disease: DiseaseContext) => {
    if (pendingId) return;
    setPendingId(disease.ontologyId);
    createConversation(
      { conversationInstructions: buildDiseaseInstructions(disease) },
      {
        onSuccess: (data) => {
          saveDiseaseContext(data.conversation_id, disease);
          navigate(`/conversations/${data.conversation_id}`);
        },
        onError: () => setPendingId(null),
      },
    );
  };

  const trimmed = query.trim();
  const showResults = trimmed.length >= 2;
  const hasHits = !!hits && hits.length > 0;

  let dropdownBody: React.ReactNode;
  if (isError) {
    dropdownBody = (
      <div className="flex items-center justify-center gap-2 py-6 text-sm text-tm-slate">
        <AlertCircle className="h-4 w-4 text-danger" />
        {tm("home.error")}
      </div>
    );
  } else if (hasHits) {
    dropdownBody = (
      <ul className="max-h-[52vh] overflow-y-auto">
        {hits.map((hit) => (
          <DiseaseResultRow
            key={hit.id}
            hit={hit}
            pending={pendingId === hit.id}
            onSelect={handleSelect}
          />
        ))}
      </ul>
    );
  } else if (isFetching) {
    dropdownBody = (
      <div className="flex items-center justify-center gap-2 py-6 text-sm text-tm-slate-soft">
        <Loader2 className="h-4 w-4 animate-spin text-tm-teal" />
        {tm("home.searching")}
      </div>
    );
  } else {
    dropdownBody = (
      <div className="py-6 text-center text-sm text-tm-slate-soft">
        {tm("home.noResults")}
      </div>
    );
  }

  return (
    <div className="relative mx-auto flex w-full max-w-[860px] flex-col items-center px-6">
      {/* Soft veil behind the content column only, so type stays readable
          over the photograph without touching the background itself. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-x-24 -inset-y-20 -z-0 bg-[radial-gradient(ellipse_at_center,rgba(247,250,252,0.92)_0%,rgba(247,250,252,0.7)_45%,rgba(247,250,252,0)_72%)]"
      />

      {/* Hero */}
      <div className="tm-fade-up relative flex flex-col items-center">
        <div className="flex items-center gap-2 text-center font-mono text-xs font-medium tracking-[0.06em] text-tm-teal-deep sm:text-[13px]">
          <Crosshair className="h-3.5 w-3.5 shrink-0" />
          {tm("home.tagline")}
        </div>
        {/* eslint-disable i18next/no-literal-string -- product name */}
        <h1 className="mt-5 font-display text-6xl font-bold tracking-[-0.035em] text-tm-ink sm:text-[84px] sm:leading-[0.95]">
          Target<span className="text-tm-teal">Mind</span>
        </h1>
        {/* eslint-enable i18next/no-literal-string */}
        <p className="mt-5 max-w-xl text-center text-xl italic text-tm-slate sm:text-[22px]">
          {tm("home.subtitle")}
        </p>
      </div>

      {/* Search + dropdown */}
      <div
        className="tm-fade-up relative z-20 mt-12 w-full"
        style={{ animationDelay: "90ms" }}
      >
        <label className="flex cursor-text items-center gap-4 rounded-[28px] border border-white/70 bg-white/45 px-6 py-6 sm:gap-5 sm:px-8 sm:py-7 shadow-[0_24px_60px_-36px_rgba(19,34,56,0.45)] backdrop-blur-md transition-colors focus-within:border-tm-teal/60">
          <Search
            className="h-7 w-7 shrink-0 text-tm-navy"
            strokeWidth={1.75}
          />
          <input
            // The disease search box is the only action on the landing page,
            // so focusing it on load is the expected behaviour here.
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={tm("home.searchPlaceholder")}
            aria-label={tm("home.searchPlaceholder")}
            className="w-full bg-transparent text-lg text-tm-ink sm:text-2xl outline-none placeholder:text-tm-slate"
          />
          {isFetching && showResults && (
            <Loader2 className="h-6 w-6 shrink-0 animate-spin text-tm-teal" />
          )}
        </label>

        {/* Results dropdown */}
        {showResults && (
          <div className="absolute left-0 right-0 top-[calc(100%+10px)] z-20 overflow-hidden rounded-[22px] border border-tm-line bg-white shadow-[0_24px_60px_-30px_rgba(19,34,56,0.45)]">
            {dropdownBody}
          </div>
        )}
      </div>
    </div>
  );
}
