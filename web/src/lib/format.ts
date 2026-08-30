import type { Status } from "./api";

export const STATUS_LABEL: Record<Status, string> = {
  done: "done",
  in_progress: "running",
  failed: "failed",
  parked: "parked",
  halted: "halted",
  pending: "pending",
  skipped: "skipped",
};

/** Ordered by how much they want your attention, not alphabetically. */
export const STATUS_ORDER: Status[] = [
  "failed", "halted", "parked", "in_progress", "done", "pending", "skipped",
];

export const STATUS_COLOR: Record<Status, string> = {
  done: "var(--color-done)",
  in_progress: "var(--color-running)",
  failed: "var(--color-failed)",
  parked: "var(--color-parked)",
  halted: "var(--color-halted)",
  pending: "var(--color-pending)",
  skipped: "var(--color-muted)",
};

/** Statuses that mean a person has to look. */
export const ATTENTION: Status[] = ["failed", "halted", "parked"];

export function money(n: number | undefined): string {
  return `$${(n ?? 0).toFixed(2)}`;
}

export function duration(seconds: number): string {
  if (!seconds) return "—";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

/** ISO timestamps come from the API; render them without the timezone noise. */
export function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  return String(iso).replace("T", " ").replace(/(\+.*|Z)$/, "");
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const secs = Math.max(0, (Date.now() - then) / 1000);
  if (secs < 90) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
