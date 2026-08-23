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
      <section className="card p-5">
        <SectionTitle title="Setup" subtitle="Everything the engine needs is configured" />
        <p className="flex items-center gap-2 text-[13.5px]" style={{ color: "var(--positive)" }}>
          <IconCheck size={16} />
          Fully armed. Applications can be found, written and sent.
        </p>
      </section>
    );
  }

  return (
    <section className="card p-5">
      <SectionTitle
        title="Setup"
        subtitle={`${outstanding.length} thing${outstanding.length === 1 ? "" : "s"} still limiting what runs without you`}
      />
      <ul className="flex flex-col gap-3">
        {checks.map((check) => (
          <li key={check.key} className="flex items-start gap-3">
            <span
              className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
              style={{
                background: check.ready ? "var(--positive-soft)" : "var(--warning-soft)",
                color: check.ready ? "var(--positive)" : "var(--warning)",
              }}
            >
              {check.ready ? <IconCheck size={12} /> : <IconBolt size={11} />}
            </span>
            <div className="min-w-0">
              <p className="text-[13.5px] font-medium text-ink">{check.label}</p>
              <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted">
                {check.ready ? check.unlocks : check.how}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
