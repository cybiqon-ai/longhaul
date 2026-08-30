"use client";

import {
  Activity, AlertTriangle, DollarSign, Image as ImageIcon,
  LayoutGrid, ListChecks, MessagesSquare, Rows3,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cx, money } from "@/lib/format";
import { ThemeToggle } from "./theme-toggle";

interface NavItem { href: string; label: string; icon: typeof Activity; count?: number }
interface NavGroup { group: string; items: NavItem[] }

export function projectNav(id: string, counts: {
  tasks?: number; runs?: number; chats?: number; proof?: number; risks?: number;
}): NavGroup[] {
  const p = `/p/${id}`;
  return [
    { group: "Delivery", items: [
      { href: p, label: "Overview", icon: LayoutGrid },
      { href: `${p}/timeline`, label: "Timeline", icon: Rows3 },
      { href: `${p}/tasks`, label: "Tasks", icon: ListChecks, count: counts.tasks },
    ]},
    { group: "Observability", items: [
      { href: `${p}/runs`, label: "Agent runs", icon: Activity, count: counts.runs },
      { href: `${p}/chats`, label: "Chats", icon: MessagesSquare, count: counts.chats },
      { href: `${p}/spend`, label: "Spend", icon: DollarSign },
    ]},
    { group: "Evidence", items: [
      { href: `${p}/proof`, label: "Proof", icon: ImageIcon, count: counts.proof },
      { href: `${p}/risks`, label: "Risks", icon: AlertTriangle, count: counts.risks },
    ]},
  ];
}

export function Sidebar({ groups, footer }: { groups: NavGroup[]; footer?: ReactNode }) {
  const pathname = usePathname();
  return (
    <nav className="sticky top-0 hidden h-screen flex-col border-r border-line bg-panel md:flex">
      <Link href="/" className="flex items-baseline gap-2 px-4 pb-3 pt-4 hover:no-underline">
        <b className="text-base tracking-tight">Longhaul</b>
      </Link>

      {groups.map((group) => (
        <div key={group.group} className="pb-1 pt-2">
          <h3 className="mb-1 px-4 text-[11px] font-semibold uppercase tracking-[0.09em] text-muted">
            {group.group}
          </h3>
          {group.items.map((item) => {
            const active =
              item.href === pathname ||
              (item.href !== "/" && pathname.startsWith(`${item.href}/`));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "flex items-center gap-2.5 border-l-2 px-4 py-1.5 text-sm hover:no-underline",
                  active
                    ? "border-accent bg-accent-soft font-semibold text-ink"
                    : "border-transparent text-ink-2 hover:bg-panel-2 hover:text-ink"
                )}
              >
                <item.icon className="size-4 shrink-0 opacity-80" />
                <span className="truncate">{item.label}</span>
                {item.count != null && item.count > 0 && (
                  <span className="ml-auto font-mono text-[11px] text-muted">
                    {item.count}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      ))}

      {footer && (
        <div className="mt-auto border-t border-line px-4 py-3 text-xs text-muted">
          {footer}
        </div>
      )}
    </nav>
  );
}

export function TopBar({
  crumbs, cost, live, extra,
}: { crumbs: ReactNode; cost?: number; live?: boolean; extra?: ReactNode }) {
  return (
    <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-panel px-5 py-2.5">
      <div className="flex min-w-0 items-center gap-2">{crumbs}</div>
      <div className="ml-auto flex items-center gap-2">
        {extra}
        {cost != null && (
          <span className="rounded-full border border-line px-2.5 py-0.5 font-mono text-xs text-ink-2">
            {money(cost)}
          </span>
        )}
        {live != null && (
          <span className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-xs text-ink-2">
            <span
              className={cx(
                "size-2 rounded-full",
                live ? "bg-done ring-2 ring-done/25" : "bg-pending"
              )}
            />
            {live ? "live" : "offline"}
          </span>
        )}
        <ThemeToggle />
      </div>
    </header>
  );
}

export function Shell({
  sidebar, topbar, children,
}: { sidebar: ReactNode; topbar: ReactNode; children: ReactNode }) {
  return (
    // Without a sidebar the two-column grid puts the only child into the first
    // column — 232px wide — and squeezes the whole page into it. The Projects
    // screen has no sidebar, so the columns have to be conditional.
    <div className={cx("grid min-h-screen", sidebar ? "md:grid-cols-[232px_1fr]" : null)}>
      {sidebar}
      <div className="min-w-0">
        {topbar}
        <main className="mx-auto w-full max-w-[1500px] px-5 pb-16 pt-5">{children}</main>
      </div>
    </div>
  );
}
