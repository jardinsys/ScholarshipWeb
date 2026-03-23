import { useState, useEffect } from 'react'
import { Loader2, LogIn } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { getUser } from '@/lib/api'
import { UserInfoSection } from '@/components/profile/UserInfoSection'
import { TagManager } from '@/components/profile/TagManager'
import { Button } from '@/components/ui/button'

export default function ProfilePage({ user: authUser }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const navigate              = useNavigate()

  useEffect(() => {
    // authUser comes from App state after login/register
    // authUser._id is the MongoDB ObjectId string
    if (!authUser) {
      setLoading(false)
      return
    }

    const userId = authUser._id ?? authUser.id
    if (!userId) {
      setError('Could not determine user ID.')
      setLoading(false)
      return
    }

    getUser(userId)
      .then(res => setUser(res.data))
      .catch(() => setError('Could not load profile.'))
      .finally(() => setLoading(false))
  }, [authUser])

  if (loading) return (
    <div className="flex h-64 items-center justify-center text-muted-foreground gap-2">
      <Loader2 size={18} className="animate-spin" /> Loading profile…
    </div>
  )

  if (!authUser) return (
    <div className="flex h-64 flex-col items-center justify-center gap-4 text-muted-foreground">
      <p className="text-sm">You need to be logged in to view your profile.</p>
      <Button onClick={() => navigate('/dashboard')}>
        <LogIn size={14} /> Go to Dashboard to Log In
      </Button>
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
        userId={user._id ?? user.id}
        tags={user.tags ?? []}
        onTagsChange={tags => setUser(u => ({ ...u, tags }))}
      />
    </main>
  )
}