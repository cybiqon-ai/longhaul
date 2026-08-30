import type { NextConfig } from "next";

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
};

export default nextConfig;
