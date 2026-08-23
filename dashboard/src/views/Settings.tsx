import { useState } from "react";
import { Pill, SectionTitle } from "../components/Primitives";
import { api, getToken, setToken } from "../api";
import { PasswordField } from "../components/PasswordField";
import type { Profile, SessionState, Stats } from "../types";

function PasswordCard({ session }: { session: SessionState | null }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);

  const hasPassword = session?.password_set ?? false;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setMessage(null);

    if (next.length < 10) {
      setMessage({ tone: "bad", text: "Use at least 10 characters." });
      return;
    }
    if (next !== confirm) {
      setMessage({ tone: "bad", text: "The two new passwords do not match." });
      return;
    }

    setBusy(true);
    try {
      await api.changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setMessage({
        tone: "ok",
        text: "Password changed. Every other signed in session was ended.",
      });
    } catch (error) {
      setMessage({ tone: "bad", text: (error as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-5">
      <SectionTitle
        title="Sign in password"
        subtitle={
          hasPassword
            ? "Changing it signs out every other device immediately."
            : "No password is set yet. Anyone who can reach this dashboard has full access."
        }
      />

      {!hasPassword ? (
        <p
          className="mb-3 rounded-lg px-3 py-2 text-[13px] leading-relaxed"
          style={{ background: "var(--warning-soft)", color: "var(--warning)" }}
        >
          Set one now. This dashboard can send email in your name.
        </p>
      ) : null}

      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3">
        <PasswordField
          label="Current"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
          disabled={!hasPassword}
          placeholder={hasPassword ? "" : "none set"}
        />
        <PasswordField
          label="New"
          value={next}
          onChange={setNext}
          autoComplete="new-password"
        />
        <PasswordField
          label="Repeat new"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
        />

        <div className="sm:col-span-3 flex flex-wrap items-center gap-2.5">
          <button type="submit" className="btn btn-primary" disabled={busy || !next}>
            {busy ? "Saving" : hasPassword ? "Change password" : "Set password"}
          </button>
          {next ? (
            <span className="text-[12.5px] text-muted">
              {next.length < 10
                ? `${10 - next.length} more character${10 - next.length === 1 ? "" : "s"} needed`
                : confirm && next !== confirm
                  ? "The two new passwords do not match yet"
                  : "Long enough"}
            </span>
          ) : null}
          {message ? (
            <span
              className="text-[13px]"
              style={{ color: message.tone === "ok" ? "var(--positive)" : "var(--danger)" }}
            >
              {message.text}
            </span>
          ) : null}
        </div>
      </form>

      <p className="mt-3 text-[12.5px] leading-relaxed text-muted">
        Only a scrypt hash is stored, never the password itself. It is kept in the database, so
        a change here survives a restart and a redeploy without touching any configuration.
      </p>
    </section>
  );
}

export function Settings({
  profile,
  stats,
  session,
}: {
  profile: Profile | null;
  stats: Stats | null;
  session: SessionState | null;
}) {
  const [token, setTokenValue] = useState(getToken());
  const [saved, setSaved] = useState(false);

  if (!profile) return null;
  const identity = profile.identity;
  const targeting = profile.targeting as Record<string, string[] | number | boolean>;

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="card p-5">
        <SectionTitle title="Who this engine writes as" subtitle="Loaded from your profile file" />
        <dl className="flex flex-col gap-2.5 text-[13.5px]">
          {[
            ["Name", identity.full_name],
            ["Headline", identity.headline],
            ["Email", identity.email],
            ["Phone", identity.phone],
            ["Location", identity.location],
            ["Portfolio", identity.website],
            ["GitHub", identity.github],
          ]
            .filter(([, value]) => Boolean(value))
            .map(([label, value]) => (
              <div key={label} className="grid grid-cols-[6.5rem_1fr] gap-3">
                <dt className="text-muted">{label}</dt>
                <dd className="truncate text-ink">{value}</dd>
              </div>
            ))}
        </dl>
      </section>

      <section className="card p-5">
        <SectionTitle title="Guardrails" subtitle="Nothing sends until every one of these passes" />
        <dl className="flex flex-col gap-2.5 text-[13.5px]">
          {[
            ["Live sending", stats?.send_enabled ? "enabled" : "disabled, dry run only"],
            ["Daily cap", `${profile.settings.daily_cap} applications`],
            ["Sent today", `${stats?.sent_today ?? 0}`],
            ["Draft threshold", `score ${profile.settings.min_score_to_draft}`],
            ["Send threshold", `score ${profile.settings.min_score_to_send}`],
            ["Writer", stats?.writer ?? profile.settings.writer],
          ].map(([label, value]) => (
            <div key={label} className="grid grid-cols-[7.5rem_1fr] gap-3">
              <dt className="text-muted">{label}</dt>
              <dd className="text-ink">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-[12.5px] leading-relaxed text-muted">
          Approval is always a human step. The API refuses a live send when the master switch is
          off, whatever the dashboard asks for.
        </p>
      </section>

      <section className="card p-5">
        <SectionTitle title="Target roles" subtitle="What counts as a match" />
        <div className="flex flex-wrap gap-1.5">
          {(targeting.roles as string[] | undefined)?.map((role) => (
            <Pill key={role} tone="accent">
              {role}
            </Pill>
          ))}
        </div>
        <p className="mb-2 mt-4 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
          Ruled out on sight
        </p>
        <div className="flex flex-wrap gap-1.5">
          {(targeting.exclude_keywords as string[] | undefined)?.slice(0, 14).map((keyword) => (
            <Pill key={keyword} tone="danger">
              {keyword}
            </Pill>
          ))}
        </div>
      </section>

      <section className="card p-5">
        <SectionTitle title="Skills the scorer looks for" />
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">Core</p>
        <div className="flex flex-wrap gap-1.5">
          {profile.skills.core.map((skill) => (
            <Pill key={skill} tone="positive">
              {skill}
            </Pill>
          ))}
        </div>
        <p className="mb-2 mt-4 text-[12px] font-semibold uppercase tracking-[0.06em] text-muted">
          Working knowledge
        </p>
        <div className="flex flex-wrap gap-1.5">
          {profile.skills.secondary.map((skill) => (
            <Pill key={skill}>{skill}</Pill>
          ))}
        </div>
      </section>

      <div className="xl:col-span-2">
        <PasswordCard session={session} />
      </div>

      <section className="card p-5 xl:col-span-2">
        <SectionTitle
          title="API access"
          subtitle="Required when the API is not on localhost. Stored in this browser only."
        />
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="password"
            value={token}
            onChange={(event) => {
              setTokenValue(event.target.value);
              setSaved(false);
            }}
            placeholder="API token"
            className="h-9 w-[280px] rounded-xl border px-3 text-[13.5px] text-ink outline-none"
            style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
          />
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              setToken(token);
              setSaved(true);
            }}
          >
            Save
          </button>
          {saved ? <Pill tone="positive">Saved</Pill> : null}
        </div>
      </section>
    </div>
  );
}
