import { useState } from 'react'
import { Check, Pencil } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { updateUser } from '@/lib/api'

export function UserInfoSection({ user, onUpdate }) {
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({
    displayname: user.displayname ?? '',
    username:    user.username    ?? '',
    bio:         user.bio         ?? '',
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateUser(user.id, form)
      onUpdate(form)
      setEditing(false)
    } catch (err) {
      console.error('Failed to save user info', err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="animate-fade-up space-y-4">
      {/* Avatar placeholder */}
      <div className="flex items-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-moss/15 text-2xl font-display font-bold text-moss">
          {(form.displayname?.[0] ?? '?').toUpperCase()}
        </div>
        <div>
          <p className="font-display text-xl font-semibold">{form.displayname || '—'}</p>
          <p className="font-mono text-sm text-muted-foreground">@{form.username || '—'}</p>
        </div>
        {!editing && (
          <Button variant="ghost" size="icon" className="ml-auto" onClick={() => setEditing(true)}>
            <Pencil size={14} />
          </Button>
        )}
      </div>

      {editing ? (
        <div className="space-y-3 rounded-xl border border-border bg-white p-5 shadow-sm">
          <Field label="Display Name">
            <Input
              value={form.displayname}
              onChange={e => setForm(f => ({ ...f, displayname: e.target.value }))}
              placeholder="Your full name"
            />
          </Field>
          <Field label="Username">
            <Input
              value={form.username}
              onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
              placeholder="handle"
            />
          </Field>
          <Field label="Bio">
            <textarea
              value={form.bio}
              onChange={e => setForm(f => ({ ...f, bio: e.target.value }))}
              placeholder="A short bio..."
              rows={3}
              className="w-full rounded-md border border-input bg-white px-3 py-2 text-sm font-body shadow-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
            />
          </Field>
          <div className="flex gap-2 pt-1">
            <Button onClick={handleSave} disabled={saving} size="sm">
              <Check size={13} /> {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button variant="outline" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        form.bio && (
          <p className="text-sm text-muted-foreground leading-relaxed max-w-lg">{form.bio}</p>
        )
      )}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</label>
      {children}
    </div>
  )
}