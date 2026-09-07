import type { ReactNode } from 'react'

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-background-subtle ${className}`}
      aria-hidden
    />
  )
}

export function SkeletonStack({
  rows = 3,
  height = 'h-4',
}: {
  rows?: number
  height?: string
}) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={`${height} w-${i === rows - 1 ? '2/3' : 'full'}`} />
      ))}
    </div>
  )
}

export function SkeletonGrid({
  count = 6,
  children,
}: {
  count?: number
  children?: ReactNode
}) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) =>
        children ? (
          <div key={i}>{children}</div>
        ) : (
          <div key={i} className="card-surface p-4">
            <SkeletonStack rows={3} />
          </div>
        ),
      )}
    </div>
  )
}
