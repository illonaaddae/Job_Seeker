import { CompanyMark, EmptyState, Pill, ScoreDial, Skeleton, StatusPill } from "./Primitives";
import { IconBriefcase, IconPin } from "./Icons";
import { relativeTime, truncate } from "../lib/format";
import type { Job } from "../types";

export function JobsTable({
  jobs,
  loading,
  onSelect,
  selectedId,
  compact = false,
}: {
  jobs: Job[];
  loading: boolean;
  onSelect: (job: Job) => void;
  selectedId?: number | null;
  compact?: boolean;
}) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2 p-4">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  if (!jobs.length) {
    return (
      <EmptyState
        icon={<IconBriefcase />}
        title="No matches here yet"
        hint="Run discover to pull open roles from the boards in data/boards.json, then score them against your profile."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr>
            <th className="eyebrow px-5 py-3 text-left">Match</th>
            <th className="eyebrow px-2 py-3 text-left">Role</th>
            {!compact ? <th className="eyebrow px-2 py-3 text-left">Location</th> : null}
            <th className="eyebrow px-2 py-3 text-left">Status</th>
            {!compact ? <th className="eyebrow px-2 py-3 text-left">Found</th> : null}
            <th className="px-5 py-3" />
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => {
            const isSelected = selectedId === job.id;
            return (
              <tr
                key={job.id}
                onClick={() => onSelect(job)}
                className="row-hover cursor-pointer border-t transition-colors"
                style={{
                  borderColor: "var(--line)",
                  background: isSelected ? "var(--surface-2)" : undefined,
                }}
              >
                <td className="px-5 py-3.5">
                  <ScoreDial value={job.score} />
                </td>

                <td className="px-2 py-3.5">
                  <div className="flex items-center gap-3">
                    <CompanyMark name={job.company_name} />
                    <div className="min-w-0">
                      <p className="truncate text-[14.5px] font-medium leading-snug text-ink">
                        {truncate(job.title, compact ? 38 : 62)}
                      </p>
                      <p className="mt-0.5 truncate text-[12.5px] text-muted">
                        {job.company_name}
                        {job.department ? ` · ${job.department}` : ""}
                      </p>
                    </div>
                  </div>
                </td>

                {!compact ? (
                  <td className="px-2 py-3">
                    <div className="flex flex-wrap items-center gap-1">
                      {job.remote ? <Pill tone="accent">Remote</Pill> : null}
                      {job.location ? (
                        <span className="flex items-center gap-1 text-[12.5px] text-muted">
                          <IconPin size={12} />
                          {truncate(job.location, 26)}
                        </span>
                      ) : null}
                    </div>
                  </td>
                ) : null}

                <td className="px-2 py-3">
                  <div className="flex flex-wrap gap-1">
                    <StatusPill status={job.application?.status ?? job.status} />
                  </div>
                </td>

                {!compact ? (
                  <td className="px-2 py-3 text-[12.5px] text-muted">
                    {relativeTime(job.discovered_at)}
                  </td>
                ) : null}

                <td className="px-5 py-3.5 text-right">
                  <span
                    className="chip"
                    style={{ background: "var(--surface-3)", color: "var(--muted)" }}
                  >
                    {job.source}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
