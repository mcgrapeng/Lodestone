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
import { X, Star, GitFork, ExternalLink, Globe, Calendar, Loader2, Download, Trash2, RefreshCw, Check } from 'lucide-react'
import type { Repo } from '../lib/types'
import { api } from '../lib/api'
import { formatStars, repoOwner, repoSlug } from '../lib/format'
import { sourceOf } from '../lib/filters'

/** 安装平台多选 — 与后端 SKILL_PLATFORM_PATHS 一一对应（config.toml [install.platforms] 可扩展） */
const PLATFORMS = [
  { id: 'claude', label: 'Claude Code' },
  { id: 'codex', label: 'Codex' },
  { id: 'opencode', label: 'OpenCode' },
  { id: 'easycode', label: 'EasyCode' },
] as const

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
  // 平台多选 — 默认不勾任何平台（2026-09 用户决策；强制显式选择避免误装）
  const [targets, setTargets] = useState<string[]>([])

  function toggleTarget(id: string) {
    setTargets((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id],
    )
  }

  // ponytail: 2026-09 — 仅 SKILL.md/skill.md/SKILL.yaml 探测通过的 repo 才显示安装按钮。
  // 不是所有 GitHub 项目都支持安装为 skill（agent framework、LLM gateway、IDE 插件等
  // 都不是可装载的 skill 格式）。HF/arXiv/MCP 条目更不可能。双重门控：
  //   1. sourceOf(repo) === 'github' — 必须是 GitHub 仓库
  //   2. repo.is_skill === true — 后端 SKILL.md 探测通过
  const installable = repo
    ? sourceOf(repo) === 'github' && repo.is_skill === true
    : false

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
            ? await api.updateSkill(repo.name, repo.url, targets)
            : await api.installSkill(repo.name, repo.url, targets)
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
                  {/* 平台多选 — 安装/更新都作用于勾选的平台；默认空（强制显式选择） */}
                  <div className="mb-2 flex items-center gap-2 text-[11px]">
                    <span className="text-foreground-subtle">已选 {targets.length}/4</span>
                    <button
                      type="button"
                      onClick={() => setTargets(['claude', 'codex', 'opencode', 'easycode'])}
                      className="rounded px-1.5 py-0.5 text-foreground-subtle hover:text-foreground"
                    >
                      全选
                    </button>
                    <button
                      type="button"
                      onClick={() => setTargets([])}
                      className="rounded px-1.5 py-0.5 text-foreground-subtle hover:text-foreground"
                    >
                      全不选
                    </button>
                  </div>
                  <div className="mb-2 flex flex-wrap items-center gap-1.5">
                    <span className="mr-1 text-[11px] text-foreground-subtle">安装到</span>
                    {PLATFORMS.map((p) => {
                      const on = targets.includes(p.id)
                      return (
                        <button
                          key={p.id}
                          type="button"
                          aria-pressed={on}
                          onClick={() => toggleTarget(p.id)}
                          className={
                            'inline-flex items-center gap-1 rounded-full px-3.5 py-1.5 text-sm font-medium ring-1 transition ' +
                            (on
                              ? 'bg-primary/20 text-primary ring-primary/50'
                              : 'bg-background-muted text-foreground-subtle ring-border-muted hover:text-foreground')
                          }
                        >
                          {on ? <Check className="h-3 w-3" /> : null}
                          {p.label}
                        </button>
                      )
                    })}
                  </div>
                  {repo.local_installed ? (
                    /* 视觉审查修正：更新=品牌色主按钮；卸载=ghost 危险操作且分隔，降低误触 */
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => act('update')}
                        disabled={busy !== null || targets.length === 0}
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
                        onClick={() => {
                          if (window.confirm(`确定卸载「${repo.name}」吗?\n\n本地 skill 文件会被删除,skills cache 标记会清除。`)) {
                            act('uninstall')
                          }
                        }}
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
                      disabled={busy !== null || targets.length === 0}
                      className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-primary/25 px-3 py-2 text-xs font-semibold text-primary ring-1 ring-primary/40 transition hover:bg-primary/35 disabled:opacity-50"
                    >
                      {busy === 'install' ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Download className="h-3.5 w-3.5" />
                      )}
                      安装为 Skill{targets.length === 0 ? '（请先勾选平台）' : ''}
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

              {/* 详细介绍 — 统一 5 桶渲染（是什么 / 能干什么 / 解决什么问题 / 同类竞品 / 何时选它）。
                  优先用 LLM 生成的 analysis_5d（含 alternatives 各自的优缺点），
                  降级到 summary_sections（README 拆分 + 同 topic 匹配），缺桶不渲染。 */}
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white">详细介绍</h3>
                <span className="text-[11px] text-foreground-subtle">
                  {repo.analysis_5d ? 'LLM 决策分析' : 'README 智能摘要'}
                </span>
              </div>
              <div className="card-surface space-y-4 p-4">
                <DetailBucket
                  label="是什么"
                  source={repo.analysis_5d}
                  fallback={repo.summary_sections?.intro}
                  field="what"
                />
                <DetailBucket
                  label="能干什么"
                  source={repo.analysis_5d}
                  fallback={repo.summary_sections?.can_do}
                  field="can_do"
                />
                <DetailBucket
                  label="解决什么问题"
                  source={repo.analysis_5d}
                  fallback={repo.summary_sections?.problem}
                  field="problem"
                />
                <DetailAlternatives
                  richAlternatives={repo.analysis_5d?.alternatives}
                  flatString={repo.summary_sections?.competitive}
                />
                <DetailBucket
                  label="何时选它"
                  source={repo.analysis_5d}
                  fallback={repo.summary_sections?.when_to_use}
                  field="when_to_use"
                />
                {!repo.analysis_5d &&
                  !repo.summary_sections?.intro &&
                  !repo.summary_sections?.can_do &&
                  !repo.summary_sections?.problem &&
                  !repo.summary_sections?.competitive &&
                  !repo.summary_sections?.when_to_use && (
                    <p className="text-sm leading-relaxed text-foreground-muted">
                      {repo.summary_zh || repo.desc_zh || repo.desc || '暂无详细描述'}
                    </p>
                  )}
              </div>

              {/* 非 skill 的 GitHub 仓库 — 提示用户为何无安装按钮 */}
              {sourceOf(repo) === 'github' && !repo.is_skill && (
                <div className="mt-3 rounded-lg border border-border-muted/50 bg-background-muted/40 p-3 text-xs leading-relaxed text-foreground-subtle">
                  ℹ️ 该项目未检测到 <code className="rounded bg-background-strong px-1 py-0.5 font-mono text-[11px]">SKILL.md</code> /
                  <code className="ml-1 rounded bg-background-strong px-1 py-0.5 font-mono text-[11px]">skill.md</code> /
                  <code className="ml-1 rounded bg-background-strong px-1 py-0.5 font-mono text-[11px]">SKILL.yaml</code>，
                  不支持作为 skill 安装；可在 GitHub 单独使用。
                </div>
              )}
            </DrawerBody>
          </>
        ) : null}
      </DrawerContent>
    </Drawer>
  )
}

