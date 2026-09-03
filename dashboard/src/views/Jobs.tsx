import { useState } from "react";
import { JobsTable } from "../components/JobsTable";
import { Segmented } from "../components/Primitives";
import { IconClose, IconPlus } from "../components/Icons";
import type { Job } from "../types";

const FILTERS: { key: string; label: string }[] = [
  { key: "shortlist", label: "Shortlist" },
  { key: "all", label: "Everything" },
  { key: "drafted", label: "Drafted" },
  { key: "applied", label: "Applied" },
  { key: "blocked", label: "Ruled out" },
];

export function Jobs({
  jobs,
  loading,
  filter,
  onFilter,
  onSelect,
  selectedId,
  onImport,
}: {
  jobs: Job[];
  loading: boolean;
  filter: string;
  onFilter: (key: string) => void;
  onSelect: (job: Job) => void;
  selectedId: number | null;
  onImport: (url: string) => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  // Adding a job by URL is a rare action. It had a permanent full width row on
  // a phone, above the queue, which is prime space spent on the exception.
  const [adding, setAdding] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    try {
      await onImport(url.trim());
      setUrl("");
      setAdding(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="region flex items-center gap-2 px-4 py-2 lg:px-6">
        <div className="scroll-x -my-0.5 min-w-0 flex-1 py-0.5">
          <div className="w-max">
            <Segmented options={FILTERS} value={filter} onChange={onFilter} label="Job filter" />
          </div>
        </div>

        <p className="hidden shrink-0 text-label text-muted sm:block">
          {loading ? (
            "Loading"
          ) : (
            <>
              <span className="tabular font-medium text-ink-2">{jobs.length}</span>{" "}
              {jobs.length === 1 ? "role" : "roles"}
            </>
          )}
        </p>

        {adding ? (
          <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2 sm:flex-none">
            <input
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="Paste a job URL"
              className="control min-w-0 flex-1 sm:w-[14rem] sm:flex-none"
              aria-label="Job posting URL"
              autoFocus
            />
            <button type="submit" className="btn btn-primary shrink-0" disabled={busy || !url.trim()}>
              {busy ? "Reading" : "Add"}
            </button>
            <button
              type="button"
              className="btn btn-quiet shrink-0"
              onClick={() => {
                setAdding(false);
                setUrl("");
              }}
              aria-label="Cancel adding a job"
            >
              <IconClose size={13} />
            </button>
          </form>
        ) : (
          <button
            type="button"
            className="btn btn-secondary shrink-0"
            onClick={() => setAdding(true)}
            title="Add a job by URL"
          >
            <IconPlus size={14} />
            <span className="hidden sm:inline">Add a job</span>
          </button>
        )}
      </div>

      <JobsTable jobs={jobs} loading={loading} onSelect={onSelect} selectedId={selectedId} />
    </div>
  );
}
