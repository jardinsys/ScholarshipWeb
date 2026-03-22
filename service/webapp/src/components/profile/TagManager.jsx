import { useState, useEffect } from 'react'
import { Plus, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { TagPill } from '@/components/ui/tag-pill'
import { getAllTags, addUserTag, removeUserTag } from '@/lib/api'

export function TagManager({ userId, tags, onTagsChange }) {
  const [allTags, setAllTags]       = useState([])   // global tag catalogue
  const [search, setSearch]         = useState('')
  const [showPicker, setShowPicker] = useState(false)
  const [adding, setAdding]         = useState(null)  // tag._id being added

  useEffect(() => {
    getAllTags()
      .then(res => setAllTags(res.data))
      .catch(() => {})
  }, [])

  const usedTypeIds = new Set(tags.map(t => String(t.tag_type)))

  const filteredCatalogue = allTags.filter(t =>
    !usedTypeIds.has(String(t._id)) &&
    (t.name.includes(search.toLowerCase()) || t.description.toLowerCase().includes(search.toLowerCase()))
  )

  const handleAdd = async (tag) => {
    const value = prompt(`Enter your value for "${tag.name}" (e.g. "computer science"):`)
    if (!value) return
    setAdding(tag._id)
    try {
      const res = await addUserTag(userId, { tag_type: tag._id, tag_value: value.trim() })
      onTagsChange(res.data.tags)
    } catch (err) {
      console.error('Failed to add tag', err)
    } finally {
      setAdding(null)
      setShowPicker(false)
      setSearch('')
    }
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
    <div className="animate-fade-up delay-150 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display font-semibold text-base">Your Tags</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Tags help us match you with relevant scholarships
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => setShowPicker(p => !p)}>
          <Plus size={13} /> Add Tag
        </Button>
      </div>

      {/* Current tags */}
      <div className="flex flex-wrap gap-2 min-h-[2rem]">
        {tags.length === 0 && (
          <p className="text-sm text-muted-foreground italic">No tags yet — add some to get matched!</p>
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

      {/* Tag picker dropdown */}
      {showPicker && (
        <div className="rounded-xl border border-border bg-white shadow-md p-4 space-y-3">
          <Input
            placeholder="Search tag types (major, state, gpa…)"
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
          />
          <div className="max-h-52 overflow-y-auto space-y-1 pr-1">
            {filteredCatalogue.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">
                No matching tags found
              </p>
            )}
            {filteredCatalogue.map(tag => (
              <button
                key={tag._id}
                onClick={() => handleAdd(tag)}
                disabled={adding === tag._id}
                className="w-full flex items-start justify-between gap-3 rounded-lg px-3 py-2 text-left hover:bg-sand-200 transition-colors"
              >
                <div>
                  <p className="font-mono text-xs font-medium text-moss">{tag.name}</p>
                  <p className="text-xs text-muted-foreground">{tag.description}</p>
                </div>
                {adding === tag._id
                  ? <Loader2 size={13} className="animate-spin text-moss mt-0.5 shrink-0" />
                  : <Plus size={13} className="text-muted-foreground mt-0.5 shrink-0" />
                }
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}