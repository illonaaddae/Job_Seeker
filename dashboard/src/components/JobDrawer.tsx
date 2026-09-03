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
  IconAlert,
  IconCheck,
  IconClose,
  IconDocument,
  IconExternal,
  IconSparkle,
} from "./Icons";
import { ApplyPack } from "./ApplyPack";
import { CompanyMark, Meter, Score, Skeleton, StatusTag, Tag } from "./Primitives";

type Tab = "match" | "draft" | "apply" | "posting";

/** A titled block inside the drawer. The label names the block; there is no
    decorative kicker above it. */
function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <p className="label mb-2">{title}</p>
      {children}
    </section>
  );
}

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

  const tabs = (
    [
      ["match", "Why it matched"],
      ["draft", "Draft"],
      ...(application?.channel === "portal" ? ([["apply", "Apply pack"]] as [Tab, string][]) : []),
      ["posting", "Job posting"],
    ] as [Tab, string][]
  );

  return (
    <>
      <button
        type="button"
        aria-label="Close panel"
        onClick={onClose}
        className="animate-scrim fixed inset-0 z-30 cursor-default"
        style={{ background: "var(--scrim)" }}
      />
      <aside
        className="animate-drawer fixed right-0 top-0 z-40 flex h-screen w-full max-w-[640px] flex-col border-l"
        style={{
          background: "var(--surface)",
          borderColor: "var(--line-strong)",
          boxShadow: "var(--shadow-pop)",
        }}
        role="dialog"
        aria-modal="true"
        aria-label="Job detail"
      >
        {loading || !job ? (
          <div className="flex flex-col gap-3 p-5">
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <>
            <header
              className="flex items-start gap-3 border-b px-4 py-3.5"
              style={{ borderColor: "var(--line)" }}
            >
              <CompanyMark name={job.company_name} size={34} />
              <div className="min-w-0 flex-1">
                <h2 className="text-ink">{job.title}</h2>
                <p className="mt-0.5 text-label text-muted">
                  {job.company_name}
                  {job.location ? ` · ${job.location}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <StatusTag status={application?.status ?? job.status} />
                  {job.remote ? <Tag tone="info">Remote</Tag> : null}
                  <Tag>{job.source}</Tag>
                  {relativeTime(job.posted_at) ? (
                    <Tag bare>posted {relativeTime(job.posted_at)}</Tag>
                  ) : null}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3">
                <Score value={job.score} size="lg" />
                <button
                  type="button"
                  onClick={onClose}
                  className="btn btn-quiet"
                  style={{ minHeight: 26, padding: 4 }}
                  aria-label="Close"
                >
                  <IconClose size={14} />
                </button>
              </div>
            </header>

            <nav className="border-b px-4 py-2" style={{ borderColor: "var(--line)" }}>
              <div className="segmented">
                {tabs.map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setTab(key)}
                    aria-pressed={tab === key}
                    className="segment"
                  >
                    {label}
                  </button>
                ))}
              </div>
            </nav>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              {tab === "match" ? (
                <div className="flex flex-col gap-5">
                  <Block title="Score breakdown">
                    <ul className="flex flex-col gap-2">
                      {signals.map(([name, value]) => (
                        <li
                          key={name}
                          className="grid items-center gap-3"
                          style={{ gridTemplateColumns: "6rem 1fr 2rem" }}
                        >
                          <span className="clip text-label text-muted">{titleCase(name)}</span>
                          <Meter value={value} max={maxSignal} />
                          <span
                            className="tabular text-right text-label text-ink-2"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {value.toFixed(0)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Block>

                  {breakdown.blockers?.length ? (
                    <Block title="Blocked because">
                      <ul className="flex flex-col gap-1.5">
                        {breakdown.blockers.map((blocker) => (
                          <li
                            key={blocker}
                            className="flex items-start gap-2 rounded-[8px] border px-2.5 py-1.5 text-[0.8125rem] leading-relaxed text-ink-2"
                            style={{
                              borderColor: "color-mix(in oklab, var(--st-red) 35%, var(--line))",
                              background: "var(--surface-2)",
                            }}
                          >
                            <IconAlert
                              size={13}
                              style={{ color: "var(--st-red)", marginTop: 2, flexShrink: 0 }}
                            />
                            {blocker}
                          </li>
                        ))}
                      </ul>
                    </Block>
                  ) : null}

                  {breakdown.reasons?.length ? (
                    <Block title="Reasoning">
                      <ul className="flex max-w-[70ch] flex-col gap-1.5">
                        {breakdown.reasons.map((reason) => (
                          <li
                            key={reason}
                            className="text-[0.8125rem] leading-relaxed text-ink-2"
                          >
                            {reason}
                          </li>
                        ))}
                      </ul>
                    </Block>
                  ) : null}

                  {breakdown.matched_skills?.length ? (
                    <Block title="Your skills this role asks for">
                      <div className="flex flex-wrap gap-1.5">
                        {breakdown.matched_skills.map((skill) => (
                          <Tag key={skill} tone="positive">
                            {skill}
                          </Tag>
                        ))}
                      </div>
                    </Block>
                  ) : null}

                  {breakdown.missing_skills?.length ? (
                    <Block title="Asked for, not on your profile">
                      <div className="flex flex-wrap gap-1.5">
                        {breakdown.missing_skills.map((skill) => (
                          <Tag key={skill} tone="warning">
                            {skill}
                          </Tag>
                        ))}
                      </div>
                    </Block>
                  ) : null}

                  {contacts.length ? (
                    <Block title="Contacts found">
                      <ul className="flex flex-col gap-1.5">
                        {contacts.map((contact) => (
                          <li
                            key={contact.id}
                            className="flex items-center justify-between gap-3 rounded-[8px] border px-2.5 py-2"
                            style={{ borderColor: "var(--line)" }}
                          >
                            <span className="min-w-0">
                              <span className="clip block text-[0.8125rem] text-ink">
                                {contact.name || contact.email}
                              </span>
                              <span className="clip block text-micro text-muted">
                                {contact.title || contact.email}
                              </span>
                            </span>
                            <Tag tone={contact.verified ? "positive" : "neutral"}>
                              {contact.source}
                            </Tag>
                          </li>
                        ))}
                      </ul>
                    </Block>
                  ) : null}
                </div>
              ) : null}

              {tab === "draft" ? (
                application ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Tag tone="info">
                        <IconSparkle size={10} />
                        {application.generator}
                      </Tag>
                      <Tag tone={application.channel === "email" ? "positive" : "warning"}>
                        {application.channel === "email" ? "email" : "apply on their portal"}
                      </Tag>
                      {application.recipient_email ? <Tag>{application.recipient_email}</Tag> : null}
                    </div>

                    {application.notes ? (
                      <p
                        className="flex items-start gap-2 rounded-[8px] border px-2.5 py-2 text-[0.8125rem] leading-relaxed text-ink-2"
                        style={{
                          borderColor: "color-mix(in oklab, var(--st-amber) 40%, var(--line))",
                          background: "var(--surface-2)",
                        }}
                      >
                        <IconAlert
                          size={13}
                          style={{ color: "var(--st-amber)", marginTop: 2, flexShrink: 0 }}
                        />
                        <span>
                          <span className="font-medium text-ink">Style check:</span>{" "}
                          {application.notes}
                        </span>
                      </p>
                    ) : null}

                    <Block title="Subject">
                      <p className="text-body font-medium text-ink">{application.subject}</p>
                    </Block>

                    <Block title="Email body">
                      <pre
                        className="whitespace-pre-wrap rounded-[8px] border p-3 font-sans text-[0.8125rem] leading-relaxed text-ink-2"
                        style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
                      >
                        {application.body}
                      </pre>
                    </Block>

                    {[
                      ["Cover letter", application.cover_letter_path],
                      ["Tailored CV", application.cv_path],
                    ].some(([, path]) => Boolean(path)) ? (
                      <div className="flex flex-wrap gap-1.5">
                        {[
                          ["Cover letter", application.cover_letter_path],
                          ["Tailored CV", application.cv_path],
                        ]
                          .filter(([, path]) => Boolean(path))
                          .map(([label, path]) => (
                            <Tag key={label} title={path}>
                              <IconDocument size={11} style={{ color: "var(--ink-tertiary)" }} />
                              {label}
                            </Tag>
                          ))}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="flex max-w-[52ch] flex-col items-start gap-3 py-6">
                    <p className="text-[0.8125rem] leading-relaxed text-muted">
                      Nothing written for this role yet. Drafting produces a tailored cover letter,
                      a CV reordered for this posting, and the email that carries them.
                    </p>
                    <button type="button" className="btn btn-primary" onClick={draft} disabled={busy}>
                      <IconSparkle size={14} />
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
                      className="btn btn-secondary self-start no-underline"
                    >
                      <IconExternal size={13} />
                      Open the original posting
                    </a>
                  ) : null}
                  <pre
                    className="max-w-[75ch] whitespace-pre-wrap font-sans text-[0.8125rem] leading-relaxed text-ink-2"
                    style={{ wordBreak: "break-word" }}
                  >
                    {job.description || "This board published no description."}
                  </pre>
                </div>
              ) : null}
            </div>

            <footer
              className="flex items-center justify-between gap-3 border-t px-4 py-3"
              style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
            >
              <span className="clip text-micro text-muted">
                {application
                  ? `Application ${application.id} · updated ${relativeTime(application.updated_at)}`
                  : "No application yet"}
              </span>
              <div className="flex shrink-0 gap-2">
                {application ? (
                  <button type="button" className="btn btn-secondary" onClick={draft} disabled={busy}>
                    Rewrite
                  </button>
                ) : null}
                {application && application.status === "draft" && application.channel === "email" ? (
                  <button type="button" className="btn btn-primary" onClick={approve} disabled={busy}>
                    <IconCheck size={14} />
                    Approve for sending
                  </button>
                ) : null}
                {application && application.channel === "portal" && application.status !== "sent" ? (
                  <>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setTab("apply")}
                    >
                      <IconDocument size={13} />
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
                      <IconCheck size={14} />
                      I submitted this
                    </button>
                  </>
                ) : null}
                {!application ? (
                  <button type="button" className="btn btn-primary" onClick={draft} disabled={busy}>
                    <IconSparkle size={14} />
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
