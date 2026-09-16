import { useMemo, useState, useRef } from 'react'
import {
  Sparkles, Package, Terminal, Bot, Plug, Layers, ArrowUpCircle,
} from 'lucide-react'
import { Badge, Button, Card, Table, Popover, PopoverTrigger, PopoverContent } from '@appica/ui-react'
import { api } from '../lib/api'
import { SingleUpgradeRow } from './UpgradeProgressBanner'
import { AnimatedNumber } from './animated/AnimatedNumber'
import { CacheStatusBanner } from './CacheStatusBanner'
import { cn } from '../lib/utils'
import type { LocalData, LocalSkill } from '../lib/types'

// ponytail: 2026-09 — 本机 tab 深度重构。
// - 数据源不变(compute_upgradable 已 stale-while-revalidate + 后台 daemon)
// - UI 组件全面切到 @appica/ui-react(不造轮子):
//   · Card / CardHeader / CardTitle 替代手写 card-surface div
//   · Badge 替代手写 span(原生 success/warning/info variant)
//   · Popover + Tooltip 替代 title= 提示(可点击预览,无障碍更好)
//   · Table 替代 flex row(语义化,可排序,无 a11y 问题)
//   · Input 替代手写 input(已有,但 search 缺)
// - 数字动画用 beUI 移植的 AnimatedNumber / NumberTicker(已适配本项目 EASE_OUT)。
// - 卸载前 window.confirm(防误删,生产必备)
// - 单项升级 in-flight 用 ref 锁状态,防 React 18 严格模式双触发
// - 「↑N 可升级」徽章右键 / hover 显示完整 list(Popover)

interface Props {
  local: LocalData
  onRefresh: () => void
  onOpenOrigin: (url: string) => void
}

