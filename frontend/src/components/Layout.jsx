import { Link, NavLink, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function RequireAuth() {
  const { user, loading } = useAuth()
  if (loading) return <p className="p-8 text-center text-slate-500">Loading…</p>
  return user ? <AppShell /> : <Navigate to="/login" replace />
}

function AppShell() {
  const { user, logout } = useAuth()
  const link = ({ isActive }) =>
    `rounded-md px-3 py-2 text-sm font-medium ${isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-3">
          <Link to="/" className="font-semibold text-slate-900">
            Viva Prep Agent
          </Link>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={link}>
              Projects
            </NavLink>
            <NavLink to="/profile" className={link}>
              {user.name}
            </NavLink>
            <button onClick={logout} className="rounded-md px-3 py-2 text-sm text-slate-500 hover:bg-slate-100">
              Log out
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

export function AuthPage({ title, children }) {
  const { user, loading } = useAuth()
  if (!loading && user) return <Navigate to="/" replace />
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <h1 className="mb-1 text-center text-2xl font-semibold text-slate-900">Viva Prep Agent</h1>
        <p className="mb-6 text-center text-sm text-slate-500">{title}</p>
        {children}
      </div>
    </div>
  )
}
