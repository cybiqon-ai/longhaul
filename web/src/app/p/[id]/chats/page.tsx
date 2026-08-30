"use client";

import { AlertTriangle, Bot, ChevronRight, User, Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import { api, type ProjectData, type Transcript, type TranscriptRef } from "@/lib/api";
import { bytes, cx, duration, money } from "@/lib/format";
import { useProjectId } from "@/lib/use-project-id";
import { ProjectPage } from "@/components/project-shell";
import { Failed, Loading } from "@/components/states";
import { Card, Empty, Tag } from "@/components/ui";

function ToolBlock({ tool }: { tool: Transcript["messages"][0]["tools"][0] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-1.5 rounded border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left text-xs"
      >
        <ChevronRight className={cx("size-3 transition-transform", open && "rotate-90")} />
        <Wrench className="size-3 opacity-70" />
        <span className="font-mono">
          {tool.kind === "call" ? tool.name || "tool" : "result"}
        </span>
        {tool.error && <span className="text-failed">failed</span>}
        <span className="ml-auto text-muted">
          {tool.input.split("\n").length} lines
        </span>
      </button>
      {open && (
        <pre className="overflow-x-auto whitespace-pre-wrap border-t border-line px-2.5 py-2 font-mono text-[11px] leading-relaxed">
          {tool.input}
        </pre>
      )}
    </div>
  );
}

function Conversation({ transcript }: { transcript: Transcript }) {
  return (
    <div className="space-y-3">
      <Card className="flex flex-wrap gap-x-5 gap-y-1 px-3.5 py-2.5 text-sm">
        <span className="tabular-nums">{money(transcript.cost_usd)}</span>
        <span className="tabular-nums">{duration(transcript.duration_ms / 1000)}</span>
        <span className="tabular-nums">{transcript.num_turns} turns</span>
        <span className="font-mono text-xs text-muted">
          {transcript.session_id?.slice(0, 8) ?? "—"}
        </span>
        {transcript.tools_used.length > 0 && (
          <span className="flex flex-wrap gap-1">
            {transcript.tools_used.map((t) => <Tag key={t}>{t}</Tag>)}
          </span>
        )}
        {transcript.retries.length > 0 && (
          <span className="flex items-center gap-1 text-xs text-parked">
            <AlertTriangle className="size-3" />
            recovered from {transcript.retries.length} API retry(s): {transcript.retries.join(", ")}
          </span>
        )}
      </Card>

      {transcript.messages.map((message, i) => (
        <Card key={i} className="px-3.5 py-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-xs text-muted">
            {message.role === "assistant"
              ? <Bot className="size-3.5" />
              : <User className="size-3.5" />}
            <span>{message.role === "assistant" ? "agent" : "tool results"}</span>
            {message.subagent && <Tag>subagent</Tag>}
          </div>
          {message.text && (
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.text}</p>
          )}
          {message.tools.map((tool, j) => <ToolBlock key={j} tool={tool} />)}
        </Card>
      ))}
    </div>
  );
}

function Chats({ data }: { data: ProjectData }) {
  const id = useProjectId();
  const refs = data.transcripts ?? [];
  const [selected, setSelected] = useState<TranscriptRef | null>(refs[0] ?? null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    setError(null);
    api.transcript(id, selected.id)
      .then(setTranscript)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, selected]);

  if (!refs.length) {
    return (
      <Empty>
        No conversations recorded yet. Every agent run writes its full transcript to{" "}
        <code className="font-mono">.longhaul/runs/</code> as it happens.
      </Empty>
    );
  }

  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-[16rem_1fr]">
      <Card className="h-fit divide-y divide-line-2">
        {refs.map((ref) => (
          <button
            key={ref.id}
            type="button"
            onClick={() => setSelected(ref)}
            className={cx(
              "block w-full px-3 py-2 text-left text-sm hover:bg-panel-2",
              selected?.id === ref.id && "bg-accent-soft"
            )}
          >
            <span className="flex items-center gap-2">
              <Tag>{ref.role}</Tag>
              <span className="font-mono text-xs text-muted">
                day {ref.day} · {ref.task}
              </span>
            </span>
            <span className="mt-0.5 block text-xs text-muted">
              attempt {ref.attempt} · {bytes(ref.size)}
            </span>
          </button>
        ))}
      </Card>

      <div className="min-w-0">
        {loading && <Loading what="the conversation" />}
        {error && <Failed error={error} />}
        {transcript && !loading && !error && <Conversation transcript={transcript} />}
      </div>
    </div>
  );
}

export default function ChatsPage() {
  return (
    <ProjectPage title="Chats">
      {(data) => (
        <>
          <p className="mt-0.5 text-sm text-muted">
            What each agent actually said and did. Stored verbatim, so a ledger row
            saying $1.99 can be opened and read.
          </p>
          <Chats data={data} />
        </>
      )}
    </ProjectPage>
  );
}
