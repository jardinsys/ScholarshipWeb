import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { register, login } from '@/lib/api'

export function AuthModal({ open, onClose, onAuth, reason }) {
  const [username, setUsername] = useState('')
  const [mode, setMode] = useState('login')  // 'login' | 'register'
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!open) return null

  const messages = {
    save: 'Save scholarships and revisit them anytime.',
    tags: 'Manage your personal tags for better matches.',
    account: 'Track applications and get personalized recommendations.',
  }

  const handleSubmit = async () => {
    if (!username.trim()) return setError('Please enter a username')
    setLoading(true)
    setError('')
    try {
      const fn = mode === 'register' ? register : login
      const res = await fn(username.trim())
      onAuth(res.data)   // pass user up to App
      onClose()
    } catch (err) {
      setError(err.response?.data?.error ?? 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-ink/30 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full max-w-sm rounded-2xl border border-border bg-white p-8 shadow-xl animate-fade-up">
        <button onClick={onClose} className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:bg-sand-200">
          <X size={15} />
        </button>

        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-moss-100">
          <span className="text-2xl">🎓</span>
        </div>

        <h2 className="font-display text-xl font-bold text-ink">
          {mode === 'register' ? 'Create Account' : 'Log In First'}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {messages[reason] ?? messages.account}
        </p>

        <div className="mt-5 space-y-3">
          <Input
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            autoFocus
          />
          {error && <p className="text-xs text-red-500">{error}</p>}
          <Button className="w-full" onClick={handleSubmit} disabled={loading}>
            {loading ? 'Please wait…' : mode === 'register' ? 'Create Account' : 'Log In'}
          </Button>
        </div>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          {mode === 'register' ? 'Already have an account? ' : 'No account yet? '}
          <button
            className="text-moss underline"
            onClick={() => { setMode(m => m === 'register' ? 'login' : 'register'); setError('') }}
          >
            {mode === 'register' ? 'Log in' : 'Create one'}
          </button>
        </p>
      </div>
    </div>
  )
}