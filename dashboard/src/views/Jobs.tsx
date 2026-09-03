import { useState } from "react";
import { JobsTable } from "../components/JobsTable";
import { Segmented } from "../components/Primitives";
import { IconPlus } from "../components/Icons";
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

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    try {
      await onImport(url.trim());
      setUrl("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="scroll-x -my-0.5 min-w-0 max-w-full py-0.5">
          <div className="w-max">
            <Segmented options={FILTERS} value={filter} onChange={onFilter} label="Job filter" />
          </div>
        </div>

        <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2 sm:flex-none">
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="Paste a job URL to add it"
            className="control min-w-0 flex-1 sm:w-[15rem] sm:flex-none"
            aria-label="Job posting URL"
          />
          <button type="submit" className="btn btn-secondary" disabled={busy || !url.trim()}>
            <IconPlus size={14} />
            {busy ? "Reading" : "Add"}
          </button>
        </form>
      </div>

      <div className="panel-flush">
        <div
          className="flex items-center justify-between border-b px-4 py-2"
          style={{ borderColor: "var(--line)" }}
        >
          <p className="text-label text-muted">
            {loading ? (
              "Loading"
            ) : (
              <>
                <span className="tabular font-medium text-ink-2">{jobs.length}</span>{" "}
                {jobs.length === 1 ? "role" : "roles"}
              </>
            )}
          </p>
        </div>
        <JobsTable jobs={jobs} loading={loading} onSelect={onSelect} selectedId={selectedId} />
      </div>
    </div>
  );
}
