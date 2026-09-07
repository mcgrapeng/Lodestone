import { useState } from 'react'
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
  DrawerDescription,
  DrawerBody,
  DrawerClose,
} from '@appica/ui-react'
import { X, Star, GitFork, ExternalLink, Globe, Calendar, Loader2, Download, Trash2, RefreshCw } from 'lucide-react'
import type { Repo } from '../lib/types'
import { api } from '../lib/api'
import { formatStars, repoOwner, repoSlug } from '../lib/format'
import { sourceOf } from '../lib/filters'

export interface RepoDrawerProps {
  repo: Repo | null
  open: boolean
  onClose: () => void
  /** 安装/卸载/更新成功后回调 — App 用它刷新快照使「已装」徽标实时更新 */
  onRepoChanged?: (repo: Repo) => void
}

type Action = 'install' | 'update' | 'uninstall'

export function RepoDrawer({ repo, open, onClose, onRepoChanged }: RepoDrawerProps) {
  const [busy, setBusy] = useState<Action | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  // ponytail: GitHub 仓库才可装为 skill（HF/arXiv/MCP registry 条目没有可克隆的 repo）
  const installable = repo ? sourceOf(repo) === 'github' : false

  async function act(kind: Action) {
    if (!repo) return
    setBusy(kind)
    setMsg(null)
    try {
      const slug = repoSlug(repo.name)
      const res =
        kind === 'uninstall'
          ? await api.uninstallSkill(slug)
          : kind === 'update'
            ? await api.updateSkill(repo.name, repo.url)
            : await api.installSkill(repo.name, repo.url)
      setMsg(res.ok ? `✅ ${res.message}` : `❌ ${res.error ?? '操作失败'}`)
      if (res.ok) {
        onRepoChanged?.({ ...repo, local_installed: kind !== 'uninstall' })
      }
    } catch (e) {
      setMsg(`❌ ${(e as Error).message}`)
    } finally {
      setBusy(null)
    }
  }

  // ponytail: Appica UI's `Drawer` IS the root (extends BaseDrawer.Root + `side`).
  // `DrawerContent` wraps Portal + Backdrop + Viewport + Popup.
  return (
    <Drawer open={open} onOpenChange={(o: boolean) => !o && onClose()} side="right">
      <DrawerContent
        backdrop
        frame
        closeButton={false}
        className="!bg-background !text-foreground !border-l !border-border-muted"
      >
        {repo ? (
          <>
            <DrawerHeader className="relative flex items-start gap-3 border-b border-border-muted p-5 pr-12">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Globe className="h-4 w-4 shrink-0 text-primary" />
                  <DrawerTitle className="truncate font-mono text-base font-medium">
                    <span className="text-primary">{repoOwner(repo.name)}/</span>
                    <span className="text-white">{repoSlug(repo.name)}</span>
                  </DrawerTitle>
                  {repo.trending && (
                    <span className="chip-accent shrink-0 text-[10px]">Trending</span>
                  )}
                  {/* 视觉审查修正：外链降为标题旁图标（把主位让给应用内管理动作） */}
                  <a
                    href={repo.url}
                    target="_blank"
                    rel="noopener"
                    title="在 GitHub 打开"
                    className="ml-auto inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-foreground-subtle transition hover:bg-background-strong hover:text-primary"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
                <DrawerDescription className="mt-2 text-sm leading-relaxed text-foreground-muted">
                  {repo.desc_zh || repo.desc || '—'}
                </DrawerDescription>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {repo.lang && repo.lang !== '—' && (
                    <span className="chip">
                      <span className="h-1.5 w-1.5 rounded-full bg-secondary" /> {repo.lang}
                    </span>
                  )}
                  {repo.local_installed && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-success/15 px-2 py-0.5 text-[11px] font-semibold text-success ring-1 ring-success/30">
                      已安装
                    </span>
                  )}
                </div>
              </div>
              {/* 视觉审查修正：× 放右上角与标题同行（惯例位置），不再悬空中部 */}
              <DrawerClose
                className="absolute right-4 top-4 z-10 rounded-md p-1.5 text-foreground-subtle transition hover:bg-background-strong hover:text-white"
                aria-label="关闭"
              >
                <X className="h-4 w-4" />
              </DrawerClose>
            </DrawerHeader>

            <DrawerBody className="p-5">
              <div className="mb-5 grid grid-cols-3 gap-3">
                <div className="card-surface p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-foreground-subtle">
                    <Star className="h-3 w-3" /> Stars
                  </div>
                  <div className="mt-1 text-lg font-semibold tabular-nums text-white">
                    {formatStars(repo.stars)}
                  </div>
                  {repo.stars_today != null && repo.stars_today > 0 && (
                    <div className="text-[11px] text-success">
                      +{formatStars(repo.stars_today)} 今天
                    </div>
                  )}
                </div>
                <div className="card-surface p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-foreground-subtle">
                    <GitFork className="h-3 w-3" /> Forks
                  </div>
                  <div className="mt-1 text-lg font-semibold tabular-nums text-white">
                    {formatStars(repo.forks)}
                  </div>
                </div>
                <div className="card-surface p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-foreground-subtle">
                    <Calendar className="h-3 w-3" /> 最近更新
                  </div>
                  <div className="mt-1 whitespace-nowrap text-sm font-medium tabular-nums text-white">
                    {repo.pushed || repo.updated || '—'}
                  </div>
                </div>
              </div>

              {/* 安装 / 更新 / 卸载 — skills 闭环 */}
              {installable && (
                <div className="mb-5">
                  {repo.local_installed ? (
                    /* 视觉审查修正：更新=品牌色主按钮；卸载=ghost 危险操作且分隔，降低误触 */
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => act('update')}
                        disabled={busy !== null}
                        className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary/25 px-3 py-2 text-xs font-semibold text-primary ring-1 ring-primary/40 transition hover:bg-primary/35 disabled:opacity-50"
                      >
                        {busy === 'update' ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        更新到最新
                      </button>
                      <span className="h-6 w-px bg-background-strong" />
                      <button
                        type="button"
                        onClick={() => act('uninstall')}
                        disabled={busy !== null}
                        className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-xs font-medium text-foreground-subtle transition hover:bg-error/10 hover:text-error disabled:opacity-50"
                      >
                        {busy === 'uninstall' ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                        卸载
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => act('install')}
                      disabled={busy !== null}
                      className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary/25 px-3 py-2 text-xs font-semibold text-primary ring-1 ring-primary/40 transition hover:bg-primary/35 disabled:opacity-50"
                    >
                      {busy === 'install' ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Download className="h-3.5 w-3.5" />
                      )}
                      安装为 Skill（claude · codex · opencode）
                    </button>
                  )}
                  {msg && (
                    <div className="mt-2 rounded-lg bg-background-muted p-2.5 text-xs leading-relaxed text-foreground-muted">
                      {msg}
                    </div>
                  )}
                </div>
              )}

              {(repo.topics ?? []).length > 0 && (
                <div className="mb-5">
                  <div className="mb-2 text-xs uppercase tracking-wider text-foreground-subtle">
                    Topics
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(repo.topics ?? []).map((t) => (
                      <span key={t} className="chip">{t}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 详细中文描述 — 爬取期生成（README 首段翻译），随数据就绪零等待。
                  2026-09 取代旧的「中文详介」按需翻译。 */}
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white">详细介绍</h3>
                <span className="text-[11px] text-foreground-subtle">README 自动摘要</span>
              </div>
              <div className="card-surface p-4">
                <p className="text-sm leading-relaxed text-foreground-muted">
                  {repo.summary_zh || repo.desc_zh || repo.desc || '暂无详细描述'}
                </p>
              </div>
            </DrawerBody>
          </>
        ) : null}
      </DrawerContent>
    </Drawer>
  )
}
