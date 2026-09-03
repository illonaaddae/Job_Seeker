export function relativeTime(value: string | null | undefined): string {
  if (!value) return "";
  const normalised = value.endsWith("Z") || value.includes("+") ? value : `${value}Z`;
  const then = new Date(normalised);
  if (Number.isNaN(then.getTime())) return "";

  const seconds = Math.round((Date.now() - then.getTime()) / 1000);
  const future = seconds < 0;
  const abs = Math.abs(seconds);
  if (abs < 45) return "just now";

  const label =
    abs < 3600
      ? plural(Math.round(abs / 60), "min")
      : abs < 86400
        ? plural(Math.round(abs / 3600), "hour")
        : abs < 604800
          ? plural(Math.round(abs / 86400), "day")
          : abs < 2629800
            ? plural(Math.round(abs / 604800), "week")
            : plural(Math.round(abs / 2629800), "month");

  return future ? `in ${label}` : `${label} ago`;
}

function plural(count: number, unit: string): string {
  return `${count} ${unit}${count === 1 ? "" : "s"}`;
}

/**
 * The same instant, short enough for a table cell.
 *
 * "14 hours ago" in a 5rem column wraps onto two lines and doubles the row
 * height of the whole table. "14h" does not, and in a column of ages the unit
 * letter is all the reader needs.
 */
export function compactTime(value: string | null | undefined): string {
  if (!value) return "";
  const normalised = value.endsWith("Z") || value.includes("+") ? value : `${value}Z`;
  const then = new Date(normalised);
  if (Number.isNaN(then.getTime())) return "";

  const seconds = Math.abs(Math.round((Date.now() - then.getTime()) / 1000));
  if (seconds < 60) return "now";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  if (seconds < 604800) return `${Math.round(seconds / 86400)}d`;
  if (seconds < 2629800) return `${Math.round(seconds / 604800)}w`;
  return `${Math.round(seconds / 2629800)}mo`;
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value.length <= 10 ? `${value}T00:00:00Z` : value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function percent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function initials(value: string): string {
  const words = value.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** Deterministic hue per company, so a logo-less avatar still feels intentional. */
export function hueFor(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 360;
  }
  return hash;
}

export function truncate(value: string, limit: number): string {
  return value.length <= limit ? value : `${value.slice(0, limit - 1).trimEnd()}…`;
}
