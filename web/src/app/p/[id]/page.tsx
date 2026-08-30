"use client";

import Link from "next/link";

import type { Task } from "@/lib/api";
import { ATTENTION, money } from "@/lib/format";
import { DayChart } from "@/components/day-chart";
import { useProjectId } from "@/lib/use-project-id";
import { ProjectPage } from "@/components/project-shell";
import { Card, Empty, SectionTitle, StatusBadge, Tag, Tile } from "@/components/ui";

function AttentionRow({ task, id }: { task: Task; id: string }) {
  return (
    <Link
      href={`/p/${id}/tasks?task=${task.id}`}
      className="flex gap-3 border-b border-line-2 px-3.5 py-2.5 last:border-0 hover:bg-panel-2 hover:no-underline"
    >
      <span className="w-14 shrink-0 pt-0.5 font-mono text-xs text-muted">
        day {task.day}
      </span>
      <span className="w-24 shrink-0 pt-0.5">
        <StatusBadge status={task.status} />
      </span>
      <span className="min-w-0">
        <span className="block truncate font-medium">{task.title}</span>
        {task.last_error && (
          <span className="mt-0.5 block truncate text-xs text-muted">
            {task.last_error.split("\n")[0]}
          </span>
        )}
      </span>
    </Link>
  );
}

export default function Overview() {
  const id = useProjectId();

  return (
    <ProjectPage title="Overview">
      {(data) => {
        const c = data.counts;
        const attention = data.tasks.filter((t) => ATTENTION.includes(t.status));
        return (
          <>
            <p className="mt-0.5 text-sm text-muted">
              {data.tasks_total} tasks over {data.target_days} days ·{" "}
              <code className="font-mono">{data.profile}</code>
            </p>

            <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4 xl:grid-cols-8">
              <Tile label="done" value={c.done} tone="done" />
              <Tile label="running" value={c.in_progress} tone="in_progress" />
              <Tile label="failed" value={c.failed} tone="failed" />
              <Tile label="parked" value={c.parked} tone="parked" />
              <Tile label="halted" value={c.halted} tone="halted" />
              <Tile label="to go" value={c.pending} />
              <Tile label="agent runs" value={data.runs.length} />
              <Tile label="spent" value={money(data.total_cost_usd)} />
            </div>

            <SectionTitle>Spend per day</SectionTitle>
            <DayChart series={data.series} metric="cost_usd" />

            <SectionTitle>Needs you</SectionTitle>
            {attention.length ? (
              <Card>
                {attention.map((task) => (
                  <AttentionRow key={task.id} task={task} id={id} />
                ))}
              </Card>
            ) : (
              <Empty>Nothing is waiting on a human.</Empty>
            )}

            {data.risk_flags.length > 0 && (
              <>
                <SectionTitle>Risk flags</SectionTitle>
                <Card className="divide-y divide-line-2">
                  {data.risk_flags.slice(0, 3).map((flag, i) => (
                    <p key={i} className="px-3.5 py-2.5 text-sm text-ink-2">
                      {flag}
                    </p>
                  ))}
                </Card>
                {data.risk_flags.length > 3 && (
                  <p className="mt-2 text-xs text-muted">
                    <Link href={`/p/${id}/risks`}>
                      {data.risk_flags.length - 3} more on the Risks page
                    </Link>
                  </p>
                )}
              </>
            )}
          </>
        );
      }}
    </ProjectPage>
  );
}
