"use client";

import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import type { DaySeries } from "@/lib/api";
import { money } from "@/lib/format";
import { Card } from "./ui";

/** Every day from 1 to N, so slack shows as a gap rather than being closed up. */
export function DayChart({
  series, metric,
}: { series: DaySeries[]; metric: "cost_usd" | "runs" }) {
  const empty = series.every((d) => d[metric] === 0);
  return (
    <Card className="p-3">
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: -22 }}>
            <CartesianGrid vertical={false} stroke="var(--color-line-2)" />
            <XAxis
              dataKey="day"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 10, fill: "var(--color-muted)" }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={48}
              tick={{ fontSize: 10, fill: "var(--color-muted)" }}
              tickFormatter={(v: number) => (metric === "cost_usd" ? money(v) : String(v))}
            />
            <Tooltip
              cursor={{ fill: "var(--color-line-2)" }}
              contentStyle={{
                background: "var(--color-panel)",
                border: "1px solid var(--color-line)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelFormatter={(d) => `Day ${d}`}
              formatter={(value) => {
                const n = Number(value ?? 0);
                return [
                  metric === "cost_usd" ? money(n) : `${n} runs`,
                  metric === "cost_usd" ? "spent" : "agent runs",
                ] as [string, string];
              }}
            />
            <Bar dataKey={metric} fill="var(--color-accent)" radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {empty && (
        <p className="pb-1 text-center text-xs text-muted">
          Nothing recorded yet — this fills in as days run.
        </p>
      )}
    </Card>
  );
}
