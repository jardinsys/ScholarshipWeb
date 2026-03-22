import { useState } from 'react'
import { Search, Rss, Bookmark, Tag, User, TrendingUp, FileX, Clock, Star } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

// ── Filter pill config ────────────────────────────────────────────────────────
const FILTERS = [
  { id: 'recommended',  label: 'Recommended',       icon: Star },
  { id: 'top_paying',   label: 'Top Paying',         icon: TrendingUp },
  { id: 'no_essay',     label: 'Essay Not Required', icon: FileX },
  { id: 'recent',       label: 'Recent',             icon: Clock },
]

// ── Sidebar nav config ────────────────────────────────────────────────────────
const SIDEBAR_ITEMS = [
  { id: 'feed',    label: 'Web Feed',   icon: Rss },
  { id: 'saved',   label: 'Saved',      icon: Bookmark },
  { id: 'tags',    label: 'Tag Search', icon: Tag },
  { id: 'account', label: 'Account',    icon: User },
]

// ── Placeholder scholarship cards ─────────────────────────────────────────────
const MOCK_SCHOLARSHIPS = [
  { id: 1, name: 'Future Engineers Scholarship', provider: 'STEM Foundation', amount: '$5,000', due: 'Apr 15', tags: ['engineering', 'gpa 3.5+'], essay: false, recommended: true },
  { id: 2, name: 'Community Leaders Award',       provider: 'National Civic Trust', amount: '$2,500', due: 'May 1',  tags: ['leadership', 'any major'], essay: true,  recommended: false },
  { id: 3, name: 'First-Gen College Fund',        provider: 'EduAccess',       amount: '$10,000', due: 'Mar 30', tags: ['first-gen', 'income-based'], essay: false, recommended: true },
  { id: 4, name: 'Women in Tech Grant',           provider: 'TechForward',     amount: '$3,000', due: 'Jun 1',  tags: ['women', 'CS / IT'], essay: false, recommended: false },
  { id: 5, name: 'Rural Scholars Program',        provider: 'Heartland Fund',  amount: '$1,500', due: 'Apr 30', tags: ['rural', 'any major'], essay: true,  recommended: false },
]

function ScholarshipCard({ s, style }) {
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
          <Button variant="ghost" size="sm" className="h-7 text-xs">Save</Button>
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

  const toggleFilter = (id) =>
    setActiveFilters(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const filtered = MOCK_SCHOLARSHIPS.filter(s => {
    if (activeFilters.has('no_essay')     && s.essay)         return false
    if (activeFilters.has('recommended')  && !s.recommended)  return false
    if (searchQuery && !s.name.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  return (
    <div className="mx-auto flex max-w-5xl gap-6 px-6 py-8">

      {/* ── Left Sidebar ── */}
      <aside className="animate-slide-in w-44 shrink-0 space-y-1 pt-1">
        {SIDEBAR_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveNav(id)}
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

        {/* Search bar */}
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
          {filtered.map((s, i) => (
            <ScholarshipCard
              key={s.id}
              s={s}
              style={{ animationDelay: `${i * 60}ms` }}
            />
          ))}
        </div>
      </main>
    </div>
  )
}