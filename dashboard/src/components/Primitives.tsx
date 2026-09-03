/**
 * The shared vocabulary: tags, scores, company marks, meters, empty states.
 *
 * There is one tag shape in this product. A row can be carrying a status, a
 * source, a channel and a remote flag at the same time, and three differently
 * filled pills next to each other read as three unrelated systems shouting.
 * So the shape is fixed and the semantics ride in a 6px glyph, which keeps the
 * one accent colour scarce and the row scannable.
 */
import type { CSSProperties, ReactNode } from "react";
import { hueFor, initials, titleCase } from "../lib/format";

export type Tone = "neutral" | "accent" | "positive" | "warning" | "danger" | "info" | "premium";

const TONE_COLOUR: Record<Tone, string> = {
  neutral: "var(--st-grey)",
  accent: "var(--accent)",
  info: "var(--st-blue)",
  positive: "var(--st-green)",
  warning: "var(--st-amber)",
  danger: "var(--st-red)",
  premium: "var(--st-violet)",
};

/**
 * Status meanings, grouped by what the user has to do about them rather than
 * by which table they came from. Grey is inert, amber wants the user, blue is
 * in play, green has progressed, violet is worth celebrating, red has failed.
 */
const STATUS_TONE: Record<string, Tone> = {
  new: "neutral",
  scored: "neutral",
  expired: "neutral",
  rejected_by_me: "neutral",
  ghosted: "neutral",
  withdrawn: "neutral",
  auto_ack: "neutral",
  other: "neutral",

  draft: "warning",
  drafted: "warning",

  shortlisted: "info",
  approved: "info",

  applied: "positive",
  sent: "positive",
  replied: "positive",
  interested: "positive",

  interview: "premium",
  offer: "premium",

  failed: "danger",
  rejected: "danger",
  rejection: "danger",
};

/** A few machine names read badly when title cased on their own. */
const STATUS_LABEL: Record<string, string> = {
  rejected_by_me: "Ruled out",
  auto_ack: "Auto reply",
  rejected: "Rejected",
  rejection: "Rejection",
  withdrawn: "Withdrawn",
};

export function Tag({
  children,
  tone,
  icon,
  bare = false,
  title,
  style,
}: {
  children: ReactNode;
  /**
   * The dot vocabulary. It means one thing across the whole product: the state
   * of the record. Do not reach for it to decorate some other dimension, or a
   * blue dot ends up meaning "shortlisted" in one column and "remote" in the
   * next. Anything that is not a state takes `icon` instead.
   */
  tone?: Tone;
  /** A drawn glyph for a non-state dimension, such as a location pin. */
  icon?: ReactNode;
  /** No background or border: for meta that sits inside another container. */
  bare?: boolean;
  title?: string;
  style?: CSSProperties;
}) {
  return (
    <span className={`tag${bare ? " tag-bare" : ""}`} title={title} style={style}>
      {tone ? (
        <span className="tag-dot" style={{ color: TONE_COLOUR[tone] }} aria-hidden="true" />
      ) : null}
      {!tone && icon ? (
        <span style={{ color: "var(--ink-tertiary)", display: "inline-flex" }} aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <span className="clip">{children}</span>
    </span>
  );
}

export function StatusTag({ status, bare = false }: { status: string; bare?: boolean }) {
  return (
    <Tag tone={STATUS_TONE[status] ?? "neutral"} bare={bare}>
      {STATUS_LABEL[status] ?? titleCase(status)}
    </Tag>
  );
}

/**
 * Match score.
 *
 * This was a progress ring per row. Sixty arcs down a table is sixty competing
 * shapes, and a ring cannot be compared to the ring eight rows below it. A
 * tabular figure can: the column becomes a column, and the eye reads the drop
 * from 87 to 62 without decoding anything. The rail on the left carries the
 * banding at a glance.
 */
export function Score({ value, size = "md" }: { value: number; size?: "sm" | "md" | "lg" }) {
  const clamped = Math.max(0, Math.min(100, value));

  /* No colour at all on the rail.
     
     This started as four status hues, which collided with the dot vocabulary
     (green meant "sent" one column over and "above 75" here). Banding it with
     the accent instead did not help: the shortlist filters at 60 and real rows
     land at 78-90, so a 75 threshold painted every rail accent and the signal
     carried nothing. The queue is sorted by score, so position already ranks
     it; weight and ink are enough to mark the top of the list, and the accent
     stays reserved for brand, primary action, focus and current selection. */
  const strong = clamped >= 85;
  const railColour = "var(--line-tertiary)";

  const metrics = {
    sm: { font: "0.8125rem", rail: 16, width: "1.5rem" },
    md: { font: "0.9375rem", rail: 20, width: "1.875rem" },
    lg: { font: "1.5rem", rail: 32, width: "2.75rem" },
  }[size];

  return (
    <span
      className="inline-flex items-center gap-2"
      title={`Match score ${clamped.toFixed(0)} of 100`}
    >
      <span
        aria-hidden="true"
        style={{
          width: 2,
          height: metrics.rail,
          borderRadius: 2,
          background: railColour,
          flexShrink: 0,
        }}
      />
      <span
        className="tabular"
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: metrics.font,
          fontWeight: strong ? 560 : 500,
          color: strong ? "var(--ink)" : "var(--ink-2)",
          minWidth: metrics.width,
          letterSpacing: "-0.02em",
        }}
      >
        {clamped.toFixed(0)}
      </span>
    </span>
  );
}

