/**
 * The apply pack.
 *
 * Portal applications cannot be submitted by this system, and should not be:
 * every major ATS forbids automated submission. What can be removed is the
 * tedium. Every answer a form asks for already exists in the profile or the
 * draft, so the work becomes copying rather than composing.
 */
import { useEffect, useState } from "react";
import { api } from "../api";
import { IconCheck, IconDocument, IconExternal, IconRefresh, IconSparkle } from "./Icons";
import { Skeleton, Tag } from "./Primitives";
import type { ApplyField, ApplyPack as Pack, FormAnswer } from "../types";

const GROUP_LABELS: Record<ApplyField["group"], string> = {
  you: "About you",
  links: "Links",
  logistics: "The usual questions",
  writing: "Free text answers",
};

const GROUP_ORDER: ApplyField["group"][] = ["you", "links", "logistics", "writing"];

function CopyRow({ field }: { field: ApplyField }) {
  const [copied, setCopied] = useState(false);
  const isLong = field.value.length > 120;

  async function copy() {
    try {
      await navigator.clipboard.writeText(field.value);
    } catch {
      // Clipboard access can be refused; select the text so it can be copied
      // by hand rather than leaving the click doing nothing at all.
      const range = document.createRange();
      const node = document.getElementById(`field-${field.label}`);
      if (node) {
        range.selectNodeContents(node);
        window.getSelection()?.removeAllRanges();
        window.getSelection()?.addRange(range);
      }
      return;
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div
      className="flex items-start gap-2 rounded-[8px] border px-3 py-2"
      style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
    >
      <div className="min-w-0 flex-1">
        <p className="label">{field.label}</p>
        <p
          id={`field-${field.label}`}
          className={`mt-1 text-[0.8125rem] leading-relaxed text-ink ${isLong ? "whitespace-pre-wrap" : "truncate"}`}
        >
          {field.value}
        </p>
      </div>
      <button
        type="button"
        onClick={copy}
        className="btn btn-secondary btn-sm shrink-0"
      >
        {copied ? <IconCheck size={13} /> : null}
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function AnswerCard({ answer }: { answer: FormAnswer }) {
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState(false);
  const preview = answer.answer.length > 220 && !open
    ? `${answer.answer.slice(0, 220).trimEnd()}...`
    : answer.answer;

  return (
    <div
      className="rounded-[8px] border px-3 py-2.5"
      style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[0.8125rem] font-medium text-ink">{answer.question}</p>
          <p className="mt-0.5 text-micro text-muted">
            {answer.words} words
            {answer.source === "tailored" ? ", written for this role" : ", your stored answer"}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm shrink-0"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(answer.answer);
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1600);
            } catch {
              setOpen(true);
            }
          }}
        >
          {copied ? <IconCheck size={13} /> : null}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      <p className="mt-2 whitespace-pre-wrap text-[0.8125rem] leading-relaxed text-ink-2">{preview}</p>

      {answer.answer.length > 220 ? (
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="mt-1.5 text-micro font-medium"
          style={{ color: "var(--accent)" }}
        >
          {open ? "Show less" : "Show the whole answer"}
        </button>
      ) : null}
    </div>
  );
}

export function ApplyPack({
  jobId,
  onSubmitted,
  notify,
}: {
  jobId: number;
  onSubmitted: () => void;
  notify: (tone: "info" | "success" | "error", message: string, detail?: string) => void;
}) {
  const [pack, setPack] = useState<Pack | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .applyPack(jobId)
      .then((result) => !cancelled && setPack(result))
      .catch((error: Error) => notify("error", "Could not build the apply pack", error.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [jobId, notify]);

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton key={index} className="h-14 w-full" />
        ))}
      </div>
    );
  }
  if (!pack) return null;

  const submitted = pack.application?.status === "sent";

  return (
    <div className="flex flex-col gap-4">
      <div
        className="rounded-[8px] border px-3 py-2.5"
        style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
      >
        <p className="text-[0.8125rem] leading-relaxed text-ink-2">
          This role is applied for on the company's own form, which this system deliberately does
          not fill in. Everything the form asks for is below. Open the form, paste, submit, then
          mark it done so follow ups are scheduled.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {pack.job.url ? (
          <a
            href={pack.job.url}
            target="_blank"
            rel="noreferrer noopener"
            className="btn btn-primary"
          >
            <IconExternal size={14} />
            Open the application form
          </a>
        ) : null}
        {pack.documents
          .filter((document) => document.filename)
          .map((document) => (
            <a key={document.label} href={document.url} className="btn btn-secondary" download>
              <IconDocument size={14} />
              {document.label}
            </a>
          ))}
      </div>

      {pack.answers.length ? (
        <section>
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="label">The questions forms keep asking</p>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const result = await api.rebuildAnswers(jobId);
                  setPack({ ...pack, answers: result.answers });
                  notify("success", "Answers rebuilt", "Tailored to this job where possible.");
                } catch (error) {
                  notify("error", "Could not rebuild", (error as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? <IconRefresh size={13} className="animate-spin" /> : <IconSparkle size={13} />}
              Rewrite for this job
            </button>
          </div>
          <div className="flex flex-col gap-2">
            {pack.answers.map((answer) => (
              <AnswerCard key={answer.key} answer={answer} />
            ))}
          </div>
        </section>
      ) : null}

      {GROUP_ORDER.map((group) => {
        const fields = pack.fields.filter((field) => field.group === group);
        if (!fields.length) return null;
        return (
          <section key={group}>
            <p className="label mb-2">{GROUP_LABELS[group]}</p>
            <div className="flex flex-col gap-2">
              {fields.map((field) => (
                <CopyRow key={field.label} field={field} />
              ))}
            </div>
          </section>
        );
      })}

      <div className="flex items-center gap-2.5">
        {submitted ? (
          <Tag tone="positive">
            <IconCheck size={12} />
            Submitted, follow ups scheduled
          </Tag>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || !pack.application}
            onClick={async () => {
              if (!pack.application) return;
              setBusy(true);
              try {
                await api.setApplicationStatus(pack.application.id, "sent");
                setPack({
                  ...pack,
                  application: { ...pack.application, status: "sent" },
                });
                onSubmitted();
                notify("success", "Marked as applied", "Follow ups are now scheduled.");
              } catch (error) {
                notify("error", "Could not update", (error as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <IconCheck size={15} />
            I submitted this
          </button>
        )}
      </div>
    </div>
  );
}
