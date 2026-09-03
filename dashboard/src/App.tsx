import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { JobDrawer } from "./components/JobDrawer";
import { MobileNav, Sidebar, type ViewKey } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { Toasts, type Toast } from "./components/Toasts";
import { useRoute } from "./lib/router";
import { applyTheme, currentTheme, type Theme } from "./lib/theme";
import { Applications } from "./views/Applications";
import { Jobs } from "./views/Jobs";
import { Overview } from "./views/Overview";
import { Replies } from "./views/Replies";
import { Settings } from "./views/Settings";
import type {
  ActivityEvent,
  Application,
  Job,
  PendingFollowup,
  Profile,
  Reply,
  SessionState,
  Stats,
  TaskStatus,
} from "./types";

const TITLES: Record<ViewKey, { title: string; subtitle: string }> = {
  overview: { title: "Overview", subtitle: "Your search, end to end" },
  jobs: { title: "Job matches", subtitle: "Scored against your profile, highest first" },
  applications: { title: "Applications", subtitle: "Review, approve, and track what happens next" },
  replies: { title: "Replies", subtitle: "What came back, and what it means" },
  settings: { title: "Profile and guardrails", subtitle: "What the engine knows and what it will not do" },
};

const JOB_FILTERS: Record<string, { status?: string; min_score?: number }> = {
  shortlist: { min_score: 60 },
  all: {},
  drafted: { status: "drafted" },
  applied: { status: "applied" },
  blocked: { status: "rejected_by_me" },
};

const VIEWS: ViewKey[] = ["overview", "jobs", "applications", "replies", "settings"];

