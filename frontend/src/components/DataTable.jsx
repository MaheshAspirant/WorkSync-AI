import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '../lib/format'

export default function DataTable({
  columns,
  rows = [],
  loading = false,
  emptyMessage = 'No records found.',
  page = 1,
  pages = 1,
  total = 0,
  onPage,
  rowKey,
  compact = false,
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="table-head">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={cn('px-4 py-3 font-semibold', column.headerClassName)}>
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {loading &&
              Array.from({ length: 6 }).map((_, index) => (
                <tr key={`skeleton-${index}`}>
                  {columns.map((column) => (
                    <td key={column.key} className={cn('px-4', compact ? 'py-2.5' : 'py-3.5')}>
                      <div className="h-3.5 w-full max-w-[140px] animate-pulse rounded bg-slate-100" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-14 text-center">
                  <p className="text-sm font-medium text-slate-500">{emptyMessage}</p>
                </td>
              </tr>
            )}
            {!loading &&
              rows.map((row, rowIndex) => (
                <tr
                  key={rowKey ? rowKey(row) : row.id || rowIndex}
                  className="transition hover:bg-slate-50/80"
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        'px-4 text-sm text-slate-700',
                        compact ? 'py-2.5' : 'py-3.5',
                        column.className,
                      )}
                    >
                      {column.render ? column.render(row) : row[column.key] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {onPage && (
        <div className="flex flex-col gap-2 border-t border-slate-200 bg-slate-50/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-slate-500">
            Showing <span className="font-semibold text-slate-700">{rows.length}</span> of{' '}
            <span className="font-semibold text-slate-700">{total}</span> records
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-secondary px-2 py-1.5"
              disabled={page <= 1}
              onClick={() => onPage(page - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs font-medium text-slate-600">
              Page {page} of {Math.max(1, pages)}
            </span>
            <button
              type="button"
              className="btn-secondary px-2 py-1.5"
              disabled={page >= pages}
              onClick={() => onPage(page + 1)}
              aria-label="Next page"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
