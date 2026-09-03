/**
 * What the engine can and cannot do right now.
 *
 * Automation that quietly does half its job is worse than automation that says
 * which piece is missing and what it would unlock. This turns the difference
 * between "configured" and "not" into something visible.
 */
import { IconCheck, IconBolt } from "./Icons";
import { SectionTitle } from "./Primitives";
import type { ReadinessCheck } from "../types";

export function Readiness({ checks }: { checks: ReadinessCheck[] }) {
  if (!checks.length) return null;
  const outstanding = checks.filter((check) => !check.ready);

  if (!outstanding.length) {
    return (
      <section className="panel p-4">
        <SectionTitle title="Setup" subtitle="Everything the engine needs is configured" />
        <p className="flex items-center gap-2 text-[0.8125rem]" style={{ color: "var(--st-green)" }}>
          <IconCheck size={14} />
          Fully armed. Applications can be found, written and sent.
        </p>
      </section>
    );
  }

  return (
    <section className="panel p-4">
      <SectionTitle
        title="Setup"
        subtitle={`${outstanding.length} thing${outstanding.length === 1 ? "" : "s"} still limiting what runs without you`}
      />
      <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {checks.map((check) => (
          <li key={check.key} className="flex items-start gap-2.5">
            <span
              className="mt-px flex h-4 w-4 shrink-0 items-center justify-center rounded-full"
              style={{
                border: `1px solid color-mix(in oklab, ${check.ready ? "var(--st-green)" : "var(--st-amber)"} 45%, var(--line))`,
                color: check.ready ? "var(--st-green)" : "var(--st-amber)",
              }}
            >
              {check.ready ? <IconCheck size={10} /> : <IconBolt size={9} />}
            </span>
            <div className="min-w-0">
              <p className="text-[0.8125rem] font-medium text-ink">{check.label}</p>
              <p className="mt-0.5 text-micro leading-relaxed text-muted">
                {check.ready ? check.unlocks : check.how}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
