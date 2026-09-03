/**
 * The nav rail.
 *
 * The rail is one surface step above the content canvas, which is the whole
 * separation: no shadow, no second border treatment. The current view is a
 * surface lift with the accent carried by its icon, because the accent in this
 * system means exactly four things and "where you are" is one of them.
 */
import type { ReactNode } from "react";
import {
  IconBriefcase,
  IconInbox,
  IconLogo,
  IconMoon,
  IconPulse,
  IconSend,
  IconSignOut,
  IconSliders,
  IconSun,
} from "./Icons";
import type { Theme } from "../lib/theme";
import type { Profile, SessionState, Stats } from "../types";
import { Meter } from "./Primitives";
import { initials } from "../lib/format";
import { api } from "../api";

export type ViewKey = "overview" | "jobs" | "applications" | "replies" | "settings";

const NAV: { key: ViewKey; label: string; icon: ReactNode }[] = [
  { key: "overview", label: "Overview", icon: <IconPulse size={16} /> },
  { key: "jobs", label: "Job matches", icon: <IconBriefcase size={16} /> },
  { key: "applications", label: "Applications", icon: <IconSend size={16} /> },
  { key: "replies", label: "Replies", icon: <IconInbox size={16} /> },
  { key: "settings", label: "Profile", icon: <IconSliders size={16} /> },
];

export function Sidebar({
  view,
  onChange,
  theme,
  onThemeChange,
  profile,
  counts,
  session,
  stats,
}: {
  view: ViewKey;
  onChange: (view: ViewKey) => void;
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
  profile: Profile | null;
  counts: Partial<Record<ViewKey, number>>;
  session: SessionState | null;
  stats: Stats | null;
}) {
  const identity = profile?.identity ?? {};

  return (
    <aside
      className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col justify-between border-r px-3 py-4 lg:flex"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      <div className="min-w-0">
        <div className="mb-6 flex items-center gap-2.5 px-2">
          <IconLogo size={26} />
          <div className="min-w-0 leading-tight">
            <p className="text-body font-semibold text-ink" style={{ letterSpacing: "-0.018em" }}>
              JobSeeker
            </p>
            <p className="clip text-micro text-muted">
              {identity.brand ? `${identity.brand} engine` : "application engine"}
            </p>
          </div>
        </div>

        <nav className="flex flex-col gap-px">
          {NAV.map((item) => {
            const isActive = view === item.key;
            const badge = counts[item.key];
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onChange(item.key)}
                aria-current={isActive ? "page" : undefined}
                className="flex min-h-[32px] items-center gap-2.5 rounded-[7px] px-2 py-1.5 text-left text-sm transition-colors"
                style={{
                  background: isActive ? "var(--surface-3)" : "transparent",
                  color: isActive ? "var(--ink)" : "var(--muted)",
                  fontWeight: isActive ? 540 : 480,
                }}
                onMouseEnter={(event) => {
                  if (!isActive) event.currentTarget.style.background = "var(--surface-2)";
                }}
                onMouseLeave={(event) => {
                  if (!isActive) event.currentTarget.style.background = "transparent";
                }}
              >
                <span
                  className="shrink-0"
                  style={{ color: isActive ? "var(--accent)" : "var(--ink-tertiary)" }}
                >
                  {item.icon}
                </span>
                <span className="clip flex-1">{item.label}</span>
                {badge ? (
                  <span
                    className="tabular shrink-0"
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.6875rem",
                      color: "var(--muted)",
                    }}
                  >
                    {badge > 99 ? "99+" : badge}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="flex flex-col gap-2.5">
        {/* The run state lives here rather than in the top bar. It was three
            tags competing with the search field and the primary action, and
            the rail had room going spare. */}
        {stats ? (
          <div
            className="flex flex-col gap-2 rounded-[10px] border px-2.5 py-2.5"
            style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="label">Sending</span>
              <span
                className="flex items-center gap-1.5 text-label font-medium"
                style={{ color: stats.send_enabled ? "var(--st-green)" : "var(--muted)" }}
              >
                <span
                  className="tag-dot"
                  style={{ color: stats.send_enabled ? "var(--st-green)" : "var(--st-grey)" }}
                />
                {stats.send_enabled ? "Live" : "Dry run"}
              </span>
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="label">Today</span>
                <span className="tabular text-label text-ink-2" style={{ fontFamily: "var(--font-mono)" }}>
                  {stats.sent_today}/{stats.daily_cap}
                </span>
              </div>
              <Meter
                value={stats.sent_today}
                max={stats.daily_cap}
                height={3}
                tone={stats.sent_today >= stats.daily_cap ? "var(--st-amber)" : "var(--accent)"}
              />
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="label">Writer</span>
              <span className="clip text-label text-ink-2">{stats.writer}</span>
            </div>
          </div>
        ) : null}

        {session && !session.password_set ? (
          <div
            className="rounded-[10px] border px-2.5 py-2"
            style={{
              borderColor: "color-mix(in oklab, var(--st-amber) 35%, var(--line))",
              background: "var(--surface-2)",
            }}
          >
            <p className="text-label font-semibold" style={{ color: "var(--st-amber)" }}>
              No password set
            </p>
            <p className="mt-1 text-micro leading-relaxed text-muted">
              Anyone who can reach this port has full access. Set one with{" "}
              <code className="font-mono text-ink-2">./run set-password</code>
            </p>
          </div>
        ) : null}

        <div className="segmented w-full" role="group" aria-label="Colour theme">
          {(
            [
              { key: "light" as Theme, label: "Light", icon: <IconSun size={13} /> },
              { key: "dark" as Theme, label: "Dark", icon: <IconMoon size={13} /> },
            ]
          ).map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => onThemeChange(option.key)}
              aria-pressed={theme === option.key}
              className="segment flex-1 justify-center"
            >
              {option.icon}
              {option.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2.5 px-1 py-1">
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[7px] text-micro font-semibold"
            style={{
              background: "var(--surface-3)",
              border: "1px solid var(--line)",
              color: "var(--ink-2)",
            }}
          >
            {initials(identity.full_name ?? "You")}
          </span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="clip block text-label font-medium text-ink">
              {identity.full_name ?? "Your profile"}
            </span>
            <span className="clip block text-micro text-muted">
              {identity.location ?? ""}
            </span>
          </span>
          {session?.auth_required ? (
            <button
              type="button"
              onClick={() => void api.signOut()}
              className="btn btn-quiet shrink-0"
              style={{ minHeight: 26, padding: "0.25rem" }}
              title="Sign out"
              aria-label="Sign out"
            >
              <IconSignOut size={14} />
            </button>
          ) : null}
        </div>
      </div>
    </aside>
  );
}

export function MobileNav({
  view,
  onChange,
}: {
  view: ViewKey;
  onChange: (view: ViewKey) => void;
}) {
  return (
    <nav
      className="sticky top-0 z-20 flex items-center gap-2 border-b px-3 py-2 lg:hidden"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      <IconLogo size={22} className="shrink-0" />
      <div className="scroll-x min-w-0 flex-1 py-0.5">
        <div className="segmented w-max">
        {NAV.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => onChange(item.key)}
            aria-pressed={view === item.key}
            className="segment"
            style={{ minHeight: 36 }}
          >
            {item.icon}
            {item.label}
          </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
