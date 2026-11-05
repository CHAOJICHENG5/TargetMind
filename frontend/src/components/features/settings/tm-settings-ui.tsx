import React from "react";
import { cn } from "#/utils/utils";

/** Building blocks for the personal settings pages (profile, preferences). */

export const TEXT_INPUT =
  "h-10 w-full rounded-lg border border-tm-line bg-white px-3 text-sm text-tm-ink outline-none transition-colors placeholder:text-tm-slate-soft focus:border-tm-teal focus:ring-2 focus:ring-tm-teal/15 disabled:cursor-not-allowed disabled:bg-tm-paper disabled:text-tm-slate";

export function SettingsCard({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <section className="max-w-[640px] rounded-xl border border-tm-line bg-tm-card shadow-[0_1px_2px_rgba(19,34,56,0.04)]">
      <header className="border-b border-tm-line px-5 py-4">
        <h3 className="text-[15px] font-semibold text-tm-ink">{title}</h3>
        {description && (
          <p className="mt-1 text-[13px] leading-relaxed text-tm-slate">
            {description}
          </p>
        )}
      </header>
      <div className="flex flex-col gap-5 px-5 py-5">{children}</div>
      {footer && (
        <footer className="flex items-center justify-end gap-3 rounded-b-xl border-t border-tm-line bg-tm-paper/60 px-5 py-3">
          {footer}
        </footer>
      )}
    </section>
  );
}

export function SettingsField({
  label,
  htmlFor,
  optional,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  optional?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={htmlFor}
        className="flex items-baseline gap-2 text-[13px] font-medium text-tm-ink"
      >
        {label}
        {optional && (
          <span className="text-xs font-normal text-tm-slate-soft">
            {optional}
          </span>
        )}
      </label>
      {children}
      {hint && <p className="text-xs text-tm-slate-soft">{hint}</p>}
    </div>
  );
}

/** Single-choice chips; clicking the active chip clears the choice. */
export function ChoiceChips<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T | null;
  onChange: (value: T | null) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(active ? null : option.value)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-[13px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tm-teal/30",
              active
                ? "border-tm-teal bg-tm-teal-soft font-medium text-tm-teal-deep"
                : "border-tm-line bg-white text-tm-slate hover:border-tm-teal/50 hover:text-tm-ink",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/** Segmented control for a small, always-set choice. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  disabled,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex w-fit rounded-lg border border-tm-line bg-tm-paper p-1"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => !active && onChange(option.value)}
            className={cn(
              "min-w-24 rounded-md px-4 py-1.5 text-[13px] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tm-teal/30 disabled:cursor-wait",
              active
                ? "bg-white font-medium text-tm-ink shadow-sm ring-1 ring-tm-line"
                : "text-tm-slate hover:text-tm-ink",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tm-teal/30 disabled:cursor-wait disabled:opacity-70",
        checked ? "bg-tm-teal" : "bg-tm-line",
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-[22px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
