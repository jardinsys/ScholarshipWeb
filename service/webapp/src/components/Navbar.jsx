import { Link, NavLink } from 'react-router-dom'
import { BookOpen, LayoutDashboard, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function Navbar({ user, onLogout }) {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-sand-100/80 backdrop-blur-md">
      <nav className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
        <Link to="/" className="font-display text-lg font-bold tracking-tight text-ink">
          Scholarship<span className="text-moss"><i>Web</i></span>
        </Link>

        <div className="flex items-center gap-3">
          <NavLink
            to="/dashboard"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                isActive ? 'bg-moss text-white' : 'text-ink/70 hover:bg-sand-200 hover:text-ink'
              )
            }
          >
            <LayoutDashboard size={14} /> Dashboard
          </NavLink>

          <NavLink
            to="/browse"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                isActive ? 'bg-moss text-white' : 'text-ink/70 hover:bg-sand-200 hover:text-ink'
              )
            }
          >
            <BookOpen size={14} /> Browse
          </NavLink>

          {user ? (
            <div className="flex items-center gap-2">
              <NavLink
                to="/profile"
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                    isActive ? 'bg-moss text-white' : 'text-ink/70 hover:bg-sand-200 hover:text-ink'
                  )
                }
              >
                <User size={14} />
                <span className="font-mono">@{user.username}</span>
              </NavLink>
              <Button variant="ghost" size="sm" onClick={onLogout}>
                Log out
              </Button>
            </div>
          ) : null}
        </div>
      </nav>
    </header>
  )
}