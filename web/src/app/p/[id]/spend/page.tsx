"use client";

import { DayChart } from "@/components/day-chart";
import { ProjectPage } from "@/components/project-shell";
import { Card, Empty, SectionTitle, Tag, Tile } from "@/components/ui";
import { duration, money } from "@/lib/format";

export default function Spend() {
  return (
    <ProjectPage title="Spend">
      {(data) => {
        const byRole = new Map<string, { runs: number; cost: number; secs: number }>();
        data.runs.forEach((run) => {
          const v = byRole.get(run.role) ?? { runs: 0, cost: 0, secs: 0 };
          byRole.set(run.role, {
            runs: v.runs + 1,
            cost: v.cost + run.cost_usd,
            secs: v.secs + run.duration_s,
          });
        });
        const roles = [...byRole.entries()].sort((a, b) => b[1].cost - a[1].cost);

        const perDay = data.total_cost_usd / Math.max(data.days_done, 1);
        const forecast = perDay * data.target_days;

        return (
          <>
            <p className="mt-0.5 text-sm text-[--color-muted]">
              {money(data.total_cost_usd)} across {data.runs.length} agent runs.
              Every figure comes from the CLI&apos;s own reported cost, not an estimate.
            </p>

            <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <Tile label="spent" value={money(data.total_cost_usd)} />
              <Tile label="per day so far" value={money(perDay)} />
              <Tile
                label={`forecast at ${data.target_days} days`}
                value={data.days_done ? money(forecast) : "—"}
              />
              <Tile label="agent runs" value={data.runs.length} />
            </div>

            <SectionTitle>Per day</SectionTitle>
            <DayChart series={data.series} metric="cost_usd" />

            <SectionTitle>By role</SectionTitle>
            {roles.length === 0 ? (
              <Empty>Nothing spent yet.</Empty>
            ) : (
              <Card className="divide-y divide-[--color-line-2]">
                {roles.map(([role, v]) => (
                  <div key={role} className="flex items-center gap-4 px-3.5 py-2.5 text-sm">
                    <span className="w-28 shrink-0"><Tag>{role}</Tag></span>
                    <span className="w-20 shrink-0 font-mono text-xs tabular-nums">
                      {v.runs} runs
                    </span>
                    <span className="w-24 shrink-0 font-mono tabular-nums">{money(v.cost)}</span>
                    <span className="font-mono text-xs tabular-nums text-[--color-muted]">
                      {duration(v.secs)}
                    </span>
                    <span
                      className="ml-auto h-1.5 rounded-full bg-[--color-accent]"
                      style={{ width: `${(v.cost / (roles[0][1].cost || 1)) * 30}%` }}
                    />
                  </div>
                ))}
              </Card>
            )}
          </>
        );
      }}
    </ProjectPage>
  );
}
