/**
 * The top bar.
 *
 * Two things this had to stop doing.
 *
 * It put "Dry run" and "0/12 today" in the same visual register as the buttons
 * beside them, so state that cannot be clicked looked clickable. The run state
 * now lives in the nav rail, and exactly one thing in this bar is an action.
 *
 * And on a phone it stacked into three rows (title, then search, then the
 * button) on top of a nav row, which spent roughly a third of the viewport on
 * chrome before the first row of content. Now it is two rows at most: the
 * title shares a line with an icon-only run button, and search sits under it.
 */
import { useEffect, useRef, useState } from "react";
import { IconBolt, IconRefresh, IconSearch, IconSparkle } from "./Icons";
import { Tag } from "./Primitives";
import type { Stats } from "../types";

const STAGES: { stage: string; label: string; hint: string }[] = [
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
];

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
  const menu = useRef<HTMLDivElement>(null);

  // A menu that ignores Escape has to be clicked out of, which is the one
  // thing a keyboard user cannot do.
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header
      className="region sticky top-0 z-10 px-4 py-2.5 lg:px-6 lg:py-3"
      style={{
        background: "color-mix(in oklab, var(--canvas) 82%, transparent)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="clip text-ink">{title}</h1>
          {/* The subtitle is orientation, not instruction. It earns a line on a
              wide screen and gets out of the way on a phone. */}
          <p className="clip mt-0.5 hidden text-sm text-muted sm:block">{subtitle}</p>
        </div>

        {stats ? (
          <div className="hidden items-center gap-1.5 2xl:flex" aria-label="Run state">
            <Tag tone={stats.send_enabled ? "positive" : "neutral"}>
              {stats.send_enabled ? "Live sending" : "Dry run"}
            </Tag>
            <Tag title="Which writer drafts the letters">
              <IconSparkle size={11} style={{ color: "var(--ink-tertiary)" }} />
              {stats.writer}
            </Tag>
          </div>
        ) : null}

        <label
          className="control hidden min-w-0 flex-1 items-center gap-2 sm:flex sm:max-w-[15rem]"
          style={{ paddingBlock: 0 }}
        >
          <IconSearch size={14} style={{ color: "var(--ink-tertiary)", flexShrink: 0 }} />
          <input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search"
            className="w-full min-w-0 bg-transparent text-sm text-ink outline-none placeholder:text-muted"
            style={{ minHeight: 32 }}
            spellCheck={false}
            aria-label="Search company or role"
          />
        </label>

        <div className="relative shrink-0">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setOpen((value) => !value)}
            disabled={Boolean(running)}
            aria-expanded={open}
            aria-haspopup="menu"
            aria-label={running ? `Running ${running}` : "Run a stage"}
            title={running ? running : "Run a stage"}
          >
            {running ? (
              <IconRefresh size={14} className="animate-spin" />
            ) : (
              <IconBolt size={14} />
            )}
            {/* The label is the first thing to go when space runs out; the
                bolt plus the tooltip still name the action. */}
            <span className="hidden sm:inline">{running ? running : "Run stage"}</span>
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
                ref={menu}
                role="menu"
                className="pop animate-pop absolute right-0 z-20 mt-1.5 w-[15rem] overflow-hidden p-1"
              >
                {STAGES.map((item) => (
                  <button
                    key={item.stage}
                    type="button"
                    role="menuitem"
                    className="row flex w-full flex-col items-start rounded-[6px] px-2 py-1.5 text-left"
                    onClick={() => {
                      setOpen(false);
                      onRun(item.stage);
                    }}
                  >
                    <span className="text-sm font-medium text-ink">{item.label}</span>
                    <span className="text-micro text-muted">{item.hint}</span>
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Phone only: search gets its own line rather than squeezing the title. */}
      <label
        className="control mt-2 flex items-center gap-2 sm:hidden"
        style={{ paddingBlock: 0 }}
      >
        <IconSearch size={14} style={{ color: "var(--ink-tertiary)", flexShrink: 0 }} />
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search company or role"
          className="w-full min-w-0 bg-transparent text-sm text-ink outline-none placeholder:text-muted"
          style={{ minHeight: 32 }}
          spellCheck={false}
          aria-label="Search company or role"
        />
      </label>
    </header>
  );
}
