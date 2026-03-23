import { useState, useEffect, useRef } from 'react'
import { Plus, Loader2, X, Check, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { TagPill } from '@/components/ui/tag-pill'
import { getAllTags, addUserTag, removeUserTag, updateUser } from '@/lib/api'

export function TagManager({ userId, tags, bio, onTagsChange, onBioChange }) {
  const [allTags, setAllTags]           = useState([])
  const [search, setSearch]             = useState('')
  const [showPicker, setShowPicker]     = useState(false)
  const [adding, setAdding]             = useState(null)
  const [pendingTag, setPendingTag]     = useState(null)
  const [pendingValue, setPendingValue] = useState('')
  const [valueError, setValueError]     = useState('')
  const valueInputRef                   = useRef(null)

  // Bio editing state
  const [editingBio, setEditingBio]   = useState(false)
  const [bioValue, setBioValue]       = useState(bio ?? '')
  const [savingBio, setSavingBio]     = useState(false)

  useEffect(() => {
    getAllTags()
      .then(res => setAllTags(res.data))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (pendingTag && valueInputRef.current) valueInputRef.current.focus()
  }, [pendingTag])

  const handleSaveBio = async () => {
    setSavingBio(true)
    try {
      await updateUser(userId, { bio: bioValue })
      onBioChange(bioValue)
      setEditingBio(false)
    } catch (err) {
      console.error('Failed to save bio', err)
    } finally {
      setSavingBio(false)
    }
  }

  const usedTypeIds = new Set(tags.map(t => String(t.tag_type?._id ?? t.tag_type)))

  const filteredCatalogue = allTags.filter(t =>
    !usedTypeIds.has(String(t._id)) &&
    (
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase())
    )
  )

  const handleSelectTag = (tag) => {
    setPendingTag(tag)
    setPendingValue('')
    setValueError('')
  }

  const handleConfirmAdd = async () => {
    if (!pendingValue.trim()) { setValueError('Please enter a value.'); return }
    setAdding(pendingTag._id)
    try {
      const res = await addUserTag(userId, {
        tag_type:  pendingTag._id,
        tag_value: pendingValue.trim(),
      })
      onTagsChange(res.data.tags)
      setPendingTag(null)
      setPendingValue('')
      setShowPicker(false)
      setSearch('')
    } catch (err) {
      console.error('Failed to add tag', err)
      setValueError('Failed to save. Please try again.')
    } finally {
      setAdding(null)
    }
  }

  const handleCancelPending = () => {
    setPendingTag(null)
    setPendingValue('')
    setValueError('')
  }

  const handleRemove = async (tagTypeId) => {
    try {
      const res = await removeUserTag(userId, tagTypeId)
      onTagsChange(res.data.tags)
    } catch (err) {
      console.error('Failed to remove tag', err)
    }
  }

  return (
    <div className="animate-fade-up delay-150 space-y-6">

      {/* ── Bio ── */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-semibold text-base">About You</h2>
          {!editingBio && (
            <Button variant="ghost" size="icon" onClick={() => setEditingBio(true)}>
              <Pencil size={14} />
            </Button>
          )}
        </div>

        {editingBio ? (
          <div className="space-y-2">
            <textarea
              value={bioValue}
              onChange={e => setBioValue(e.target.value)}
              placeholder="Write a short bio — your background, goals, field of study…"
              rows={3}
              autoFocus
              className="w-full rounded-md border border-input bg-white px-3 py-2 text-sm font-body shadow-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSaveBio} disabled={savingBio}>
                <Check size={13} /> {savingBio ? 'Saving…' : 'Save'}
              </Button>
              <Button size="sm" variant="outline" onClick={() => { setEditingBio(false); setBioValue(bio ?? '') }}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground leading-relaxed">
            {bioValue || <span className="italic">No bio yet — add one to help with matches.</span>}
          </p>
        )}
      </div>

      <hr className="border-border" />

      {/* ── Tags ── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-display font-semibold text-base">Your Tags</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Tags help us match you with relevant scholarships
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => { setShowPicker(p => !p); setPendingTag(null) }}
          >
            <Plus size={13} /> Add Tag
          </Button>
        </div>

        {/* Current tags */}
        <div className="flex flex-wrap gap-2 min-h-[2rem]">
          {tags.length === 0 && (
            <p className="text-sm text-muted-foreground italic">
              No tags yet — add some to get matched!
            </p>
          )}
          {tags.map((t, i) => (
            <TagPill
              key={i}
              name={t.tag_type?.name ?? t.tag_type}
              value={t.tag_value}
              removable
              onRemove={() => handleRemove(t.tag_type?._id ?? t.tag_type)}
            />
          ))}
        </div>

        {/* Tag picker */}
        {showPicker && (
          <div className="rounded-xl border border-border bg-white shadow-md p-4 space-y-3">
            {pendingTag ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">
                    Enter your <span className="text-moss font-mono">{pendingTag.name}</span> value
                  </p>
                  <button onClick={handleCancelPending} className="text-muted-foreground hover:text-ink transition-colors">
                    <X size={14} />
                  </button>
                </div>
                <p className="text-xs text-muted-foreground">{pendingTag.description}</p>
                <Input
                  ref={valueInputRef}
                  placeholder={`e.g. "${pendingTag.name === 'major' ? 'computer science' : pendingTag.name === 'state' ? 'california' : pendingTag.name === 'gpa' ? '3.5' : 'your value'}"`}
                  value={pendingValue}
                  onChange={e => { setPendingValue(e.target.value); setValueError('') }}
                  onKeyDown={e => e.key === 'Enter' && handleConfirmAdd()}
                />
                {valueError && <p className="text-xs text-red-500">{valueError}</p>}
                <div className="flex gap-2">
                  <Button size="sm" onClick={handleConfirmAdd} disabled={adding === pendingTag._id}>
                    {adding === pendingTag._id
                      ? <><Loader2 size={12} className="animate-spin" /> Saving…</>
                      : 'Add Tag'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleCancelPending}>Cancel</Button>
                </div>
              </div>
            ) : (
              <>
                <Input
                  placeholder="Search tag types (major, state, gpa…)"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  autoFocus
                />
                <div className="max-h-52 overflow-y-auto space-y-1 pr-1">
                  {filteredCatalogue.length === 0 && (
                    <p className="text-xs text-muted-foreground text-center py-4">
                      {allTags.length === 0
                        ? 'No tag types exist yet. Tags are created automatically as scholarships are processed.'
                        : 'No matching tags found.'}
                    </p>
                  )}
                  {filteredCatalogue.map(tag => (
                    <button
                      key={tag._id}
                      onClick={() => handleSelectTag(tag)}
                      className="w-full flex items-start justify-between gap-3 rounded-lg px-3 py-2 text-left hover:bg-sand-200 transition-colors"
                    >
                      <div>
                        <p className="font-mono text-xs font-medium text-moss">{tag.name}</p>
                        <p className="text-xs text-muted-foreground">{tag.description}</p>
                      </div>
                      <Plus size={13} className="text-muted-foreground mt-0.5 shrink-0" />
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}