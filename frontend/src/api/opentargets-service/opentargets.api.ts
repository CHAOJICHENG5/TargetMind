/**
 * OpenTargets Platform GraphQL client (browser-direct, CORS-enabled).
 * Used by the TargetMind home page to search diseases and resolve ontology IDs.
 */
const OPENTARGETS_GQL = "https://api.platform.opentargets.org/api/v4/graphql";

/** Abort a request that hangs — the home page must not spin forever. */
const REQUEST_TIMEOUT_MS = 12_000;

export interface DiseaseHit {
  id: string; // EFO id, e.g. "EFO_1001517"
  name: string;
  description?: string | null;
}

export interface DiseaseXref {
  mondoId: string | null;
  description: string | null;
}

export interface OntologyTerm {
  id: string;
  name: string;
}

/** Context for the workspace disease card (therapeutic areas, lineage, size). */
export interface DiseaseProfile {
  therapeuticAreas: OntologyTerm[];
  parents: OntologyTerm[];
  /** Targets with any association evidence for the disease. */
  associatedTargets: number | null;
}

interface DiseaseProfileResponse {
  data?: {
    disease?: {
      therapeuticAreas?: OntologyTerm[] | null;
      parents?: OntologyTerm[] | null;
      associatedTargets?: { count?: number | null } | null;
    } | null;
  };
}

interface SearchResponse {
  data?: {
    search?: {
      hits?: Array<{
        id: string;
        name: string;
        description?: string | null;
        entity: string;
      }>;
    };
  };
}

interface DiseaseXrefResponse {
  data?: {
    disease?: {
      id: string;
      name: string;
      description?: string | null;
      dbXRefs?: string[] | null;
    };
  };
}

const SEARCH_QUERY = `
  query TargetMindDiseaseSearch($q: String!) {
    search(queryString: $q, entityNames: ["disease"], page: { index: 0, size: 8 }) {
      hits { id name description entity }
    }
  }
`;

const PROFILE_QUERY = `
  query TargetMindDiseaseProfile($efoId: String!) {
    disease(efoId: $efoId) {
      therapeuticAreas { id name }
      parents { id name }
      associatedTargets(page: { index: 0, size: 1 }) { count }
    }
  }
`;

const XREF_QUERY = `
  query TargetMindDiseaseXref($efoId: String!) {
    disease(efoId: $efoId) { id name description dbXRefs }
  }
`;

/**
 * Combine the caller's abort signal with a timeout, so a stalled OpenTargets
 * request surfaces as an error state instead of an endless spinner.
 */
function withTimeout(signal?: AbortSignal): {
  signal: AbortSignal;
  clear: () => void;
} {
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(new Error("OpenTargets request timed out")),
    REQUEST_TIMEOUT_MS,
  );

  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  else signal?.addEventListener("abort", abort);

  return {
    signal: controller.signal,
    clear: () => {
      clearTimeout(timeoutId);
      signal?.removeEventListener("abort", abort);
    },
  };
}

export class OpenTargetsService {
  private static async gql<T>(
    query: string,
    variables: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<T> {
    const timeout = withTimeout(signal);
    try {
      const res = await fetch(OPENTARGETS_GQL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, variables }),
        signal: timeout.signal,
      });
      if (!res.ok) {
        throw new Error(`OpenTargets request failed (${res.status})`);
      }
      return (await res.json()) as T;
    } finally {
      timeout.clear();
    }
  }

  /** Typeahead search over the disease entity. */
  static async searchDiseases(
    queryString: string,
    signal?: AbortSignal,
  ): Promise<DiseaseHit[]> {
    const trimmed = queryString.trim();
    if (!trimmed) return [];
    const json = await OpenTargetsService.gql<SearchResponse>(
      SEARCH_QUERY,
      { q: trimmed },
      signal,
    );
    const hits = json.data?.search?.hits ?? [];
    return hits
      .filter((h) => h.entity === "disease")
      .map((h) => ({ id: h.id, name: h.name, description: h.description }));
  }

  /** Resolve the MONDO cross-reference (and richer description) for an EFO id. */
  static async resolveMondoId(
    efoId: string,
    signal?: AbortSignal,
  ): Promise<DiseaseXref> {
    const json = await OpenTargetsService.gql<DiseaseXrefResponse>(
      XREF_QUERY,
      { efoId },
      signal,
    );
    const disease = json.data?.disease;
    const xrefs = disease?.dbXRefs ?? [];
    // dbXRefs entries look like "MONDO:0000494"; normalise to "MONDO_0000494".
    const mondoRaw = xrefs.find((x) => /^MONDO[:_]/i.test(x));
    const mondoId = mondoRaw ? mondoRaw.replace(":", "_").toUpperCase() : null;
    return { mondoId, description: disease?.description ?? null };
  }

  /** Therapeutic areas, parent terms and associated-target count of a disease. */
  static async getDiseaseProfile(
    efoId: string,
    signal?: AbortSignal,
  ): Promise<DiseaseProfile | null> {
    const json = await OpenTargetsService.gql<DiseaseProfileResponse>(
      PROFILE_QUERY,
      { efoId },
      signal,
    );
    const disease = json.data?.disease;
    if (!disease) return null;
    return {
      therapeuticAreas: disease.therapeuticAreas ?? [],
      parents: disease.parents ?? [],
      associatedTargets: disease.associatedTargets?.count ?? null,
    };
  }
}

export default OpenTargetsService;
