import { Link, NavLink } from 'react-router-dom'
import { BookOpen, User, LayoutDashboard } from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/profile',   label: 'Profile',   icon: User },
  { to: '/browse',    label: 'Browse',    icon: BookOpen },
]

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-sand-100/80 backdrop-blur-md">
      <nav className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
        {/* Wordmark */}
        <Link to="/" className="font-display text-lg font-bold tracking-tight text-ink">
          Scholar<span className="text-moss">Match</span>
        </Link>

        {/* Links */}
        <div className="flex items-center gap-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150',
                  isActive
                    ? 'bg-moss text-white'
                    : 'text-ink/70 hover:bg-sand-200 hover:text-ink'
                )
              }
            >
              <Icon size={14} />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </header>
  )
}