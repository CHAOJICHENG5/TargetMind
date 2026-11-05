import { NavLink } from "react-router";
import TargetMindLogo from "#/assets/branding/targetmind-logo.svg?react";
import { StyledTooltip } from "#/components/shared/buttons/styled-tooltip";

export function TargetMindLogoButton() {
  return (
    <StyledTooltip content="TargetMind">
      <NavLink
        to="/"
        aria-label="TargetMind home"
        className="grid size-[30px] place-items-center rounded-lg bg-white shadow-sm transition-opacity hover:opacity-90 md:size-10 md:rounded-xl"
      >
        <TargetMindLogo className="size-6 md:size-8" />
      </NavLink>
    </StyledTooltip>
  );
}
