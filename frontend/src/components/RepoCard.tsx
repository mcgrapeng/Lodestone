import { Star, GitFork, ExternalLink, Flame, Sparkles, Download } from 'lucide-react'
import type { Repo } from '../lib/types'
import { formatStars, repoOwner, repoSlug } from '../lib/format'

export interface RepoCardProps {
  repo: Repo
  variant?: 'grid' | 'row'
  onOpen: (repo: Repo) => void
}

export function RepoCard({ repo, variant = 'grid', onOpen }: RepoCardProps) {
  // ponytail: 详细中文描述优先（README 首段翻译，爬取期生成），
  // 逐级回退：summary_zh → desc_zh → desc。
  const displayName = repo.summary_zh || repo.desc_zh || repo.desc || '—'
  const topics = (repo.topics ?? []).slice(0, 3)

  if (variant === 'row') {
    return (
      <button
        type="button"
        onClick={() => onOpen(repo)}
        className="group card-surface flex w-full items-center gap-4 p-4 text-left transition-colors hover:border-primary/30 hover:bg-background-subtle"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate font-mono text-sm font-medium text-primary">
              {repoOwner(repo.name)}/<span className="text-white">{repoSlug(repo.name)}</span>
            </span>
            {repo.trending && (
              <span className="chip-accent text-[10px]">
                <Flame className="h-2.5 w-2.5" /> Trending
              </span>
            )}
            {repo.local_installed && (
              <span className="chip text-[10px]">
                <Download className="h-2.5 w-2.5" /> 已装
              </span>
            )}
          </div>
          <p className="mt-1 line-clamp-2 text-sm text-foreground-muted">{displayName}</p>
          {topics.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {topics.map((t) => (
                <span key={t} className="chip text-[10px]">{t}</span>
              ))}
            </div>
          )}
        </div>
        <div className="hidden shrink-0 items-center gap-4 text-xs text-foreground-subtle sm:flex">
          {repo.lang && (
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-secondary" />
              {repo.lang}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Star className="h-3 w-3" />
            {formatStars(repo.stars)}
          </span>
          {repo.stars_today != null && repo.stars_today > 0 && (
            <span className="flex items-center gap-1 text-success">
              <Sparkles className="h-3 w-3" />+{formatStars(repo.stars_today)}
            </span>
          )}
          <ExternalLink className="h-3.5 w-3.5 text-foreground-subtle transition group-hover:text-primary" />
        </div>
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={() => onOpen(repo)}
      className="group card-surface relative flex h-48 w-full flex-col p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg hover:shadow-brand-500/10"
    >
      {/* 顶部 accent 线 — hover 时从左到右亮起 */}
      <span className="absolute inset-x-4 top-0 h-px origin-left scale-x-0 bg-gradient-to-r from-primary/60 via-secondary/40 to-transparent transition-transform duration-300 group-hover:scale-x-100" />
      {/* 视觉审查修正：状态徽章与标题同行、文档流内布局 — 标题 truncate 收缩、
          徽章 shrink-0 固定右侧，任何长度都不会重叠（替代旧的 absolute 悬浮定位） */}
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <div className="truncate font-mono text-[13px] font-medium text-primary">
            {repoOwner(repo.name)}/<span className="text-white">{repoSlug(repo.name)}</span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {repo.local_installed && (
            <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success ring-1 ring-success/30">
              <Download className="h-2.5 w-2.5" /> 已装
            </span>
          )}
          {repo.trending && (
            <span className="chip-accent text-[10px]">
              <Flame className="h-2.5 w-2.5" /> Trending
            </span>
          )}
        </div>
      </div>
      <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-foreground-muted">{displayName}</p>
      {topics.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {topics.map((t) => (
            <span key={t} className="chip text-[10px]">{t}</span>
          ))}
        </div>
      )}
      <div className="mt-auto flex items-center gap-3 pt-3 text-[11px] text-foreground-subtle">
        {repo.lang && (
          <span className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-secondary" />
            {repo.lang}
          </span>
        )}
        <span className="flex items-center gap-0.5">
          <Star className="h-3 w-3" />
          {formatStars(repo.stars)}
        </span>
        {repo.forks != null && (
          <span className="flex items-center gap-0.5">
            <GitFork className="h-3 w-3" />
            {formatStars(repo.forks)}
          </span>
        )}
        {repo.stars_today != null && repo.stars_today > 0 && (
          <span className="ml-auto flex items-center gap-0.5 text-success">
            <Sparkles className="h-3 w-3" />+{formatStars(repo.stars_today)}
          </span>
        )}
      </div>
    </button>
  )
}
