"use client";

import { ProjectPage } from "@/components/project-shell";
import { Card, Empty, Note, SectionTitle, Tag } from "@/components/ui";
import { bytes } from "@/lib/format";

export default function Proof() {
  return (
    <ProjectPage title="Proof">
      {(data) => {
        const shots = data.proof.filter((a) => a.is_image);
        const others = data.proof.filter((a) => !a.is_image);
        return (
          <>
            <p className="mt-0.5 text-sm text-muted">
              What each day actually produced. Tests passing is not evidence an
              application works.
            </p>

            {data.proof_linked > 0 && (
              <Note>
                {data.proof_linked} image(s) too large to embed are linked instead.
              </Note>
            )}

            <div className="mt-4">
              {shots.length === 0 ? (
                <Empty>
                  No proof artefacts yet. A day&apos;s proof lands in{" "}
                  <code className="font-mono">.longhaul/proof/day-NN/</code>.
                </Empty>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {shots.map((shot) => (
                    <figure
                      key={shot.href}
                      className="overflow-hidden rounded-lg border border-line bg-panel"
                    >
                      <a href={`/${shot.href}`}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`/${shot.href}`}
                          alt={`day ${shot.day} — ${shot.task}`}
                          loading="lazy"
                          className="block w-full bg-surface"
                        />
                      </a>
                      <figcaption className="flex justify-between border-t border-line px-2.5 py-1.5 text-xs text-muted">
                        <span>day {shot.day} · {shot.task}</span>
                        <span>{bytes(shot.size)}</span>
                      </figcaption>
                    </figure>
                  ))}
                </div>
              )}
            </div>

            {others.length > 0 && (
              <>
                <SectionTitle>Other artefacts</SectionTitle>
                <Card className="divide-y divide-line-2">
                  {others.map((item) => (
                    <a
                      key={item.href}
                      href={`/${item.href}`}
                      className="flex items-center gap-3 px-3.5 py-2 text-sm hover:bg-panel-2 hover:no-underline"
                    >
                      <span className="font-mono text-xs text-muted">
                        day {item.day}
                      </span>
                      <span>{item.name}</span>
                      <span className="ml-auto"><Tag>{bytes(item.size)}</Tag></span>
                    </a>
                  ))}
                </Card>
              </>
            )}
          </>
        );
      }}
    </ProjectPage>
  );
}
