"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * The project id from the URL.
 *
 * A static export prerenders `/p/[id]` as `/p/_`, and the Python server rewrites
 * `/p/neon-drift/tasks` to that file. So the params baked into the HTML say
 * `_`, and the real id is only in `location.pathname`.
 *
 * Reading the path directly is deterministic and does not depend on how Next's
 * client router reconciles a rewritten URL with prerendered params — which is an
 * internal detail that could change under us.
 */
export function useProjectId(): string {
  const params = useParams<{ id: string }>();
  const fromParams = params?.id ?? "";
  const [id, setId] = useState(fromParams === "_" ? "" : fromParams);

  useEffect(() => {
    const match = window.location.pathname.match(/^\/p\/([^/]+)/);
    const fromPath = match ? decodeURIComponent(match[1]) : "";
    if (fromPath && fromPath !== "_") setId(fromPath);
    else if (fromParams && fromParams !== "_") setId(fromParams);
  }, [fromParams]);

  return id;
}
