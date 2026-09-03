import { useState } from "react";
import { SectionTitle, Tag } from "../components/Primitives";
import { api, getToken, setToken } from "../api";
import { PasswordField } from "../components/PasswordField";
import { IconAlert, IconCheck } from "../components/Icons";
import type { Profile, SessionState, Stats } from "../types";

/** A labelled list of facts. Used for identity and for the guardrails. */
function Facts({ rows, labelWidth }: { rows: [string, string][]; labelWidth: string }) {
  return (
    <dl className="flex flex-col gap-2 text-[0.8125rem]">
      {rows.map(([label, value]) => (
        <div key={label} className="grid gap-3" style={{ gridTemplateColumns: `${labelWidth} 1fr` }}>
          <dt className="label">{label}</dt>
          <dd className="clip text-ink-2">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A group of tags under a plain label. Not a kicker: it names the group. */
function TagGroup({ label, items }: { label: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="label mb-2">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <Tag key={item}>{item}</Tag>
        ))}
      </div>
    </div>
  );
}

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
    <section className="panel p-4">
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
          className="mb-3 flex items-start gap-2 rounded-[8px] border px-2.5 py-2 text-[0.8125rem] leading-relaxed"
          style={{
            borderColor: "color-mix(in oklab, var(--st-amber) 40%, var(--line))",
            background: "var(--surface-2)",
            color: "var(--ink-2)",
          }}
        >
          <IconAlert size={14} style={{ color: "var(--st-amber)", marginTop: 2, flexShrink: 0 }} />
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
        <PasswordField label="New" value={next} onChange={setNext} autoComplete="new-password" />
        <PasswordField
          label="Repeat new"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
        />

        <div className="flex flex-wrap items-center gap-2.5 sm:col-span-3">
          <button type="submit" className="btn btn-primary" disabled={busy || !next}>
            {busy ? "Saving" : hasPassword ? "Change password" : "Set password"}
          </button>
          {next ? (
            <span className="text-label text-muted">
              {next.length < 10
                ? `${10 - next.length} more character${10 - next.length === 1 ? "" : "s"} needed`
                : confirm && next !== confirm
                  ? "The two new passwords do not match yet"
                  : "Long enough"}
            </span>
          ) : null}
          {message ? (
            <span
              className="text-label"
              style={{ color: message.tone === "ok" ? "var(--st-green)" : "var(--st-red)" }}
            >
              {message.text}
            </span>
          ) : null}
        </div>
      </form>

      <p className="mt-3 max-w-[75ch] text-micro leading-relaxed text-muted">
        Only a scrypt hash is stored, never the password itself. It is kept in the database, so a
        change here survives a restart and a redeploy without touching any configuration.
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

  const identityRows: [string, string][] = (
    [
      ["Name", identity.full_name],
      ["Headline", identity.headline],
      ["Email", identity.email],
      ["Phone", identity.phone],
      ["Location", identity.location],
      ["Portfolio", identity.website],
      ["GitHub", identity.github],
    ] as [string, string | undefined][]
  )
    .filter((row): row is [string, string] => Boolean(row[1]))
    .map(([label, value]) => [label, value]);

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="panel p-4">
        <SectionTitle title="Who this engine writes as" subtitle="Loaded from your profile file" />
        <Facts rows={identityRows} labelWidth="5.5rem" />
      </section>

      <section className="panel p-4">
        <SectionTitle
          title="Guardrails"
          subtitle="Nothing sends until every one of these passes"
        />
        <Facts
          labelWidth="7rem"
          rows={[
            ["Live sending", stats?.send_enabled ? "enabled" : "disabled, dry run only"],
            ["Daily cap", `${profile.settings.daily_cap} applications`],
            ["Sent today", `${stats?.sent_today ?? 0}`],
            ["Draft threshold", `score ${profile.settings.min_score_to_draft}`],
            ["Send threshold", `score ${profile.settings.min_score_to_send}`],
            ["Writer", stats?.writer ?? profile.settings.writer],
          ]}
        />
        <p className="mt-3 max-w-[70ch] text-micro leading-relaxed text-muted">
          Approval is always a human step. The API refuses a live send when the master switch is
          off, whatever the dashboard asks for.
        </p>
      </section>

      <section className="panel flex flex-col gap-4 p-4">
        <SectionTitle title="Target roles" subtitle="What counts as a match" />
        <TagGroup label="Looking for" items={(targeting.roles as string[] | undefined) ?? []} />
        <TagGroup
          label="Ruled out on sight"
          items={((targeting.exclude_keywords as string[] | undefined) ?? []).slice(0, 14)}
        />
      </section>

      <section className="panel flex flex-col gap-4 p-4">
        <SectionTitle
          title="Skills the scorer looks for"
          subtitle="Core skills weigh heaviest in the match"
        />
        <TagGroup label="Core" items={profile.skills.core} />
        <TagGroup label="Working knowledge" items={profile.skills.secondary} />
      </section>

      <div className="xl:col-span-2">
        <PasswordCard session={session} />
      </div>

      <section className="panel p-4 xl:col-span-2">
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
            aria-label="API token"
            className="control w-[17rem]"
          />
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              setToken(token);
              setSaved(true);
            }}
          >
            Save
          </button>
          {saved ? (
            <span
              className="flex items-center gap-1.5 text-label"
              style={{ color: "var(--st-green)" }}
            >
              <IconCheck size={13} />
              Saved
            </span>
          ) : null}
        </div>
      </section>
    </div>
  );
}
