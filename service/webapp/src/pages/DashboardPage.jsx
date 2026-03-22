import { useState, useEffect } from 'react'
import { Search, Rss, Bookmark, Tag, User, TrendingUp, FileX, Clock, Star, Tags } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AuthModal } from '@/components/ui/AuthModal'
import { cn } from '@/lib/utils'
import { getScholarships } from '@/lib/api'

const FILTERS = [
  { id: 'recommended', label: 'Recommended',       icon: Star },
  { id: 'top_paying',  label: 'Top Paying',         icon: TrendingUp },
  { id: 'no_essay',    label: 'Essay Not Required', icon: FileX },
//  { id: 'recent',      label: 'Recent',             icon: Clock },
]

const SIDEBAR_ITEMS = [
  { id: 'feed',    label: 'Web Feed',   icon: Rss },
  { id: 'saved',   label: 'Saved',      icon: Bookmark },
  { id: 'tags',    label: 'Tag Search', icon: Tags },
  { id: 'account', label: 'Account',    icon: User },
]

// Sidebar items that require auth
const AUTH_REQUIRED = new Set(['saved', 'tags', 'account'])

// inside DashboardPage(), replace MOCK_SCHOLARSHIPS with:
const [scholarships, setScholarships] = useState([])
const [loading, setLoading] = useState(true)

useEffect(() => {
  getScholarships({
    search:   searchQuery   || undefined,
    no_essay: activeFilters.has('no_essay') || undefined,
  })
    .then(res => setScholarships(res.data.scholarships))
    .catch(err => console.error(err))
    .finally(() => setLoading(false))
}, [searchQuery, activeFilters])

function ScholarshipCard({ s, style, onSave }) {
  return (
    <article
      style={style}
      className="animate-fade-up group flex flex-col gap-3 rounded-xl border border-border bg-white p-5 shadow-sm hover:shadow-md transition-shadow duration-200"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-display font-semibold text-sm leading-snug group-hover:text-moss transition-colors">
            {s.name}
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">{s.provider}</p>
        </div>
        <span className="shrink-0 font-mono text-sm font-medium text-amber">{s.amount}</span>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {s.tags.map(t => (
          <Badge key={t} variant="default" className="text-[10px]">{t}</Badge>
        ))}
        {!s.essay && <Badge variant="amber" className="text-[10px]">No Essay</Badge>}
        {s.recommended && <Badge variant="outline" className="text-[10px] border-amber/40 text-amber">★ Match</Badge>}
      </div>

      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-muted-foreground">Due {s.due}</span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={onSave}>
            Save
          </Button>
          <Button size="sm" className="h-7 text-xs">Apply →</Button>
        </div>
      </div>
    </article>
  )
}

export default function DashboardPage() {
  const [activeNav,     setActiveNav]     = useState('feed')
  const [activeFilters, setActiveFilters] = useState(new Set())
  const [searchQuery,   setSearchQuery]   = useState('')
  const [modal,         setModal]         = useState({ open: false, reason: 'account' })

  const openModal = (reason) => setModal({ open: true, reason })
  const closeModal = ()      => setModal(m => ({ ...m, open: false }))

  const handleNavClick = (id) => {
    if (AUTH_REQUIRED.has(id)) {
      openModal(id)   // 'saved', 'tags', or 'account'
    } else {
      setActiveNav(id)
    }
  }

  const toggleFilter = (id) =>
    setActiveFilters(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const filtered = MOCK_SCHOLARSHIPS.filter(s => {
    if (activeFilters.has('no_essay')    && s.essay)        return false
    if (activeFilters.has('recommended') && !s.recommended) return false
    if (searchQuery && !s.name.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  return (
    <>
      <AuthModal open={modal.open} onClose={closeModal} reason={modal.reason} />

      <div className="mx-auto flex max-w-5xl gap-6 px-6 py-8">

        {/* ── Left Sidebar ── */}
        <aside className="animate-slide-in w-44 shrink-0 space-y-1 pt-1">
          {SIDEBAR_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => handleNavClick(id)}
              className={cn(
                'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150',
                activeNav === id
                  ? 'bg-moss text-white'
                  : 'text-ink/70 hover:bg-sand-200 hover:text-ink'
              )}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </aside>

        {/* ── Main Feed ── */}
        <main className="flex-1 space-y-4">

          {/* Search */}
          <div className="animate-fade-up relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search scholarships…"
              className="pl-9"
            />
          </div>

          {/* Filter pills */}
          <div className="animate-fade-up delay-75 flex flex-wrap gap-2">
            {FILTERS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => toggleFilter(id)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-all duration-150',
                  activeFilters.has(id)
                    ? 'border-moss bg-moss text-white'
                    : 'border-border bg-white text-ink/70 hover:border-moss/50 hover:text-ink'
                )}
              >
                <Icon size={11} />
                {label}
              </button>
            ))}
          </div>

          {/* Cards */}
          <div className="space-y-3">
            {filtered.length === 0 && (
              <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border text-sm text-muted-foreground">
                No scholarships match your filters
              </div>
            )}
            {scholarships.map((s, i) => (
              <ScholarshipCard
                key={s.id}
                s={s}
                style={{ animationDelay: `${i * 60}ms` }}
                onSave={() => openModal('save')}
              />
            ))}
          </div>
        </main>
      </div>
    </>
  )
}