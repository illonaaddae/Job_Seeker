/**
 * The pipeline as one funnel.
 *
 * This replaced four identically sized stat cards. Four cards of icon plus
 * label plus figure are the lazy container: they imply the four numbers are
 * unrelated peers, when in fact every one of them is a survivor of the one
 * before it. A discovered role becomes shortlisted, becomes written, becomes
 * sent, and might come back. Laid out in order with the drop between stages
 * shown, the same six numbers answer a question the cards could not: where the
 * search is actually leaking.
 *
 * Two things the first version got wrong:
 *
 *  - It filled each bar in its own hue. Six hues encode nothing here (two of
 *    them were the same green) and the length already carries the value, so it
 *    was a second colour system competing with the one accent. The tracks are
 *    neutral now and the accent marks the stage the user has to act on.
 *  - At phone width it laid out as a 2x3 grid, which is six stat tiles: the
 *    exact pattern this component exists to refuse. Below `sm` it is a single
 *    column, so the sequence survives.
 */
import { Skeleton } from "./Primitives";
import type { Stats } from "../types";

type Target = { view: "jobs" | "applications" | "replies"; filter?: string };

interface Stage {
  label: string;
  value: number;
  target: Target;
  /** Shown beside the figure: what share of the previous stage survived. */
  showConversion: boolean;
}

function stagesFor(stats: Stats): Stage[] {
  const jobs = stats.jobs_by_status ?? {};
  const apps = stats.applications_by_status ?? {};

  return [
    {
      label: "Discovered",
      value: stats.jobs_total ?? 0,
      target: { view: "jobs", filter: "all" },
      showConversion: false,
    },
    {
      label: "Shortlisted",
      value: jobs.shortlisted ?? 0,
      target: { view: "jobs", filter: "shortlist" },
      showConversion: true,
    },
    {
      label: "Written",
      value: (apps.draft ?? 0) + (apps.approved ?? 0),
      target: { view: "applications", filter: "draft" },
      showConversion: true,
    },
    {
      label: "Sent",
      value: stats.sent ?? 0,
      target: { view: "applications", filter: "sent" },
      showConversion: true,
    },
    {
      label: "Replied",
      value: stats.replied ?? 0,
      target: { view: "replies" },
      showConversion: true,
    },
    {
      label: "Interviews",
      value: stats.positive ?? 0,
      target: { view: "applications", filter: "interview" },
      showConversion: true,
    },
  ];
}

/** The last stage that still has anything in it: what the user acts on next. */
function currentStage(stages: Stage[]): number {
  let last = 0;
  stages.forEach((stage, index) => {
    if (stage.value > 0) last = index;
  });
  return last;
}

export function Funnel({
  stats,
  onNavigate,
}: {
  stats: Stats | null;
  onNavigate: (view: "jobs" | "applications" | "replies", filter?: string) => void;
}) {
  // Rendering zeros while loading asserts "0 discovered" as a fact. A skeleton
  // says the truth, which is that we do not know yet.
  if (!stats) {
    return (
      <div className="grid grid-cols-1 gap-px sm:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="flex flex-col gap-2.5 px-4 py-4">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-6 w-12" />
            <Skeleton className="h-1 w-full" />
          </div>
        ))}
      </div>
    );
  }

  const stages = stagesFor(stats);
  const top = Math.max(1, stages[0].value);
  const current = currentStage(stages);

  return (
    <div className="grid grid-cols-1 gap-px sm:grid-cols-3 xl:grid-cols-6">
      {stages.map((stage, index) => {
        const previous = index > 0 ? stages[index - 1].value : 0;
        const conversion =
          stage.showConversion && previous > 0 ? Math.round((stage.value / previous) * 100) : null;
        const isCurrent = index === current;

        return (
          <button
            key={stage.label}
            type="button"
            onClick={() => onNavigate(stage.target.view, stage.target.filter)}
            className="row flex items-baseline gap-3 px-4 py-3 text-left sm:flex-col sm:items-start sm:gap-2.5 sm:py-4"
          >
            <span className="label w-24 shrink-0 sm:w-auto">{stage.label}</span>

            <span className="flex flex-1 items-baseline gap-2 sm:flex-none">
              <span className={`figure ${isCurrent ? "text-ink" : "text-ink-2"}`}>
                {stage.value}
              </span>
              {conversion !== null ? (
                <span className="tabular text-label text-muted">{conversion}%</span>
              ) : null}
            </span>

            {/* The fill is this stage against the top of the funnel, so the
                run of tracks draws the narrowing directly. A value of zero
                draws nothing: painting a sliver for 0 lies about the data. */}
            <span
              className="block w-20 shrink-0 overflow-hidden rounded-full sm:w-full"
              style={{ background: "var(--surface-4)", height: 4 }}
            >
              {stage.value > 0 ? (
                <span
                  className="block h-full w-full origin-left rounded-full"
                  style={{
                    transform: `scaleX(${Math.max(0.02, stage.value / top)})`,
                    background: isCurrent ? "var(--accent)" : "var(--line-tertiary)",
                    transition: "transform 480ms cubic-bezier(0.16,1,0.3,1)",
                  }}
                />
              ) : null}
            </span>
          </button>
        );
      })}
    </div>
  );
}
