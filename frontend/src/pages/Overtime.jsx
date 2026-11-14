import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AlertTriangle, Clock3, TimerReset, Users } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import PageHeader from '../components/PageHeader'
import StatCard from '../components/StatCard'
import ChartCard from '../components/ChartCard'
import DataTable from '../components/DataTable'
import Badge from '../components/Badge'
import Alert from '../components/Alert'
import { formatDate, formatNumber, formatShortDate, toISODate } from '../lib/format'

export default function Overtime() {
  const today = new Date()
  const [start, setStart] = useState(toISODate(new Date(today.getTime() - 30 * 86400000)))
  const [end, setEnd] = useState(toISODate(today))
  const [employeeFilter, setEmployeeFilter] = useState('')
  const [page, setPage] = useState(1)

  const query = `?start=${start}&end=${end}${employeeFilter ? `&employee_id=${employeeFilter}` : ''}`
  const { data, loading, error } = useApi(`/attendance/overtime${query}`)
  const rows = data?.rows || []

  const weekly = useMemo(() => {
    const map = new Map()
    for (const row of rows) {
      map.set(row.week_start, Number(((map.get(row.week_start) || 0) + Number(row.overtime_hours || 0)).toFixed(2)))
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => String(a).localeCompare(String(b)))
      .map(([week, overtime]) => ({ week: formatShortDate(week), overtime }))
  }, [rows])

  const pageRows = rows.slice((page - 1) * 20, page * 20)

  const columns = [
    {
      key: 'employee',
      label: 'Employee',
      render: (row) => (
        <div>
          <p className="font-semibold text-slate-800">{row.employee_name}</p>
          <p className="text-xs text-slate-500">{row.employee_id} · {row.team_id}</p>
        </div>
      ),
    },
    { key: 'week_start', label: 'Week starting', render: (row) => <span className="text-xs text-slate-600">{formatDate(row.week_start)}</span> },
    { key: 'scheduled_hours', label: 'Scheduled', render: (row) => <span className="text-sm">{formatNumber(row.scheduled_hours, 1)}h</span> },
    { key: 'actual_hours', label: 'Actual', render: (row) => <span className="text-sm">{formatNumber(row.actual_hours, 1)}h</span> },
    { key: 'overtime_hours', label: 'Overtime', render: (row) => <span className={`text-sm font-semibold ${row.overtime_hours > 0 ? 'text-amber-700' : 'text-slate-400'}`}>{formatNumber(row.overtime_hours, 1)}h</span> },
    { key: 'overtime_cap', label: 'Cap', render: (row) => <span className="text-xs text-slate-500">{formatNumber(row.overtime_cap, 0)}h</span> },
    { key: 'cap_exceeded', label: 'Cap status', render: (row) => <Badge tone={row.cap_exceeded ? 'red' : 'green'}>{row.cap_exceeded ? 'Exceeded' : 'Within cap'}</Badge> },
  ]

  return (
    <div>
      <PageHeader
        title="Overtime monitor"
        subtitle="Overtime is calculated from attendance actual hours above the weekly standard — never entered as an independent number."
      />
      {error && <Alert tone="error" className="mb-4">{error}</Alert>}

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Total overtime" value={formatNumber(data?.total_overtime_hours, 1)} suffix="h" icon={Clock3} tone="amber" />
        <StatCard label="Average / employee" value={formatNumber(data?.average_overtime_per_employee, 2)} suffix="h" icon={TimerReset} tone="brand" />
        <StatCard label="Employees over cap" value={data?.employees_over_cap ?? 0} icon={AlertTriangle} tone="red" />
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div><label className="label">From</label><input type="date" className="input" value={start} onChange={(e) => { setStart(e.target.value); setPage(1) }} /></div>
        <div><label className="label">To</label><input type="date" className="input" value={end} onChange={(e) => { setEnd(e.target.value); setPage(1) }} /></div>
        <div className="min-w-64">
          <label className="label">Employee ID (optional)</label>
          <input className="input" placeholder="EMP-000001" value={employeeFilter} onChange={(e) => { setEmployeeFilter(e.target.value.trim()); setPage(1) }} />
        </div>
        <span className="ml-auto inline-flex items-center gap-1 text-xs text-slate-500"><Users size={14} /> {rows.length} employee-week rows</span>
      </div>

      <div className="mb-6">
        <ChartCard title="Weekly overtime" subtitle="Sum of employee weekly overtime in the selected period" height="h-64">
          {weekly.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weekly}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(value) => [`${value}h`, 'Overtime']} contentStyle={{ borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 12 }} />
                <Bar dataKey="overtime" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="flex h-full items-center justify-center text-sm text-slate-500">No overtime rows in this period.</p>
          )}
        </ChartCard>
      </div>

      <DataTable
        columns={columns}
        rows={pageRows}
        loading={loading}
        page={page}
        pages={Math.max(1, Math.ceil(rows.length / 20))}
        total={rows.length}
        onPage={setPage}
        rowKey={(row) => `${row.employee_id}-${row.week_start}`}
        emptyMessage="No overtime recorded for this period."
      />
    </div>
  )
}
