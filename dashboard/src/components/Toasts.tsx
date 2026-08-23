import { useEffect } from "react";
import { IconCheck, IconClose } from "./Icons";

export interface Toast {
  id: number;
  tone: "info" | "success" | "error";
  message: string;
  detail?: string;
}

const TONE: Record<Toast["tone"], { border: string; icon: string }> = {
  info: { border: "var(--line-strong)", icon: "var(--muted)" },
  success: { border: "var(--positive)", icon: "var(--positive)" },
  error: { border: "var(--danger)", icon: "var(--danger)" },
};

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
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-[330px] flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className="card animate-slide-in pointer-events-auto flex items-start gap-2.5 p-3"
          style={{ borderLeft: `3px solid ${TONE[toast.tone].border}`, boxShadow: "var(--shadow-lift)" }}
        >
          <IconCheck size={15} style={{ color: TONE[toast.tone].icon, marginTop: 2 }} />
          <div className="min-w-0 flex-1">
            <p className="text-[14px] font-medium text-ink">{toast.message}</p>
            {toast.detail ? (
              <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted">{toast.detail}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={() => onDismiss(toast.id)}
            className="rounded p-0.5 text-muted hover:text-ink"
            aria-label="Dismiss"
          >
            <IconClose size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
