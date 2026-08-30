"use client";

import {
  type ColumnDef, type SortingState, flexRender,
  getCoreRowModel, getSortedRowModel, useReactTable,
} from "@tanstack/react-table";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Fragment, type ReactNode, useState } from "react";

import { cx } from "@/lib/format";

/**
 * One dense table for every view that lists things.
 *
 * Sorting is client-side because everything is already in memory — the payload
 * is one project's plan, not a paginated dataset — and a round trip to a
 * loopback socket to re-sort ten rows would be theatre.
 */
export function DataTable<T extends object>({
  columns, rows, expand, rowKey, empty,
}: {
  columns: ColumnDef<T, unknown>[];
  rows: T[];
  rowKey: (row: T) => string;
  expand?: (row: T) => ReactNode;
  empty?: ReactNode;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (!rows.length) {
    return (
      <div className="rounded-lg border border-[--color-line] bg-[--color-panel] px-4 py-10 text-center text-sm text-[--color-muted]">
        {empty ?? "Nothing to show."}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[--color-line] bg-[--color-panel]">
      <table className="w-full border-collapse">
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => {
                const sortable = header.column.getCanSort();
                const dir = header.column.getIsSorted();
                return (
                  <th
                    key={header.id}
                    onClick={sortable ? header.column.getToggleSortingHandler() : undefined}
                    className={cx(
                      "sticky top-0 z-[1] whitespace-nowrap border-b border-[--color-line-2] bg-[--color-panel-2] px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-[0.07em] text-[--color-muted]",
                      sortable && "cursor-pointer select-none hover:text-[--color-ink]"
                    )}
                  >
                    <span className="inline-flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {dir === "asc" && <ChevronUp className="size-3" />}
                      {dir === "desc" && <ChevronDown className="size-3" />}
                    </span>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const key = rowKey(row.original);
            const isOpen = !!open[key];
            return (
              <Fragment key={key}>
                <tr
                  onClick={expand ? () => setOpen((o) => ({ ...o, [key]: !isOpen })) : undefined}
                  className={cx(
                    "border-b border-[--color-line-2] last:border-0 hover:bg-[--color-panel-2]",
                    expand && "cursor-pointer"
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2 align-top">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
                {expand && isOpen && (
                  <tr className="border-b border-[--color-line-2] bg-[--color-panel-2]">
                    <td colSpan={row.getVisibleCells().length} className="px-4 py-3">
                      {expand(row.original)}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
