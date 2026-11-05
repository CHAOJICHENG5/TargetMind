import { useQuery } from "@tanstack/react-query";
import React from "react";
import OpenTargetsService, {
  DiseaseHit,
} from "#/api/opentargets-service/opentargets.api";

/** Debounce a rapidly-changing value. */
function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export function useOpenTargetsDiseaseSearch(rawQuery: string) {
  const query = useDebounced(rawQuery.trim(), 300);
  return useQuery<DiseaseHit[]>({
    queryKey: ["opentargets", "disease-search", query],
    queryFn: ({ signal }) => OpenTargetsService.searchDiseases(query, signal),
    enabled: query.length >= 2,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}
