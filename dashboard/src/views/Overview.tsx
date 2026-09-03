/**
 * The Overview.
 *
 * Composition note, because this changed twice.
 *
 * It was four identical stat cards over a chart, which is the category default
 * and says nothing: the pipeline figures are not peers, each one is a survivor
 * of the one before it. So they became a funnel.
 *
 * Then it was six rounded panels floating in a padded grid, which is the other
 * category default. Card chrome doubled every border, spent the gutter twice,
 * and on a phone left about a third of the viewport to padding. Now the page is
 * one continuous surface: full bleed regions divided by hairlines, with the
 * secondary column held by a single vertical rule rather than by three more
 * boxes. The queue is the protagonist and sits directly under the funnel.
 */
import { AreaChart } from "../components/Charts";
import { ActivityFeed, FollowupList } from "../components/ActivityFeed";
import { Funnel } from "../components/Funnel";
import { JobsTable } from "../components/JobsTable";
import { Readiness } from "../components/Readiness";
import { IconArrowRight } from "../components/Icons";
import { percent } from "../lib/format";
import type { ActivityEvent, Job, PendingFollowup, Profile, Stats } from "../types";

/**
 * One sentence saying what is actually waiting, so the top of the page answers
 * "what should I do now" rather than restating figures that are on screen a few
 * pixels below.
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

/** A heading inside a region. No card, no kicker. */
function RegionHead({
  title,
  meta,
  action,
}: {
  title: string;
  meta?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h2 className="text-ink">{title}</h2>
        {meta ? <p className="mt-0.5 text-label leading-snug text-muted">{meta}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
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
  const outstanding = (profile?.readiness ?? []).some((check) => !check.ready);

  return (
    <div>
      {/* The one sentence and the funnel are the page's thesis. */}
      <section className="region px-4 py-3 lg:px-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
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
      </section>

      {/* The hairline grid gap draws the divisions between stages. */}
      <section className="region" style={{ background: "var(--line)" }}>
        <Funnel stats={stats} onNavigate={onNavigate} />
      </section>

      <div className="xl:flex xl:items-stretch">
        <div className="min-w-0 xl:flex-1">
          {/* The queue is the protagonist, so it comes first and runs to the
              edges of its column. */}
          <section className="region">
            <div className="px-4 pb-1 pt-3.5 lg:px-6">
              <RegionHead
                title="Best matches right now"
                meta="Ranked by how well they fit your profile"
                action={
                  <button
                    type="button"
                    className="btn btn-quiet btn-sm"
                    onClick={() => onNavigate("jobs", "shortlist")}
                  >
                    All matches
                    <IconArrowRight size={12} />
                  </button>
                }
              />
            </div>
            <JobsTable jobs={jobs.slice(0, 8)} loading={loading} onSelect={onSelect} compact />
          </section>

          {outstanding ? (
            <section className="region region-pad">
              <Readiness checks={profile?.readiness ?? []} />
            </section>
          ) : null}

          <section className="region region-pad">
            <RegionHead
              title="Sending rhythm"
              meta={
                sends.length
                  ? `${thisWeek} sent this week against ${lastWeek} last week · ${percent(stats?.reply_rate ?? 0, 1)} reply rate`
                  : "Applications per day over the last 30 days"
              }
            />
            <AreaChart points={sends.map((day) => ({ label: day.day, value: day.n }))} />
          </section>
        </div>

        {/* Secondary column. One vertical hairline, not three more panels. */}
        <aside className="rail shrink-0 xl:w-[21rem]">
          <section className="region region-pad">
            <RegionHead title="Follow ups due" meta="Sent into the original thread" />
            <FollowupList
              followups={followups}
              onSelect={(jobId) => {
                const job = jobs.find((candidate) => candidate.id === jobId);
                if (job) onSelect(job);
                else onNavigate("applications", "sent");
              }}
            />
          </section>

          <section className="region-pad">
            <RegionHead title="Recent activity" meta="Every stage you run is logged" />
            <ActivityFeed events={events.slice(0, 6)} />
          </section>
        </aside>
      </div>
    </div>
  );
}
