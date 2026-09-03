/**
 * The sending rhythm chart, drawn by hand in SVG.
 *
 * A charting library would be several times the bundle for one chart type, and
 * drawing it here means it reads the theme variables directly and stays
 * legible in both themes with no second palette to maintain.
 */
import { useId, useMemo, useState } from "react";
import { shortDate } from "../lib/format";

export interface Point {
  label: string;
  value: number;
}

const WIDTH = 560;
const PADDING = { top: 12, right: 6, bottom: 20, left: 6 };

/** The sparse form: a quantity per day, drawn as a column. */
function ColumnChart({ points, height }: { points: Point[]; height: number }) {
  const innerHeight = height - PADDING.top - PADDING.bottom;
  const maximum = Math.max(1, ...points.map((point) => point.value));
  // Wide columns for one or two days would read as a progress bar, so the bar
  // width is fixed and the group is centred instead of stretched.
  const barWidth = 52;
  const gap = 20;
  const groupWidth = points.length * barWidth + (points.length - 1) * gap;
  const startX = (WIDTH - groupWidth) / 2;

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${height}`}
      className="w-full"
      style={{ height }}
      role="img"
      aria-label="Applications sent per day"
    >
      {[0, 0.5, 1].map((fraction) => (
        <line
          key={fraction}
          x1={PADDING.left}
          x2={WIDTH - PADDING.right}
          y1={PADDING.top + innerHeight * fraction}
          y2={PADDING.top + innerHeight * fraction}
          stroke="var(--line)"
          strokeDasharray="2 6"
          strokeWidth="1"
        />
      ))}
      {points.map((point, index) => {
        const barHeight = Math.max(2, (point.value / maximum) * innerHeight);
        const x = startX + index * (barWidth + gap);
        return (
          <g key={point.label}>
            <rect
              x={x}
              y={PADDING.top + innerHeight - barHeight}
              width={barWidth}
              height={barHeight}
              rx="3"
              fill="var(--accent)"
            />
            <text
              x={x + barWidth / 2}
              y={PADDING.top + innerHeight - barHeight - 6}
              textAnchor="middle"
              fontSize="12"
              fontWeight="560"
              fill="var(--ink)"
            >
              {point.value}
            </text>
            <text
              x={x + barWidth / 2}
              y={height - 4}
              textAnchor="middle"
              fontSize="9.5"
              fill="var(--muted)"
            >
              {shortDate(point.label)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/**
 * Picks the honest form for the amount of data there is.
 *
 * A line needs at least two points to be a line. With one day of data the path
 * came out as a single `M` command and the chart rendered as an empty box that
 * still claimed to show a trend. Below four points the honest form is columns:
 * one day is a quantity, not a rhythm.
 *
 * This dispatcher deliberately calls no hooks. The branch used to live inside
 * the line chart, after `useId` and `useState` but before two `useMemo` calls,
 * so the sparse path ran two hooks and the dense path ran four. React throws
 * error #300 for that and unmounts the entire tree, which took the whole
 * dashboard to a blank page for anyone whose data happened to be sparse.
 */
export function AreaChart({ points, height = 140 }: { points: Point[]; height?: number }) {
  if (points.length > 0 && points.length < 4) {
    return <ColumnChart points={points} height={height} />;
  }
  return <LineChart points={points} height={height} />;
}

function LineChart({ points, height }: { points: Point[]; height: number }) {
  const gradientId = useId();
  const [hover, setHover] = useState<number | null>(null);

  const innerWidth = WIDTH - PADDING.left - PADDING.right;
  const innerHeight = height - PADDING.top - PADDING.bottom;

  const maximum = Math.max(1, ...points.map((point) => point.value));
  const step = points.length > 1 ? innerWidth / (points.length - 1) : innerWidth;

  const coordinates = useMemo(
    () =>
      points.map((point, index) => ({
        x: PADDING.left + index * step,
        y: PADDING.top + innerHeight - (point.value / maximum) * innerHeight,
        ...point,
      })),
    [points, step, innerHeight, maximum],
  );

  // A monotone-ish cubic keeps the line calm without overshooting below zero.
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

  const grid = [0, 0.25, 0.5, 0.75, 1];

  if (!points.length) {
    /* A flat grey box says "broken". A ghosted version of the real chart says
       "this is where your sending rhythm will appear", which is the truth. The
       ghost is the same shape the real chart will be, not a different one. */
    return (
      <div className="relative" style={{ height }}>
        <svg
          viewBox={`0 0 ${WIDTH} ${height}`}
          className="w-full"
          style={{ height }}
          aria-hidden="true"
        >
          {grid.map((fraction) => (
            <line
              key={fraction}
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={PADDING.top + innerHeight * fraction}
              y2={PADDING.top + innerHeight * fraction}
              stroke="var(--line)"
              strokeDasharray="2 6"
              strokeWidth="1"
            />
          ))}
          <path
            d={`M 6 ${PADDING.top + innerHeight * 0.85} C 140 ${PADDING.top + innerHeight * 0.9} 180 ${PADDING.top + innerHeight * 0.4} 300 ${PADDING.top + innerHeight * 0.5} C 420 ${PADDING.top + innerHeight * 0.6} 460 ${PADDING.top + innerHeight * 0.18} 554 ${PADDING.top + innerHeight * 0.28}`}
            fill="none"
            stroke="var(--surface-4)"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
          <p
            className="rounded-[6px] px-2 py-0.5 text-sm font-medium text-ink"
            style={{ background: "var(--surface)" }}
          >
            No applications sent yet
          </p>
          <p
            className="max-w-[24ch] rounded-[6px] px-2 py-0.5 text-center text-micro leading-relaxed text-muted"
            style={{ background: "var(--surface)" }}
          >
            Approve a draft, then run a send. This fills in one point per day.
          </p>
        </div>
      </div>
    );
  }

  const active = hover === null ? null : coordinates[hover];
  const labelEvery = Math.max(1, Math.ceil(coordinates.length / 6));

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="w-full"
        style={{ height }}
        role="img"
        aria-label="Applications sent per day"
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {grid.map((fraction) => (
          <line
            key={fraction}
            x1={PADDING.left}
            x2={WIDTH - PADDING.right}
            y1={PADDING.top + innerHeight * fraction}
            y2={PADDING.top + innerHeight * fraction}
            stroke="var(--line)"
            strokeDasharray="2 6"
            strokeWidth="1"
          />
        ))}

        <path
          d={`${path} L ${coordinates[coordinates.length - 1].x} ${PADDING.top + innerHeight} L ${coordinates[0].x} ${PADDING.top + innerHeight} Z`}
          fill={`url(#${gradientId})`}
        />
        <path
          d={path}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.75"
          strokeLinecap="round"
        />

        {active ? (
          <>
            <line
              x1={active.x}
              x2={active.x}
              y1={PADDING.top}
              y2={PADDING.top + innerHeight}
              stroke="var(--line-strong)"
              strokeWidth="1"
            />
            <circle
              cx={active.x}
              cy={active.y}
              r="3.5"
              fill="var(--surface)"
              stroke="var(--accent)"
              strokeWidth="2"
            />
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
          .filter((_, index) => index % labelEvery === 0)
          .map((point) => (
            <text
              key={`label-${point.label}`}
              x={point.x}
              y={height - 4}
              textAnchor="middle"
              fontSize="9.5"
              fill="var(--muted)"
            >
              {shortDate(point.label)}
            </text>
          ))}
      </svg>

      {active ? (
        <div
          className="pop pointer-events-none absolute -translate-x-1/2 px-2 py-1 text-micro font-medium text-ink"
          style={{ left: `${(active.x / WIDTH) * 100}%`, top: 0, borderRadius: 6 }}
        >
          <span className="tabular" style={{ fontFamily: "var(--font-mono)" }}>
            {active.value}
          </span>{" "}
          on {shortDate(active.label)}
        </div>
      ) : null}
    </div>
  );
}
