"use client";

import { DayChart } from "@/components/day-chart";
import { ProjectPage } from "@/components/project-shell";
import { Card, StatusBadge } from "@/components/ui";
import { money } from "@/lib/format";

export default function Timeline() {
  return (
    <ProjectPage title="Timeline">
      {(data) => {
        const byDay = new Map<number, typeof data.tasks>();
        data.tasks.forEach((t) => {
          byDay.set(t.day, [...(byDay.get(t.day) ?? []), t]);
        });

        return (
          <>
            <p className="mt-0.5 text-sm text-[--color-muted]">
              Every day from 1 to {data.target_days}, so slack shows as slack rather
              than being closed up.
            </p>
            <div className="mt-4">
              <DayChart series={data.series} metric="runs" />
            </div>

            <Card className="mt-3 divide-y divide-[--color-line-2]">
              {data.series.map((day) => {
                const tasks = byDay.get(day.day) ?? [];
                return (
                  <div key={day.day} className="flex gap-4 px-3.5 py-2.5">
                    <span className="w-16 shrink-0 pt-0.5 font-mono text-xs text-[--color-muted]">
                      day {day.day}
                    </span>
                    {tasks.length === 0 ? (
                      <span className="text-sm italic text-[--color-muted]">
                        slack — no task planned
                      </span>
                    ) : (
                      <div className="min-w-0 flex-1 space-y-2">
                        {tasks.map((task) => (
                          <div key={task.id} className="flex flex-wrap items-baseline gap-x-3">
                            <span className="w-24 shrink-0">
                              <StatusBadge status={task.status} />
                            </span>
                            <span className="min-w-0 flex-1">
                              <span className="block font-medium">{task.title}</span>
                              <span className="text-xs text-[--color-muted]">
                                {task.milestone}
                              </span>
                            </span>
                            <span className="font-mono text-xs tabular-nums text-[--color-muted]">
                              {task.cost_usd ? money(task.cost_usd) : "—"}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </Card>
          </>
        );
      }}
    </ProjectPage>
  );
}
