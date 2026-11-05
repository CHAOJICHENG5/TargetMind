import { useQuery } from "@tanstack/react-query";
import OpenTargetsService from "#/api/opentargets-service/opentargets.api";

/**
 * Therapeutic areas, lineage and associated-target count for the workspace
 * disease card. Decorative: failures leave the card in its plain form.
 */
export function useDiseaseProfile(efoId: string | null | undefined) {
  return useQuery({
    queryKey: ["opentargets", "disease-profile", efoId],
    queryFn: ({ signal }) =>
      OpenTargetsService.getDiseaseProfile(efoId!, signal),
    enabled: !!efoId,
    staleTime: 24 * 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    retry: 1,
    meta: { disableToast: true },
  });
}
