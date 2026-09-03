/**
 * The review queue.
 *
 * This is the surface the user spends their morning in, so density is the
 * feature. Notes on three decisions:
 *
 *  - The score is a tabular figure, not a ring per row. Sixty arcs cannot be
 *    compared to each other; a column of numbers can.
 *  - Widths are fixed in a colgroup and overflow is trimmed by CSS, so a long
 *    location is clipped at the width the browser has rather than at a
 *    character count guessed in JS.
 *  - Below `md` the table becomes a stacked list. A six column table cannot
 *    fit a phone: the first version kept the table and simply clipped the
 *    status column off the right edge mid-word. Responsive behaviour in
 *    product UI is structural, not a smaller font.
 */
import { CompanyMark, EmptyState, Score, Skeleton, StatusTag, Tag } from "./Primitives";
import { IconBriefcase, IconChevronRight, IconPin } from "./Icons";
import { compactTime, relativeTime } from "../lib/format";
import type { Job } from "../types";

function rowLabel(job: Job): string {
  return `${job.title} at ${job.company_name}, match ${job.score.toFixed(0)}`;
}

/**
 * Where the role is, in one string.
 *
 * The remote flag and the location string overlap: a board that sets
 * `remote = 1` often also writes "Remote - United States" into the location,
 * and prefixing it unconditionally produced "Remote · Remote - United States".
 */
function placeOf(job: Job): string {
  const location = (job.location ?? "").trim();
  if (!job.remote) return location || "\u2014";
  if (!location) return "Remote";
  return /remote|anywhere|home based/i.test(location) ? location : `Remote \u00b7 ${location}`;
}

/** The phone presentation: two lines of identity, one line of meta. */
function JobCard({
  job,
  selected,
  onSelect,
}: {
  job: Job;
  selected: boolean;
  onSelect: (job: Job) => void;
}) {
  const status = job.application?.status ?? job.status;
  return (
    <button
      type="button"
      onClick={() => onSelect(job)}
      aria-label={rowLabel(job)}
      className={`flex w-full flex-col gap-2 border-t px-4 py-3 text-left ${
        selected ? "row-current" : "row"
      }`}
      style={{ borderColor: "var(--line)" }}
    >
      <div className="flex w-full min-w-0 items-start gap-2.5">
        <CompanyMark name={job.company_name} size={24} />
        <div className="min-w-0 flex-1">
          {/* Two lines, then ellipsis: a phone has the height for a wrapped
              title and the reader needs the whole role name. */}
          <div
            className="text-sm font-medium leading-snug text-ink"
            style={{
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {job.title}
          </div>
          <div className="clip mt-0.5 text-label text-muted">
            {job.company_name}
            {job.department ? ` · ${job.department}` : ""}
          </div>
        </div>
        <Score value={job.score} size="sm" />
      </div>

      <div className="flex w-full min-w-0 flex-wrap items-center gap-1.5">
        <StatusTag status={status} />
        {job.location || job.remote ? (
          <Tag bare icon={<IconPin size={11} />}>
            {placeOf(job)}
          </Tag>
        ) : null}
        <span
          className="tabular ml-auto shrink-0 text-micro text-muted"
          title={relativeTime(job.discovered_at)}
        >
          {compactTime(job.discovered_at)}
        </span>
      </div>
    </button>
  );
}

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
    // Skeletons at the real row height, so the table does not jump when the
    // data lands.
    return (
      <div className="flex flex-col">
        {Array.from({ length: compact ? 5 : 8 }).map((_, index) => (
          <div
            key={index}
            className="flex items-center gap-3 border-t px-4"
            style={{ borderColor: "var(--line)", height: 52 }}
          >
            <Skeleton className="h-4 w-7" />
            <Skeleton className="h-6 w-6 shrink-0" />
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="ml-auto h-4 w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (!jobs.length) {
    return (
      <EmptyState
        icon={<IconBriefcase size={16} />}
        title="No matches here yet"
        hint="Run discover to pull open roles from the boards in data/boards.json, then score them against your profile."
      />
    );
  }

  return (
    <>
      {/* Phones and small tablets. */}
      <div className="md:hidden">
        {jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            selected={selectedId === job.id}
            onSelect={onSelect}
          />
        ))}
      </div>

      {/* Everything wide enough to hold the real columns. */}
      <table className="hidden w-full table-fixed border-collapse text-left md:table">
        <colgroup>
          <col style={{ width: "3.5rem" }} />
          <col />
          {!compact ? <col style={{ width: "12rem" }} /> : null}
          <col style={{ width: "7rem" }} />
          {!compact ? <col style={{ width: "6rem" }} /> : null}
          <col style={{ width: "3rem" }} />
          <col style={{ width: "1.75rem" }} />
        </colgroup>

        <thead>
          <tr>
            <th className="th px-4 pb-2 pt-1 text-left">Match</th>
            <th className="th pb-2 pl-1 pr-2 pt-1 text-left">Role</th>
            {!compact ? <th className="th px-2 pb-2 pt-1 text-left">Location</th> : null}
            <th className="th px-2 pb-2 pt-1 text-left">Status</th>
            {!compact ? <th className="th px-2 pb-2 pt-1 text-left">Source</th> : null}
            <th className="th px-2 pb-2 pt-1 text-right">Age</th>
            <th className="pb-2 pr-3 pt-1" />
          </tr>
        </thead>

        <tbody>
          {jobs.map((job) => {
            const isSelected = selectedId === job.id;
            const status = job.application?.status ?? job.status;
            return (
              <tr
                key={job.id}
                onClick={() => onSelect(job)}
                tabIndex={0}
                role="button"
                aria-label={rowLabel(job)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(job);
                  }
                }}
                className={`group cursor-pointer border-t ${isSelected ? "row-current" : "row"}`}
                style={{ borderColor: "var(--line)" }}
              >
                <td className="px-4 py-2.5">
                  <Score value={job.score} />
                </td>

                <td className="py-2.5 pl-1 pr-2">
                  <div className="flex items-center gap-2.5">
                    <CompanyMark name={job.company_name} size={24} />
                    <div className="min-w-0 leading-tight">
                      <div className="clip text-sm font-medium text-ink">{job.title}</div>
                      <div className="clip mt-px text-label text-muted">
                        {job.company_name}
                        {job.department ? ` · ${job.department}` : ""}
                      </div>
                    </div>
                  </div>
                </td>

                {!compact ? (
                  <td className="px-2 py-2.5">
                    {/* A pin, not a coloured dot. The dot vocabulary belongs
                        to status; reusing the blue dot here made one token mean
                        "shortlisted" in one column and "remote" in the next. */}
                    <Tag
                      bare
                      icon={<IconPin size={11} />}
                      title={placeOf(job)}
                    >
                      {placeOf(job)}
                    </Tag>
                  </td>
                ) : null}

                <td className="px-2 py-2.5">
                  <StatusTag status={status} />
                </td>

                {!compact ? (
                  <td className="px-2 py-2.5">
                    <span className="clip block text-label text-muted">{job.source}</span>
                  </td>
                ) : null}

                <td
                  className="tabular px-2 py-2.5 text-right text-label text-muted"
                  title={relativeTime(job.discovered_at)}
                >
                  {compactTime(job.discovered_at)}
                </td>

                <td className="pr-3">
                  <IconChevronRight
                    size={14}
                    className="opacity-0 transition-opacity group-hover:opacity-100"
                    style={{ color: "var(--ink-tertiary)" }}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </>
  );
}
