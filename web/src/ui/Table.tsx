import type { ReactNode } from "react";

export interface Column<T> {
  /** Stable key for the column (also used for React keys). */
  key: string;
  header: ReactNode;
  /** Cell renderer for a row. */
  render: (row: T, index: number) => ReactNode;
  /** Optional inline width/align for the column. */
  width?: string;
  align?: "left" | "right" | "center";
}

export interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  /** Stable React key per row. */
  rowKey: (row: T, index: number) => string;
  /** Optional row click handler (e.g. expand CFR text on /rules). */
  onRowClick?: (row: T, index: number) => void;
  /** Optional per-row data attributes (e.g. data-severity for tinting). */
  rowAttrs?: (row: T, index: number) => Record<string, string> | undefined;
  empty?: ReactNode;
  className?: string;
  caption?: ReactNode;
}

/**
 * Generic, typed table built on the Evidentia .tbl class set. Presentation
 * only — sorting/filtering live in the calling route. Renders inside a
 * horizontally-scrollable .table-wrap.
 */
export function Table<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  rowAttrs,
  empty,
  className,
  caption,
}: TableProps<T>) {
  return (
    <div className={className ? `table-wrap ${className}` : "table-wrap"}>
      <table className="tbl">
        {caption != null && <caption className="muted">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                style={{
                  width: c.width,
                  textAlign: c.align ?? "left",
                }}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="muted">
                {empty ?? "Nothing to show."}
              </td>
            </tr>
          )}
          {rows.map((row, i) => (
            <tr
              key={rowKey(row, i)}
              onClick={onRowClick ? () => onRowClick(row, i) : undefined}
              style={onRowClick ? { cursor: "pointer" } : undefined}
              {...(rowAttrs?.(row, i) ?? {})}
            >
              {columns.map((c) => (
                <td key={c.key} style={{ textAlign: c.align ?? "left" }}>
                  {c.render(row, i)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default Table;
