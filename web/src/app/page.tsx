"use client";

import { FolderOpen, TriangleAlert } from "lucide-react";
import Link from "next/link";

import { api, type ProjectRow } from "@/lib/api";
import { ATTENTION, STATUS_COLOR, ago, cx, money } from "@/lib/format";
import { useData } from "@/lib/use-data";
import { Failed, Loading } from "@/components/states";
import { Shell, TopBar } from "@/components/shell";
import { Card, Empty, Tag } from "@/components/ui";

/** A compressed view of a project's whole plan: one segment per day. */
function DayStrip({ project }: { project: ProjectRow }) {
  const counts = project.counts;
  if (!counts) return null;
  const order = ["done", "in_progress", "failed", "halted", "parked", "pending"] as const;
  const total = order.reduce((n, k) => n + (counts[k] ?? 0), 0) || 1;
  return (
    <div className="mt-3 flex h-1.5 overflow-hidden rounded-full bg-line-2">
      {order.map((status) =>
        counts[status] ? (
          <span
            key={status}
            title={`${counts[status]} ${status}`}
            style={{
              width: `${(counts[status] / total) * 100}%`,
              background: STATUS_COLOR[status],
            }}
          />
        ) : null
      )}
    </div>
  );
}

function ProjectCard({ project }: { project: ProjectRow }) {
  const broken = project.status !== "ok";
  const needsYou = project.needs_you ?? 0;

  const body = (
    <Card
      className={cx(
        "h-full p-4 transition-colors",
        !broken && "hover:border-accent",
        broken && "opacity-70"
      )}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-semibold">{project.title ?? project.name}</h3>
          <p className="truncate font-mono text-xs text-muted">{project.path}</p>
        </div>
        {needsYou > 0 && (
          <span className="ml-auto flex shrink-0 items-center gap-1 rounded-full border border-parked/50 px-2 py-0.5 text-xs text-parked">
            <TriangleAlert className="size-3" />
            {needsYou}
          </span>
        )}
      </div>

      {broken ? (
        <p className="mt-3 text-sm text-ink-2">
          {project.status === "missing"
            ? "The directory no longer has a .longhaul/ folder."
            : (project.problem ?? "No plan yet — run `longhaul plan` in it.")}
        </p>
      ) : (
        <>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2">
            <span className="tabular-nums">
              day {project.days_done}/{project.target_days}
            </span>
            <span className="tabular-nums">{money(project.total_cost_usd)}</span>
            <span className="tabular-nums">{project.runs ?? 0} runs</span>
            <Tag>{project.profile}</Tag>
          </div>
          <DayStrip project={project} />
          <p className="mt-2 text-xs text-muted">
            updated {ago(project.updated_at)}
          </p>
        </>
      )}
    </Card>
  );

  return broken ? body : <Link href={`/p/${project.id}`} className="hover:no-underline">{body}</Link>;
}

export default function Home() {
  const { data, error, loading, live } = useData(() => api.projects(), []);
  const projects = data?.projects ?? [];
  const attention = projects.reduce((n, p) => n + (p.needs_you ?? 0), 0);

  return (
    <Shell
      sidebar={null}
      topbar={
        <TopBar crumbs={<b className="text-[15px]">Projects</b>} live={live} />
      }
    >
      <h1 className="text-xl font-semibold tracking-tight">Projects on this machine</h1>
      <p className="mt-0.5 text-sm text-muted">
        {projects.length
          ? `${projects.length} registered${attention ? ` · ${attention} task(s) waiting on you` : ""}`
          : "Longhaul runs locally. Nothing leaves your machine."}
      </p>

      <div className="mt-5">
        {loading && <Loading what="projects" />}
        {error && <Failed error={error} />}
        {!loading && !error && projects.length === 0 && (
          <Empty>
            <span className="flex flex-col items-center gap-2">
              <FolderOpen className="size-5 opacity-60" />
              No projects registered yet. Run{" "}
              <code className="font-mono">longhaul init</code> inside a repository,
              or <code className="font-mono">longhaul projects --add &lt;path&gt;</code>.
            </span>
          </Empty>
        )}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      </div>
    </Shell>
  );
}