export default function App() {
  const [route, navigate] = useRoute();
  const view: ViewKey = VIEWS.includes(route.view as ViewKey)
    ? (route.view as ViewKey)
    : "overview";
  const selectedJob = route.jobId;
  const setView = (next: ViewKey) => navigate({ view: next, jobId: null });

  // A figure on the overview should lead to the rows behind it, with the right
  // filter already applied, rather than dropping the user on an unfiltered list.
  const goTo = (next: "jobs" | "applications" | "replies", filter?: string) => {
    if (next === "jobs" && filter) setJobFilter(filter in JOB_FILTERS ? filter : "all");
    if (next === "applications") setAppFilter(filter ?? "");
    navigate({ view: next, jobId: null });
  };
  const setSelectedJob = (jobId: number | null) => navigate({ view, jobId });
  const [theme, setTheme] = useState<Theme>(() => currentTheme());
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [jobFilter, setJobFilter] = useState("shortlist");
  const [appFilter, setAppFilter] = useState("");

  const [stats, setStats] = useState<Stats | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [applicationCounts, setApplicationCounts] = useState<Record<string, number>>({});
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [replies, setReplies] = useState<Reply[]>([]);
  const [session, setSession] = useState<SessionState | null>(null);
  const [followups, setFollowups] = useState<PendingFollowup[]>([]);

  const [loadingJobs, setLoadingJobs] = useState(true);
  const [running, setRunning] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback(
    (tone: Toast["tone"], message: string, detail?: string) => {
      setToasts((current) => [...current, { id: Date.now() + Math.random(), tone, message, detail }]);
    },
    [],
  );

  const dismiss = useCallback(
    (id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)),
    [],
  );

  // Typing in the search box should not fire a request per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search), 260);
    return () => window.clearTimeout(timer);
  }, [search]);

  const loadJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const filter = JOB_FILTERS[jobFilter] ?? {};
      const payload = await api.jobs({
        ...filter,
        search: debouncedSearch || undefined,
        limit: 60,
      });
      setJobs(payload.jobs);
    } catch (error) {
      notify("error", "Could not load jobs", (error as Error).message);
    } finally {
      setLoadingJobs(false);
    }
  }, [jobFilter, debouncedSearch, notify]);

  const loadSupporting = useCallback(async () => {
    const [statsResult, eventsResult, followupsResult, appsResult, repliesResult] =
      await Promise.allSettled([
        api.stats(),
        api.events(24),
        api.followups(),
        api.applications(appFilter || undefined),
        api.replies(),
      ]);

    if (statsResult.status === "fulfilled") setStats(statsResult.value);
    if (eventsResult.status === "fulfilled") setEvents(eventsResult.value.events);
    if (followupsResult.status === "fulfilled") setFollowups(followupsResult.value.followups);
    if (appsResult.status === "fulfilled") {
      setApplications(appsResult.value.applications);
      setApplicationCounts(appsResult.value.counts ?? {});
    }
    if (repliesResult.status === "fulfilled") setReplies(repliesResult.value.replies);

    if (statsResult.status === "rejected") {
      notify(
        "error",
        "The API is not answering",
        "Start it with: python3 -m jobseeker serve",
      );
    }
  }, [appFilter, notify]);

  useEffect(() => {
    api
      .profile()
      .then(setProfile)
      .catch(() => undefined);
    api
      .session()
      .then(setSession)
      .catch(() => undefined);
    api
      .runStatus()
      .then((status) => {
        if (status.status === "running" && status.stage) setRunning(status.stage);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    void loadSupporting();
  }, [loadSupporting]);

  const refresh = useCallback(() => {
    void loadJobs();
    void loadSupporting();
  }, [loadJobs, loadSupporting]);

  async function runStage(stage: string) {
    setRunning(stage);
    try {
      await api.run(stage);
    } catch (error) {
      setRunning(null);
      notify("error", `${stage} could not start`, (error as Error).message);
      return;
    }

    notify("info", `${stage} started`, "This can take a few minutes. You can keep working.");

    // Poll until the worker reports back. Nothing here holds a request open, so
    // a long stage is not at the mercy of the host's request timeout.
    const deadline = Date.now() + 20 * 60 * 1000;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 2500));

      let status: TaskStatus;
      try {
        status = await api.runStatus();
      } catch {
        continue; // a single failed poll is not a failed stage
      }

      if (status.status === "running") continue;

      if (status.status === "failed") {
        notify("error", `${stage} failed`, status.error ?? "no detail given");
      } else if (status.status === "finished" && status.result) {
        const summary = Object.entries(status.result.counts)
          .map(([key, value]) => `${value} ${key}`)
          .join(", ");
        notify("success", `${stage} finished`, summary || "nothing to do");
        if (status.result.messages.length) {
          notify("info", "Notes from this run", status.result.messages[0]);
        }
      }
      break;
    }

    setRunning(null);
    refresh();
  }

  async function importUrl(url: string) {
    try {
      const payload = await api.importUrl(url);
      notify("success", "Job added", `${payload.job.title} at ${payload.job.company_name}`);
      refresh();
      setSelectedJob(payload.job.id);
    } catch (error) {
      notify("error", "Could not add that URL", (error as Error).message);
    }
  }

  const counts = useMemo(
    () => ({
      jobs: stats?.jobs_by_status?.shortlisted ?? 0,
      applications: stats?.applications_by_status?.draft ?? 0,
      replies: replies.length,
    }),
    [stats, replies.length],
  );

  return (
    <div className="flex min-h-screen">
      <Sidebar
        view={view}
        onChange={setView}
        theme={theme}
        onThemeChange={(next) => {
          applyTheme(next);
          setTheme(next);
        }}
        profile={profile}
        counts={counts}
        session={session}
        stats={stats}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <MobileNav view={view} onChange={setView} />
        <TopBar
          title={TITLES[view].title}
          subtitle={TITLES[view].subtitle}
          search={search}
          onSearch={setSearch}
          onRun={runStage}
          running={running}
          stats={stats}
        />

        <main className="flex-1 px-4 py-4 lg:px-6">
          {view === "overview" ? (
            <Overview
              stats={stats}
              jobs={jobs}
              events={events}
              followups={followups}
              loading={loadingJobs}
              profile={profile}
              onSelect={(job) => setSelectedJob(job.id)}
              onNavigate={goTo}
            />
          ) : null}

          {view === "jobs" ? (
            <Jobs
              jobs={jobs}
              loading={loadingJobs}
              filter={jobFilter}
              onFilter={setJobFilter}
              onSelect={(job) => setSelectedJob(job.id)}
              selectedId={selectedJob}
              onImport={importUrl}
            />
          ) : null}

          {view === "applications" ? (
            <Applications
              applications={applications}
              counts={applicationCounts}
              filter={appFilter}
              onFilter={setAppFilter}
              onApprove={async (id) => {
                try {
                  await api.approve(id);
                  notify("success", "Approved", "It will go out on the next send run.");
                  refresh();
                } catch (error) {
                  notify("error", "Could not approve", (error as Error).message);
                }
              }}
              onStatus={async (id, status) => {
                try {
                  await api.setApplicationStatus(id, status);
                  notify("success", `Marked ${status}`);
                  refresh();
                } catch (error) {
                  notify("error", "Could not update", (error as Error).message);
                }
              }}
              onOpenJob={setSelectedJob}
            />
          ) : null}

          {view === "replies" ? <Replies replies={replies} /> : null}
          {view === "settings" ? (
            <Settings profile={profile} stats={stats} session={session} />
          ) : null}
        </main>
      </div>

      <JobDrawer
        jobId={selectedJob}
        onClose={() => setSelectedJob(null)}
        onChanged={refresh}
        notify={notify}
      />
      <Toasts toasts={toasts} onDismiss={dismiss} />
    </div>
  );
}
