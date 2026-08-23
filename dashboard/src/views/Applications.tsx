import { CompanyMark, EmptyState, Pill, StatusPill } from "../components/Primitives";
import { IconCheck, IconSend } from "../components/Icons";
import { relativeTime, truncate } from "../lib/format";
import type { Application } from "../types";

const FILTERS = ["draft", "approved", "sent", "replied", "interview", "rejected"];

export function Applications({
  applications,
  counts,
  filter,
  onFilter,
  onApprove,
  onStatus,
  onOpenJob,
}: {
  applications: Application[];
  counts: Record<string, number>;
  filter: string;
  onFilter: (value: string) => void;
  onApprove: (id: number) => void;
  onStatus: (id: number, status: string) => void;
  onOpenJob: (jobId: number) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-1.5">
        {["", ...FILTERS].map((value) => {
          const count = counts[value || "all"] ?? 0;
          const active = filter === value;
          return (
            <button
              key={value || "all"}
              type="button"
              onClick={() => onFilter(value)}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13.5px] font-medium capitalize transition-colors"
              style={{
                background: active ? "var(--accent)" : "var(--surface)",
                color: active ? "var(--accent-ink)" : count ? "var(--muted)" : "var(--line-strong)",
                border: `1px solid ${active ? "transparent" : "var(--line)"}`,
              }}
            >
              {value || "All"}
              <span
                className="tabular rounded px-1 text-[11.5px]"
                style={{
                  background: active
                    ? "color-mix(in oklab, var(--accent-ink) 22%, transparent)"
                    : "var(--surface-3)",
                }}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {!applications.length ? (
        <div className="card">
          <EmptyState
            icon={<IconSend />}
            title={`Nothing is ${filter || "here"}`}
            hint={
              Object.entries(counts)
                .filter(([key, value]) => key !== "all" && value > 0)
                .map(([key, value]) => `${value} ${key}`)
                .join(", ") || "Draft an application from the job matches view first."
            }
          />
        </div>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {applications.map((application) => (
            <li key={application.id} className="card p-4">
              <div className="flex flex-wrap items-start gap-3">
                <CompanyMark name={application.job?.company_name ?? "?"} size={38} />

                <div className="min-w-0 flex-1">
                  <button
                    type="button"
                    onClick={() => application.job && onOpenJob(application.job.id)}
                    className="text-left"
                  >
                    <p className="text-[14.5px] font-medium leading-tight text-ink hover:underline">
                      {application.job?.title ?? `Application ${application.id}`}
                    </p>
                    <p className="mt-0.5 text-[12.5px] text-muted">
                      {application.job?.company_name}
                      {application.recipient_email ? ` · ${application.recipient_email}` : ""}
                    </p>
                  </button>

                  {application.tailored_summary ? (
                    <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
                      {truncate(application.tailored_summary, 150)}
                    </p>
                  ) : null}

                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    <StatusPill status={application.status} />
                    <Pill tone={application.channel === "email" ? "accent" : "warning"}>
                      {application.channel}
                    </Pill>
                    <Pill>{application.generator}</Pill>
                    <span className="text-[12px] text-muted">
                      {application.sent_at
                        ? `sent ${relativeTime(application.sent_at)}`
                        : `updated ${relativeTime(application.updated_at)}`}
                    </span>
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap gap-2">
                  {application.channel === "portal" && application.status !== "sent" ? (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => application.job && onOpenJob(application.job.id)}
                    >
                      Apply pack
                    </button>
                  ) : null}
                  {application.status === "draft" && application.channel === "email" ? (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => onApprove(application.id)}
                    >
                      <IconCheck size={14} />
                      Approve
                    </button>
                  ) : null}
                  {application.status === "sent" ? (
                    <select
                      className="btn btn-ghost"
                      defaultValue=""
                      onChange={(event) =>
                        event.target.value && onStatus(application.id, event.target.value)
                      }
                    >
                      <option value="" disabled>
                        Mark as
                      </option>
                      <option value="replied">Replied</option>
                      <option value="interview">Interview</option>
                      <option value="rejected">Rejected</option>
                      <option value="ghosted">Ghosted</option>
                    </select>
                  ) : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
