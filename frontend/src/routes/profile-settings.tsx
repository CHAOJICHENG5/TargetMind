import React from "react";
import { Link } from "react-router";
import { KeyRound, Lock, ShieldCheck } from "lucide-react";
import {
  ACCOUNT_ROLES,
  type AccountInfo,
  type AccountRole,
  type ProfileUpdate,
} from "#/api/auth-service/auth.types";
import { useCurrentAccount } from "#/hooks/query/use-current-account";
import { useUpdateProfile } from "#/hooks/mutation/use-update-profile";
import { useTMText } from "#/i18n/targetmind-strings";
import {
  displayErrorToast,
  displaySuccessToast,
} from "#/utils/custom-toast-handlers";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import {
  ChoiceChips,
  SettingsCard,
  SettingsField,
  TEXT_INPUT,
} from "#/components/features/settings/tm-settings-ui";

type Draft = {
  name: string;
  organization: string;
  role: AccountRole | null;
  research_field: string;
};

const toDraft = (account: AccountInfo): Draft => ({
  name: account.name ?? "",
  organization: account.organization ?? "",
  role: (ACCOUNT_ROLES as readonly string[]).includes(account.role ?? "")
    ? (account.role as AccountRole)
    : null,
  research_field: account.research_field ?? "",
});

const clean = (value: string) => value.trim().replace(/\s+/g, " ") || null;

const toUpdate = (draft: Draft): ProfileUpdate => ({
  name: clean(draft.name),
  organization: clean(draft.organization),
  role: draft.role,
  research_field: clean(draft.research_field),
});

/** Profile: the details from the access application (website /apply). */
export default function ProfileSettingsScreen() {
  const tm = useTMText();
  const { data: account, isLoading } = useCurrentAccount();
  const updateProfile = useUpdateProfile();
  const [draft, setDraft] = React.useState<Draft | null>(null);

  React.useEffect(() => {
    if (account) setDraft(toDraft(account));
  }, [account]);

  if (isLoading || !account || !draft) {
    return (
      <div className="flex justify-center py-10">
        <LoadingSpinner size="small" />
      </div>
    );
  }

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));

  const isDirty =
    JSON.stringify(toUpdate(draft)) !==
    JSON.stringify(toUpdate(toDraft(account)));

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isDirty) return;
    updateProfile.mutate(toUpdate(draft), {
      onSuccess: () => displaySuccessToast(tm("profile.saved")),
      onError: () => displayErrorToast(tm("profile.saveFailed")),
    });
  };

  const roleOptions = ACCOUNT_ROLES.map((role) => ({
    value: role,
    label: tm(`role.${role}`),
  }));

  return (
    <div className="flex flex-col gap-6 pb-10">
      <p className="max-w-[640px] text-sm text-tm-slate">
        {tm("profile.subtitle")}
      </p>

      <form onSubmit={onSubmit} data-testid="profile-form">
        <SettingsCard
          title={tm("profile.account")}
          footer={
            <button
              type="submit"
              disabled={!isDirty || updateProfile.isPending}
              className="h-9 rounded-lg bg-tm-teal px-4 text-sm font-semibold text-white transition-colors hover:bg-tm-teal-deep disabled:cursor-not-allowed disabled:opacity-50"
            >
              {updateProfile.isPending
                ? tm("profile.saving")
                : tm("profile.save")}
            </button>
          }
        >
          <SettingsField
            label={tm("profile.email")}
            htmlFor="profile-email"
            hint={tm("profile.emailHint")}
          >
            <div className="relative">
              <input
                id="profile-email"
                value={account.email}
                readOnly
                disabled
                className={`${TEXT_INPUT} pr-9`}
              />
              <Lock className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-tm-slate-soft" />
            </div>
            {account.is_admin && (
              <span className="inline-flex w-fit items-center gap-1 rounded-full bg-tm-teal-soft px-2 py-0.5 text-[11px] font-medium text-tm-teal-deep">
                <ShieldCheck className="h-3 w-3" />
                {tm("profile.admin")}
              </span>
            )}
          </SettingsField>

          <div className="grid gap-5 sm:grid-cols-2">
            <SettingsField label={tm("profile.name")} htmlFor="profile-name">
              <input
                id="profile-name"
                value={draft.name}
                maxLength={100}
                autoComplete="name"
                onChange={(e) => set("name", e.target.value)}
                className={TEXT_INPUT}
              />
            </SettingsField>
            <SettingsField label={tm("profile.org")} htmlFor="profile-org">
              <input
                id="profile-org"
                value={draft.organization}
                maxLength={200}
                autoComplete="organization"
                placeholder={tm("profile.orgPlaceholder")}
                onChange={(e) => set("organization", e.target.value)}
                className={TEXT_INPUT}
              />
            </SettingsField>
          </div>

          <SettingsField
            label={tm("profile.role")}
            optional={tm("profile.optional")}
          >
            <ChoiceChips
              label={tm("profile.role")}
              options={roleOptions}
              value={draft.role}
              onChange={(role) => set("role", role)}
            />
          </SettingsField>

          <SettingsField
            label={tm("profile.field")}
            htmlFor="profile-field"
            optional={tm("profile.optional")}
          >
            <input
              id="profile-field"
              value={draft.research_field}
              maxLength={200}
              placeholder={tm("profile.fieldPlaceholder")}
              onChange={(e) => set("research_field", e.target.value)}
              className={TEXT_INPUT}
            />
          </SettingsField>
        </SettingsCard>
      </form>

      <SettingsCard title={tm("profile.security")}>
        <div className="flex items-center justify-between gap-4">
          <p className="text-[13px] text-tm-slate">
            {tm("profile.securityHint")}
          </p>
          <Link
            to="/change-password?returnTo=/settings"
            className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-tm-line bg-white px-3 py-2 text-sm font-medium text-tm-ink transition-colors hover:border-tm-teal hover:text-tm-teal"
          >
            <KeyRound className="h-4 w-4" />
            {tm("auth.changePassword")}
          </Link>
        </div>
      </SettingsCard>
    </div>
  );
}
