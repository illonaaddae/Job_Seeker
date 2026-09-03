import { IconClock, IconPulse } from "./Icons";
import { EmptyState, Tag, type Tone } from "./Primitives";
import { compactTime, relativeTime, titleCase } from "../lib/format";
import type { ActivityEvent, PendingFollowup } from "../types";

const EVENT_TONE: Record<string, Tone> = {
  discover: "neutral",
  score: "neutral",
  draft: "warning",
  send_sent: "positive",
  send_dry_run: "info",
  send_blocked: "warning",
  send_failed: "danger",
};

const TONE_COLOUR: Record<Tone, string> = {
  neutral: "var(--st-grey)",
  accent: "var(--accent)",
  info: "var(--st-blue)",
  positive: "var(--st-green)",
  warning: "var(--st-amber)",
  danger: "var(--st-red)",
  premium: "var(--st-violet)",
};

export function ActivityFeed({ events }: { events: ActivityEvent[] }) {
  if (!events.length) {
    return (
      <EmptyState
        icon={<IconPulse size={16} />}
        title="No activity yet"
        hint="Run a stage from the button in the top bar. Everything it does is logged here."
      />
    );
  }

  return (
    <ol className="flex flex-col">
      {events.map((event, index) => {
        const tone = EVENT_TONE[event.type] ?? "neutral";
        return (
          <li key={event.id} className="relative flex gap-3 pb-3.5 last:pb-0">
            {index < events.length - 1 ? (
              <span
                className="absolute left-[3px] top-3 h-full w-px"
                style={{ background: "var(--line)" }}
                aria-hidden="true"
              />
            ) : null}
            <span
              className="relative z-10 mt-[5px] h-[7px] w-[7px] shrink-0 rounded-full"
              style={{
                background: TONE_COLOUR[tone],
                // The ring hides the timeline rule behind each dot.
                boxShadow: "0 0 0 3px var(--surface)",
              }}
              aria-hidden="true"
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="text-label font-medium text-ink">{titleCase(event.type)}</span>
                <span
                  className="tabular text-micro text-muted"
                  title={relativeTime(event.created_at)}
                >
                  {compactTime(event.created_at)}
                </span>
              </div>
              <p className="mt-0.5 text-[0.8125rem] leading-snug text-muted">{event.message}</p>
            </div>
          </li>
        );
      })}
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
        icon={<IconClock size={16} />}
        title="Nothing scheduled"
        hint="Follow ups queue themselves once an application has actually been sent."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-1">
      {followups.slice(0, 6).map((followup) => (
        <li key={followup.id}>
          <button
            type="button"
            disabled={!onSelect}
            onClick={onSelect ? () => onSelect(followup.job_id) : undefined}
            className="row flex w-full items-center gap-2.5 rounded-[8px] px-2 py-1.5 text-left disabled:cursor-default"
          >
            <span
              className="tabular flex h-6 w-6 shrink-0 items-center justify-center rounded-[6px] text-micro"
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--line)",
                color: "var(--st-amber)",
                fontFamily: "var(--font-mono)",
              }}
              title={`Follow up number ${followup.sequence_no}`}
            >
              {followup.sequence_no}
            </span>
            <span className="min-w-0 flex-1 leading-tight">
              <span className="clip block text-[0.8125rem] font-medium text-ink">
                {followup.company_name}
              </span>
              <span className="clip block text-micro text-muted">{followup.title}</span>
            </span>
            <Tag bare title={relativeTime(followup.due_at)}>
              {relativeTime(followup.due_at)}
            </Tag>
          </button>
        </li>
      ))}
    </ul>
  );
}