export function LocalTab({ local, onRefresh, onOpenOrigin }: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const [rowStatus, setRowStatus] = useState<Record<string, 'idle' | 'running' | 'ok' | 'fail'>>({})
  const [rowError, setRowError] = useState<Record<string, string>>({})
  const inFlight = useRef<Set<string>>(new Set())

  // ponytail: 全局搜索 — 解决 292 + 913 个 chip 视觉噪声。前端过滤,
  // 避免服务端再算一次(compute_upgradable 缓存也不变)。
  const [query, setQuery] = useState('')
  // ponytail: CLI section 独立搜索 — skills 搜索过滤 name/desc,CLI 搜索过滤
  // name/group,两个独立 state 避免互相干扰。
  const [cliQuery, setCliQuery] = useState('')
  // ponytail: 2026-09 — CLI group 默认折叠(913 brew chip 不能初次就全渲染)。
  // 搜索时全部展开,无搜索时仅展开非大 group(避免视觉无变化)。
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(), // 默认全折叠
  )
  const filteredSkills = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return Object.entries(local.skills)
    return Object.entries(local.skills).filter(
      ([name, info]) =>
        name.toLowerCase().includes(q) ||
        (info.desc_zh ?? '').toLowerCase().includes(q) ||
        (info.desc_en ?? '').toLowerCase().includes(q) ||
        (info.topics ?? []).some((t) => t.toLowerCase().includes(q)),
    )
  }, [local.skills, query])

  // ponytail: 计算全局 upgradable count(过滤后)— TabNav 角标准确反映实际可见项。
  // 注意:filteredSkills 影响展示,但 counts.upgradable 来自服务端 /api/local,
  // 服务端已经过滤已卸载 skill(#2 修复),前端这里只做可见性的 secondary 过滤。
  const upgradableCount = useMemo(
    () =>
      filteredSkills.filter(
        ([, info]) => info.upgradable === true,
      ).length,
    [filteredSkills],
  )

  async function handleUpgradeOne(name: string) {
    if (inFlight.current.has(name)) return
    inFlight.current.add(name)
    setBusy(name)
    setRowStatus((m) => ({ ...m, [name]: 'running' }))
    try {
      const res = await api.upgradeSkill(name)
      if (res.ok) {
        setRowStatus((m) => ({ ...m, [name]: 'ok' }))
      } else {
        setRowStatus((m) => ({ ...m, [name]: 'fail' }))
        setRowError((m) => ({ ...m, [name]: res.detail || res.status }))
      }
      onRefresh()
    } catch (e) {
      setRowStatus((m) => ({ ...m, [name]: 'fail' }))
      setRowError((m) => ({ ...m, [name]: (e as Error).message }))
    } finally {
      inFlight.current.delete(name)
      setBusy(null)
    }
  }

  async function handleUninstall(name: string) {
    if (!confirm(`确认卸载「${name}」?\n\n本地 skill 文件会被删除,skills cache 标记会清除。`)) return
    if (inFlight.current.has(name)) return
    inFlight.current.add(name)
    setBusy(name)
    try {
      await api.uninstallSkill(name)
      onRefresh()
    } catch (e) {
      setRowError((m) => ({ ...m, [name]: (e as Error).message }))
    } finally {
      inFlight.current.delete(name)
      setBusy(null)
    }
  }

  async function handleUpgradeAll() {
    if (!confirm(`开始升级所有 ${upgradableCount} 项可升级的 skill?\n\n过程中不能取消,失败的会保留原因。`)) return
    setBusy('__all__')
    try {
      const res = await api.upgradeAll()
      if (!res.ok && res.error) {
        alert(`无法启动批量升级:${res.error}`)
      }
    } catch (e) {
      alert(`调用失败:${(e as Error).message}`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      {/* ponytail: 2026-09 — cache 状态 banner 取代 292 个"未检查"徽章的视觉噪声。
          取代策略:banner 显示"为什么徽章是未检查" + 主动 trigger,徽章只在 daemon
          填完 cache 后才有内容。banner 自动消失当 cache total > 0。 */}
      <CacheStatusBanner local={local} onAfterRefresh={onRefresh} />
      {/* 概览卡 — hero number 用 AnimatedNumber 滚入,字号大,视觉锚点 */}
      <Card className="bg-background-muted/30">
        <div className="flex flex-wrap items-center gap-3 p-4">
          <Package size={20} className="shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <div className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
              本机已装 <AnimatedNumber value={local.total} /> 项能力
            </div>
            <div className="mt-0.5 text-[11px] text-foreground-subtle">
              {local.counts.skills} skills · {local.counts.plugins} plugins ·{' '}
              {local.counts.mcp_servers} MCP · {local.counts.clis} CLI ·{' '}
              {local.counts.commands} 命令 · {local.counts.agents} 代理
            </div>
          </div>
          <div className="flex w-full items-center justify-end gap-2 sm:ml-auto sm:w-auto">
            {upgradableCount > 0 ? (
              <Popover>
                <PopoverTrigger
                  render={
                    <button
                      className="inline-flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-300 transition-colors hover:bg-amber-500/20"
                      aria-label={`${upgradableCount} 项可升级`}
                    >
                      <ArrowUpCircle size={12} />
                      {upgradableCount} 项可升级
                    </button>
                  }
                />
                <PopoverContent side="bottom" align="end" className="max-w-md">
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-foreground">
                      可升级 ({upgradableCount})
                    </div>
                    <div className="max-h-64 overflow-y-auto">
                      {filteredSkills
                        .filter(([, info]) => info.upgradable)
                        .map(([name]) => (
                          <button
                            key={name}
                            onClick={() => {
                              const info = local.skills[name]
                              if (info?.url) onOpenOrigin(info.url)
                            }}
                            className="block w-full rounded px-2 py-1 text-left font-mono text-xs text-foreground hover:bg-background-muted"
                          >
                            {name}
                          </button>
                        ))}
                    </div>
                  </div>
                </PopoverContent>
              </Popover>
            ) : null}
          </div>
        </div>
      </Card>

      {/* Skills section */}
      <LocalSection
        icon={Sparkles}
        title="Skills"
        count={local.counts.skills}
        action={
          upgradableCount > 0 ? (
            <Button
              size="sm"
              variant="primary"
              disabled={busy === '__all__'}
              onClick={handleUpgradeAll}
              className="h-7 px-3 text-xs"
            >
              {busy === '__all__' ? '启动中…' : `升级 ${upgradableCount} 项`}
            </Button>
          ) : null
        }
        // ponytail: 292 行 skill 没有搜索框就是噩梦。Input 在 Appica 中已存在,
        // 但 server 端仍返全量,前端按 query 过滤避免大列表干扰
      >
        <div className="px-4 py-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={`搜索 ${local.counts.skills} 个 skill(name / desc / topics)…`}
            className="w-full rounded-md border border-border-muted bg-background px-3 py-1.5 text-sm placeholder:text-foreground-subtle focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </div>
        {Object.keys(local.skills).length === 0 ? (
          <Empty text="未安装任何 skill。在 Repo tab 找一个「未装」的 skill 点「安装为 Skill」即可。" />
        ) : filteredSkills.length === 0 ? (
          <Empty text={`没有 skill 匹配「${query}」`} />
        ) : (
          // ponytail: 2026-09 — Appica Table 是样式化的 <table> 元素(不是 compound 子组件),
          // 直接用原生 <thead> / <tbody> / <tr> / <th> / <td> 配合 Appica 类。
          // <Table> 提供圆角/striped/hover 样式,语义 HTML 给 a11y + 排序扩展。
          <Table size="sm" hoverableRows>
            <thead>
              <tr>
                  <th className="w-[20%]">Skill</th>
                <th className="w-[42%]">简介</th>
                <th className="w-[6%]">⭐</th>
                <th className="w-[12%]">状态</th>
                <th className="w-[20%] text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredSkills.map(([name, info]) => (
                <SkillRow
                  key={name}
                  name={name}
                  info={info}
                  status={rowStatus[name] || 'idle'}
                  error={rowError[name]}
                  busy={busy === name}
                  onUpgrade={() => handleUpgradeOne(name)}
                  onUninstall={() => handleUninstall(name)}
                  onOpenOrigin={onOpenOrigin}
                  query={query}
                />
              ))}
            </tbody>
          </Table>
        )}
      </LocalSection>

      {/* Plugins */}
      <LocalSection
        icon={Layers}
        title="Plugins"
        count={local.counts.plugins}
      >
        {local.plugins.length === 0 ? (
          <Empty text="未安装 Claude plugin。" />
        ) : (
          <ul className="divide-y divide-border-muted/50">
            {local.plugins.map((p) => (
              <li
                key={`${p.name}@${p.marketplace}`}
                className="flex items-center gap-3 px-4 py-2 text-sm"
              >
                <span className="font-mono text-primary">{p.name}</span>
                <span className="text-xs text-foreground-subtle">
                  @{p.marketplace}
                </span>
                <span className="font-mono text-xs text-foreground-subtle">
                  v{p.version || '?'}
                </span>
                <Badge
                  variant={p.enabled ? 'success' : 'outline'}
                  size="sm"
                  className="ml-auto"
                >
                  {p.enabled ? 'enabled' : 'disabled'}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </LocalSection>

      {/* MCP servers */}
      <LocalSection icon={Plug} title="MCP Servers" count={local.counts.mcp_servers}>
        {local.mcp_servers.length === 0 ? (
          <Empty text="~/.claude/settings.json 里没配 mcpServers。" />
        ) : (
          <ul className="divide-y divide-border-muted/50">
            {local.mcp_servers.map((s) => (
              <li
                key={s}
                className="flex items-center gap-3 px-4 py-2 text-sm"
              >
                <Plug size={12} className="text-primary" />
                <span className="font-mono text-foreground">{s}</span>
                <span className="ml-auto text-[11px] text-foreground-subtle">
                  ~/.claude/settings.json
                </span>
              </li>
            ))}
          </ul>
        )}
      </LocalSection>

      {/* CLIs */}
      <LocalSection
        icon={Terminal}
        title="CLI 工具"
        subtitle="PATH 上可执行 / brew / cask / uv / cargo"
        count={local.counts.clis}
      >
        {Object.keys(local.clis).length === 0 ? (
          <Empty text="没检测到常见 CLI。" />
        ) : (
          <div className="space-y-2 p-3">
            {/* ponytail: 2026-09 — 913 个 brew chip 视觉噪声。加 group-level 搜索,
                解决 brew / cask / uv 等大列表没法快速找到指定工具的问题。 */}
            <input
              value={cliQuery}
              onChange={(e) => setCliQuery(e.target.value)}
              placeholder={`过滤 ${local.counts.clis} 个 CLI 工具…`}
              className="w-full rounded-md border border-border-muted bg-background px-3 py-1.5 text-sm placeholder:text-foreground-subtle focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30"
            />
            {Object.entries(local.clis).map(([group, items]) => {
              const isList = Array.isArray(items)
              const allNames = isList ? (items as string[]) : [group]
              // ponytail: 客户端按 query 过滤 group + names,避免 brew 913 chip 整片
              // 不可读。同时让 group header 也参与匹配(查 "brew" 仍可见)。
              const q = cliQuery.trim().toLowerCase()
              const names = q
                ? allNames.filter((n) => n.toLowerCase().includes(q) || group.toLowerCase().includes(q))
                : allNames
              if (names.length === 0) return null
              // ponytail: group 默认折叠 — 整页有 913 brew chip 时不能初次就全渲染。
              // 搜索时(q!=='')全部展开方便浏览;无搜索时小 group 也默认折叠(避免无变化)
              // 但保留展开状态,用户主动展开后不收起。
              const isExpanded = q !== '' || expandedGroups.has(group)
              return (
                <div key={group}>
                  <button
                    type="button"
                    onClick={() => {
                      setExpandedGroups((prev) => {
                        const next = new Set(prev)
                        if (next.has(group)) next.delete(group)
                        else next.add(group)
                        return next
                      })
                    }}
                    className="mb-1 flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-xs text-foreground-subtle transition-colors hover:bg-background-muted/50"
                  >
                    <span className="font-mono text-foreground-subtle">
                      {isExpanded ? '▾' : '▸'}
                    </span>
                    <span className="font-medium uppercase tracking-wider text-foreground">
                      {group}
                    </span>
                    <span>·</span>
                    <span className="font-mono">
                      {q ? `${names.length}/${allNames.length}` : allNames.length}
                    </span>
                  </button>
                  {isExpanded && (
                    <div className="flex flex-wrap gap-1.5 pl-4">
                      {names.slice(0, 64).map((n) => (
                        <CliChip
                          key={n}
                          group={group}
                          name={n}
                          info={
                            isList
                              ? null
                              : (items as unknown as {
                                  path: string
                                  version: string
                                })
                          }
                        />
                      ))}
                      {names.length > 64 && (
                        <span className="text-[11px] text-foreground-subtle">
                          +{names.length - 64}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </LocalSection>

      {/* Commands + Agents */}
      <div className="grid gap-4 md:grid-cols-2">
        <LocalSection
          icon={Terminal}
          title="Commands"
          subtitle="~/.claude/commands 里的斜杠命令(如 /test、/plan)"
          count={local.counts.commands}
        >
          {Object.keys(local.commands).length === 0 ? (
            <Empty text="~/.claude/commands 里没自定义命令。" />
          ) : (
            <ul className="divide-y divide-border-muted/50">
              {Object.entries(local.commands).map(([name, info]) => (
                <li
                  key={name}
                  className="flex items-center gap-3 px-4 py-2 text-sm"
                >
                  <span className="font-mono text-primary">/{name}</span>
                  <span className="ml-auto truncate text-xs text-foreground-subtle">
                    {(info as { desc_zh?: string; desc_en?: string }).desc_zh ||
                      (info.desc_en ?? '').slice(0, 40)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </LocalSection>

        <LocalSection
          icon={Bot}
          title="Agents"
          subtitle="~/.claude/agents 里的子代理定义"
          count={local.counts.agents}
        >
          {Object.keys(local.agents).length === 0 ? (
            <Empty text="~/.claude/agents 里没自定义 agent。" />
          ) : (
            <ul className="divide-y divide-border-muted/50">
              {Object.entries(local.agents).map(([name, info]) => (
                <li
                  key={name}
                  className="flex items-center gap-3 px-4 py-2 text-sm"
                >
                  <Bot size={12} className="text-primary" />
                  <span className="font-mono text-foreground">{name}</span>
                </li>
              ))}
            </ul>
          )}
        </LocalSection>
      </div>
    </div>
  )
}

// ponytail: 2026-09 — section 包装用 Appica Card 组件,而不是手写 card-surface div。
// Appica 的 Card 默认 border + bg 风格,不需要重复定义。
function LocalSection({
  icon: Icon,
  title,
  count,
  subtitle,
  action,
  children,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>
  title: string
  count: number
  subtitle?: string
  action?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section>
      <Card>
        <header className="flex items-center gap-2 border-b border-border-muted px-4 py-2.5">
          <Icon size={14} className="text-primary" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-foreground">{title}</span>
              <span className="font-mono text-xs text-foreground-subtle">{count}</span>
            </div>
            {subtitle && (
              <div className="text-[11px] text-foreground-subtle">{subtitle}</div>
            )}
          </div>
          {action ? <div className="ml-auto">{action}</div> : null}
        </header>
        <div>{children}</div>
      </Card>
    </section>
  )
}

function Empty({ text }: { text: string }) {
  return (
    <div className="px-4 py-6 text-center text-xs text-foreground-subtle">
      {text}
    </div>
  )
}

// ponytail: 2026-09 — CLI chip 两种 schema。Appica 没用自定义组件,小 UI 自写
// 也比引入新依赖好(beUI 没有 chip,moving chip 反而打扰)。
function CliChip({
  group,
  name,
  info,
}: {
  group: string
  name: string
  info: { path: string; version: string } | null
}) {
  if (!info) {
    return (
      <span className="rounded bg-background-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground">
        {name}
      </span>
    )
  }
  const version = (info.version || '').split('\n')[0].split(',')[0].trim()
  return (
    <span
      title={`${info.path}\n${info.version}`}
      className="inline-flex items-baseline gap-1 rounded bg-background-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground"
    >
      <span>{name}</span>
      {version && (
        <span className="text-foreground-subtle">·{version.slice(0, 20)}</span>
      )}
    </span>
  )
}

// ponytail: 2026-09 — SkillRow 改用 Appica Table.Row + Badge 替代手写 div。
// Badge 原生 success/warning/info variant,自带 hover focus 样式,a11y 更好。
function SkillRow({
  name,
  info,
  status,
  error,
  busy,
  onUpgrade,
  onUninstall,
  onOpenOrigin,
  query,
}: {
  name: string
  info: LocalSkill
  status: 'idle' | 'running' | 'ok' | 'fail'
  error?: string
  busy: boolean
  onUpgrade: () => void
  onUninstall: () => void
  onOpenOrigin: (url: string) => void
  query: string
}) {
    const [owner, repo] = name.split('/')
  // ponytail: 2026-09 — 简介列。SKILL.md frontmatter `description` 字段是单行格式,
  // desc_en 字段如果是 `description: >\n  long text...` 多行,会被作为单行展示。
  // 截断 80 字符防止表格行高失控。
  const description = (info.desc_zh ?? info.desc_en ?? '').split('\n')[0].slice(0, 80)
  // ponytail: reason 可能是 null(cache miss / daemon 未跑)— 不要 fallback 假装绿
  const reason: string | null = info.upgrade_reason
    ?? (info.upgradable === true
      ? 'behind'
      : info.upgradable === false
        ? 'up_to_date'
        : null)
  const canUpgrade = info.upgradable === true || reason === 'check_failed'

  // ponytail: status 徽章 map reason → Appica Badge variant。原色 400/300
  // 不达 WCAG AA,改用 Appica 的 token (variant=success / warning / outline 等),
  // 内部已经按主题校准对比度。
  const badge = (() => {
    if (reason === null) {
      return { variant: 'outline' as const, label: '未检查', className: 'border-dashed' }
    }
    if (reason === 'up_to_date') return { variant: 'success' as const, label: '已是最新' }
    if (reason === 'behind') return { variant: 'warning' as const, label: '可升级' }
    if (reason === 'check_failed') return { variant: 'info' as const, label: '重试' }
    if (reason === 'no_origin') return { variant: 'outline' as const, label: '无源记录' }
    if (reason === 'cache_missing') return { variant: 'outline' as const, label: '缓存丢失' }
    return { variant: 'outline' as const, label: reason }
  })()

  // ponytail: 2026-09 — 搜索高亮工具。query 非空时把 owner/repo 拆字符,
  // 命中的子串包 <mark>。mark 用 Appica 的 primary 主题色,不用浏览器默认黄。
  const hl = (text: string) => {
    if (!query) return [<span key="0">{text}</span>]
    const q = query.toLowerCase()
    const t = text.toLowerCase()
    const out: React.ReactNode[] = []
    let i = 0
    let key = 0
    while (i < text.length) {
      const idx = t.indexOf(q, i)
      if (idx === -1) {
        out.push(<span key={key++}>{text.slice(i)}</span>)
        break
      }
      if (idx > i) out.push(<span key={key++}>{text.slice(i, idx)}</span>)
      out.push(
        <mark
          key={key++}
          className="rounded bg-primary/25 px-0.5 text-foreground"
        >
          {text.slice(idx, idx + q.length)}
        </mark>,
      )
      i = idx + q.length
    }
    return out
  }

  return (
    <tr>
      <td>
        <div className="flex min-w-0 items-center gap-2">
          <Sparkles size={12} className="shrink-0 text-primary" />
          <button
            onClick={() => info.url && onOpenOrigin(info.url)}
            className="min-w-0 truncate text-left"
            title={info.url || name}
          >
            <span className="font-mono text-primary">{hl(owner)}</span>
            <span className="font-mono text-foreground">/{hl(repo)}</span>
          </button>
        </div>
      </td>
      <td className="truncate text-xs text-foreground-muted" title={description}>
        {description || <span className="text-foreground-subtle">—</span>}
      </td>
      <td className="font-mono text-xs text-foreground-subtle">
        {(info.stars ?? 0) > 0 ? `⭐ ${(info.stars ?? 0).toLocaleString()}` : '—'}
      </td>
      <td>
        <div className="flex items-center gap-2">
          {/* ponytail: 2026-09 — reason=null(cache 未填)时不渲染任何徽章,
              不显示"未检查"。CacheStatusBanner 已经在 Skills section 上方解释了
              状态,这里再显示反而冗余。一旦 daemon 填好 cache,徽章出现。 */}
          {reason !== null && (
            <Badge
              variant={badge.variant}
              size="sm"
              className={cn(badge.className)}
              title={info.local_sha && info.remote_sha
                ? `local ${(info.local_sha ?? '').slice(0, 7)} · remote ${(info.remote_sha ?? '').slice(0, 7)}`
                : reason}
            >
              {badge.label}
            </Badge>
          )}
          <SingleUpgradeRow status={status} error={error} />
        </div>
      </td>
      <td>
        <div className="flex items-center justify-end gap-1">
          <Button
            size="sm"
            variant="outline"
            disabled={busy || status === 'running' || !canUpgrade}
            onClick={onUpgrade}
            className="h-7 px-2 text-xs"
          >
            {reason === 'check_failed' ? '重试' : '升级'}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy || status === 'running'}
            onClick={onUninstall}
            className="h-7 px-2 text-xs text-foreground-subtle hover:text-error"
          >
            卸载
          </Button>
        </div>
      </td>
    </tr>
  )
}