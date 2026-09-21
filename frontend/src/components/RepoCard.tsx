import { useState } from 'react'
import { Star, GitFork, ExternalLink, Flame, Sparkles, Download, Plus } from 'lucide-react'
import type { Repo } from '../lib/types'
import { formatStars, repoOwner, repoSlug } from '../lib/format'
import { sourceOf } from '../lib/filters'
import { PlatformDot, type Cli } from './PlatformDot'
import { api } from '../lib/api'

export interface RepoCardProps {
  repo: Repo
  variant?: 'grid' | 'row'
  onOpen: (repo: Repo) => void
}

export function RepoCard({ repo, variant = 'grid', onOpen }: RepoCardProps) {
  // ponytail: 2026-09 — 三段摘要优先用 intro（最像「是什么」的段），回退 summary_zh。
  // 逐级回退：summary_sections.intro → summary_zh → desc_zh → desc。
  const intro = repo.summary_sections?.intro?.trim()
  const displayName = intro || repo.summary_zh || repo.desc_zh || repo.desc || '—'
  const topics = (repo.topics ?? []).slice(0, 3)
  // ponytail: 2026-09 — 是否是可安装的 skill(github 源 + 是 SKILL.md)。
  // 未装时 RepoCard 显示「+ 安装」按钮,让用户一眼看到可装。点开 drawer 选平台。
  const installable =
    !repo.local_installed &&
    sourceOf(repo) === 'github' &&
    repo.is_skill === true

  // ponytail: 2026-09 P2 — per-platform install click handler. busy target
  // disables that dot while the POST is in flight; other dots remain live.
  const [busy, setBusy] = useState<Cli | null>(null)
  async function toggleInstall(name: string, url: string, target: Cli) {
    setBusy(target)
    try {
      await api.installToTarget(name, url, target)
    } catch (e) {
      console.error(e)
    } finally {
      setBusy(null)
    }
  }

  if (variant === 'row') {
    return (
      <button
        type="button"
        onClick={() => onOpen(repo)}
        className="group card-surface flex w-full items-center gap-4 p-4 text-left transition-colors hover:border-primary/30 hover:bg-background-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
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
            {installable && (
              <span className="chip text-[10px] text-primary" title="该 skill 仓库包含 SKILL.md,可一键安装">
                <Plus className="h-2.5 w-2.5" /> 可装
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
        {/* ponytail: 2026-09 P2 — 4 platform dots. stopPropagation prevents the
            outer <button>'s onOpen handler from firing when a dot is clicked. */}
        <div
          className="flex shrink-0 items-center gap-1"
          onClick={(e) => e.stopPropagation()}
        >
          <PlatformDot
            cli="claude"
            installed={Boolean(repo.local_installed)}
            disabled={busy === 'claude'}
            onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
          />
          <PlatformDot
            cli="codex"
            installed={false}
            disabled={busy === 'codex'}
            onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
          />
          <PlatformDot
            cli="opencode"
            installed={false}
            disabled={busy === 'opencode'}
            onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
          />
          <PlatformDot
            cli="easycode"
            installed={false}
            disabled={busy === 'easycode'}
            onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
          />
        </div>
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={() => onOpen(repo)}
      className="group card-surface relative flex h-48 w-full flex-col p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg hover:shadow-brand-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      {/* 顶部 accent 线 — hover 时从左到右亮起 */}
      <span className="absolute inset-x-4 top-0 h-px origin-left scale-x-0 bg-gradient-to-r from-primary/60 via-secondary/40 to-transparent transition-transform duration-300 group-hover:scale-x-100" />
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
          {installable && (
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-semibold text-primary ring-1 ring-primary/30" title="该 skill 仓库包含 SKILL.md,可一键安装">
              <Plus className="h-2.5 w-2.5" /> 可装
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
      {/* ponytail: 2026-09 P2 — 4 platform dots (grid variant, pinned bottom-right
          so they don't crowd the header chips). stopPropagation keeps the card's
          onOpen from firing when a dot is clicked. */}
      <div
        className="absolute bottom-2 right-2 flex shrink-0 items-center gap-1"
        onClick={(e) => e.stopPropagation()}
      >
        <PlatformDot
          cli="claude"
          installed={Boolean(repo.local_installed)}
          disabled={busy === 'claude'}
          onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
        />
        <PlatformDot
          cli="codex"
          installed={false}
          disabled={busy === 'codex'}
          onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
        />
        <PlatformDot
          cli="opencode"
          installed={false}
          disabled={busy === 'opencode'}
          onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
        />
        <PlatformDot
          cli="easycode"
          installed={false}
          disabled={busy === 'easycode'}
          onToggle={(cli) => toggleInstall(repo.name, repo.url, cli)}
        />
      </div>
    </button>
  )
}
