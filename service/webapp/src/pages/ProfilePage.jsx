import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { getUser } from '@/lib/api'
import { UserInfoSection } from '@/components/profile/UserInfoSection'
import { TagManager } from '@/components/profile/TagManager'

// TODO: replace with real auth/session once you have login
const MOCK_USER_ID = '1'

export default function ProfilePage() {
  const [user, setUser]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

  useEffect(() => {
    getUser(MOCK_USER_ID)
      .then(res => setUser(res.data))
      .catch(() => setError('Could not load profile.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex h-64 items-center justify-center text-muted-foreground gap-2">
      <Loader2 size={18} className="animate-spin" /> Loading profile…
    </div>
  )

  if (error) return (
    <div className="flex h-64 items-center justify-center text-red-500 text-sm">{error}</div>
  )

  return (
    <main className="mx-auto max-w-2xl px-6 py-10 space-y-10">
      {/* Page heading */}
      <div className="animate-fade-up">
        <h1 className="font-display text-3xl font-bold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Keep your info and tags up to date for the best scholarship matches.
        </p>
      </div>

      <hr className="border-border" />

      {/* User info */}
      <UserInfoSection
        user={user}
        onUpdate={patch => setUser(u => ({ ...u, ...patch }))}
      />

      <hr className="border-border" />

      {/* Tags */}
      <TagManager
        userId={user.id}
        tags={user.tags ?? []}
        onTagsChange={tags => setUser(u => ({ ...u, tags }))}
      />
    </main>
  )
}