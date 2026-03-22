import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function AuthModal({ open, onClose, reason }) {
  if (!open) return null

  const messages = {
    save:   'Create an account to save scholarships and revisit them anytime.',
    tags:   'Sign in to search and manage your personal tags for better matches.',
    account: 'Create an account to track applications, save scholarships, and get personalized recommendations.',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-ink/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-sm rounded-2xl border border-border bg-white p-8 shadow-xl animate-fade-up">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:bg-sand-200 transition-colors"
        >
          <X size={15} />
        </button>

        {/* Icon */}
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-moss-100">
          <span className="text-2xl">🕷️</span>
        </div>

        <h2 className="font-display text-xl font-bold text-ink">Join ScholarshipWeb</h2>
        <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
          {messages[reason] ?? messages.account}
        </p>

        <div className="mt-6 flex flex-col gap-2">
          <Button className="w-full" onClick={onClose}>
            Create Account
          </Button>
          <Button variant="outline" className="w-full" onClick={onClose}>
            Log In
          </Button>
        </div>
      </div>
    </div>
  )
}