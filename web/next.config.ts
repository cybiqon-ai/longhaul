import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import type { NextConfig } from "next";

/**
 * A deterministic build id, derived from the source rather than randomised.
 *
 * Next generates a random id per build and bakes it into asset paths and every
 * emitted HTML file, which makes the export differ on every rebuild even when
 * nothing changed. Since the export is committed and shipped in the Python
 * wheel, that would mean a 55-file diff on every build and no way for CI to tell
 * a stale export from a fresh one.
 *
 * Hashing the source makes the id change exactly when the source does, which is
 * what the id is for.
 */
function sourceHash(): string {
  const hash = createHash("sha256");
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir).sort()) {
      const path = join(dir, entry);
      if (statSync(path).isDirectory()) walk(path);
      else hash.update(entry).update(readFileSync(path));
    }
  };
  walk(join(process.cwd(), "src"));
  hash.update(readFileSync(join(process.cwd(), "package-lock.json")));
  return hash.digest("hex").slice(0, 20);
}

/**
 * Statically exported, and bundled into the Python wheel at release time.
 *
 * That is what keeps the promise that a user runs `uv tool install longhaul-ai`
 * and gets the interface with no Node, no npm and no build step. Contributors
 * need a JavaScript toolchain; users never do.
 *
 * A static export means no server components at request time and no image
 * optimiser — both fine here, because every route reads from a local HTTP API
 * on the same machine.
 */
const nextConfig: NextConfig = {
  output: "export",
  // The Python server serves /p/neon-drift by falling back to index.html, so
  // trailing slashes would only add a redirect that never resolves.
  trailingSlash: false,
  images: { unoptimized: true },
  generateBuildId: async () => sourceHash(),
};

export default nextConfig;
