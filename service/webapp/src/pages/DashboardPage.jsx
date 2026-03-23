import { useState, useEffect, useCallback } from 'react'
import { Search, Rss, Bookmark, Tag, User, TrendingUp, FileX, Star, Tags, BookmarkCheck, BookmarkPlus, ExternalLink } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { AuthModal } from '@/components/ui/AuthModal'
import { cn } from '@/lib/utils'
import { getScholarships, getMatchedScholarships, saveScholarship, unsaveScholarship, getSaved } from '@/lib/api'

const FILTERS = [
  { id: 'recommended', label: 'Recommended', icon: Star },
  { id: 'top_paying',  label: 'Top Paying',  icon: TrendingUp },
  { id: 'no_essay',    label: 'No Essay',    icon: FileX },
]

const SIDEBAR_ITEMS = [
  { id: 'feed',    label: 'Web Feed',   icon: Rss },
  { id: 'saved',   label: 'Saved',      icon: Bookmark },
  { id: 'tags',    label: 'Tag Search', icon: Tags },
  { id: 'account', label: 'Account',    icon: User },
]

const AUTH_REQUIRED = new Set(['saved', 'tags', 'account'])

function cleanTagValue(value) {
  if (typeof value !== 'string') return String(value ?? '')
  // Strip patterns like: tag 'hispanic', tag "hispanic", 'hispanic'
  return value
    .replace(/^tag\s+['"](.+)['"]\s*$/i, '$1')
    .replace(/^['"](.+)['"]\s*$/i, '$1')
    .trim()
}

function ScholarshipCard({ s, isSaved, onSave, onUnsave, user, style }) {
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
    <article
      style={style}
      className="animate-fade-up group flex flex-col gap-3 rounded-xl border border-border bg-white p-5 shadow-sm hover:shadow-md transition-shadow duration-200"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-display font-semibold text-sm leading-snug group-hover:text-moss transition-colors">
            {s.name || 'Untitled Scholarship'}
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {s.provider || 'Unknown Provider'}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {s.amount && (
            <span className="font-mono text-sm font-medium text-amber">{s.amount}</span>
          )}
          <button
            onClick={user ? handleSaveToggle : () => onSave(s._id)}
            disabled={saving}
            title={isSaved ? 'Unsave' : 'Save'}
            className={cn(
              'rounded-md p-1.5 transition-colors',
              isSaved
                ? 'text-moss bg-moss-100 hover:bg-moss-200'
                : 'text-muted-foreground hover:bg-sand-200 hover:text-moss'
            )}
          >
            {isSaved ? <BookmarkCheck size={15} /> : <BookmarkPlus size={15} />}
          </button>
        </div>
      </div>

      {s.matchScore != null && (
        <div className="flex items-center gap-1.5">
          <Star size={11} className="text-amber fill-amber" />
          <span className="text-xs text-amber font-medium">{s.matchScore}% match</span>
        </div>
      )}

      {s.tags?.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {s.tags.map((t, i) => (
            <Badge key={i} variant="default" className="text-[10px]">
              {t.tag_type?.name ?? t.tag_type}: {cleanTagValue(t.tag_value)}
            </Badge>
          ))}
          {s.essay_required === false && (
            <Badge variant="amber" className="text-[10px]">No Essay</Badge>
          )}
        </div>
      ) : s.summary ? (
        <p className="text-xs text-muted-foreground line-clamp-2">{s.summary}</p>
      ) : null}

      <div className="flex items-center justify-between pt-1 border-t border-border/50">
        <span className="text-xs text-muted-foreground">
          {s.date?.due
            ? `Due ${new Date(s.date.due).toLocaleDateString()}`
            : s.date?.found
            ? `Found ${new Date(s.date.found).toLocaleDateString()}`
            : ''}
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

export default function DashboardPage({ user, onAuth }) {
  const [activeNav, setActiveNav]         = useState('feed')
  const [activeFilters, setActiveFilters] = useState(new Set())
  const [searchQuery, setSearchQuery]     = useState('')
  const [modal, setModal]                 = useState({ open: false, reason: 'account' })
  const [scholarships, setScholarships]   = useState([])
  const [savedIds, setSavedIds]           = useState(new Set())
  const [loading, setLoading]             = useState(true)

  // Load saved scholarships for the current user
  useEffect(() => {
    if (!user) { setSavedIds(new Set()); return }
    const userId = user._id ?? user.id
    getSaved(userId)
      .then(res => setSavedIds(new Set(res.data.map(s => s._id ?? s))))
      .catch(() => {})
  }, [user])

  // Fetch scholarships — handle recommended filter separately
  useEffect(() => {
    setLoading(true)

    const isRecommended = activeFilters.has('recommended')

    if (isRecommended && user) {
      // Use the tag-match endpoint
      const userId = user._id ?? user.id
      getMatchedScholarships(userId)
        .then(res => setScholarships(res.data))
        .catch(err => { console.error(err); setScholarships([]) })
        .finally(() => setLoading(false))
    } else {
      getScholarships({
        search:   searchQuery || undefined,
        no_essay: activeFilters.has('no_essay') || undefined,
        limit:    20,
        skip:     0,
      })
        .then(res => setScholarships(res.data.scholarships))
        .catch(err => { console.error(err); setScholarships([]) })
        .finally(() => setLoading(false))
    }
  }, [searchQuery, activeFilters, user])

  const openModal = (reason) => setModal({ open: true, reason })
  const closeModal = () => setModal(m => ({ ...m, open: false }))

  const handleNavClick = (id) => {
    if (id === 'account') {
      // Always navigate to profile page whether logged in or not
      // (ProfilePage handles the not-logged-in case itself)
      window.location.href = '/profile'
      return
    }
    if (!user && AUTH_REQUIRED.has(id)) {
      openModal(id)
    } else {
      setActiveNav(id)
    }
  }

  const toggleFilter = (id) => {
    if (id === 'recommended' && !user) {
      openModal('account')
      return
    }
    setActiveFilters(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const handleSave = useCallback(async (scholarshipId) => {
    if (!user) { openModal('save'); return }
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

  // Saved view
  const displayedScholarships = activeNav === 'saved'
    ? scholarships.filter(s => savedIds.has(s._id))
    : scholarships

  return (
    <>
      <AuthModal
        open={modal.open}
        onClose={closeModal}
        onAuth={(u) => { onAuth(u); closeModal() }}
        reason={modal.reason}
      />

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
                {id === 'recommended' && !user && (
                  <span className="ml-1 opacity-60 text-[10px]">(login required)</span>
                )}
              </button>
            ))}
          </div>

          {/* Cards */}
          <div className="space-y-3">
            {loading && (
              <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                Loading scholarships…
              </div>
            )}
            {!loading && displayedScholarships.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-white/50 px-8 py-12 text-center">
                <span className="text-3xl">
                  {activeNav === 'saved' ? '🔖' : '🕷️'}
                </span>
                <p className="font-display font-semibold text-ink">
                  {activeNav === 'saved'
                    ? 'No saved scholarships yet'
                    : activeFilters.has('recommended')
                    ? 'No matches found — try adding more tags to your profile'
                    : 'No scholarships to show right now'}
                </p>
                {activeNav !== 'saved' && !activeFilters.has('recommended') && (
                  <p className="text-sm text-muted-foreground max-w-sm leading-relaxed">
                    The crawler is actively discovering scholarships. They'll appear here once processed.
                  </p>
                )}
              </div>
            )}
            {!loading && displayedScholarships.map((s, i) => (
              <ScholarshipCard
                key={s._id}
                s={s}
                isSaved={savedIds.has(s._id)}
                onSave={handleSave}
                onUnsave={handleUnsave}
                user={user}
                style={{ animationDelay: `${i * 60}ms` }}
              />
            ))}
          </div>
        </main>
      </div>

      {/* AI disclaimer footnote */}
      <footer className="mx-auto max-w-5xl px-6 py-4 border-t border-border">
        <p className="text-xs text-muted-foreground text-center leading-relaxed">
          ⚠️ Scholarships are discovered and classified automatically by AI. Results may not always be accurate.
        </p>
      </footer>
    </>
  )
}