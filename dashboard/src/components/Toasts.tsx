import { useEffect } from "react";
import { IconAlert, IconCheck, IconClose, IconInfo } from "./Icons";

export interface Toast {
  id: number;
  tone: "info" | "success" | "error";
  message: string;
  detail?: string;
}

/* The icon has to agree with the tone. The previous version drew a checkmark
   on every toast, including the failures. */
const TONE = {
  info: { colour: "var(--st-blue)", Icon: IconInfo },
  success: { colour: "var(--st-green)", Icon: IconCheck },
  error: { colour: "var(--st-red)", Icon: IconAlert },
} as const;

export function Toasts({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: number) => void;
}) {
  useEffect(() => {
    if (!toasts.length) return;
    const timers = toasts.map((toast) =>
      window.setTimeout(() => onDismiss(toast.id), toast.tone === "error" ? 9000 : 5000),
    );
    return () => timers.forEach(window.clearTimeout);
  }, [toasts, onDismiss]);

  return (
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[20rem] flex-col gap-2"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const { colour, Icon } = TONE[toast.tone];
        return (
          <div
            key={toast.id}
            role="status"
            className="pop animate-pop pointer-events-auto flex items-start gap-2.5 p-3"
          >
            <Icon size={14} style={{ color: colour, marginTop: 2, flexShrink: 0 }} />
            <div className="min-w-0 flex-1">
              <p className="text-[0.8125rem] font-medium text-ink">{toast.message}</p>
              {toast.detail ? (
                <p className="mt-0.5 text-micro leading-relaxed text-muted">{toast.detail}</p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={() => onDismiss(toast.id)}
              className="btn btn-quiet shrink-0"
              style={{ minHeight: 20, padding: 2 }}
              aria-label="Dismiss"
            >
              <IconClose size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
