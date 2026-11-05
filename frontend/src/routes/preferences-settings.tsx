import { useTranslation } from "react-i18next";
import { useSettings } from "#/hooks/query/use-settings";
import { useSaveSettings } from "#/hooks/mutation/use-save-settings";
import { useTMText } from "#/i18n/targetmind-strings";
import { AvailableLanguages } from "#/i18n";
import {
  displayErrorToast,
  displaySuccessToast,
} from "#/utils/custom-toast-handlers";
import {
  Segmented,
  SettingsCard,
  Toggle,
} from "#/components/features/settings/tm-settings-ui";

type Language = "en" | "zh-CN";

const normalizeLanguage = (value: string | null | undefined): Language =>
  value?.toLowerCase().startsWith("zh") ? "zh-CN" : "en";

/** Preferences: personal look and behaviour only (language, sound). */
export default function PreferencesSettingsScreen() {
  const tm = useTMText();
  const { i18n } = useTranslation();
  const { data: settings } = useSettings();
  const save = useSaveSettings();

  // An account without a saved choice follows the browser language.
  const language = normalizeLanguage(settings?.language || i18n?.language);
  const sound = settings?.enable_sound_notifications ?? false;

  const persist = (
    update: { language: Language } | { enable_sound_notifications: boolean },
  ) =>
    save.mutate(update, {
      onSuccess: () => displaySuccessToast(tm("prefs.saved")),
      onError: () => displayErrorToast(tm("prefs.saveFailed")),
    });

  const changeLanguage = (next: Language) => {
    // Switch immediately; the saved choice follows the account across devices.
    i18n?.changeLanguage?.(next);
    persist({ language: next });
  };

  return (
    <div className="flex flex-col gap-6 pb-10">
      <p className="max-w-[640px] text-sm text-tm-slate">
        {tm("prefs.subtitle")}
      </p>

      <SettingsCard title={tm("prefs.language")}>
        <div className="flex flex-col gap-3">
          <p className="text-[13px] text-tm-slate">
            {tm("prefs.languageHint")}
          </p>
          <Segmented<Language>
            label={tm("prefs.language")}
            options={[...AvailableLanguages]
              .reverse()
              .map(({ label, value }) => ({
                label,
                value: value as Language,
              }))}
            value={language}
            onChange={changeLanguage}
            disabled={save.isPending}
          />
        </div>
      </SettingsCard>

      <SettingsCard title={tm("prefs.sound")}>
        <div className="flex items-center justify-between gap-4">
          <p className="text-[13px] text-tm-slate">{tm("prefs.soundHint")}</p>
          <Toggle
            label={tm("prefs.sound")}
            checked={sound}
            onChange={(checked) =>
              persist({ enable_sound_notifications: checked })
            }
            disabled={save.isPending}
          />
        </div>
      </SettingsCard>
    </div>
  );
}
