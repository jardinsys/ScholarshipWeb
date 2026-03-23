import { useState, useEffect, useCallback } from 'react'
import { Search, Filter, ChevronLeft, ChevronRight, FileX, BookmarkPlus, BookmarkCheck, ExternalLink } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AuthModal } from '@/components/ui/AuthModal'
import { cn } from '@/lib/utils'
import { getScholarships, saveScholarship, unsaveScholarship, getSaved } from '@/lib/api'

const PAGE_SIZE = 15

const FILTER_OPTIONS = [
  { id: 'no_essay', label: 'No Essay Required', icon: FileX },
]

function ScholarshipCard({ s, isSaved, onSave, onUnsave, user }) {
  const [saving, setSaving] = useState(false)

  const handleSaveToggle = async () => {
    if (saving) return
    setSaving(true)
    try {
      if (isSaved) await onUnsave(s._id)
      else await onSave(s._id)
    } finally {
      setSaving(false)
    }
  }

  return (
    <article className="animate-fade-up group flex flex-col gap-3 rounded-xl border border-border bg-white p-5 shadow-sm hover:shadow-md transition-shadow duration-200">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-display font-semibold text-sm leading-snug group-hover:text-moss transition-colors truncate">
            {s.name || 'Untitled Scholarship'}
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">{s.provider || 'Unknown Provider'}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {s.amount && (
            <span className="font-mono text-sm font-semibold text-amber">{s.amount}</span>
          )}
          <button
            onClick={user ? handleSaveToggle : onSave}
            disabled={saving}
            title={isSaved ? 'Unsave' : 'Save'}
            className={cn(
              'rounded-md p-1.5 transition-colors',
              isSaved
                ? 'text-moss bg-moss-100 hover:bg-moss-200'
                : 'text-muted-foreground hover:bg-sand-200 hover:text-moss'
            )}
          >
            {isSaved
              ? <BookmarkCheck size={15} />
              : <BookmarkPlus size={15} />
            }
          </button>
        </div>
      </div>

      {s.tags?.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {s.tags.map((t, i) => (
            <Badge key={i} variant="default" className="text-[10px]">
              {t.tag_type?.name ?? t.tag_type}: {t.tag_value}
            </Badge>
          ))}
          {s.essay_required === false && (
            <Badge variant="amber" className="text-[10px]">No Essay</Badge>
          )}
        </div>
      ) : s.summary ? (
        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">{s.summary}</p>
      ) : null}

      <div className="flex items-center justify-between pt-1 border-t border-border/50">
        <span className="text-xs text-muted-foreground">
          {s.date?.due
            ? `Due ${new Date(s.date.due).toLocaleDateString()}`
            : s.date?.found
            ? `Found ${new Date(s.date.found).toLocaleDateString()}`
            : 'No deadline listed'}
        </span>
        <Button
          size="sm"
          className="h-7 text-xs gap-1"
          onClick={() => window.open(s.url, '_blank')}
        >
          Apply <ExternalLink size={11} />
        </Button>
      </div>
    </article>
  )
}

export default function BrowsePage({ user, onAuth }) {
  const [scholarships, setScholarships] = useState([])
  const [total, setTotal]               = useState(0)
  const [page, setPage]                 = useState(0)
  const [loading, setLoading]           = useState(true)
  const [search, setSearch]             = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [activeFilters, setActiveFilters]     = useState(new Set())
  const [savedIds, setSavedIds]               = useState(new Set())
  const [modal, setModal]                     = useState({ open: false })

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(0)
    }, 350)
    return () => clearTimeout(t)
  }, [search])

  // Load saved IDs when user logs in
  useEffect(() => {
    if (!user) { setSavedIds(new Set()); return }
    const userId = user._id ?? user.id
    getSaved(userId)
      .then(res => setSavedIds(new Set(res.data.map(s => s._id ?? s))))
      .catch(() => {})
  }, [user])

  // Fetch scholarships
  useEffect(() => {
    setLoading(true)
    getScholarships({
      search:   debouncedSearch || undefined,
      no_essay: activeFilters.has('no_essay') || undefined,
      limit:    PAGE_SIZE,
      skip:     page * PAGE_SIZE,
    })
      .then(res => {
        setScholarships(res.data.scholarships)
        setTotal(res.data.total)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [debouncedSearch, activeFilters, page])

  const toggleFilter = (id) => {
    setActiveFilters(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
    setPage(0)
  }

  const handleSave = useCallback(async (scholarshipId) => {
    if (!user) { setModal({ open: true }); return }
    const userId = user._id ?? user.id
    await saveScholarship(userId, scholarshipId)
    setSavedIds(prev => new Set([...prev, scholarshipId]))
  }, [user])

  const handleUnsave = useCallback(async (scholarshipId) => {
    if (!user) return
    const userId = user._id ?? user.id
    await unsaveScholarship(userId, scholarshipId)
    setSavedIds(prev => { const next = new Set(prev); next.delete(scholarshipId); return next })
  }, [user])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <>
      <AuthModal
        open={modal.open}
        onClose={() => setModal({ open: false })}
        onAuth={(u) => { onAuth(u); setModal({ open: false }) }}
        reason="save"
      />

      <div className="mx-auto max-w-5xl px-6 py-8 space-y-6">
        {/* Header */}
        <div className="animate-fade-up">
          <h1 className="font-display text-2xl font-bold tracking-tight">Browse Scholarships</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {total > 0 ? `${total.toLocaleString()} scholarships discovered` : 'Searching the web for scholarships…'}
          </p>
        </div>

        {/* Search + Filters */}
        <div className="animate-fade-up delay-75 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by name, provider, or keyword…"
              className="pl-9"
            />
          </div>
          <div className="flex gap-2">
            {FILTER_OPTIONS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => toggleFilter(id)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-150 whitespace-nowrap',
                  activeFilters.has(id)
                    ? 'border-moss bg-moss text-white'
                    : 'border-border bg-white text-ink/70 hover:border-moss/50 hover:text-ink'
                )}
              >
                <Icon size={11} /> {label}
              </button>
            ))}
          </div>
        </div>

        {/* Results */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-white p-5 animate-pulse space-y-3">
                <div className="h-4 bg-sand-300 rounded w-3/4" />
                <div className="h-3 bg-sand-200 rounded w-1/2" />
                <div className="flex gap-2">
                  <div className="h-5 bg-sand-200 rounded-full w-20" />
                  <div className="h-5 bg-sand-200 rounded-full w-16" />
                </div>
              </div>
            ))}
          </div>
        ) : scholarships.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-white/50 px-8 py-16 text-center">
            <span className="text-4xl">🕷️</span>
            <p className="font-display font-semibold">No scholarships found</p>
            <p className="text-sm text-muted-foreground max-w-sm">
              {debouncedSearch
                ? `No results for "${debouncedSearch}". Try a different search term.`
                : 'The crawler is still discovering scholarships. Check back soon!'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {scholarships.map((s, i) => (
              <ScholarshipCard
                key={s._id}
                s={s}
                isSaved={savedIds.has(s._id)}
                onSave={handleSave}
                onUnsave={handleUnsave}
                user={user}
                style={{ animationDelay: `${i * 40}ms` }}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              <ChevronLeft size={14} /> Prev
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
            >
              Next <ChevronRight size={14} />
            </Button>
          </div>
        )}

        {/* AI disclaimer */}
        <footer className="border-t border-border pt-4">
          <p className="text-xs text-muted-foreground text-center">
            ⚠️ Scholarships are discovered and classified automatically by AI. Results may not always be accurate. Always verify on the official website.
          </p>
        </footer>
      </div>
    </>
  )
}