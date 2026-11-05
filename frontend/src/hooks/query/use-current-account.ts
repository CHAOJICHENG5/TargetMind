import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import AuthService from "#/api/auth-service/auth-service.api";
import { AccountInfo } from "#/api/auth-service/auth.types";

export const CURRENT_ACCOUNT_QUERY_KEY = ["auth", "me"] as const;

/** Fetch the logged-in account; resolves to null when there is no session. */
export const fetchCurrentAccount = async (): Promise<AccountInfo | null> => {
  try {
    return await AuthService.me();
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      return null;
    }
    throw error;
  }
};

export const useCurrentAccount = () =>
  useQuery({
    queryKey: CURRENT_ACCOUNT_QUERY_KEY,
    queryFn: fetchCurrentAccount,
    staleTime: 1000 * 60 * 5,
    retry: false,
    meta: { disableToast: true },
  });
