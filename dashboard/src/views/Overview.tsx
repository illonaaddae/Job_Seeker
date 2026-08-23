import { AreaChart, BarBreakdown } from "../components/Charts";
import { ActivityFeed, FollowupList } from "../components/ActivityFeed";
import { JobsTable } from "../components/JobsTable";
import { Readiness } from "../components/Readiness";
import { SectionTitle } from "../components/Primitives";
import { StatTile } from "../components/StatTile";
import {
  IconBriefcase,
  IconCheck,
  IconInbox,
  IconSend,
} from "../components/Icons";
import { percent, titleCase } from "../lib/format";
import type { ActivityEvent, Job, PendingFollowup, Profile, Stats } from "../types";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

/**
 * One sentence telling the user what is actually waiting for them, so the top
 * of the page answers "what should I do now" instead of restating the metrics
 * that are already on screen below.
 */
function nextAction(stats: Stats | null): string {
  if (!stats) return "Loading your pipeline.";
  const drafts = stats.applications_by_status?.draft ?? 0;
  const approved = stats.applications_by_status?.approved ?? 0;
  const shortlisted = stats.jobs_by_status?.shortlisted ?? 0;

  if (drafts) {
    return `${drafts} draft${drafts === 1 ? "" : "s"} waiting for your review.`;
  }
  if (approved) {
    return `${approved} approved and ready for the next send run.`;
  }
  if (shortlisted) {
    return `${shortlisted} shortlisted role${shortlisted === 1 ? "" : "s"} with nothing drafted yet.`;
  }
  return "Run discover to pull today's openings.";
}

export function Overview({
  stats,
  jobs,
  events,
  followups,
  loading,
  profile,
  onSelect,
  onNavigate,
}: {
  stats: Stats | null;
  jobs: Job[];
  events: ActivityEvent[];
  followups: PendingFollowup[];
  loading: boolean;
  profile: Profile | null;
  onSelect: (job: Job) => void;
  onNavigate: (view: "jobs" | "applications" | "replies", filter?: string) => void;
}) {
  const firstName = (profile?.identity?.full_name ?? "").split(" ")[0];
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  const sends = stats?.sends_by_day ?? [];
  const thisWeek = sends.slice(-7).reduce((total, day) => total + day.n, 0);
  const lastWeek = sends.slice(-14, -7).reduce((total, day) => total + day.n, 0);

  const statusPoints = Object.entries(stats?.jobs_by_status ?? {})
    .map(([label, value]) => ({ label: titleCase(label), value }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);

  return (
    <div className="flex flex-col gap-5">
      <section
        className="card card-accent flex flex-wrap items-end justify-between gap-4 px-5 py-4"
        style={{ background: "var(--surface-2)" }}
      >
        <div>
          <p className="eyebrow">{today}</p>
          <h2
            className="mt-1.5 text-[23px] leading-none text-ink"
            style={{ fontWeight: 650, letterSpacing: "-0.008em" }}
          >
            {greeting()}
            {firstName ? `, ${firstName}` : ""}
          </h2>
          <p className="mt-2 text-[13.5px] text-muted">{nextAction(stats)}</p>
        </div>
        <dl className="flex gap-6">
          {([
            ["Shortlisted", stats?.jobs_by_status?.shortlisted ?? 0, "jobs", "shortlist"],
            ["Awaiting review", stats?.applications_by_status?.draft ?? 0, "applications", "draft"],
            ["Follow ups queued", stats?.followups_pending ?? 0, "applications", "sent"],
          ] as [string, number, "jobs" | "applications", string][]).map(
            ([label, value, view, filter]) => (
              <button
                key={label}
                type="button"
                onClick={() => onNavigate(view, filter)}
                className="text-left transition-opacity hover:opacity-70"
              >
                <dt className="eyebrow">{label}</dt>
                <dd
                  className="font-display mt-1 text-[21px] leading-none text-ink"
                  style={{ fontWeight: 650, letterSpacing: "-0.008em" }}
                >
                  {value}
                </dd>
              </button>
            ),
          )}
        </dl>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Matches found"
          value={stats?.jobs_total ?? 0}
          hint={`${stats?.jobs_by_status?.shortlisted ?? 0} shortlisted, average score ${stats?.avg_score ?? 0}`}
          icon={<IconBriefcase size={15} />}
          onClick={() => onNavigate("jobs", "shortlist")}
          actionLabel="See the shortlist"
        />
        <StatTile
          label="Applications sent"
          value={stats?.sent ?? 0}
          delta={{ value: thisWeek - lastWeek }}
          hint={`${thisWeek} this week against ${lastWeek} last week`}
          icon={<IconSend size={15} />}
          accent
          onClick={() => onNavigate("applications", "sent")}
          actionLabel="See what was sent"
        />
        <StatTile
          label="Replies"
          value={stats?.replied ?? 0}
          hint={`${percent(stats?.reply_rate ?? 0, 1)} of everything sent`}
          icon={<IconInbox size={15} />}
          onClick={() => onNavigate("replies")}
          actionLabel="Read them"
        />
        <StatTile
          label="Interviews and offers"
          value={stats?.positive ?? 0}
          hint={`${percent(stats?.interview_rate ?? 0, 1)} conversion from sent`}
          icon={<IconCheck size={15} />}
          onClick={() => onNavigate("applications", "interview")}
          actionLabel="See them"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <div className="card p-5">
          <SectionTitle
            title="Sending rhythm"
            subtitle="Applications per day over the last 30 days"
          />
          <AreaChart points={sends.map((day) => ({ label: day.day, value: day.n }))} />
        </div>

        <div className="card p-5">
          <SectionTitle title="Pipeline" subtitle="Where every discovered role sits" />
          {statusPoints.length ? (
            <BarBreakdown
              points={statusPoints}
              onSelect={(label) =>
                onNavigate("jobs", label.toLowerCase().replace(/ /g, "_"))
              }
            />
          ) : (
            <p className="py-8 text-center text-xs text-muted">Run discover to fill the pipeline.</p>
          )}
        </div>
      </section>

      {(profile?.readiness ?? []).some((check) => !check.ready) ? (
        <Readiness checks={profile?.readiness ?? []} />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <div className="card overflow-hidden">
          <div className="px-5 pb-1 pt-5">
            <SectionTitle title="Best matches right now" subtitle="Ranked by how well they fit your profile" />
          </div>
          <JobsTable jobs={jobs.slice(0, 7)} loading={loading} onSelect={onSelect} compact />
        </div>

        <div className="flex flex-col gap-4">
          <div className="card p-5">
            <SectionTitle title="Follow ups due" subtitle="Sent into the original thread" />
            <FollowupList
              followups={followups}
              onSelect={(jobId) => {
                const job = jobs.find((candidate) => candidate.id === jobId);
                if (job) onSelect(job);
                else onNavigate("applications", "sent");
              }}
            />
          </div>
          <div className="card p-5">
            <SectionTitle title="Recent activity" />
            <ActivityFeed events={events.slice(0, 7)} />
          </div>
        </div>
      </section>
    </div>
  );
}