/** 单段详介的展示单元 — 缺桶不渲染，保留呼吸感 */
function SummarySection({ label, text }: { label: string; text?: string }) {
  if (!text || !text.trim()) return null
  return (
    <div>
      <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
        <span className="h-1 w-1 rounded-full bg-primary" />
        {label}
      </div>
      <p className="text-sm leading-relaxed text-foreground-muted">{text.trim()}</p>
    </div>
  )
}

/** 5 维度分析的单桶渲染 — 支持纯文本段落或列表（项目 / 优缺）。stacked=true 列表竖排。 */
function Analysis5dSection({
  label,
  text,
  items,
  renderItem,
  stacked,
}: {
  label: string
  text?: string
  items?: string[]
  renderItem?: (item: string) => React.ReactNode
  stacked?: boolean
}) {
  if (text && text.trim()) {
    return (
      <div>
        <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
          <span className="h-1 w-1 rounded-full bg-primary" />
          {label}
        </div>
        <p className="text-sm leading-relaxed text-foreground-muted">{text.trim()}</p>
      </div>
    )
  }
  if (items && items.length && renderItem) {
    return (
      <div>
        <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
          <span className="h-1 w-1 rounded-full bg-primary" />
          {label}
        </div>
        <div className={stacked ? 'space-y-1.5' : 'flex flex-wrap gap-1.5'}>
          {items.map((it, i) => (
            <div key={i}>{renderItem(it)}</div>
          ))}
        </div>
      </div>
    )
  }
  return null
}

