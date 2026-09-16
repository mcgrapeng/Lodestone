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
  lastWidth = 'w-2/3',
}: {
  rows?: number
  height?: string
  /** 最后一行的宽度(Tailwind class)。默认 2/3,与原行为一致。
   * ponytail: 2026-09 — 显式 className prop 替代动态字符串拼接,
   * Tailwind JIT 不会从 `w-${...}` 模板字面量抽取 class,之前每行都是默认宽度。 */
  lastWidth?: string
}) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton
          key={i}
          className={`${height} ${i === rows - 1 ? lastWidth : 'w-full'}`}
        />
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
