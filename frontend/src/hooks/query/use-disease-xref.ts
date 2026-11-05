import { useQuery } from "@tanstack/react-query";
import OpenTargetsService from "#/api/opentargets-service/opentargets.api";

/** Resolve the MONDO id + description for an EFO id, cached aggressively. */
export function useDiseaseXref(efoId: string, enabled = true) {
  return useQuery({
    queryKey: ["opentargets", "disease-xref", efoId],
    queryFn: ({ signal }) => OpenTargetsService.resolveMondoId(efoId, signal),
    enabled: enabled && !!efoId,
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });
}
