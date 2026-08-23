/**
 * The review surface. Everything needed to decide on one application lives
 * here: why it scored what it scored, what was written, and the two actions
 * that matter (draft it, approve it). Approval is deliberately a click a human
 * has to make.
 */
import { useEffect, useState } from "react";
import { api } from "../api";
import { relativeTime, titleCase } from "../lib/format";
import type { Application, Contact, Job } from "../types";
import {
  IconCheck,
  IconClose,
  IconDocument,
  IconExternal,
  IconSparkle,
} from "./Icons";
import { ApplyPack } from "./ApplyPack";
import { CompanyMark, Pill, ScoreDial, Skeleton, StatusPill } from "./Primitives";

type Tab = "match" | "draft" | "apply" | "posting";

export function JobDrawer({
  jobId,
  onClose,
  onChanged,
  notify,
}: {
  jobId: number | null;
  onClose: () => void;
  onChanged: () => void;
  notify: (tone: "info" | "success" | "error", message: string, detail?: string) => void;
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [application, setApplication] = useState<Application | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [tab, setTab] = useState<Tab>("match");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    setLoading(true);
    api
      .job(jobId)
      .then((payload) => {
        if (cancelled) return;
        setJob(payload.job);
        setApplication(payload.application);
        setContacts(payload.contacts);
        setTab(payload.application ? "draft" : "match");
      })
      .catch((error: Error) => notify("error", "Could not load that job", error.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [jobId, notify]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!jobId) return null;

  const breakdown = job?.score_breakdown ?? {};
  const signals = Object.entries(breakdown.signals ?? {});
  const maxSignal = Math.max(1, ...signals.map(([, value]) => value));

  async function draft() {
    if (!job) return;
    setBusy(true);
    try {
      const result = await api.draftJob(job.id);
      setApplication(result.application);
      setTab("draft");
      onChanged();
      notify("success", "Draft written", `${job.title} at ${job.company_name}`);
    } catch (error) {
      notify("error", "Drafting failed", (error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!application) return;
    setBusy(true);
    try {
      await api.approve(application.id);
      setApplication({ ...application, status: "approved" });
      onChanged();
      notify("success", "Approved", "It will go out on the next send run.");
    } catch (error) {
      notify("error", "Could not approve", (error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close panel"
        onClick={onClose}
        className="fixed inset-0 z-30 cursor-default"
        style={{ background: "color-mix(in oklab, var(--ink) 28%, transparent)" }}
      />
      <aside
        className="animate-slide-in fixed right-0 top-0 z-40 flex h-screen w-full max-w-[620px] flex-col border-l"
        style={{ background: "var(--surface)", borderColor: "var(--line)" }}
        role="dialog"
        aria-modal="true"
        aria-label="Job detail"
      >
        {loading || !job ? (
          <div className="flex flex-col gap-3 p-6">
            <Skeleton className="h-12 w-2/3" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <>
            <header
              className="flex items-start gap-3 border-b px-5 py-4"
              style={{ borderColor: "var(--line)" }}
            >
              <CompanyMark name={job.company_name} size={42} />
              <div className="min-w-0 flex-1">
                <h2 className="text-[16.5px] font-semibold leading-tight text-ink">{job.title}</h2>
                <p className="mt-0.5 text-[13.5px] text-muted">
                  {job.company_name}
                  {job.location ? ` · ${job.location}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <StatusPill status={application?.status ?? job.status} />
                  {job.remote ? <Pill tone="accent">Remote</Pill> : null}
                  <Pill>{job.source}</Pill>
                  {relativeTime(job.posted_at) ? (
                    <Pill>posted {relativeTime(job.posted_at)}</Pill>
                  ) : null}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <ScoreDial value={job.score} size={46} />
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg p-1.5 text-muted hover:text-ink"
                  aria-label="Close"
                >
                  <IconClose size={16} />
                </button>
              </div>
            </header>

            <nav
              className="flex gap-1 border-b px-4 py-2"
              style={{ borderColor: "var(--line)" }}
            >
              {(
                [
                  ["match", "Why it matched"],
                  ["draft", application ? "Draft" : "Draft (none yet)"],
                  ...(application?.channel === "portal"
                    ? ([["apply", "Apply pack"]] as [Tab, string][])
                    : []),
                  ["posting", "Job posting"],
                ] as [Tab, string][]
              ).map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setTab(key)}
                  className="rounded-lg px-3 py-1.5 text-[13.5px] font-medium transition-colors"
                  style={{
                    background: tab === key ? "var(--surface-3)" : "transparent",
                    color: tab === key ? "var(--ink)" : "var(--muted)",
                  }}
                >
                  {label}
                </button>
              ))}
            </nav>

            <div className="flex-1 overflow-y-auto px-5 py-4">
              {tab === "match" ? (
                <div className="flex flex-col gap-5">
                  <section>
                    <h3 className="mb-2.5 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                      Score breakdown
                    </h3>
                    <ul className="flex flex-col gap-2">
                      {signals.map(([name, value]) => (
                        <li key={name} className="grid grid-cols-[5.5rem_1fr_2rem] items-center gap-3">
                          <span className="text-[13px] text-muted">{titleCase(name)}</span>
                          <span
                            className="h-1.5 overflow-hidden rounded-full"
                            style={{ background: "var(--surface-3)" }}
                          >
                            <span
                              className="block h-full rounded-full"
                              style={{
                                width: `${(value / maxSignal) * 100}%`,
                                background: "var(--accent)",
                              }}
                            />
                          </span>
                          <span className="text-right text-[13px] font-semibold tabular text-ink">
                            {value.toFixed(0)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </section>

                  {breakdown.blockers?.length ? (
                    <section>
                      <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                        Blocked because
                      </h3>
                      <ul className="flex flex-col gap-1.5">
                        {breakdown.blockers.map((blocker) => (
                          <li
                            key={blocker}
                            className="rounded-lg px-2.5 py-1.5 text-[13px]"
                            style={{ background: "var(--danger-soft)", color: "var(--danger)" }}
                          >
                            {blocker}
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  {breakdown.reasons?.length ? (
                    <section>
                      <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                        Reasoning
                      </h3>
                      <ul className="flex flex-col gap-1">
                        {breakdown.reasons.map((reason) => (
                          <li key={reason} className="text-[13.5px] leading-relaxed text-ink-2">
                            {reason}
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}

                  {breakdown.matched_skills?.length ? (
                    <section>
                      <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                        Your skills this role asks for
                      </h3>
                      <div className="flex flex-wrap gap-1.5">
                        {breakdown.matched_skills.map((skill) => (
                          <Pill key={skill} tone="positive">
                            {skill}
                          </Pill>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  {breakdown.missing_skills?.length ? (
                    <section>
                      <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                        Asked for, not on your profile
                      </h3>
                      <div className="flex flex-wrap gap-1.5">
                        {breakdown.missing_skills.map((skill) => (
                          <Pill key={skill} tone="warning">
                            {skill}
                          </Pill>
                        ))}
                      </div>
                    </section>
                  ) : null}

                  {contacts.length ? (
                    <section>
                      <h3 className="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                        Contacts found
                      </h3>
                      <ul className="flex flex-col gap-1.5">
                        {contacts.map((contact) => (
                          <li
                            key={contact.id}
                            className="flex items-center justify-between rounded-lg border px-2.5 py-2"
                            style={{ borderColor: "var(--line)" }}
                          >
                            <span className="min-w-0">
                              <span className="block truncate text-[13.5px] text-ink">
                                {contact.name || contact.email}
                              </span>
                              <span className="block truncate text-[12px] text-muted">
                                {contact.title || contact.email}
                              </span>
                            </span>
                            <Pill tone={contact.verified ? "positive" : "neutral"}>
                              {contact.source}
                            </Pill>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}
                </div>
              ) : null}

              {tab === "draft" ? (
                application ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Pill tone="accent">
                        <IconSparkle size={11} />
                        {application.generator}
                      </Pill>
                      <Pill tone={application.channel === "email" ? "positive" : "warning"}>
                        {application.channel === "email" ? "email" : "apply on their portal"}
                      </Pill>
                      {application.recipient_email ? (
                        <Pill>{application.recipient_email}</Pill>
                      ) : null}
                    </div>

                    {application.notes ? (
                      <p
                        className="rounded-lg px-3 py-2 text-[13px]"
                        style={{ background: "var(--warning-soft)", color: "var(--warning)" }}
                      >
                        Style check: {application.notes}
                      </p>
                    ) : null}

                    <div>
                      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                        Subject
                      </p>
                      <p className="text-[14.5px] font-medium text-ink">{application.subject}</p>
                    </div>

                    <div>
                      <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
                        Email body
                      </p>
                      <pre
                        className="whitespace-pre-wrap rounded-xl border p-3.5 font-sans text-[13.5px] leading-relaxed text-ink-2"
                        style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
                      >
                        {application.body}
                      </pre>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {[
                        ["Cover letter", application.cover_letter_path],
                        ["Tailored CV", application.cv_path],
                      ]
                        .filter(([, path]) => Boolean(path))
                        .map(([label, path]) => (
                          <span
                            key={label}
                            className="flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[12.5px] text-muted"
                            style={{ borderColor: "var(--line)" }}
                            title={path}
                          >
                            <IconDocument size={13} />
                            {label}
                          </span>
                        ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-start gap-3 py-8">
                    <p className="text-[14px] text-muted">
                      Nothing written for this role yet. Drafting produces a tailored cover letter,
                      a CV reordered for this posting, and the email that carries them.
                    </p>
                    <button type="button" className="btn btn-primary" onClick={draft} disabled={busy}>
                      <IconSparkle size={15} />
                      Write the application
                    </button>
                  </div>
                )
              ) : null}

              {tab === "apply" && application ? (
                <ApplyPack jobId={job.id} onSubmitted={onChanged} notify={notify} />
              ) : null}

              {tab === "posting" ? (
                <div className="flex flex-col gap-3">
                  {job.url ? (
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="btn btn-ghost self-start"
                    >
                      <IconExternal size={14} />
                      Open the original posting
                    </a>
                  ) : null}
                  <pre
                    className="whitespace-pre-wrap font-sans text-[13.5px] leading-relaxed text-ink-2"
                    style={{ wordBreak: "break-word" }}
                  >
                    {job.description || "This board published no description."}
                  </pre>
                </div>
              ) : null}
            </div>

            <footer
              className="flex items-center justify-between gap-3 border-t px-5 py-3.5"
              style={{ borderColor: "var(--line)" }}
            >
              <span className="text-[12.5px] text-muted">
                {application
                  ? `Application ${application.id} · updated ${relativeTime(application.updated_at)}`
                  : "No application yet"}
              </span>
              <div className="flex gap-2">
                {application ? (
                  <button type="button" className="btn btn-ghost" onClick={draft} disabled={busy}>
                    Rewrite
                  </button>
                ) : null}
                {application && application.status === "draft" && application.channel === "email" ? (
                  <button type="button" className="btn btn-primary" onClick={approve} disabled={busy}>
                    <IconCheck size={15} />
                    Approve for sending
                  </button>
                ) : null}
                {application && application.channel === "portal" && application.status !== "sent" ? (
                  <>
                    <button type="button" className="btn btn-ghost" onClick={() => setTab("apply")}>
                      <IconDocument size={14} />
                      Apply pack
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await api.setApplicationStatus(application.id, "sent");
                          setApplication({ ...application, status: "sent" });
                          onChanged();
                          notify("success", "Marked as applied", "Follow ups are now scheduled.");
                        } catch (error) {
                          notify("error", "Could not update", (error as Error).message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      <IconCheck size={15} />
                      I submitted this
                    </button>
                  </>
                ) : null}
                {!application ? (
                  <button type="button" className="btn btn-primary" onClick={draft} disabled={busy}>
                    <IconSparkle size={15} />
                    Draft
                  </button>
                ) : null}
              </div>
            </footer>
          </>
        )}
      </aside>
    </>
  );
}
