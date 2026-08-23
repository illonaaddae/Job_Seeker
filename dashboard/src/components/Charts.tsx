/**
 * Charts drawn by hand in SVG.
 *
 * A charting library would be four times the bundle for two chart types, and
 * hand drawing them means they inherit the theme variables directly and stay
 * legible in both light and dark without a second palette to maintain.
 */
import { useId, useMemo, useState } from "react";
import { shortDate } from "../lib/format";

export interface Point {
  label: string;
  value: number;
}

export function AreaChart({
  points,
  height = 132,
  accent = "var(--accent)",
}: {
  points: Point[];
  height?: number;
  accent?: string;
}) {
  const gradientId = useId();
  const [hover, setHover] = useState<number | null>(null);

  const width = 560;
  const padding = { top: 10, right: 6, bottom: 20, left: 6 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const maximum = Math.max(1, ...points.map((point) => point.value));
  const step = points.length > 1 ? innerWidth / (points.length - 1) : innerWidth;

  const coordinates = useMemo(
    () =>
      points.map((point, index) => ({
        x: padding.left + index * step,
        y: padding.top + innerHeight - (point.value / maximum) * innerHeight,
        ...point,
      })),
    [points, step, innerHeight, maximum, padding.left, padding.top],
  );

  // A monotone-ish cubic keeps the line calm without overshooting above zero.
  const path = useMemo(() => {
    if (!coordinates.length) return "";
    return coordinates
      .map((point, index) => {
        if (index === 0) return `M ${point.x} ${point.y}`;
        const previous = coordinates[index - 1];
        const controlX = (previous.x + point.x) / 2;
        return `C ${controlX} ${previous.y} ${controlX} ${point.y} ${point.x} ${point.y}`;
      })
      .join(" ");
  }, [coordinates]);

  if (!points.length) {
    // A flat grey box says "broken". A ghosted version of the real chart says
    // "this is where your sending rhythm will appear", which is the truth.
    const ghost = [18, 32, 24, 46, 38, 60, 44, 72, 56, 84, 66, 92];
    return (
      <div className="relative" style={{ height }}>
        <svg
          viewBox="0 0 560 132"
          className="w-full"
          style={{ height, opacity: 0.5 }}
          aria-hidden="true"
        >
          {[0.25, 0.5, 0.75, 1].map((fraction) => (
            <line
              key={fraction}
              x1="6"
              x2="554"
              y1={10 + 102 * fraction}
              y2={10 + 102 * fraction}
              stroke="var(--line)"
              strokeDasharray="3 5"
              strokeWidth="1"
            />
          ))}
          {ghost.map((value, index) => (
            <rect
              key={index}
              x={14 + index * 45}
              y={112 - value}
              width="22"
              height={value}
              rx="5"
              fill="var(--surface-3)"
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
          <span
            className="absolute h-20 w-72 rounded-full"
            style={{
              background: "var(--surface)",
              filter: "blur(22px)",
            }}
            aria-hidden="true"
          />
          <p className="relative text-[14px] font-medium text-ink">No applications sent yet</p>
          <p className="relative max-w-[16rem] text-center text-[12.5px] leading-relaxed text-muted">
            Approve a draft, then run a send. This fills in one bar per day.
          </p>
        </div>
      </div>
    );
  }

  const active = hover === null ? null : coordinates[hover];

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
        role="img"
        aria-label="Applications sent per day"
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity="0.26" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75, 1].map((fraction) => (
          <line
            key={fraction}
            x1={padding.left}
            x2={width - padding.right}
            y1={padding.top + innerHeight * fraction}
            y2={padding.top + innerHeight * fraction}
            stroke="var(--line)"
            strokeDasharray="3 5"
            strokeWidth="1"
          />
        ))}

        <path
          d={`${path} L ${coordinates[coordinates.length - 1].x} ${padding.top + innerHeight} L ${coordinates[0].x} ${padding.top + innerHeight} Z`}
          fill={`url(#${gradientId})`}
        />
        <path d={path} fill="none" stroke={accent} strokeWidth="2" strokeLinecap="round" />

        {active ? (
          <>
            <line
              x1={active.x}
              x2={active.x}
              y1={padding.top}
              y2={padding.top + innerHeight}
              stroke="var(--line-strong)"
              strokeWidth="1"
            />
            <circle cx={active.x} cy={active.y} r="4.5" fill={accent} />
            <circle cx={active.x} cy={active.y} r="8" fill={accent} opacity="0.18" />
          </>
        ) : null}

        {coordinates.map((point, index) => (
          <rect
            key={point.label}
            x={point.x - step / 2}
            y={0}
            width={Math.max(step, 6)}
            height={height}
            fill="transparent"
            onMouseEnter={() => setHover(index)}
          />
        ))}

        {coordinates
          .filter((_, index) => index % Math.ceil(coordinates.length / 6) === 0)
          .map((point) => (
            <text
              key={`label-${point.label}`}
              x={point.x}
              y={height - 4}
              textAnchor="middle"
              fontSize="10"
              fill="var(--muted)"
            >
              {shortDate(point.label)}
            </text>
          ))}
      </svg>

      {active ? (
        <div
          className="pointer-events-none absolute -translate-x-1/2 rounded-lg px-2 py-1 text-[12px] font-medium shadow-lg"
          style={{
            left: `${(active.x / width) * 100}%`,
            top: 0,
            background: "var(--ink)",
            color: "var(--surface)",
          }}
        >
          {active.value} on {shortDate(active.label)}
        </div>
      ) : null}
    </div>
  );
}

export function BarBreakdown({
  points,
  max,
  onSelect,
}: {
  points: (Point & { tone?: string })[];
  max?: number;
  onSelect?: (label: string) => void;
}) {
  const maximum = max ?? Math.max(1, ...points.map((point) => point.value));
  return (
    <ul className="flex flex-col gap-2.5">
      {points.map((point) => (
        <li
          key={point.label}
          onClick={onSelect ? () => onSelect(point.label) : undefined}
          className={`grid grid-cols-[7.5rem_1fr_2.2rem] items-center gap-3 rounded-lg ${
            onSelect ? "cursor-pointer transition-opacity hover:opacity-70" : ""
          }`}
        >
          <span className="truncate text-xs text-muted" title={point.label}>
            {point.label}
          </span>
          <span
            className="h-2 overflow-hidden rounded-full"
            style={{ background: "var(--surface-3)" }}
          >
            <span
              className="block h-full rounded-full"
              style={{
                width: `${Math.max(2, (point.value / maximum) * 100)}%`,
                background: point.tone ?? "var(--accent)",
                transition: "width 600ms cubic-bezier(0.2,0.7,0.3,1)",
              }}
            />
          </span>
          <span className="text-right text-xs font-semibold tabular text-ink">
            {point.value}
          </span>
        </li>
      ))}
    </ul>
  );
}
