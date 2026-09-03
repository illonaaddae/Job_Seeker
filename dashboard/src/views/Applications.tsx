import { CompanyMark, EmptyState, Segmented, StatusTag, Tag } from "../components/Primitives";
import { IconCheck, IconSend } from "../components/Icons";
import { relativeTime } from "../lib/format";
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
  const options = ["", ...FILTERS].map((value) => ({
    key: value,
    label: value ? value[0].toUpperCase() + value.slice(1) : "All",
    count: counts[value || "all"] ?? 0,
  }));

  return (
    <div className="flex flex-col gap-3">
      <div className="scroll-x -my-0.5 max-w-full py-0.5">
        <div className="w-max">
          <Segmented
            options={options}
            value={filter}
            onChange={onFilter}
            label="Application filter"
          />
        </div>
      </div>

      {!applications.length ? (
        <div className="panel">
          <EmptyState
            icon={<IconSend size={16} />}
            title={`Nothing is ${filter || "here"}`}
            hint={
              Object.entries(counts)
                .filter(([key, value]) => key !== "all" && value > 0)
                .map(([key, value]) => `${value} ${key}`)
                .join(" · ") || "Draft an application from the job matches view first."
            }
          />
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {applications.map((application) => (
            <li key={application.id} className="panel p-3.5">
              <div className="flex flex-wrap items-start gap-3">
                <CompanyMark name={application.job?.company_name ?? "?"} size={30} />

                <div className="min-w-0 flex-1">
                  <button
                    type="button"
                    onClick={() => application.job && onOpenJob(application.job.id)}
                    className="max-w-full text-left"
                  >
                    <p className="text-body font-medium leading-tight text-ink hover:underline">
                      {application.job?.title ?? `Application ${application.id}`}
                    </p>
                    <p className="mt-0.5 text-label text-muted">
                      {application.job?.company_name}
                      {application.recipient_email ? ` · ${application.recipient_email}` : ""}
                    </p>
                  </button>

                  {application.tailored_summary ? (
                    <p className="mt-2 max-w-[70ch] text-[0.8125rem] leading-relaxed text-ink-2">
                      {application.tailored_summary}
                    </p>
                  ) : null}

                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    <StatusTag status={application.status} />
                    <Tag tone={application.channel === "email" ? "info" : "warning"}>
                      {application.channel === "email" ? "email" : "their portal"}
                    </Tag>
                    <Tag>{application.generator}</Tag>
                    <Tag bare>
                      {application.sent_at
                        ? `sent ${relativeTime(application.sent_at)}`
                        : `updated ${relativeTime(application.updated_at)}`}
                    </Tag>
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {application.channel === "portal" && application.status !== "sent" ? (
                    <button
                      type="button"
                      className="btn btn-secondary"
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
                      <IconCheck size={13} />
                      Approve
                    </button>
                  ) : null}
                  {application.status === "sent" ? (
                    <select
                      className="control"
                      defaultValue=""
                      aria-label="Mark this application as"
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
