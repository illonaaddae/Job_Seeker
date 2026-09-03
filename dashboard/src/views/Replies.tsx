import { EmptyState, StatusTag, Tag } from "../components/Primitives";
import { IconInbox } from "../components/Icons";
import { relativeTime } from "../lib/format";
import type { Reply } from "../types";

export function Replies({ replies }: { replies: Reply[] }) {
  if (!replies.length) {
    return (
      <div>
        <EmptyState
          icon={<IconInbox size={16} />}
          title="No replies read yet"
          hint="Run the replies stage to read your inbox over IMAP. Every reply is matched back to the application that caused it, and any pending follow up for that thread is cancelled automatically."
        />
      </div>
    );
  }

  return (
    <ul>
      {replies.map((reply) => (
        <li key={reply.id} className="region px-4 py-3 lg:px-6">
          <div className="flex flex-wrap items-center gap-2">
            <StatusTag status={reply.classification} />
            <span className="text-[0.8125rem] font-medium text-ink">{reply.from_addr}</span>
            <Tag bare>{relativeTime(reply.received_at)}</Tag>
            {reply.application_id ? (
              <Tag title="The application this reply answers">
                <span className="tabular" style={{ fontFamily: "var(--font-mono)" }}>
                  #{reply.application_id}
                </span>
              </Tag>
            ) : null}
          </div>
          <p className="mt-2 text-[0.8125rem] font-medium text-ink">{reply.subject}</p>
          <p className="mt-1 max-w-[75ch] text-[0.8125rem] leading-relaxed text-muted">
            {reply.snippet}
          </p>
        </li>
      ))}
    </ul>
  );
}
