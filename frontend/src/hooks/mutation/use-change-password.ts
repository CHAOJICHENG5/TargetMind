import { useMutation, useQueryClient } from "@tanstack/react-query";
import AuthService from "#/api/auth-service/auth-service.api";
import { CURRENT_ACCOUNT_QUERY_KEY } from "#/hooks/query/use-current-account";

export const useChangePassword = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      currentPassword,
      newPassword,
    }: {
      currentPassword: string;
      newPassword: string;
    }) => AuthService.changePassword(currentPassword, newPassword),
    onSuccess: (account) => {
      queryClient.setQueryData(CURRENT_ACCOUNT_QUERY_KEY, account);
    },
    meta: { disableToast: true },
  });
};
