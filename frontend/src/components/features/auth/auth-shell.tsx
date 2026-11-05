import React from "react";
import TargetMindLogo from "#/assets/branding/targetmind-logo.svg?react";
import geneBackground from "#/assets/images/gene-background.webp";

interface AuthShellProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

/** Full-page frame for the sign-in / password screens (no sidebar). */
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: AuthShellProps) {
  return (
    <main
      className="tm-hero relative flex min-h-[100dvh] w-full items-center justify-center bg-tm-paper bg-cover bg-center bg-no-repeat px-4 py-12"
      style={{ backgroundImage: `url("${geneBackground}")` }}
    >
      <div className="tm-fade-up w-full max-w-[400px] rounded-2xl border border-tm-line bg-tm-card/95 p-8 shadow-[0_24px_60px_-28px_rgba(19,34,56,0.45)] backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-xl bg-white shadow-sm ring-1 ring-tm-line">
            <TargetMindLogo className="size-8" />
          </span>
          {/* eslint-disable i18next/no-literal-string -- product name */}
          <span className="font-display text-2xl font-bold tracking-[-0.03em] text-tm-ink">
            Target<span className="text-tm-teal">Mind</span>
          </span>
          {/* eslint-enable i18next/no-literal-string */}
        </div>
        <h1 className="mt-7 text-lg font-semibold text-tm-ink">{title}</h1>
        <p className="mt-1 text-sm leading-relaxed text-tm-slate">{subtitle}</p>
        <div className="mt-6">{children}</div>
        {footer && (
          <p className="mt-6 border-t border-tm-line pt-4 text-xs leading-relaxed text-tm-slate-soft">
            {footer}
          </p>
        )}
      </div>
    </main>
  );
}

interface AuthFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
}

// Thin labelled wrapper around <input>; forwards every native input attribute.
/* eslint-disable react/jsx-props-no-spreading */
export function AuthField({ label, hint, id, ...input }: AuthFieldProps) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-tm-ink">{label}</span>
      <input
        id={id}
        className="h-11 rounded-lg border border-tm-line bg-white px-3 text-sm text-tm-ink outline-none transition-colors placeholder:text-tm-slate-soft focus:border-tm-teal focus:ring-2 focus:ring-tm-teal/15"
        {...input}
      />
      {hint && <span className="text-xs text-tm-slate-soft">{hint}</span>}
    </label>
  );
}
/* eslint-enable react/jsx-props-no-spreading */

export function AuthError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      data-testid="auth-error"
      className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
    >
      {message}
    </p>
  );
}

export function AuthSubmit({
  children,
  disabled,
}: {
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="h-11 w-full cursor-pointer rounded-lg bg-tm-teal text-sm font-semibold text-white transition-colors hover:bg-tm-teal-deep disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}

/** Server error detail (FastAPI ``{detail}``) or a fallback message. */
export function errorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

/** Only allow same-site relative return paths. */
export function safeReturnTo(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//")
    ? value
    : "/";
}
