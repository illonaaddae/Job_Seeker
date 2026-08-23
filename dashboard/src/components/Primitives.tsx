/** Small shared pieces: pills, score dial, avatars, empty and loading states. */
import type { ReactNode } from "react";
import { hueFor, initials, titleCase } from "../lib/format";

type Tone = "neutral" | "accent" | "positive" | "warning" | "danger";

const TONE_STYLE: Record<Tone, { background: string; color: string }> = {
  neutral: { background: "var(--surface-3)", color: "var(--muted)" },
  accent: { background: "var(--accent-soft)", color: "var(--accent)" },
  positive: { background: "var(--positive-soft)", color: "var(--positive)" },
  warning: { background: "var(--warning-soft)", color: "var(--warning)" },
  danger: { background: "var(--danger-soft)", color: "var(--danger)" },
};

const STATUS_TONE: Record<string, Tone> = {
  new: "neutral",
  scored: "neutral",
  shortlisted: "accent",
  drafted: "warning",
  applied: "positive",
  rejected_by_me: "neutral",
  expired: "neutral",
  draft: "warning",
  approved: "accent",
  sent: "accent",
  failed: "danger",
  replied: "positive",
  interview: "positive",
  offer: "positive",
  rejected: "danger",
  ghosted: "neutral",
  withdrawn: "neutral",
  interested: "positive",
  auto_ack: "neutral",
  rejection: "danger",
  other: "neutral",
};

export function Pill({
  children,
  tone = "neutral",
  title,
}: {
  children: ReactNode;
  tone?: Tone;
  title?: string;
}) {
  return (
    <span className="chip" style={TONE_STYLE[tone]} title={title}>
      {children}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  return <Pill tone={STATUS_TONE[status] ?? "neutral"}>{titleCase(status)}</Pill>;
}

/**
 * Score as a ring rather than a number in a box. The arc is readable at a
 * glance across a long table, which a bare number is not.
 */
export function ScoreDial({ value, size = 40 }: { value: number; size?: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  const radius = (size - 5) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (clamped / 100) * circumference;
  const colour =
    clamped >= 75 ? "var(--positive)" : clamped >= 55 ? "var(--accent)" : "var(--muted)";

  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center"
      style={{ width: size, height: size }}
      title={`Match score ${clamped.toFixed(0)} of 100`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--line)"
          strokeWidth={3}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={colour}
          strokeWidth={3}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          style={{ transition: "stroke-dasharray 500ms cubic-bezier(0.2,0.7,0.3,1)" }}
        />
      </svg>
      <span
        className="font-display absolute"
        style={{ fontSize: size * 0.34, color: colour, fontWeight: 650, letterSpacing: "-0.008em" }}
      >
        {clamped.toFixed(0)}
      </span>
    </span>
  );
}

/** Companies rarely give us a logo, so the mark is derived from the name. */
export function CompanyMark({ name, size = 34 }: { name: string; size?: number }) {
  const hue = hueFor(name);
  return (
    <span
      className="font-display inline-flex shrink-0 items-center justify-center rounded-[9px]"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.34,
        fontWeight: 650,
        background: `color-mix(in oklab, hsl(${hue} 62% 52%) 16%, var(--surface-3))`,
        color: `hsl(${hue} 55% 38%)`,
        border: "1px solid var(--line)",
      }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}

export function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-[17.5px] text-ink">{title}</h2>
        {subtitle ? <p className="mt-1 text-[13px] text-muted">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <span
        className="flex h-11 w-11 items-center justify-center rounded-full"
        style={{ background: "var(--surface-3)", color: "var(--muted)" }}
      >
        {icon}
      </span>
      <div>
        <p className="text-sm font-medium text-ink">{title}</p>
        {hint ? <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted">{hint}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg ${className}`}
      style={{ background: "var(--surface-3)" }}
    />
  );
}
