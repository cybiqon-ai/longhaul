/**
 * The client for Longhaul's local API.
 *
 * Everything is read-only and served from the same machine, so there is no auth,
 * no retry policy and no cache layer here on purpose — the network is a loopback
 * socket. What this file does care about is that a failure is legible: an
 * unreachable server usually means the CLI stopped, and saying so is more useful
 * than a spinner that never resolves.
 */

export type Status =
  | "done" | "in_progress" | "failed" | "parked" | "halted" | "pending" | "skipped";

export interface Counts extends Record<Status, number> {}

export interface ProjectRow {
  id: string;
  path: string;
  name: string;
  status: "ok" | "missing" | "unplanned";
  problem?: string;
  title?: string;
  profile?: string;
  target_days?: number;
  tasks?: number;
  counts?: Counts;
  days_done?: number;
  total_cost_usd?: number;
  updated_at?: string;
  runs?: number;
  needs_you?: number;
}

export interface Task {
  id: string;
  day: number;
  title: string;
  kind: string;
  risk: string;
  needs_human: boolean;
  criteria: string[];
  depends_on: string[];
  milestone: string;
  proof_expect: string;
  proof_detail: string;
  proof_artifacts: string[];
  status: Status;
  attempts: number;
  cost_usd: number;
  branch: string | null;
  commit_sha: string | null;
  pr_number: number | null;
  pr_url: string | null;
  started_at: string | null;
  finished_at: string | null;
  last_error: string;
  findings: string[];
}

export interface Run {
  at: string;
  task: string;
  day: number | null;
  title: string;
  role: string;
  attempt: number;
  session_id: string | null;
  cost_usd: number;
  duration_s: number;
  ok: boolean;
}

export interface DaySeries {
  day: number;
  cost_usd: number;
  runs: number;
  statuses: Status[];
}

export interface ProofItem {
  day: number;
  task: string;
  name: string;
  href: string;
  src: string;
  is_image: boolean;
  size: number;
}

export interface TranscriptRef {
  id: string;
  day: number;
  task: string;
  role: string;
  attempt: number;
  size: number;
  modified: number;
}

export interface ProjectData {
  project: string;
  project_id: string;
  path: string;
  profile: string;
  target_days: number;
  updated_at: string;
  counts: Counts;
  tasks_total: number;
  days_done: number;
  total_cost_usd: number;
  risk_flags: string[];
  milestones: { id: string; title: string; days: number[] }[];
  tasks: Task[];
  runs: Run[];
  series: DaySeries[];
  proof: ProofItem[];
  proof_linked: number;
  transcripts: TranscriptRef[];
  error?: string;
}

export interface TranscriptMessage {
  role: "assistant" | "user" | "system" | "result";
  text: string;
  subagent: boolean;
  tools: { kind: "call" | "result"; name: string; input: string; error?: boolean }[];
}

export interface Transcript {
  id: string;
  session_id: string | null;
  cost_usd: number;
  duration_ms: number;
  num_turns: number;
  retries: string[];
  result: string;
  ok: boolean;
  tools_used: string[];
  messages: TranscriptMessage[];
  error?: string;
}

/** In development the app runs on :3000 and the API on :4321. */
const BASE =
  process.env.NODE_ENV === "development" ? "http://127.0.0.1:4321" : "";

export class ApiError extends Error {}

async function get<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { cache: "no-store" });
  } catch {
    throw new ApiError(
      "Cannot reach Longhaul. Is `longhaul ui` still running in a terminal?"
    );
  }
  if (!response.ok) throw new ApiError(`${path} returned ${response.status}`);
  return (await response.json()) as T;
}

export const api = {
  projects: () => get<{ projects: ProjectRow[] }>("/api/projects"),
  project: (id: string) => get<ProjectData>(`/api/projects/${id}`),
  transcript: (id: string, path: string) =>
    get<Transcript>(`/api/projects/${id}/transcript/${path}`),
};

/** Subscribe to the server's change stream. Returns an unsubscribe function. */
export function onUpdate(handler: () => void): () => void {
  if (typeof window === "undefined" || !("EventSource" in window)) return () => {};
  let source: EventSource | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let backoff = 1000;
  let closed = false;

  const connect = () => {
    if (closed) return;
    source = new EventSource(`${BASE}/events`);
    source.addEventListener("open", () => { backoff = 1000; });
    source.addEventListener("update", () => handler());
    source.addEventListener("error", () => {
      // The orchestrator restarting is normal; back off rather than hammering
      // a socket that is not there.
      source?.close();
      timer = setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 30_000);
    });
  };
  connect();

  return () => {
    closed = true;
    if (timer) clearTimeout(timer);
    source?.close();
  };
}
