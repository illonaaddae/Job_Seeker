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
import type { Profile, SessionState } from "../types";
import { initials } from "../lib/format";
import { api } from "../api";

export type ViewKey = "overview" | "jobs" | "applications" | "replies" | "settings";

const NAV: { key: ViewKey; label: string; icon: ReactNode }[] = [
  { key: "overview", label: "Overview", icon: <IconPulse /> },
  { key: "jobs", label: "Job matches", icon: <IconBriefcase /> },
  { key: "applications", label: "Applications", icon: <IconSend /> },
  { key: "replies", label: "Replies", icon: <IconInbox /> },
  { key: "settings", label: "Profile", icon: <IconSliders /> },
];

export function Sidebar({
  view,
  onChange,
  theme,
  onThemeChange,
  profile,
  counts,
  session,
}: {
  view: ViewKey;
  onChange: (view: ViewKey) => void;
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
  profile: Profile | null;
  counts: Partial<Record<ViewKey, number>>;
  session: SessionState | null;
}) {
  const identity = profile?.identity ?? {};

  return (
    <aside
      className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col justify-between border-r px-3.5 py-5 lg:flex"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      <div>
        <div className="mb-7 flex items-center gap-2.5 px-2">
          <IconLogo size={30} />
          <div className="leading-tight">
            <p
              className="font-display text-[17.5px] text-ink"
              style={{ fontWeight: 700, letterSpacing: "-0.008em" }}
            >
              JobSeeker
            </p>
            <p className="text-[11.5px] text-muted">
              {identity.brand ? `${identity.brand} engine` : "application engine"}
            </p>
          </div>
        </div>

        <p className="eyebrow mb-2 px-3">Workspace</p>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const isActive = view === item.key;
            const badge = counts[item.key];
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onChange(item.key)}
                aria-current={isActive ? "page" : undefined}
                className="group flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 text-left text-[14.5px] font-medium transition-colors"
                style={{
                  background: isActive ? "var(--accent)" : "transparent",
                  color: isActive ? "var(--accent-ink)" : "var(--ink-2)",
                }}
              >
                <span style={{ opacity: isActive ? 1 : 0.72 }}>{item.icon}</span>
                <span className="flex-1">{item.label}</span>
                {badge ? (
                  <span
                    className="tabular rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
                    style={{
                      background: isActive
                        ? "color-mix(in oklab, var(--accent-ink) 22%, transparent)"
                        : "var(--surface-3)",
                      color: isActive ? "var(--accent-ink)" : "var(--muted)",
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

      <div className="flex flex-col gap-3">
        {session && !session.password_set ? (
          <div
            className="rounded-xl border px-3 py-2.5"
            style={{
              borderColor: "color-mix(in oklab, var(--warning) 40%, var(--line))",
              background: "var(--warning-soft)",
            }}
          >
            <p
              className="font-display text-[13px]"
              style={{ color: "var(--warning)", fontWeight: 650 }}
            >
              No password set
            </p>
            <p className="mt-1 text-[11.5px] leading-relaxed" style={{ color: "var(--warning)" }}>
              Anyone who can reach this port has full access. Set one with
              <code className="ml-1 font-mono">./run set-password</code>
            </p>
          </div>
        ) : null}

        <div
          className="flex rounded-xl p-1"
          style={{ background: "var(--surface-3)" }}
          role="group"
          aria-label="Colour theme"
        >
          {(
            [
              { key: "light" as Theme, label: "Light", icon: <IconSun size={14} /> },
              { key: "dark" as Theme, label: "Dark", icon: <IconMoon size={14} /> },
            ]
          ).map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => onThemeChange(option.key)}
              aria-pressed={theme === option.key}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[12.5px] font-medium transition-colors"
              style={{
                background: theme === option.key ? "var(--surface)" : "transparent",
                color: theme === option.key ? "var(--ink)" : "var(--muted)",
                boxShadow: theme === option.key ? "var(--shadow)" : "none",
              }}
            >
              {option.icon}
              {option.label}
            </button>
          ))}
        </div>

        <div
          className="flex items-center gap-2.5 rounded-xl border px-2.5 py-2.5"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
        >
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[12px] font-semibold"
            style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
          >
            {initials(identity.full_name ?? "You")}
          </span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-[13.5px] font-medium text-ink">
              {identity.full_name ?? "Your profile"}
            </span>
            <span className="block truncate text-[11.5px] text-muted">
              {identity.location ?? ""}
            </span>
          </span>
          {session?.auth_required ? (
            <button
              type="button"
              onClick={() => void api.signOut()}
              className="shrink-0 rounded-lg p-1.5 text-muted transition-colors hover:text-ink"
              title="Sign out"
              aria-label="Sign out"
            >
              <IconSignOut size={15} />
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
      className="sticky top-0 z-20 flex gap-1 overflow-x-auto border-b px-3 py-2 lg:hidden"
      style={{ background: "var(--surface)", borderColor: "var(--line)" }}
    >
      {NAV.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onChange(item.key)}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
          style={{
            background: view === item.key ? "var(--accent)" : "var(--surface-3)",
            color: view === item.key ? "var(--accent-ink)" : "var(--muted)",
          }}
        >
          {item.icon}
          {item.label}
        </button>
      ))}
    </nav>
  );
}
