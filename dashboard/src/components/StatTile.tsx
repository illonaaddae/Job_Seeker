import type { ReactNode } from "react";
import { IconArrowDown, IconArrowUp } from "./Icons";

export function StatTile({
  label,
  value,
  hint,
  delta,
  icon,
  accent,
  onClick,
  actionLabel,
}: {
  label: string;
  value: string | number;
  hint?: string;
  delta?: { value: number; suffix?: string };
  icon?: ReactNode;
  accent?: boolean;
  onClick?: () => void;
  actionLabel?: string;
}) {
  const positive = (delta?.value ?? 0) >= 0;
  const interactive = Boolean(onClick);

  // A figure that leads somewhere should say so, and be reachable by keyboard.
  const Element = interactive ? "button" : "article";

  return (
    <Element
      type={interactive ? "button" : undefined}
      onClick={onClick}
      aria-label={interactive ? `${label}: ${value}. ${actionLabel ?? "Open"}` : undefined}
      className={`card group flex flex-col gap-3.5 p-5 text-left ${accent ? "card-accent" : ""} ${
        interactive ? "cursor-pointer transition-transform hover:-translate-y-0.5" : ""
      }`}
      style={interactive ? { boxShadow: "var(--shadow)" } : undefined}>
      <header className="flex items-center justify-between gap-2">
        <span className="eyebrow">{label}</span>
        {icon ? (
          <span
            className="flex h-8 w-8 items-center justify-center rounded-[9px]"
            style={{
              background: accent ? "var(--accent-soft)" : "var(--surface-3)",
              color: accent ? "var(--accent)" : "var(--muted)",
            }}
          >
            {icon}
          </span>
        ) : null}
      </header>

      <div className="flex items-end gap-2.5">
        <span
          className="font-display text-[37px] leading-[0.9] text-ink"
          style={{ fontWeight: 650, letterSpacing: "-0.008em" }}
        >
          {value}
        </span>
        {delta ? (
          <span
            className="chip mb-0.5"
            style={{
              background: positive ? "var(--positive-soft)" : "var(--danger-soft)",
              color: positive ? "var(--positive)" : "var(--danger)",
            }}
          >
            {positive ? <IconArrowUp size={11} /> : <IconArrowDown size={11} />}
            {Math.abs(delta.value)}
            {delta.suffix ?? ""}
          </span>
        ) : null}
      </div>

      {hint ? <p className="text-[13px] leading-snug text-muted">{hint}</p> : null}

      {interactive ? (
        <span
          className="text-[12px] font-medium opacity-0 transition-opacity group-hover:opacity-100"
          style={{ color: "var(--accent)" }}
        >
          {actionLabel ?? "Open"}
        </span>
      ) : null}
    </Element>
  );
}
