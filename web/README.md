# The Longhaul interface

Next.js, statically exported, and **bundled into the Python package at release
time** — so a user runs `uv tool install longhaul-ai` and gets the interface with
no Node, no npm and no build step. Contributors need a JavaScript toolchain;
users never do.

## Working on it

```bash
cd web
npm install
npm run dev          # http://localhost:3000
```

In development the app talks to the Python API on `http://127.0.0.1:4321`, so
run the backend alongside it in another terminal:

```bash
longhaul ui          # serves the API, and the bundled app if one is built
```

## Building

```bash
npm run build        # → ../src/longhaul/ui/static/
```

That copies the export into the Python package. Commit the result: it is what
ships in the wheel.

## What is deliberate here

**No component library.** Eight primitives in `src/components/ui.tsx`, written by
hand. They are used everywhere, and owning them means the interface has one
visual language rather than a library's defaults plus a layer of overrides.

**The palette is stated as roles, not swatches** (`src/app/globals.css`) — the
same discipline the Designer role is told to apply to projects it plans.

**Sorting and filtering are client-side.** The payload is one project's plan, not
a paginated dataset, and a round trip to a loopback socket to re-sort ten rows
would be theatre.

**The project id comes from `location.pathname`, not from route params.** A
static export prerenders `/p/[id]` as `/p/_`, and the Python server rewrites
`/p/neon-drift/tasks` onto that file — so the baked-in params say `_` and only
the URL knows the real id. See `src/lib/use-project-id.ts`.

**The zero-dependency page still exists.** `longhaul report` writes one
self-contained HTML file for CI artefacts and email attachments, and the server
falls back to it when no export is bundled. Two surfaces with different jobs.
