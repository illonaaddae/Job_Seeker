import { useState } from "react";
import { IconBolt, IconRefresh, IconSearch, IconSparkle } from "./Icons";
import { Pill } from "./Primitives";
import type { Stats } from "../types";

export function TopBar({
  title,
  subtitle,
  search,
  onSearch,
  onRun,
  running,
  stats,
}: {
  title: string;
  subtitle: string;
  search: string;
  onSearch: (value: string) => void;
  onRun: (stage: string) => void;
  running: string | null;
  stats: Stats | null;
}) {
  const [open, setOpen] = useState(false);

  return (
    <header
      className="sticky top-0 z-10 flex flex-wrap items-center gap-3 border-b px-5 py-4 backdrop-blur lg:px-8"
      style={{
        background: "color-mix(in oklab, var(--canvas) 88%, transparent)",
        borderColor: "var(--line)",
      }}
    >
      <div className="min-w-0 flex-1">
        <h1
          className="truncate text-[24px] leading-tight text-ink"
          style={{ fontWeight: 650, letterSpacing: "-0.008em" }}
        >
          {title}
        </h1>
        <p className="truncate text-[13.5px] text-muted">{subtitle}</p>
      </div>

      <label
        className="flex h-9 min-w-[190px] flex-1 items-center gap-2 rounded-xl border px-3 lg:max-w-[300px]"
        style={{ borderColor: "var(--line)", background: "var(--surface)" }}
      >
        <IconSearch size={15} style={{ color: "var(--muted)" }} />
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search company or role"
          className="w-full bg-transparent text-[14px] text-ink outline-none placeholder:text-muted"
          spellCheck={false}
        />
      </label>

      {stats ? (
        <div className="hidden items-center gap-1.5 xl:flex">
          <Pill tone={stats.send_enabled ? "positive" : "neutral"}>
            {stats.send_enabled ? "Live sending on" : "Dry run"}
          </Pill>
          <Pill tone="neutral" title="Applications sent today against the daily cap">
            {stats.sent_today}/{stats.daily_cap} today
          </Pill>
          <Pill tone="accent" title="Which writer drafts the letters">
            <IconSparkle size={11} />
            {stats.writer}
          </Pill>
        </div>
      ) : null}

      <div className="relative">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setOpen((value) => !value)}
          disabled={Boolean(running)}
        >
          {running ? (
            <>
              <IconRefresh size={15} className="animate-spin" />
              {running}
            </>
          ) : (
            <>
              <IconBolt size={15} />
              Run stage
            </>
          )}
        </button>

        {open && !running ? (
          <>
            <button
              type="button"
              className="fixed inset-0 z-10 cursor-default"
              aria-label="Close menu"
              onClick={() => setOpen(false)}
            />
            <div
              className="card animate-rise absolute right-0 z-20 mt-2 w-60 overflow-hidden p-1.5"
              style={{ boxShadow: "var(--shadow-lift)" }}
            >
              {[
                { stage: "discover", label: "Discover roles", hint: "pull from every board" },
                { stage: "score", label: "Score matches", hint: "rank against your profile" },
                { stage: "draft", label: "Draft applications", hint: "letters and tailored CVs" },
                {
                  stage: "prospect_local",
                  label: "Find reachable companies",
                  hint: "addresses companies publish, no key needed",
                },
                { stage: "send", label: "Send (dry run)", hint: "validate without sending" },
                { stage: "followup", label: "Follow ups (dry run)", hint: "check what is due" },
                { stage: "replies", label: "Sync replies", hint: "read the inbox" },
                { stage: "respond", label: "Draft answers", hint: "reply to people who wrote back" },
                { stage: "digest", label: "Email me a summary", hint: "what happened, what needs you" },
              ].map((item) => (
                <button
                  key={item.stage}
                  type="button"
                  className="row-hover flex w-full flex-col items-start rounded-lg px-2.5 py-2 text-left"
                  onClick={() => {
                    setOpen(false);
                    onRun(item.stage);
                  }}
                >
                  <span className="text-[14px] font-medium text-ink">{item.label}</span>
                  <span className="text-[12px] text-muted">{item.hint}</span>
                </button>
              ))}
            </div>
          </>
        ) : null}
      </div>
    </header>
  );
}
