import { Bot, Code2, MessageSquare, Sparkles } from 'lucide-react'
import { useState } from 'react'

export type Cli = 'claude' | 'codex' | 'opencode' | 'easycode'

const LABEL: Record<Cli, string> = {
  claude: 'Claude Code',
  codex: 'Codex',
  opencode: 'OpenCode',
  easycode: 'EasyCode',
}

const ICON: Record<Cli, typeof Bot> = {
  claude: Sparkles,
  codex: MessageSquare,
  opencode: Bot,
  easycode: Code2,
}

const COLOR: Record<Cli, string> = {
  claude: 'text-amber-400 border-amber-400/40 bg-amber-400/15',
  codex: 'text-emerald-400 border-emerald-400/40 bg-emerald-400/15',
  opencode: 'text-cyan-400 border-cyan-400/40 bg-cyan-400/15',
  easycode: 'text-fuchsia-400 border-fuchsia-400/40 bg-fuchsia-400/15',
}

const COLOR_OFF: Record<Cli, string> = {
  claude: 'text-foreground-subtle border-border-muted',
  codex: 'text-foreground-subtle border-border-muted',
  opencode: 'text-foreground-subtle border-border-muted',
  easycode: 'text-foreground-subtle border-border-muted',
}

export interface PlatformDotProps {
  cli: Cli
  installed: boolean
  /** When true, dot is rendered hollow and non-clickable (e.g. not supported) */
  disabled?: boolean
  /** Optional click handler — receives the cli id */
  onToggle?: (cli: Cli) => void
  size?: 'sm' | 'md'
}

export function PlatformDot({ cli, installed, disabled, onToggle, size = 'md' }: PlatformDotProps) {
  const [hover, setHover] = useState(false)
  const Icon = ICON[cli]
  const sz = size === 'sm' ? 'h-5 w-5 text-[10px]' : 'h-7 w-7 text-xs'
  const cls = installed
    ? COLOR[cli]
    : disabled
      ? 'text-foreground-subtle/30 border-border-muted/30 cursor-not-allowed'
      : COLOR_OFF[cli]
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => !disabled && onToggle?.(cli)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title={disabled ? `${LABEL[cli]} (not supported)` : (installed ? `${LABEL[cli]} 已装 — 点击卸载` : `${LABEL[cli]} — 点击安装`)}
      aria-label={disabled ? LABEL[cli] : (installed ? `Uninstall from ${LABEL[cli]}` : `Install to ${LABEL[cli]}`)}
      aria-pressed={installed}
      className={`inline-flex items-center justify-center rounded-full border transition-all duration-150 ${sz} ${cls} ${hover && !disabled ? 'scale-110' : ''}`}
    >
      <Icon className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
    </button>
  )
}
