"use client";

import { Loader2 } from "lucide-react";

import { Card } from "./ui";

export function Loading({ what }: { what: string }) {
  return (
    <div className="flex items-center gap-2 px-1 py-10 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" />
      Loading {what}…
    </div>
  );
}

export function Failed({ error }: { error: string }) {
  return (
    <Card className="border-failed/40">
      <div className="px-4 py-5">
        <p className="text-sm font-semibold text-failed">Could not load this</p>
        <p className="mt-1 text-sm text-ink-2">{error}</p>
        <p className="mt-3 text-xs text-muted">
          Longhaul reads from a local server. If it has stopped, start it again with{" "}
          <code className="font-mono">longhaul ui</code>.
        </p>
      </div>
    </Card>
  );
}