/** 单桶文本(来源:LLM analysis_5d → 降级 summary_sections).
 * 统一处理"什么字段优先用哪个数据源"的逻辑,缺桶不渲染。 */
function DetailBucket({
  label,
  source,
  fallback,
  field,
}: {
  label: string
  source?: Record<string, unknown> | null
  fallback?: string
  field: string
}) {
  // ponytail: 2026-09 — 三级 fallback chain:
  //   1. analysis_5d[field]    (LLM 决策分析)
  //   2. summary_sections[field] (README 拆分 + 同 topic 匹配)
  //   3. 完全无内容 → 返回 null(抽屉该桶不渲染)
  const src = source && typeof source === 'object' ? (source as Record<string, unknown>) : null
  const srcVal = src ? src[field] : undefined
  const fb = fallback && fallback.trim() ? fallback.trim() : ''
  const text =
    (typeof srcVal === 'string' && srcVal.trim()) || fb || ''
  if (!text) return null
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
        <span className="h-1 w-1 rounded-full bg-primary" />
        {label}
      </div>
      <p className="text-sm leading-relaxed text-foreground-muted">{text}</p>
    </div>
  )
}

/** 同类竞品 — 两种来源:
 * 1. analysis_5d.alternatives = [{name, pros, cons}, ...] — LLM 生成,带每个竞品的优缺点
 * 2. summary_sections.competitive = "同类项目: A、B、C" — README 拆分 + 同 topic 匹配(纯字符串)
 */
function DetailAlternatives({
  richAlternatives,
  flatString,
}: {
  richAlternatives?: Array<{ name: string; pros: string; cons: string }>
  flatString?: string
}) {
  // LLM 路径:列表含 name/pros/cons,渲染为竞品卡片网格
  if (richAlternatives && richAlternatives.length > 0) {
    return (
      <div>
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
          <span className="h-1 w-1 rounded-full bg-primary" />
          同类项目
        </div>
        <div className="space-y-2">
          {richAlternatives.map((alt, i) => (
            <div
              key={i}
              className="rounded-lg border border-border-muted/40 bg-background-muted/30 p-2.5"
            >
              <a
                href={`https://github.com/${alt.name.includes('/') ? alt.name : `search?q=${encodeURIComponent(alt.name)}`}`}
                target="_blank"
                rel="noopener"
                className="text-sm font-medium text-primary hover:underline"
              >
                {alt.name}
              </a>
              {alt.pros && (
                <div className="mt-1 text-[12px] leading-relaxed text-foreground-muted">
                  <span className="mr-1 font-semibold text-success">✓</span>
                  {alt.pros}
                </div>
              )}
              {alt.cons && (
                <div className="text-[12px] leading-relaxed text-foreground-muted">
                  <span className="mr-1 font-semibold text-warning">✗</span>
                  {alt.cons}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    )
  }
  // 降级路径:字符串 "同类项目: A、B、C",解析成链接 chip
  if (flatString && flatString.trim()) {
    const cleaned = flatString
      .replace(/^同类项目[:：]\s*/, '')
      .trim()
    const names = cleaned.split(/[、,，\s]+/).filter(Boolean)
    if (names.length === 0) return null
    return (
      <div>
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
          <span className="h-1 w-1 rounded-full bg-primary" />
          同类项目
        </div>
        <div className="flex flex-wrap gap-1.5">
          {names.map((n, i) => (
            <a
              key={i}
              href={`https://github.com/${n.includes('/') ? n : `search?q=${encodeURIComponent(n)}`}`}
              target="_blank"
              rel="noopener"
              className="inline-flex items-center rounded-full bg-background-muted px-2.5 py-0.5 text-[11px] font-medium text-primary ring-1 ring-border-muted transition hover:bg-primary/15 hover:ring-primary/40"
            >
              {n}
            </a>
          ))}
        </div>
      </div>
    )
  }
  return null
}
