import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

// ponytail: 2026-09 — beUI/shared utility helper。clsx 处理条件 class,
// twMerge 解决 Tailwind class 冲突(say `p-2 p-4` → `p-4`)。已存在依赖里
// (clsx + tailwind-merge 通过 @appica/ui-react 间接装上)。
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ponytail: 2026-09 — beUI motion tokens。EASE_OUT 是 beUI NumberTicker / AnimatedNumber
// 等所有 motion 组件用的统一缓动曲线。直接复制 beUI 源,避免散落 magic numbers。
export const EASE_OUT = [0.16, 1, 0.3, 1] as const
export const EASE_IN_OUT = [0.77, 0, 0.175, 1] as const
export const EASE_DRAWER = [0.32, 0.72, 0, 1] as const
export const EASE_OUT_CSS = 'cubic-bezier(0.16, 1, 0.3, 1)'