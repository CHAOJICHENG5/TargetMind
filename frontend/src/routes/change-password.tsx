import React from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import {
  AuthError,
  AuthField,
  AuthShell,
  AuthSubmit,
  errorDetail,
  safeReturnTo,
} from "#/components/features/auth/auth-shell";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import { useChangePassword } from "#/hooks/mutation/use-change-password";
import { useCurrentAccount } from "#/hooks/query/use-current-account";
import { useTMText } from "#/i18n/targetmind-strings";

export default function ChangePasswordScreen() {
  const tm = useTMText();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = safeReturnTo(searchParams.get("returnTo"));
  const { data: account, isLoading } = useCurrentAccount();
  const changePassword = useChangePassword();
  const [error, setError] = React.useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-tm-paper">
        <LoadingSpinner size="large" />
      </div>
    );
  }
  if (!account) return <Navigate to="/login" replace />;

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const newPassword = String(form.get("new-password") ?? "");
    if (newPassword !== String(form.get("confirm-password") ?? "")) {
      setError(tm("auth.mismatch"));
      return;
    }
    setError(null);
    changePassword.mutate(
      {
        currentPassword: String(form.get("current-password") ?? ""),
        newPassword,
      },
      {
        onSuccess: () => navigate(returnTo, { replace: true }),
        onError: (e) => setError(errorDetail(e, tm("auth.genericError"))),
      },
    );
  };

  return (
    <AuthShell
      title={tm("auth.changeTitle")}
      subtitle={
        account.must_change_password
          ? tm("auth.changeSubtitle")
          : tm("auth.changeSubtitleVoluntary")
      }
    >
      <form
        data-testid="change-password-form"
        onSubmit={onSubmit}
        className="flex flex-col gap-4"
      >
        <input
          type="email"
          name="username"
          autoComplete="username"
          value={account.email}
          readOnly
          hidden
        />
        <AuthField
          id="current-password"
          name="current-password"
          type="password"
          label={tm("auth.currentPassword")}
          autoComplete="current-password"
          required
          autoFocus
        />
        <AuthField
          id="new-password"
          name="new-password"
          type="password"
          label={tm("auth.newPassword")}
          hint={tm("auth.passwordRule")}
          autoComplete="new-password"
          minLength={10}
          required
        />
        <AuthField
          id="confirm-password"
          name="confirm-password"
          type="password"
          label={tm("auth.confirmPassword")}
          autoComplete="new-password"
          minLength={10}
          required
        />
        <AuthError message={error} />
        <AuthSubmit disabled={changePassword.isPending}>
          {changePassword.isPending ? tm("auth.saving") : tm("auth.save")}
        </AuthSubmit>
      </form>
    </AuthShell>
  );
}