/**
 * Companies rarely give us a logo, so the mark is derived from the name. The
 * hue is deterministic, which makes a company recognisable down a long list,
 * but it is held at low chroma so a table of twenty marks does not turn into
 * a colour chart competing with the one accent.
 */
export function CompanyMark({ name, size = 22 }: { name: string; size?: number }) {
  const hue = hueFor(name);
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center"
      style={{
        width: size,
        height: size,
        borderRadius: size <= 24 ? 5 : 7,
        fontSize: Math.max(9, size * 0.38),
        fontWeight: 560,
        letterSpacing: "-0.01em",
        background: `color-mix(in oklab, oklch(0.62 0.09 ${hue}) 22%, var(--surface-3))`,
        color: `color-mix(in oklab, oklch(0.62 0.11 ${hue}) 82%, var(--ink))`,
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
      <div className="min-w-0">
        <h2 className="text-ink">{title}</h2>
        {subtitle ? (
          <p className="mt-1 text-[0.8125rem] leading-snug text-muted">{subtitle}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

/** Selection is a surface lift. See the note on `.segmented` in index.css. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { key: T; label: string; count?: number; disabled?: boolean }[];
  value: T;
  onChange: (key: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => {
        const active = option.key === value;
        return (
          <button
            key={option.key}
            type="button"
            className="segment"
            aria-pressed={active}
            disabled={option.disabled}
            onClick={() => onChange(option.key)}
          >
            {option.label}
            {option.count !== undefined ? (
              <span
                className="tabular"
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.6875rem",
                  color: "var(--muted)",
                }}
              >
                {option.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/**
 * One horizontal bar. Used for score signals and the daily cap.
 *
 * The default is neutral, not accent: six accent meters stacked in the drawer
 * spent the one accent colour on six rows at once, which is what makes it stop
 * meaning "act here". Pass a tone only when the bar itself is the subject.
 */
export function Meter({
  value,
  max,
  tone = "var(--line-tertiary)",
  height = 4,
}: {
  value: number;
  max: number;
  tone?: string;
  height?: number;
}) {
  return (
    <span
      className="block overflow-hidden rounded-full"
      style={{ background: "var(--surface-3)", height }}
    >
      {value > 0 ? (
        <span
          className="block h-full w-full origin-left rounded-full"
          style={{
            transform: `scaleX(${Math.max(0.02, value / Math.max(1, max))})`,
            background: tone,
            transition: "transform 420ms cubic-bezier(0.16,1,0.3,1)",
          }}
        />
      ) : null}
    </span>
  );
}

/**
 * An empty state teaches the interface. "Nothing here" tells the user only
 * that they cannot tell whether the product is broken.
 */
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
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <span
        className="flex h-9 w-9 items-center justify-center rounded-[10px]"
        style={{
          background: "var(--surface-2)",
          border: "1px solid var(--line)",
          color: "var(--ink-tertiary)",
        }}
      >
        {icon}
      </span>
      <div>
        <p className="text-body font-medium text-ink">{title}</p>
        {hint ? (
          <p className="mx-auto mt-1.5 max-w-[34ch] text-[0.8125rem] leading-relaxed text-muted">
            {hint}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-[6px] ${className}`}
      style={{ background: "var(--surface-2)" }}
    />
  );
}
