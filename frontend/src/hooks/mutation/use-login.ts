import { useMutation, useQueryClient } from "@tanstack/react-query";
import AuthService from "#/api/auth-service/auth-service.api";
import { CURRENT_ACCOUNT_QUERY_KEY } from "#/hooks/query/use-current-account";

export const useLogin = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      AuthService.login(email, password),
    onSuccess: (account) => {
      queryClient.setQueryData(CURRENT_ACCOUNT_QUERY_KEY, account);
    },
    meta: { disableToast: true },
  });
};
