// ponytail: tiny pure utilities — no React, no DOM. Safe to use in render.

export function formatStars(n: number | null | undefined): string {
  // 视觉审查修正：统一 k 缩写口径（此前 ≥10k 才缩写，8,193 与 37.7k 混排）
  if (n == null || isNaN(n)) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

export function formatDelta(n: number | null | undefined): string {
  if (n == null) return ''
  const sign = n > 0 ? '+' : ''
  return `${sign}${formatStars(n)}`
}

export function stripEmoji(s: string): string {
  // remove leading emoji + space from category names like "🤖 AI Agent & Skills"
  return s.replace(/^[\p{Emoji_Presentation}\p{Extended_Pictographic}]\s*/u, '').trim()
}

export function shortCategory(s: string, max = 22): string {
  const stripped = stripEmoji(s)
  return stripped.length > max ? `${stripped.slice(0, max)}…` : stripped
}

export function repoOwner(name: string): string {
  return name.split('/')[0] ?? ''
}

export function repoSlug(name: string): string {
  return name.split('/')[1] ?? name
}

// ponytail: 2026-09 UI 回归 — categoryAccent(每分类彩色渐变)已删除,
// 分类视觉统一 Appica monochrome token(侧边栏选中态用 primary)。

export function isGithubSource(src: string | undefined): boolean {
  if (!src) return false
  return src.startsWith('github') || src === 'github_trending' || src === 'github_search_html'
}
