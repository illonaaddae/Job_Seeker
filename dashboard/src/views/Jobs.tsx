import { useState } from "react";
import { JobsTable } from "../components/JobsTable";
import { Pill } from "../components/Primitives";
import { IconExternal } from "../components/Icons";
import type { Job } from "../types";

const FILTERS: { key: string; label: string; status?: string; minScore?: number }[] = [
  { key: "shortlist", label: "Shortlist", minScore: 60 },
  { key: "all", label: "Everything" },
  { key: "drafted", label: "Drafted", status: "drafted" },
  { key: "applied", label: "Applied", status: "applied" },
  { key: "blocked", label: "Ruled out", status: "rejected_by_me" },
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
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => onFilter(item.key)}
              className="rounded-lg px-3 py-1.5 text-[13.5px] font-medium transition-colors"
              style={{
                background: filter === item.key ? "var(--accent)" : "var(--surface)",
                color: filter === item.key ? "var(--accent-ink)" : "var(--muted)",
                border: `1px solid ${filter === item.key ? "transparent" : "var(--line)"}`,
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        <form onSubmit={submit} className="flex items-center gap-2">
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="Paste a job URL to add it"
            className="h-9 w-[240px] rounded-xl border px-3 text-[13.5px] text-ink outline-none placeholder:text-muted"
            style={{ borderColor: "var(--line)", background: "var(--surface)" }}
          />
          <button type="submit" className="btn btn-ghost" disabled={busy || !url.trim()}>
            <IconExternal size={14} />
            {busy ? "Reading" : "Add"}
          </button>
        </form>
      </div>

      <div className="card overflow-hidden">
        <div
          className="flex items-center justify-between border-b px-5 py-3"
          style={{ borderColor: "var(--line)" }}
        >
          <p className="text-[13.5px] text-muted">
            {loading ? "Loading" : `${jobs.length} role${jobs.length === 1 ? "" : "s"}`}
          </p>
          <Pill tone="neutral">Click a row to review it</Pill>
        </div>
        <JobsTable jobs={jobs} loading={loading} onSelect={onSelect} selectedId={selectedId} />
      </div>
    </div>
  );
}
