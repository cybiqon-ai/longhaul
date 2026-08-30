"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import type { Run } from "@/lib/api";
import { duration, money, when } from "@/lib/format";
import { DataTable } from "@/components/data-table";
import { ProjectPage } from "@/components/project-shell";
import { Chip, StatusBadge, Tag } from "@/components/ui";

const columns: ColumnDef<Run, unknown>[] = [
  { accessorKey: "at", header: "Time",
    cell: (c) => <span className="whitespace-nowrap font-mono text-xs text-muted">{when(c.getValue<string>())}</span> },
  { accessorKey: "role", header: "Role", cell: (c) => <Tag>{c.getValue<string>()}</Tag> },
  { accessorKey: "task", header: "Task",
    cell: (c) => <span className="font-mono text-xs">{c.getValue<string>()}</span> },
  { accessorKey: "title", header: "Working on",
    cell: (c) => <span className="text-sm">{c.getValue<string>()}</span> },
  { accessorKey: "attempt", header: "Try",
    cell: (c) => <span className="font-mono text-xs text-muted">{c.getValue<number>()}</span> },
  { accessorKey: "duration_s", header: "Duration",
    cell: (c) => <span className="font-mono text-xs tabular-nums">{duration(c.getValue<number>())}</span> },
  { accessorKey: "cost_usd", header: "Cost",
    cell: (c) => <span className="font-mono text-xs tabular-nums">{money(c.getValue<number>())}</span> },
  { accessorKey: "ok", header: "Result",
    cell: (c) => <StatusBadge status={c.getValue<boolean>() ? "done" : "failed"} /> },
  { accessorKey: "session_id", header: "Session",
    cell: (c) => {
      const id = c.getValue<string | null>();
      return <span className="font-mono text-xs text-muted">{id ? id.slice(0, 8) : "—"}</span>;
    } },
];

function RunList({ runs }: { runs: Run[] }) {
  const [role, setRole] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const roles = useMemo(() => {
    const out: Record<string, number> = {};
    runs.forEach((r) => { out[r.role] = (out[r.role] ?? 0) + 1; });
    return out;
  }, [runs]);

  const q = query.trim().toLowerCase();
  const rows = runs.filter((r) => {
    if (role && r.role !== role) return false;
    if (!q) return true;
    return [r.task, r.role, r.title, r.session_id].join(" ").toLowerCase().includes(q);
  });

  return (
    <>
      <p className="mt-0.5 text-sm text-muted">
        Every invocation, from <code className="font-mono">.longhaul/ledger.jsonl</code>.
        Append-only, so the bill is auditable after the fact.
      </p>
      <div className="mb-3 mt-3 flex flex-wrap items-center gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search runs — task, role, session"
          className="min-w-[12rem] flex-1 rounded-lg border border-line bg-panel px-2.5 py-1.5 text-sm outline-none placeholder:text-muted focus:border-accent"
        />
        <Chip active={!role} onClick={() => setRole(null)} count={runs.length}>All roles</Chip>
        {Object.keys(roles).sort().map((r) => (
          <Chip key={r} active={role === r} count={roles[r]}
                onClick={() => setRole(role === r ? null : r)}>
            {r}
          </Chip>
        ))}
      </div>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(r) => `${r.at}-${r.task}-${r.role}-${r.attempt}`}
        empty="No agent has run yet."
      />
    </>
  );
}

export default function Runs() {
  return <ProjectPage title="Agent runs">{(data) => <RunList runs={data.runs} />}</ProjectPage>;
}
