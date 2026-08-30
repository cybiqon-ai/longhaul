"use client";

/**
 * The small set of primitives every view is built from.
 *
 * Deliberately hand-written rather than pulled from a component library: there
 * are eight of them, they are used everywhere, and owning them means the
 * interface has one visual language instead of a library's defaults plus
 * overrides.
 */
import type { ReactNode } from "react";

import type { Status } from "@/lib/api";
import { STATUS_COLOR, STATUS_LABEL, cx } from "@/lib/format";

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cx("rounded-lg border border-[--color-line] bg-[--color-panel]", className)}>
      {children}
    </div>
  );
}

export function Tile({
  label, value, tone,
}: { label: string; value: ReactNode; tone?: Status }) {
  return (
    <Card className="px-3.5 py-2.5">
      <div
        className="text-2xl leading-tight tracking-tight tabular-nums"
        style={tone ? { color: STATUS_COLOR[tone] } : undefined}
      >
        {value}
      </div>
      <div className="text-xs text-[--color-muted]">{label}</div>
    </Card>
  );
}

export function StatusDot({ status }: { status: Status }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-block size-2 shrink-0 rounded-full",
        status === "in_progress" && "motion-safe:animate-pulse",
        status === "pending" && "border border-[--color-pending]"
      )}
      style={status === "pending" ? undefined : { background: STATUS_COLOR[status] }}
    />
  );
}

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-sm">
      <StatusDot status={status} />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function Tag({
  children, tone,
}: { children: ReactNode; tone?: "warn" | "risk" }) {
  return (
    <span
      className={cx(
        "inline-block rounded border px-1.5 py-px font-mono text-[11px]",
        tone === "warn" && "border-[--color-parked]/50 text-[--color-parked]",
        tone === "risk" && "border-[--color-failed]/50 text-[--color-failed]",
        !tone && "border-[--color-line] text-[--color-muted]"
      )}
    >
      {children}
    </span>
  );
}

export function Chip({
  children, active, onClick, count,
}: { children: ReactNode; active?: boolean; onClick?: () => void; count?: number }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cx(
        "rounded-full border px-2.5 py-1 text-sm transition-colors",
        active
          ? "border-[--color-accent] bg-[--color-accent] font-semibold text-[--color-panel]"
          : "border-[--color-line] bg-[--color-panel] text-[--color-ink-2] hover:text-[--color-ink]"
      )}
    >
      {children}
      {count != null && <span className="ml-1.5 font-mono text-xs opacity-75">{count}</span>}
    </button>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <Card>
      <p className="px-4 py-10 text-center text-sm text-[--color-muted]">{children}</p>
    </Card>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-7 mb-2 text-xs font-semibold uppercase tracking-[0.09em] text-[--color-muted]">
      {children}
    </h2>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return (
    <p className="my-2 border-l-2 border-[--color-parked] bg-[--color-panel] px-3 py-2 text-sm text-[--color-ink-2]">
      {children}
    </p>
  );
}
