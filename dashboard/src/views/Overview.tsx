import { AreaChart } from "../components/Charts";
import { ActivityFeed, FollowupList } from "../components/ActivityFeed";
import { Funnel } from "../components/Funnel";
import { JobsTable } from "../components/JobsTable";
import { Readiness } from "../components/Readiness";
import { SectionTitle } from "../components/Primitives";
import { IconArrowRight } from "../components/Icons";
import { percent } from "../lib/format";
import type { ActivityEvent, Job, PendingFollowup, Profile, Stats } from "../types";

/**
 * One sentence saying what is actually waiting, so the top of the page answers
 * "what should I do now" rather than restating figures that are already on
 * screen a few pixels below.
 */
function nextAction(stats: Stats | null): { text: string; target?: [string, string] } {
  if (!stats) return { text: "Loading your pipeline." };
  const drafts = stats.applications_by_status?.draft ?? 0;
  const approved = stats.applications_by_status?.approved ?? 0;
  const shortlisted = stats.jobs_by_status?.shortlisted ?? 0;

  if (drafts) {
    return {
      text: `${drafts} draft${drafts === 1 ? "" : "s"} waiting for your review.`,
      target: ["applications", "draft"],
    };
  }
  if (approved) {
    return {
      text: `${approved} approved and ready for the next send run.`,
      target: ["applications", "approved"],
    };
  }
  if (shortlisted) {
    return {
      text: `${shortlisted} shortlisted role${shortlisted === 1 ? "" : "s"} with nothing drafted yet.`,
      target: ["jobs", "shortlist"],
    };
  }
  return { text: "Run discover to pull today's openings." };
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
  const sends = stats?.sends_by_day ?? [];
  const thisWeek = sends.slice(-7).reduce((total, day) => total + day.n, 0);
  const lastWeek = sends.slice(-14, -7).reduce((total, day) => total + day.n, 0);
  const action = nextAction(stats);

  return (
    <div className="flex flex-col gap-4">
      {/* The funnel and the one sentence above it are the page's thesis. The
          panel is flush so the six stages read as one object divided by
          hairlines, not as six cards. */}
      <section className="panel-flush order-1">
        <div
          className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b px-4 py-3.5"
          style={{ borderColor: "var(--line)" }}
        >
          <h2 className="text-ink">
            {firstName ? `${firstName}, ` : ""}
            <span className="font-normal text-ink-2">{action.text}</span>
          </h2>
          {action.target ? (
            <button
              type="button"
              className="btn btn-quiet btn-sm"
              onClick={() =>
                onNavigate(action.target![0] as "jobs" | "applications", action.target![1])
              }
            >
              Take me there
              <IconArrowRight size={12} />
            </button>
          ) : null}
        </div>

        <div style={{ background: "var(--line)" }}>
          <Funnel stats={stats} onNavigate={onNavigate} />
        </div>
      </section>

      <section className="order-4 grid items-start gap-4 xl:order-2 xl:grid-cols-[1.7fr_1fr]">
        <div className="panel p-4">
          <SectionTitle
            title="Sending rhythm"
            subtitle={
              sends.length
                ? `${thisWeek} sent this week against ${lastWeek} last week · ${percent(stats?.reply_rate ?? 0, 1)} reply rate`
                : "Applications per day over the last 30 days"
            }
          />
          <AreaChart points={sends.map((day) => ({ label: day.day, value: day.n }))} />
        </div>

        <div className="panel p-4">
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
      </section>

      {(profile?.readiness ?? []).some((check) => !check.ready) ? (
        <div className="order-3">
          <Readiness checks={profile?.readiness ?? []} />
        </div>
      ) : null}

      <section className="order-2 grid items-start gap-4 xl:order-4 xl:grid-cols-[1.7fr_1fr]">
        <div className="panel-flush">
          <div
            className="flex items-center justify-between border-b px-4 py-3"
            style={{ borderColor: "var(--line)" }}
          >
            <div>
              <h2 className="text-ink">Best matches right now</h2>
              <p className="mt-0.5 text-label text-muted">
                Ranked by how well they fit your profile
              </p>
            </div>
            <button
              type="button"
              className="btn btn-quiet btn-sm"
              onClick={() => onNavigate("jobs", "shortlist")}
            >
              All matches
              <IconArrowRight size={12} />
            </button>
          </div>
          <JobsTable jobs={jobs.slice(0, 7)} loading={loading} onSelect={onSelect} compact />
        </div>

        <div className="panel p-4">
          <SectionTitle title="Recent activity" subtitle="Every stage you run is logged" />
          <ActivityFeed events={events.slice(0, 7)} />
        </div>
      </section>
    </div>
  );
}
