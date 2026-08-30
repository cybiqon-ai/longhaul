"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { api, type ProjectData } from "@/lib/api";
import { ago } from "@/lib/format";
import { useData } from "@/lib/use-data";
import { useProjectId } from "@/lib/use-project-id";
import { Shell, Sidebar, TopBar, projectNav } from "./shell";
import { Failed, Loading } from "./states";

/**
 * Every project route renders through here, so the sidebar, breadcrumb and live
 * indicator are defined once and the routes only describe their own content.
 */
export function ProjectPage({
  title,
  children,
}: {
  title: string;
  children: (data: ProjectData) => ReactNode;
}) {
  const id = useProjectId();
  const { data, error, loading, live } = useData(() => api.project(id), [id]);

  const nav = projectNav(id, {
    tasks: data?.tasks_total,
    runs: data?.runs.length,
    chats: data?.transcripts?.length,
    proof: data?.proof.length,
    risks: data?.risk_flags.length,
  });

  return (
    <Shell
      sidebar={
        <Sidebar
          groups={nav}
          footer={
            data ? (
              <>
                day {data.days_done} of {data.target_days}
                <br />
                updated {ago(data.updated_at)}
              </>
            ) : null
          }
        />
      }
      topbar={
        <TopBar
          live={live}
          cost={data?.total_cost_usd}
          crumbs={
            <>
              <Link href="/" className="text-sm text-muted hover:text-ink">
                Projects
              </Link>
              <span className="text-muted">/</span>
              <b className="truncate text-[15px]">{data?.project ?? id}</b>
              {data && (
                <span className="ml-1 rounded-full border border-line px-2 py-0.5 font-mono text-xs text-ink-2">
                  day {data.days_done}/{data.target_days}
                </span>
              )}
            </>
          }
        />
      }
    >
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {loading && <Loading what={title.toLowerCase()} />}
      {error && <div className="mt-4"><Failed error={error} /></div>}
      {data?.error && <div className="mt-4"><Failed error={data.error} /></div>}
      {data && !data.error && children(data)}
    </Shell>
  );
}
