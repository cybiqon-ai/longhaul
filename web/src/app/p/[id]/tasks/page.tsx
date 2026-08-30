"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import type { Status, Task } from "@/lib/api";
import { STATUS_LABEL, STATUS_ORDER, money, when } from "@/lib/format";
import { DataTable } from "@/components/data-table";
import { ProjectPage } from "@/components/project-shell";
import { Chip, StatusBadge, Tag } from "@/components/ui";

function Detail({ task }: { task: Task }) {
  const rows: [string, React.ReactNode][] = [
    ["Acceptance criteria", (
      <ul className="list-disc pl-4 text-[--color-ink-2]">
        {task.criteria.map((c, i) => <li key={i}>{c}</li>)}
      </ul>
    )],
  ];
  if (task.milestone) rows.push(["Milestone", task.milestone]);
  if (task.depends_on.length) rows.push(["Depends on", task.depends_on.join(", ")]);
  if (task.proof_expect) rows.push(["Proof must show", task.proof_expect]);
  if (task.proof_detail) rows.push(["Proof result", task.proof_detail]);
  if (task.branch) {
    rows.push(["Branch", (
      <code className="font-mono text-xs">
        {task.branch}{task.commit_sha ? ` · ${task.commit_sha}` : ""}
      </code>
    )]);
  }
  if (task.pr_url) rows.push(["Pull request", <a href={task.pr_url}>#{task.pr_number}</a>]);
  if (task.started_at) rows.push(["Started", when(task.started_at)]);
  if (task.finished_at) rows.push(["Finished", when(task.finished_at)]);

  return (
    <div className="space-y-3 text-sm">
      <dl className="grid grid-cols-[9rem_1fr] gap-x-4 gap-y-1.5">
        {rows.map(([label, value], i) => (
          <div key={i} className="contents">
            <dt className="text-xs text-[--color-muted]">{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {task.findings.length > 0 && (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-[--color-line] bg-[--color-surface] p-2.5 font-mono text-xs">
          {task.findings.join("\n")}
        </pre>
      )}
      {task.last_error && (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-[--color-line] bg-[--color-surface] p-2.5 font-mono text-xs">
          {task.last_error}
        </pre>
      )}
    </div>
  );
}

const columns: ColumnDef<Task, unknown>[] = [
  { accessorKey: "day", header: "Day",
    cell: (c) => <span className="font-mono text-xs text-[--color-muted]">{c.getValue<number>()}</span> },
  { accessorKey: "id", header: "ID",
    cell: (c) => <span className="font-mono text-xs">{c.getValue<string>()}</span> },
  { accessorKey: "status", header: "Status",
    cell: (c) => <StatusBadge status={c.getValue<Status>()} /> },
  { accessorKey: "kind", header: "Kind",
    cell: (c) => {
      const task = c.row.original;
      return (
        <span className="flex flex-wrap gap-1">
          <Tag>{task.kind}</Tag>
          {task.needs_human && <Tag tone="warn">needs you</Tag>}
          {task.risk !== "low" && <Tag tone="risk">{task.risk}</Tag>}
        </span>
      );
    } },
  { accessorKey: "title", header: "Task",
    cell: (c) => <span className="font-medium">{c.getValue<string>()}</span> },
  { accessorKey: "attempts", header: "Try",
    cell: (c) => <span className="font-mono text-xs text-[--color-muted]">{c.getValue<number>() || "—"}</span> },
  { accessorKey: "cost_usd", header: "Cost",
    cell: (c) => {
      const n = c.getValue<number>();
      return <span className="font-mono text-xs tabular-nums">{n ? money(n) : "—"}</span>;
    } },
];

function TaskList({ tasks, total }: { tasks: Task[]; total: number }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [query, setQuery] = useState("");

  const counts = useMemo(() => {
    const out: Partial<Record<Status, number>> = {};
    tasks.forEach((t) => { out[t.status] = (out[t.status] ?? 0) + 1; });
    return out;
  }, [tasks]);

  const q = query.trim().toLowerCase();
  const rows = tasks.filter((t) => {
    if (status && t.status !== status) return false;
    if (!q) return true;
    return [t.id, t.title, t.kind, t.milestone, t.last_error]
      .join(" ").toLowerCase().includes(q);
  });

  return (
    <>
      <p className="mt-0.5 text-sm text-[--color-muted]">{rows.length} of {total} shown</p>
      <div className="mb-3 mt-3 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search tasks — title, id, kind, error"
          className="min-w-[12rem] flex-1 rounded-lg border border-[--color-line] bg-[--color-panel] px-2.5 py-1.5 text-sm outline-none placeholder:text-[--color-muted] focus:border-[--color-accent]"
        />
        <Chip active={!status} onClick={() => setStatus(null)} count={total}>All</Chip>
        {STATUS_ORDER.filter((s) => counts[s]).map((s) => (
          <Chip key={s} active={status === s} count={counts[s]}
                onClick={() => setStatus(status === s ? null : s)}>
            {STATUS_LABEL[s]}
          </Chip>
        ))}
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(t) => t.id}
        expand={(t) => <Detail task={t} />}
        empty="No task matches those filters."
      />
    </>
  );
}

export default function Tasks() {
  return (
    <ProjectPage title="Tasks">
      {(data) => <TaskList tasks={data.tasks} total={data.tasks_total} />}
    </ProjectPage>
  );
}
