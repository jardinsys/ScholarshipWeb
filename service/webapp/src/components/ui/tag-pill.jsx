import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * TagPill — displays a single user tag (name + value).
 * @param {string}   name       — tag category e.g. "major"
 * @param {string}   value      — tag value e.g. "computer science"
 * @param {boolean}  removable  — show the ✕ button
 * @param {function} onRemove   — called when ✕ is clicked
 * @param {string}   className
 */
export function TagPill({ name, value, removable = false, onRemove, className }) {
  return (
    <span
      className={cn(
        'animate-tag-pop inline-flex items-center gap-1.5 rounded-full border border-moss/25',
        'bg-moss-100 px-3 py-1 font-mono text-xs text-moss-600',
        className
      )}
    >
      <span className="font-medium opacity-60">{name}:</span>
      <span>{value}</span>
      {removable && (
        <button
          type="button"
          onClick={onRemove}
          className="ml-0.5 rounded-full p-0.5 hover:bg-moss/20 transition-colors"
          aria-label={`Remove ${name} tag`}
        >
          <X size={10} strokeWidth={2.5} />
        </button>
      )}
    </span>
  )
}