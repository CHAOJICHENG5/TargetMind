import { NavLink } from "react-router";
import { cn } from "#/utils/utils";

interface SidebarRailItemProps {
  /** Route to navigate to. Mutually exclusive with `onClick`. */
  to?: string;
  onClick?: () => void;
  /** Accessible name; also shown as the native tooltip, since the rail is
   *  icon-only and carries no visible caption. */
  ariaLabel: string;
  icon: React.ReactNode;
  testId?: string;
  disabled?: boolean;
  /** Forces the active treatment for items whose state isn't route-based. */
  isActive?: boolean;
  /** Filled teal treatment, for the single primary action on the rail. */
  variant?: "primary" | "ghost";
}

/** Uniform hit area for every rail tile — icons are centred inside it. */
export const RAIL_TILE =
  "flex h-11 w-11 items-center justify-center rounded-xl";

/**
 * One icon tile on the TargetMind sidebar rail.
 *
 * Icon-only by design: a single 44×44 hit area per destination, the primary
 * action filled teal, and a teal edge marker on the active tile so the current
 * destination stays readable against the navy gradient.
 */
export function SidebarRailItem({
  to,
  onClick,
  ariaLabel,
  icon,
  testId,
  disabled = false,
  isActive,
  variant = "ghost",
}: SidebarRailItemProps) {
  const tile = (active: boolean) =>
    cn(
      "group relative transition-all duration-150",
      RAIL_TILE,
      variant === "primary"
        ? "bg-tm-teal text-white shadow-[0_8px_20px_-10px_rgba(14,124,155,0.9)] hover:bg-tm-teal-deep"
        : cn(
            "text-white/65 hover:bg-white/10 hover:text-white",
            active && "bg-white/15 text-white",
          ),
      disabled && "pointer-events-none opacity-40",
    );

  const body = (active: boolean) => (
    <>
      {/* Teal edge marker for the active ghost tile. */}
      {variant === "ghost" && active && (
        <span className="absolute -left-2 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-tm-teal-soft" />
      )}
      {icon}
    </>
  );

  if (to) {
    return (
      <NavLink
        to={to}
        data-testid={testId}
        aria-label={ariaLabel}
        title={ariaLabel}
        tabIndex={disabled ? -1 : 0}
        onClick={(e) => {
          if (disabled) e.preventDefault();
        }}
        className={({ isActive: routeActive }) => tile(isActive ?? routeActive)}
      >
        {({ isActive: routeActive }) => body(isActive ?? routeActive)}
      </NavLink>
    );
  }

  return (
    <button
      type="button"
      data-testid={testId}
      aria-label={ariaLabel}
      title={ariaLabel}
      aria-pressed={isActive}
      onClick={onClick}
      disabled={disabled}
      className={cn(tile(!!isActive), "cursor-pointer border-0 bg-transparent")}
    >
      {body(!!isActive)}
    </button>
  );
}
