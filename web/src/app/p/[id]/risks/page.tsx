"use client";

import { TriangleAlert } from "lucide-react";

import { ProjectPage } from "@/components/project-shell";
import { Card, Empty } from "@/components/ui";

export default function Risks() {
  return (
    <ProjectPage title="Risks">
      {(data) => (
        <>
          <p className="mt-0.5 text-sm text-muted">
            Written by the Planner up front, not discovered later.
          </p>
          <div className="mt-4">
            {data.risk_flags.length === 0 ? (
              <Empty>The plan declared no risk flags.</Empty>
            ) : (
              <Card className="divide-y divide-line-2">
                {data.risk_flags.map((flag, i) => (
                  <p key={i} className="flex gap-3 px-3.5 py-3 text-sm text-ink-2">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0 text-parked" />
                    <span>{flag}</span>
                  </p>
                ))}
              </Card>
            )}
          </div>
        </>
      )}
    </ProjectPage>
  );
}
