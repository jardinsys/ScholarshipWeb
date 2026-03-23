import { Link, NavLink } from 'react-router-dom'
import { BookOpen, User, LayoutDashboard } from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/browse',    label: 'Browse',    icon: BookOpen },
]

export function Navbar({ user, onLogout }) {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-sand-100/80 backdrop-blur-md">
      <nav className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
        <Link to="/" className="font-display text-lg font-bold tracking-tight text-ink">
          Scholarship<span className="text-moss"><i>Web</i></span>
        </Link>

        <div className="flex items-center gap-3">
          <NavLink to="/browse" className={({ isActive }) =>
            cn('flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              isActive ? 'bg-moss text-white' : 'text-ink/70 hover:bg-sand-200 hover:text-ink')
          }>
            <BookOpen size={14} /> Browse
          </NavLink>

          {user ? (
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-muted-foreground">@{user.username}</span>
              <Button variant="ghost" size="sm" onClick={onLogout}>Log out</Button>
            </div>
          ) : null}
        </div>
      </nav>
    </header>
  )
}