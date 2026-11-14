import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BadgeCheck,
  BarChart3,
  CalendarDays,
  ClipboardList,
  Clock3,
  FileSearch,
  LayoutDashboard,
  LogOut,
  Menu,
  Repeat2,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
  UsersRound,
  X,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { cn, initials } from '../lib/format'

const NAV_GROUPS = [
  {
    label: 'Workspace',
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, roles: ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE'] },
      { to: '/schedule', label: 'Shift Schedule', icon: CalendarDays, roles: ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE'] },
      { to: '/leave', label: 'Leave', icon: ClipboardList, roles: ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE'] },
      { to: '/swaps', label: 'Shift Swaps', icon: Repeat2, roles: ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE'] },
      { to: '/attendance', label: 'Attendance', icon: BadgeCheck, roles: ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE'] },
      { to: '/overtime', label: 'Overtime', icon: Clock3, roles: ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE'] },
    ],
  },
  {
    label: 'People',
    items: [
      { to: '/employees', label: 'Employees', icon: Users, roles: ['ADMIN', 'HR', 'MANAGER'] },
      { to: '/teams', label: 'Teams', icon: UsersRound, roles: ['ADMIN', 'HR', 'MANAGER'] },
      { to: '/skills', label: 'Skills', icon: Sparkles, roles: ['ADMIN', 'HR'] },
    ],
  },
  {
    label: 'Insights',
    items: [
      { to: '/analytics', label: 'Analytics', icon: BarChart3, roles: ['ADMIN', 'HR', 'MANAGER'] },
      { to: '/exceptions', label: 'Exceptions', icon: ShieldCheck, roles: ['ADMIN', 'HR', 'MANAGER', 'EMPLOYEE'] },
      { to: '/audit', label: 'Audit Trail', icon: FileSearch, roles: ['ADMIN', 'HR'] },
      { to: '/admin', label: 'Administration', icon: Settings, roles: ['ADMIN'] },
    ],
  },
]

const TITLES = {
  '/': 'Dashboard',
  '/schedule': 'Shift Schedule',
  '/leave': 'Leave Management',
  '/swaps': 'Shift Swaps',
  '/attendance': 'Attendance',
  '/overtime': 'Overtime Monitor',
  '/employees': 'Employees',
  '/teams': 'Teams',
  '/skills': 'Skills',
  '/analytics': 'Analytics & Reports',
  '/exceptions': 'Conflicts & Exceptions',
  '/audit': 'Audit Trail',
  '/admin': 'System Administration',
  '/profile': 'My Profile',
}

export default function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const role = user?.role || 'EMPLOYEE'
  const groups = useMemo(
    () =>
      NAV_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => item.roles.includes(role)),
      })).filter((group) => group.items.length),
    [role],
  )
  const title = TITLES[location.pathname] || 'WorkSync AI'

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-slate-50">
      {open && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-slate-950 text-slate-300 transition-transform lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center gap-3 border-b border-white/10 px-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500 text-white shadow-lg shadow-brand-900/40">
            <CalendarDays size={19} />
          </span>
          <div>
            <p className="text-sm font-bold tracking-tight text-white">WorkSync AI</p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">Workforce OS</p>
          </div>
          <button
            type="button"
            className="ml-auto rounded-md p-1 text-slate-400 hover:bg-white/10 lg:hidden"
            onClick={() => setOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {groups.map((group) => (
            <div key={group.label} className="mb-5">
              <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.to === '/'}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition',
                          isActive
                            ? 'bg-brand-600 text-white shadow-sm'
                            : 'text-slate-400 hover:bg-white/5 hover:text-white',
                        )
                      }
                    >
                      <Icon size={17} />
                      {item.label}
                    </NavLink>
                  )
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-white/10 p-3">
          <button
            type="button"
            onClick={() => navigate('/profile')}
            className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-white/5"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-500/20 text-xs font-bold text-brand-200">
              {initials(user?.username?.slice(0, 1), user?.username?.slice(1, 2))}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-white">{user?.username}</span>
              <span className="block text-[11px] uppercase tracking-wide text-slate-500">{role}</span>
            </span>
            <LogOut
              size={16}
              className="text-slate-500 hover:text-white"
              onClick={(event) => {
                event.stopPropagation()
                logout()
              }}
            />
          </button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
            onClick={() => setOpen(true)}
          >
            <Menu size={20} />
          </button>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">{title}</p>
            <p className="text-[11px] text-slate-500">
              {new Date().toLocaleDateString('en-IN', {
                weekday: 'long',
                day: '2-digit',
                month: 'long',
                year: 'numeric',
              })}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              API connected
            </span>
            <button
              type="button"
              onClick={() => navigate('/profile')}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white"
              title="Profile"
            >
              {initials(user?.username?.slice(0, 1), user?.username?.slice(1, 2))}
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
