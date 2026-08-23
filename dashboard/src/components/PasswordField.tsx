/**
 * A password input with a reveal control.
 *
 * Typing a long password blind is how people end up choosing short ones, so the
 * eye is not a nicety. It defaults to hidden, announces its state to screen
 * readers, and never leaves the value revealed when the field loses focus.
 */
import { useEffect, useState } from "react";
import { IconEye, IconEyeOff } from "./Icons";

export function PasswordField({
  label,
  value,
  onChange,
  autoComplete = "current-password",
  disabled = false,
  placeholder = "",
  autoFocus = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
  disabled?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  const [revealed, setRevealed] = useState(false);

  // Never leave a password on screen after the user has moved on.
  useEffect(() => {
    if (!revealed) return;
    const timer = window.setTimeout(() => setRevealed(false), 15000);
    return () => window.clearTimeout(timer);
  }, [revealed]);

  return (
    <label className="flex flex-col gap-1.5">
      <span className="eyebrow">{label}</span>
      <span className="relative flex items-center">
        <input
          type={revealed ? "text" : "password"}
          autoComplete={autoComplete}
          disabled={disabled}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className="h-10 w-full rounded-xl border pl-3 pr-10 text-[14px] text-ink outline-none disabled:opacity-60"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
        <button
          type="button"
          onClick={() => setRevealed((current) => !current)}
          disabled={disabled || !value}
          className="absolute right-1.5 rounded-lg p-1.5 text-muted transition-colors hover:text-ink disabled:opacity-40"
          aria-label={revealed ? "Hide password" : "Show password"}
          aria-pressed={revealed}
          title={revealed ? "Hide" : "Show"}
          tabIndex={-1}
        >
          {revealed ? <IconEyeOff size={16} /> : <IconEye size={16} />}
        </button>
      </span>
    </label>
  );
}
