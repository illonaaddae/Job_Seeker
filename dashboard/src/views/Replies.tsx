import { EmptyState, Pill, StatusPill } from "../components/Primitives";
import { IconInbox } from "../components/Icons";
import { relativeTime } from "../lib/format";
import type { Reply } from "../types";

export function Replies({ replies }: { replies: Reply[] }) {
  if (!replies.length) {
    return (
      <div className="card">
        <EmptyState
          icon={<IconInbox />}
          title="No replies read yet"
          hint="Run the replies stage to read your inbox over IMAP. Every reply is matched back to the application that caused it, and any pending follow up for that thread is cancelled automatically."
        />
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-2.5">
      {replies.map((reply) => (
        <li key={reply.id} className="card p-4">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={reply.classification} />
            <span className="text-[14px] font-medium text-ink">{reply.from_addr}</span>
            <span className="text-[12px] text-muted">{relativeTime(reply.received_at)}</span>
            {reply.application_id ? (
              <Pill tone="neutral">application {reply.application_id}</Pill>
            ) : null}
          </div>
          <p className="mt-1.5 text-[13.5px] font-medium text-ink-2">{reply.subject}</p>
          <p className="mt-1 text-[13px] leading-relaxed text-muted">{reply.snippet}</p>
        </li>
      ))}
    </ul>
  );
}
