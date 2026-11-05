import { useTranslation } from "react-i18next";
import { LogOut, Settings } from "lucide-react";
import { NavLink } from "react-router";
import { I18nKey } from "#/i18n/declaration";
import { useTMText } from "#/i18n/targetmind-strings";
import { useCurrentAccount } from "#/hooks/query/use-current-account";
import { useLogout } from "#/hooks/mutation/use-logout";

interface AccountMenuProps {
  onClose: () => void;
}

// `group` so the icon follows the row's hover/focus colour, not just the text.
const ITEM_CLASS =
  "group flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-tm-ink transition-colors hover:bg-tm-teal-soft hover:text-tm-teal-deep focus-visible:bg-tm-teal-soft focus-visible:outline-none disabled:cursor-wait disabled:opacity-60";
const ICON_CLASS =
  "h-4 w-4 shrink-0 text-tm-slate transition-colors group-hover:text-tm-teal-deep";

/**
 * Account popover for the sidebar rail: who is signed in, Settings and
 * sign-out (the password change lives on Settings → Profile). Opened by clicking the avatar (never by hover) and
 * styled on the light TargetMind surface so labels keep a readable contrast.
 */
export function AccountMenu({ onClose }: AccountMenuProps) {
  const { t } = useTranslation();
  const tm = useTMText();
  const { data: account } = useCurrentAccount();
  const logout = useLogout();

  return (
    <div
      data-testid="account-menu"
      role="menu"
      className="absolute bottom-0 left-[calc(100%+10px)] z-30 w-[220px] overflow-hidden rounded-xl border border-tm-line bg-tm-card p-1 shadow-[0_18px_45px_-20px_rgba(19,34,56,0.45)]"
    >
      {account && (
        <div className="border-b border-tm-line px-3 pb-2.5 pt-2">
          {account.name && (
            <p className="truncate text-sm font-semibold text-tm-ink">
              {account.name}
            </p>
          )}
          <p
            data-testid="account-menu-email"
            className="truncate text-xs text-tm-slate"
          >
            {account.email}
          </p>
        </div>
      )}
      <NavLink
        to="/settings"
        role="menuitem"
        data-testid="account-menu-settings"
        onClick={onClose}
        className={ITEM_CLASS}
      >
        <Settings className={ICON_CLASS} />
        {t(I18nKey.SETTINGS$TITLE)}
      </NavLink>
      <button
        type="button"
        role="menuitem"
        data-testid="account-menu-logout"
        disabled={logout.isPending}
        onClick={() => logout.mutate()}
        className={ITEM_CLASS}
      >
        <LogOut className={ICON_CLASS} />
        {tm("auth.signOut")}
      </button>
    </div>
  );
}
