export function generateStaticParams() {
  // A static export needs at least one param to emit the route. The Python
  // server falls back to index.html for any unknown path, so the client router
  // resolves the real project id at runtime — this is only a build-time seed.
  return [{ id: "_" }];
}

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  return children;
}
