import { IconClock, IconPulse } from "./Icons";
import { EmptyState, Pill } from "./Primitives";
import { relativeTime, titleCase, truncate } from "../lib/format";
import type { ActivityEvent, PendingFollowup } from "../types";

const EVENT_TONE: Record<string, "neutral" | "accent" | "positive" | "warning" | "danger"> = {
  discover: "neutral",
  score: "neutral",
  draft: "warning",
  send_sent: "positive",
  send_dry_run: "accent",
  send_blocked: "warning",
  send_failed: "danger",
};

export function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (!events.length) {
    return <EmptyState icon={<IconPulse />} title="No activity yet" hint="Every stage you run is logged here." />;
  }

  return (
    <ol className="flex flex-col">
      {events.map((event, index) => (
        <li key={event.id} className="relative flex gap-3 pb-4 pl-1 last:pb-0">
          {index < events.length - 1 ? (
            <span
              className="absolute left-[7px] top-4 h-full w-px"
              style={{ background: "var(--line)" }}
              aria-hidden="true"
            />
          ) : null}
          <span
            className="relative z-10 mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full ring-4"
            style={{
              background: "var(--accent)",
              // The ring hides the timeline rule behind each dot.
              boxShadow: "0 0 0 4px var(--surface)",
            }}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <Pill tone={EVENT_TONE[event.type] ?? "neutral"}>{titleCase(event.type)}</Pill>
              <span className="text-[12px] text-muted">{relativeTime(event.created_at)}</span>
            </div>
            <p className="mt-1 text-[13.5px] leading-snug text-ink-2">
              {truncate(event.message, 110)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function FollowupList({
  followups,
  onSelect,
}: {
  followups: PendingFollowup[];
  onSelect?: (jobId: number) => void;
}) {
  if (!followups.length) {
    return (
      <EmptyState
        icon={<IconClock />}
        title="Nothing scheduled"
        hint="Follow ups are queued automatically once an application is actually sent."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {followups.slice(0, 6).map((followup) => (
        <li
          key={followup.id}
          onClick={onSelect ? () => onSelect(followup.job_id) : undefined}
          className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 ${
            onSelect ? "cursor-pointer transition-colors hover:border-[var(--line-strong)]" : ""
          }`}
          style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
        >
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[12px] font-semibold"
            style={{ background: "var(--warning-soft)", color: "var(--warning)" }}
          >
            #{followup.sequence_no}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13.5px] font-medium text-ink">{followup.company_name}</p>
            <p className="truncate text-[12px] text-muted">{truncate(followup.title, 40)}</p>
          </div>
          <span className="shrink-0 text-[12px] text-muted">{relativeTime(followup.due_at)}</span>
        </li>
      ))}
    </ul>
  );
}
