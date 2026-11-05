import { useMutation, useQueryClient } from "@tanstack/react-query";
import AuthService from "#/api/auth-service/auth-service.api";
import { ProfileUpdate } from "#/api/auth-service/auth.types";
import { CURRENT_ACCOUNT_QUERY_KEY } from "#/hooks/query/use-current-account";

/** Save the logged-in account's profile and refresh the cached account. */
export const useUpdateProfile = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (profile: ProfileUpdate) => AuthService.updateProfile(profile),
    onSuccess: (account) =>
      queryClient.setQueryData(CURRENT_ACCOUNT_QUERY_KEY, account),
    meta: { disableToast: true },
  });
};
