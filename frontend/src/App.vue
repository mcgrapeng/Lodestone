<script setup>
import { ref, computed, onMounted, onUnmounted, watch, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Search, ExternalLink, X, Bot, Brain, MessageSquareText,
  Code2, Workflow, Image, Dumbbell, BarChart3, Bookmark, Star,
  Flame, Sparkles, Download, RefreshCw, Folder, Terminal,
  Users, Plug, Hash, AtSign, ArrowLeft, TrendingUp,
  Monitor, Globe, Activity,
} from 'lucide-vue-next'

// ponytail: data layer is /api/* — Vue 3 is presentation only. No JSON import, no build-time snapshot.
const snap = ref(null)
const localSkills = ref({})   // legacy alias — skills only
const localCmds = ref({})
const localAgents = ref({})
const localPlugins = ref([])
const localClis = ref({})
const localMcp = ref([])         // ponytail: mcp_servers (context7 / chrome-devtools-mcp)
const localGroups = ref([])      // ponytail: [{url, slug, name, label, counts, items}, ...]
const localReplacements = ref([]) // ponytail: [{installed, recommended, alternatives_count}] — skill only
const workbuddyPicks = ref([])   // ponytail: curated list of useful WorkBuddy plugins/tools
// ponytail: tiny category label map — category keys use hyphens (workbuddy_picks.json),
// Vue would coerce the prop to underscored identifier if extracted inline.
const WORKBUDDY_CAT_LABELS = { 'agent-platform': '平台', 'marketplace': '市场', 'doc': '文档', 'automation': '自动化', 'design': '设计', 'data': '数据' }
// HMR nudge 2026-07-21 13:43 — force full template re-render so workbuddy section renders fresh
const localTotal = ref(0)
const showAllAgents = ref(false)
const q = ref('')
// ponytail: trending-only filter — repo must have appeared in github.com/trending?since=daily
// in the last crawl AND passed is_ai_relevant(). Same predicate as the 🔥 Trending badge
// shown on cards, so toggling this never disagrees with what users already see.
const trendingOnly = ref(false)
const _q = window.location.search
const view = ref(_q.includes('page=top') ? 'top' : _q.includes('page=gain') ? 'gain' : 'main')
// ponytail: per-category "show all" toggle so 30+ repos don't get clipped to 18 in view=main
const catShowAll = reactive({})
window.addEventListener('popstate', () => {
  const q = window.location.search
  view.value = q.includes('page=top') ? 'top' : q.includes('page=gain') ? 'gain' : 'main'
})

// ponytail: /top view state — fetcher + paginator. Refresh on view enter (skip if cached)
const topPage = ref(1)
const topPerPage = 12
const topSort = ref('stars')
const topData = ref(null)
const topLoading = ref(false)

async function loadTop(page = 1) {
  topLoading.value = true
  try {
    const r = await fetch(`/api/top?page=${page}&size=${topPerPage}&sort=${topSort.value}`)
    topData.value = await r.json()
    topPage.value = page
  } catch (e) {
    console.error('Failed to load /top:', e)
    topData.value = null
  } finally {
    topLoading.value = false
  }
}

watch([view, topSort], () => {
  if (view.value === 'top' && !topData.value) loadTop(1)
}, { immediate: true })

// ponytail: /gain view — 24h star gainers only (sourced from repos.stars_today, scraped from github.com/trending)
const gainMinDelta = 50
const gainPage = ref(1)
const gainSize = ref(24)
const gainData = ref(null)
const gainLoading = ref(false)

async function loadGain() {
  gainLoading.value = true
  try {
    const r = await fetch(
      `/api/gain?min_delta=${gainMinDelta}&page=${gainPage.value}&size=${gainSize.value}`
    )
    gainData.value = await r.json()
  } catch (e) {
    console.error('Failed to load /gain:', e)
    gainData.value = null
  } finally {
    gainLoading.value = false
  }
}

function changeGainPage(p) {
  gainPage.value = p
  loadGain()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

watch(view, () => {
  if (view.value === 'gain' && !gainData.value) loadGain()
}, { immediate: true })

async function changeSort(s) {
  topSort.value = s
  await loadTop(1)
}

function pageNumbers() {
  const total = topData.value?.pages || 1
  const cur = topPage.value
  const out = new Set([1, cur - 1, cur, cur + 1, total])
  const arr = [...out].filter(p => p >= 1 && p <= total).sort((a, b) => a - b)
  const compact = []
  for (let i = 0; i < arr.length; i++) {
    if (i > 0 && arr[i] - arr[i-1] > 1) compact.push(-1)
    compact.push(arr[i])
  }
  return compact
}
const activeSection = ref('hot')
const selected = ref(null)
const drawerOpen = ref(false)
const refreshing = ref(false)

// ponytail: capability-origin modal state — let user tag commands/agents/plugins with GitHub URL
const capOpen = ref(false)
const capKind = ref('')          // 'commands' | 'agents' | 'plugins'
const capName = ref('')          // file stem for commands/agents; "name@marketplace" for plugins
const capUrl = ref('')
const capDescZh = ref('')
const capDescEn = ref('')
const capPath = ref('')          // display only: file path or install_path
const capSaving = ref(false)

// ponytail: group drill-in modal — show all items inside a source group
const groupModalOpen = ref(false)
const groupModalSlug = ref('')
const groupModalUrl = ref('')
const groupModalItems = ref([])

// ponytail: replacement confirm modal — installed skill has a stronger alternative
const replaceOpen = ref(false)
const replaceOld = ref(null)    // {name, url, stars}
const replaceNew = ref(null)    // {name, url, stars, desc_zh, desc_en}
const replaceMode = ref('alongside')  // 'replace' | 'alongside' — AI-chosen action
const replaceBusy = ref(false)
const alongsideBusy = ref(false)
function replacementFor(skillName) {
  return localReplacements.value.find(r => r.installed.name === skillName) || null
}
function openReplaceConfirm(installedName) {
  const r = replacementFor(installedName)
  if (!r) return
  replaceOld.value = r.installed
  replaceNew.value = r.recommended
  replaceMode.value = r.mode || 'alongside'
  replaceOpen.value = true
}
async function confirmReplace() {
  if (!replaceOld.value || !replaceNew.value) return
  replaceBusy.value = true
  try {
    const res = await fetch('/api/local/replace', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old: replaceOld.value.name, new: replaceNew.value.name, url: replaceNew.value.url }),
    })
    const d = await res.json()
    if (d.ok) {
      ElMessage.success(`已用 ${replaceNew.value.name} 替换 ${replaceOld.value.name}`)
      replaceOpen.value = false
      await fetchAll()
    } else {
      ElMessage.error(d.error || '替换失败')
    }
  } catch (e) {
    ElMessage.error('请求失败：' + e.message)
  } finally {
    replaceBusy.value = false
  }
}
// ponytail: alongside-install — same modal, but only install the recommended skill
// without uninstalling the existing one. Useful when the user wants both: keep their
// current setup AND try the alternative. Reuses installSkill() payload.
async function confirmInstallAlongside() {
  if (!replaceNew.value) return
  alongsideBusy.value = true
  try {
    const res = await fetch('/api/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: replaceNew.value.name, url: replaceNew.value.url }),
    })
    const d = await res.json()
    if (d.ok) {
      ElMessage.success(`已并存安装 ${replaceNew.value.name}（${replaceOld.value?.name ?? ''} 保留）`)
      replaceOpen.value = false
      await fetchAll()
    } else {
      ElMessage.error(d.error || '安装失败')
    }
  } catch (e) {
    ElMessage.error('请求失败：' + e.message)
  } finally {
    alongsideBusy.value = false
  }
}
// ponytail: dialog reload trigger 2026-07-21
function openGroupModal(group) {
  groupModalSlug.value = group.slug || '未分类'
  groupModalUrl.value = group.url || ''
  groupModalItems.value = group.items || []
  groupModalOpen.value = true
}

const CAT_ICONS = {
  agent: Bot, memory: Brain, llm: MessageSquareText, devtool: Code2,
  workflow: Workflow, multimodal: Image, finetune: Dumbbell,
  eval: BarChart3, awesome: Bookmark,
  ide: Monitor, gateway: Globe, observability: Activity,
}

async function fetchAll() {
  try {
    const [dataResp, localResp, wbResp] = await Promise.all([
      fetch('/api/data'),
      fetch('/api/local'),
      fetch('/api/workbuddy'),
    ])
    if (dataResp.ok) snap.value = await dataResp.json()
    if (localResp.ok) {
      const d = await localResp.json()
      localSkills.value = d.skills || {}
      localCmds.value = d.commands || {}
      localAgents.value = d.agents || {}
      localPlugins.value = d.plugins || []
      localClis.value = d.clis || {}
      localMcp.value = d.mcp_servers || []
      localGroups.value = d.groups || []
      localReplacements.value = d.replacements || []
      localTotal.value = d.total || 0
    }
    if (wbResp.ok) {
      const d = await wbResp.json()
      workbuddyPicks.value = d.picks || []
    }
  } catch (e) {
    console.error('fetchAll failed:', e)
  }
}

async function refreshAll() {
  refreshing.value = true
  ElMessage.info('正在爬取 GitHub，预计 1-2 分钟…完成后自动刷新')
  try {
    await fetch('/api/crawl', { method: 'POST' })
    // ponytail: poll /api/data until fetched_at changes, then refresh
    const before = snap.value?.fetched_at
    for (let i = 0; i < 90; i++) {
      await new Promise(r => setTimeout(r, 2000))
      const r = await fetch('/api/data')
      if (!r.ok) continue
      const d = await r.json()
      if (d.fetched_at && d.fetched_at !== before) {
        snap.value = d
        break
      }
    }
    await fetchAll()
    ElMessage.success('已刷新')
  } catch (e) {
    ElMessage.error('刷新失败：' + e.message)
  } finally {
    refreshing.value = false
  }
}

async function installSkill(repo) {
  try {
    const r = await fetch('/api/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: repo.name, url: repo.url }),
    })
    const d = await r.json()
    if (d.ok) {
      ElMessage.success(d.message)
      await fetchAll()
      if (selected.value?.name === repo.name) {
        selected.value = { ...selected.value, local_installed: true }
      }
    } else {
      ElMessage.error(d.error || '安装失败')
    }
  } catch (e) {
    ElMessage.error('请求失败：' + e.message)
  }
}

// ponytail: wrap a CLI tool as a /slash command so Claude invokes it directly
async function wrapCli(name) {
  try {
    const r = await fetch('/api/install-cli', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, command: name }),
    })
    const d = await r.json()
    if (d.ok) {
      ElMessage.success(d.message)
      await fetchAll()
    } else {
      ElMessage.error(d.error || '包装失败')
    }
  } catch (e) {
    ElMessage.error('请求失败：' + e.message)
  }
}

// ponytail: open the edit-origin modal pre-filled from current meta
function openCapability(kind, name, meta) {
  capKind.value = kind
  capName.value = name
  capUrl.value = meta?.url || ''
  capDescZh.value = meta?.desc_zh || ''
  capDescEn.value = meta?.desc_en || ''
  capPath.value = meta?.path || meta?.install_path || ''
  capOpen.value = true
}

async function saveCapabilityOrigin() {
  capSaving.value = true
  try {
    const r = await fetch('/api/local/origin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        kind: capKind.value,
        name: capName.value,
        url: capUrl.value,
        desc_zh: capDescZh.value,
        desc_en: capDescEn.value,
      }),
    })
    const d = await r.json()
    if (d.ok) {
      ElMessage.success(capUrl.value ? '已保存 GitHub 出处' : '已清除出处')
      capOpen.value = false
      await fetchAll()
    } else {
      ElMessage.error(d.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error('请求失败：' + e.message)
  } finally {
    capSaving.value = false
  }
}

// ponytail: facts is the evidence-based line; plain is older topic-only fallback
const whyFor = r => r.facts || r.plain || ''

const hasData = computed(() => Boolean(snap.value && Array.isArray(snap.value.hot_now)))
const totalRepos = computed(() => {
  if (!snap.value) return 0
  return (snap.value.hot_now?.length || 0) +
    (snap.value.categories?.reduce((n, c) => n + (c.repos?.length || 0), 0) || 0)
})
const installedCount = computed(() => localTotal.value)
const cmdCount = computed(() => Object.keys(localCmds.value).length)
const agentCount = computed(() => Object.keys(localAgents.value).length)
const pluginCount = computed(() => localPlugins.value.length)
const cliCount = computed(() =>
  Object.values(localClis.value).reduce((n, arr) => n + (arr?.length || 0), 0)
    + localMcp.value.length
)
const recommendedSkills = computed(() => {
  if (!snap.value) return []
  // ponytail: build installedSet from ALL local capabilities (skills + plugins + mcp + clis),
  // not just localSkills — otherwise ECC (a plugin) gets recommended as "not installed"
  const installedSet = new Set()
  for (const k of Object.keys(localSkills.value)) installedSet.add(k.toLowerCase())
  for (const p of (localPlugins.value || [])) {
    installedSet.add((p.name || '').toLowerCase())
    installedSet.add((p.marketplace || '').toLowerCase())
  }
  for (const m of (localMcp.value || [])) installedSet.add(m.toLowerCase())
  for (const items of Object.values(localClis.value || {})) {
    if (Array.isArray(items)) for (const it of items) installedSet.add((it || '').toLowerCase())
    if (typeof items === 'object' && items) for (const it of Object.keys(items)) installedSet.add(it.toLowerCase())
  }
  const seen = new Set()
  const out = []
  for (const cat of snap.value.categories) {
    for (const r of cat.repos) {
      if (r.local_installed) continue
      // ponytail: skip if repo name or last segment matches ANY installed capability
      const seg = r.name.split('/').pop().toLowerCase()
      const full = r.name.toLowerCase()
      if (installedSet.has(seg) || installedSet.has(full)) continue
      if (seen.has(r.name)) continue
      // ponytail: only recommend repos that look like skills — agent/mcp/awesome categories
      const cats = r.categories || []
      const isSkill = cats.some(c => ['agent', 'devtool', 'awesome'].includes(c))
        || (r.topics || []).some(t => /skill|mcp|sub.?agent|claude.?code/i.test(t))
      if (!isSkill) continue
      seen.add(r.name)
      out.push(r)
      if (out.length >= 8) return out
    }
  }
  return out
})

const filteredHot = computed(() => {
  if (!snap.value) return []
  return _qFilter(snap.value.hot_now)
})

const filteredCats = computed(() => {
  if (!snap.value) return []
  if (!q.value.trim()) return snap.value.categories
  return snap.value.categories.map(cat => ({
    ...cat,
    repos: _qFilter(cat.repos),
  })).filter(cat => cat.repos.length > 0)
})

// ponytail: rank-aware search — name match wins over description, description over topics.
// Returns {item, score} so callers can sort by relevance. Empty query returns inputs unchanged.
function _qRanked(rows) {
  const raw = q.value.trim()
  if (!raw || !rows) return (rows || []).map(r => ({ item: r, score: 0, hits: [] }))
  const t = raw.toLowerCase()
  const tokens = t.split(/\s+/).filter(Boolean)
  const out = []
  for (const r of rows) {
    let score = 0
    let hits = []
    const name = String(r.name || '').toLowerCase()
    const descZh = String(r.desc_zh || '').toLowerCase()
    const desc = String(r.description || r.desc || '').toLowerCase()
    const topics = (r.topics || []).map(x => String(x).toLowerCase())
    // ponytail: word-boundary substring — token must be at start of word or after a
    // non-alphanumeric char. Two-char tokens also require a non-alphanumeric char (or end)
    // AFTER them, since 'pi' inside 'pipeline' / 'pii-detection' / 'Pipedream' would
    // otherwise drown the user in noise. Three+ char tokens are specific enough that
    // 'graph' inside 'graphrag' is a legitimate user search we keep.
    // Single-char tokens fall back to plain includes (regex word-boundary rejects 'pi'
    // the project name itself).
    const wb = (tok, hay) => {
      if (tok.length < 2) return hay.includes(tok)
      const escaped = tok.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const right = tok.length === 2 ? '([^a-z0-9]|$)' : ''
      const re = new RegExp(`(^|[^a-z0-9])${escaped}${right}`, 'i')
      return re.test(hay)
    }
    for (const tok of tokens) {
      // name match is a strong signal — name is the primary identifier
      if (wb(tok, name)) { score += 10; hits.push('name'); continue }
      // description match in either language — desc_zh is what most users see
      if (wb(tok, descZh)) { score += 5; hits.push('desc_zh'); continue }
      if (wb(tok, desc)) { score += 5; hits.push('description'); continue }
      // topic match is weakest — many repos share topics like 'agent', 'llm'
      if (topics.some(tp => wb(tok, tp))) { score += 2; hits.push('topics'); continue }
      // ponytail: require ALL tokens to match somewhere — AND semantics, not OR
      score = 0; hits = []; break
    }
    if (score > 0) out.push({ item: r, score, hits })
  }
  // ponytail: sort strongest match first, then by stars as tiebreaker
  out.sort((a, b) => b.score - a.score || (b.item.stars || 0) - (a.item.stars || 0))
  return out
}

function _qFilter(rows) {
  let out = _qRanked(rows).map(x => x.item)
  if (trendingOnly.value) out = out.filter(r => r.trending)
  return out
}

function openRepo(r) {
  selected.value = r
  drawerOpen.value = true
}
function closeDrawer() {
  drawerOpen.value = false
  setTimeout(() => { selected.value = null }, 200)
}
function starsFmt(n) {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}
function openUrl(url) {
  window.open(url, '_blank', 'noopener')
}
function goToTop() {
  history.pushState({}, '', '?page=top')
  view.value = 'top'
  if (!topData.value) loadTop(1)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function goToMain() {
  history.pushState({}, '', window.location.pathname)
  view.value = 'main'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function goToGain() {
  history.pushState({}, '', '?page=gain')
  view.value = 'gain'
  if (!gainData.value) loadGain()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

let pollTimer = null
onMounted(async () => {
  await fetchAll()
  // ponytail: poll every 30s so external crawls surface without manual refresh
  pollTimer = setInterval(fetchAll, 30000)
  const sections = ['local', 'hot', ...(snap.value?.categories || []).map(c => 'cat-' + c.id)]
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) activeSection.value = e.target.id })
  }, { rootMargin: '-40% 0px -55% 0px' })
  sections.forEach(id => {
    const el = document.getElementById(id)
    if (el) obs.observe(el)
  })
})
onUnmounted(() => pollTimer && clearInterval(pollTimer))

const navTabs = computed(() => [
  { id: 'local', label: '本机能力', icon: Folder },
  { id: 'hot', label: '全站最热', icon: Flame },
  { id: 'workbuddy', label: 'WorkBuddy', icon: Sparkles },
  ...(snap.value?.categories || []).map(c => ({
    id: 'cat-' + c.id,
    label: c.name.split('(')[0].split('&')[0].trim(),
    icon: CAT_ICONS[c.id] || Star,
  })),
])
</script>

<template>
  <el-config-provider>
    <!-- Aurora background -->
    <div class="aurora-bg" aria-hidden="true">
      <div class="aurora-blob aurora-1"></div>
      <div class="aurora-blob aurora-2"></div>
      <div class="aurora-blob aurora-3"></div>
      <div class="aurora-grid"></div>
      <!-- ponytail: dark vignette over aurora so text never fights color -->
      <div class="aurora-vignette"></div>
    </div>

    <!-- Hero -->
    <header class="px-6 md:px-12 pt-16 pb-10 border-b border-white/5 relative">
      <div class="max-w-7xl mx-auto">
        <div class="flex items-center justify-between flex-wrap gap-4 mb-4">
          <div class="flex items-center gap-3">
            <el-icon :size="32" color="#a78bfa"><Sparkles /></el-icon>
            <h1 class="text-5xl md:text-6xl font-black tracking-tight gradient-text">Lodestone</h1>
          </div>
          <div class="flex gap-2 flex-wrap">
            <el-button type="primary" :icon="RefreshCw" :loading="refreshing" @click="refreshAll" plain>
              刷新
            </el-button>
            <el-button :icon="Sparkles" @click="goToTop" plain>
              ⭐ 1k+ 主流
            </el-button>
            <el-button :icon="TrendingUp" @click="goToGain" plain>
              🚀 今日星增
            </el-button>
          </div>
        </div>
        <p class="text-lg text-white/60 max-w-2xl">
          GitHub AI 项目的每日精选
        </p>
        <div v-if="snap" class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6 max-w-3xl">
          <div class="stat-tile">
            <el-icon :size="20" color="#34d399"><Folder /></el-icon>
            <div class="stat-number">{{ installedCount }}</div>
            <div class="stat-label">本机能力</div>
          </div>
          <div class="stat-tile">
            <el-icon :size="20" color="#fbbf24"><Flame /></el-icon>
            <div class="stat-number">{{ totalRepos }}</div>
            <div class="stat-label">今日 Repos</div>
          </div>
          <div class="stat-tile">
            <el-icon :size="20" color="#a78bfa"><Bookmark /></el-icon>
            <div class="stat-number">{{ snap.categories.length }}</div>
            <div class="stat-label">分类</div>
          </div>
          <div class="stat-tile">
            <el-icon :size="20" color="#94a3b8"><Terminal /></el-icon>
            <div class="stat-number">{{ cliCount }}</div>
            <div class="stat-label">CLI 工具</div>
          </div>
        </div>
        <div v-if="snap" class="mt-3 text-xs text-white/40 font-mono">
          🕒 数据更新于 {{ snap.fetched_at.slice(0, 16).replace('T', ' ') }}
        </div>
        <div class="relative mt-8 flex items-center gap-3 max-w-2xl flex-wrap">
          <div class="relative flex-1 min-w-[260px]">
            <el-icon class="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"><Search /></el-icon>
            <input
              v-model="q"
              type="text"
              placeholder="搜索项目名、描述、用途…"
              class="w-full pl-10 pr-4 py-3 rounded-full bg-white/5 border border-white/10 text-white placeholder-white/40 outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition"
              autofocus
            />
          </div>
          <button
            @click="trendingOnly = !trendingOnly"
            :class="[
              'shrink-0 inline-flex items-center gap-1.5 px-4 py-3 rounded-full text-sm font-semibold transition border',
              trendingOnly
                ? 'bg-gradient-to-r from-orange-500/30 to-amber-500/30 border-orange-400/60 text-orange-100 shadow-lg shadow-orange-500/10'
                : 'bg-white/5 border-white/10 text-white/60 hover:border-orange-400/40 hover:text-orange-200'
            ]"
            :title="trendingOnly ? '点击显示全部' : '只显示 GitHub Trending 当日榜上有名的（爬取时已筛 AI 相关）'"
          >
            <span>🔥 Trending</span>
            <span v-if="trendingOnly" class="text-[10px] opacity-70">仅</span>
          </button>
        </div>
      </div>
    </header>

    <!-- Sticky Nav -->
    <nav class="sticky top-0 z-30 backdrop-blur-xl bg-black/40 border-b border-white/5 px-6 py-3 overflow-x-auto">
      <div class="max-w-7xl mx-auto flex gap-1">
        <a
          v-for="tab in navTabs"
          :key="tab.id"
          :href="'#' + tab.id"
          class="nav-tab"
          :class="{ active: activeSection === tab.id }"
        >
          <el-icon :size="16"><component :is="tab.icon" /></el-icon>
          {{ tab.label }}
        </a>
      </div>
    </nav>

    <!-- Main -->
    <main v-if="view === 'main'" class="max-w-7xl mx-auto px-6 md:px-12 py-12">
      <div v-if="!hasData" class="py-20 text-center text-white/60">
        <el-icon :size="32" class="mb-4 text-purple-400 animate-spin"><RefreshCw /></el-icon>
        <p>正在从 <code class="text-purple-300">/api/data</code> 加载…</p>
        <p class="text-sm mt-2 text-white/40">若无数据，运行 <code class="text-purple-300">./radar.py crawl</code></p>
        <el-button size="small" plain class="mt-4" @click="fetchAll">手动重试</el-button>
      </div>

      <!-- 本机能力总览 -->
      <section id="local" class="scroll-mt-24 mb-16">
        <div class="section-title">
          <el-icon color="#34d399"><Folder /></el-icon>
          本机能力 · 共 {{ installedCount }} 项
        </div>
        <p class="text-white/50 text-sm mb-5">扫描 <code class="text-emerald-300">~/.claude/{skills,commands,agents,plugins}</code> + <code class="text-emerald-300">~/.codex/skills</code></p>

        <!-- 计数 chip 行 — 5 大类各自一张卡 -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
          <a href="#cap-skills" class="system-cap-card group">
            <el-icon :size="24" color="#34d399"><Folder /></el-icon>
            <div class="system-cap-num">{{ Object.keys(localSkills).length }}</div>
            <div class="system-cap-label">Skills</div>
            <div class="system-cap-sub">任务型能力</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
          <a href="#cap-sources" class="system-cap-card group">
            <el-icon :size="24" color="#fb923c"><Terminal /></el-icon>
            <div class="system-cap-num">{{ cmdCount }}</div>
            <div class="system-cap-label">Commands</div>
            <div class="system-cap-sub">斜杠指令</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
          <a href="#cap-sources" class="system-cap-card group">
            <el-icon :size="24" color="#22d3ee"><Bot /></el-icon>
            <div class="system-cap-num">{{ agentCount }}</div>
            <div class="system-cap-label">Agents</div>
            <div class="system-cap-sub">子代理</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
          <a href="#cap-sources" class="system-cap-card group">
            <el-icon :size="24" color="#fbbf24"><Plug /></el-icon>
            <div class="system-cap-num">{{ pluginCount }}</div>
            <div class="system-cap-label">Plugins</div>
            <div class="system-cap-sub">市场插件</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
          <a href="#cap-clis" class="system-cap-card group">
            <el-icon :size="24" color="#94a3b8"><Terminal /></el-icon>
            <div class="system-cap-num">{{ cliCount }}</div>
            <div class="system-cap-label">CLIs</div>
            <div class="system-cap-sub">brew/uv/cargo/MCP</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
        </div>

        <!-- 本机能力 · 按来源分组（skills + commands + agents + plugins 合并） -->
        <div v-if="localGroups.length > 0" id="cap-sources" class="scroll-mt-24 mb-8">
          <div class="flex items-center gap-2 mb-3">
            <el-icon color="#a78bfa"><Layers /></el-icon>
            <h3 class="text-lg font-bold text-white/90">
              本机能力来源 <span class="text-white/40 text-sm font-normal">— Skills · Commands · Agents · Plugins 按出处分组</span>
            </h3>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div
              v-for="g in localGroups"
              :key="g.url || g.name"
              class="capability-card group cursor-pointer"
              @click="openGroupModal(g)"
            >
              <div class="flex items-start justify-between gap-3 mb-2">
                <h3 class="capability-name font-mono break-all">{{ g.slug || g.name }}</h3>
                <a
                  v-if="g.url"
                  :href="g.url"
                  target="_blank"
                  rel="noopener"
                  @click.stop
                  class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-200 border border-emerald-400/40 hover:bg-emerald-500/30 transition shrink-0"
                  title="打开 GitHub 仓库"
                >↗ GitHub</a>
              </div>
              <div class="flex gap-1 flex-wrap">
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-200 border border-purple-400/30 font-mono">
                  {{ g.items.length }} 项
                </span>
                <span v-if="g.counts.skills" class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-200 border border-emerald-400/30 font-mono">
                  {{ g.counts.skills }} 技能
                </span>
                <span v-if="g.counts.commands" class="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-200 border border-orange-400/30 font-mono">
                  /{{ g.counts.commands }} 命令
                </span>
                <span v-if="g.counts.agents" class="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-200 border border-cyan-400/30 font-mono">
                  {{ g.counts.agents }} 代理
                </span>
                <span v-if="g.counts.plugins" class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-200 border border-amber-400/30 font-mono">
                  {{ g.counts.plugins }} 插件
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- ponytail: 本机 CLI 集成 — 显示对本机集成有用的 4 个工具 (rtk / context7 / graphify / code-review-graph) -->
        <div
          v-if="localClis.rtk || localMcp.includes('context7') || (localClis.uv && localClis.uv.includes('graphifyy')) || (localClis.uv && localClis.uv.includes('code-review-graph'))"
          id="cap-clis"
          class="scroll-mt-24 mb-8"
        >
          <div class="flex items-center gap-2 mb-3">
            <el-icon color="#94a3b8"><Terminal /></el-icon>
            <h3 class="text-lg font-bold text-white/90">
              本机 CLI 集成 <span class="text-white/40 text-sm font-normal">— 4 个 Claude Code 集成工具</span>
            </h3>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            <!-- rtk (brew) -->
            <div v-if="localClis.rtk" class="capability-card">
              <div class="flex items-center gap-2 mb-2">
                <span class="capability-name font-mono">rtk</span>
                <span class="text-xs px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded">brew</span>
              </div>
              <div class="text-xs text-white/40 mb-1">{{ localClis.rtk.version }}</div>
              <a href="https://github.com/rtk-ai/rtk" target="_blank" rel="noopener"
                 class="text-xs text-emerald-400 hover:text-emerald-300 font-mono">github.com/rtk-ai/rtk →</a>
            </div>
            <!-- context7 (MCP) -->
            <div v-if="localMcp.includes('context7')" class="capability-card">
              <div class="flex items-center gap-2 mb-2">
                <span class="capability-name font-mono">context7</span>
                <span class="text-xs px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded">mcp</span>
              </div>
              <div class="text-xs text-white/40 mb-1">实时文档查询</div>
              <a href="https://github.com/upstash/context7" target="_blank" rel="noopener"
                 class="text-xs text-emerald-400 hover:text-emerald-300 font-mono">github.com/upstash/context7 →</a>
            </div>
            <!-- graphify (uv) -->
            <div v-if="localClis.uv && localClis.uv.includes('graphifyy')" class="capability-card">
              <div class="flex items-center gap-2 mb-2">
                <span class="capability-name font-mono">graphify</span>
                <span class="text-xs px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded">uv</span>
              </div>
              <div class="text-xs text-white/40 mb-1">代码图谱 / MCP</div>
              <a href="https://github.com/Graphify-Labs/graphify" target="_blank" rel="noopener"
                 class="text-xs text-emerald-400 hover:text-emerald-300 font-mono">github.com/Graphify-Labs/graphify →</a>
            </div>
            <!-- code-review-graph (uv) -->
            <div v-if="localClis.uv && localClis.uv.includes('code-review-graph')" class="capability-card">
              <div class="flex items-center gap-2 mb-2">
                <span class="capability-name font-mono">code-review-graph</span>
                <span class="text-xs px-1.5 py-0.5 bg-emerald-100 text-emerald-700 rounded">uv</span>
              </div>
              <div class="text-xs text-white/40 mb-1">CRG 代码审查图谱</div>
              <a href="https://github.com/tirth8205/code-review-graph" target="_blank" rel="noopener"
                 class="text-xs text-emerald-400 hover:text-emerald-300 font-mono">github.com/tirth8205/code-review-graph →</a>
            </div>
          </div>
        </div>

        <!-- CLI 工具 / Plugins / Skills 单独展示已移除 — 全部并入上面"本机能力来源"按 GitHub 仓库分组 -->
        <!-- 未安装推荐 (only for skills, since commands/agents/plugins aren't from GitHub) -->
        <div v-if="recommendedSkills.length > 0">
          <div class="text-sm font-semibold text-white/70 mb-3 mt-2">🔥 没装但很值得装的 Skills</div>
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div
              v-for="r in recommendedSkills"
              :key="r.name"
              class="repo-card"
              @click="openRepo(r)"
            >
              <div class="flex items-start justify-between gap-2 mb-2">
                <h3 class="font-bold text-base leading-tight flex-1 min-w-0 break-all">{{ r.name }}</h3>
                <span v-if="r.trending" class="top-card-trending-badge shrink-0">🔥 Trending</span>
                <span class="text-amber-400 font-mono text-sm whitespace-nowrap shrink-0">⭐ {{ starsFmt(r.stars) }}</span>
              </div>
              <div class="text-sm font-medium text-purple-300 leading-snug mb-2">
                💡 {{ whyFor(r) }}
              </div>
              <p class="text-sm text-white/65 leading-relaxed mb-3" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                {{ (r.desc_zh || r.desc || '').slice(0, 140) }}
              </p>
              <div class="flex items-center justify-between flex-wrap gap-1">
                <div class="flex gap-1 flex-wrap">
                  <el-tag
                    v-for="t in (r.topics || []).slice(0, 3)"
                    :key="t"
                    size="small"
                    effect="plain"
                    class="!text-xs"
                  >{{ t }}</el-tag>
                </div>
                <span class="text-xs text-cyan-400 font-mono">{{ r.lang }}</span>
              </div>
              <div class="flex gap-2 mt-3">
                <el-button type="primary" size="small" :icon="Download" @click.stop="installSkill(r)" plain>
                  一键安装
                </el-button>
                <el-button size="small" @click.stop="openRepo(r)" plain>详情</el-button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- WorkBuddy 精选插件/工具 — anchor 锚点 section -->
      <section id="workbuddy" class="scroll-mt-24 mb-16">
        <div class="section-title">
          <el-icon color="#a78bfa"><Sparkles /></el-icon>
          WorkBuddy 生态 · {{ workbuddyPicks.length }} 个精选
          <span class="text-white/40 text-sm font-normal ml-2">— 腾讯 AI 桌面代理好用的插件/工具</span>
        </div>
        <p class="text-white/50 text-sm mb-5">
          数据源混合：<code class="text-purple-300">codebuddy.cn/work</code> 官方市场 + CSDN 实战博客
          <a href="https://codebuddy.cn/work" target="_blank" rel="noopener" class="ml-2 text-purple-300 hover:text-purple-200 text-xs">↗ 打开官网</a>
        </p>
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="p in workbuddyPicks"
            :key="p.name"
            class="repo-card hover:!border-purple-400/40 transition relative"
          >
            <div class="flex items-start justify-between gap-2 mb-2">
              <h3 class="font-bold text-base leading-tight flex-1 min-w-0 break-all">{{ p.name }}</h3>
              <span
                class="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded shrink-0"
                :class="{
                  'bg-purple-500/20 text-purple-200 border border-purple-400/30': p.category === 'agent-platform' || p.category === 'marketplace',
                  'bg-blue-500/20 text-blue-200 border border-blue-400/30': p.category === 'doc',
                  'bg-cyan-500/20 text-cyan-200 border border-cyan-400/30': p.category === 'automation',
                  'bg-pink-500/20 text-pink-200 border border-pink-400/30': p.category === 'design',
                  'bg-emerald-500/20 text-emerald-200 border border-emerald-400/30': p.category === 'data',
                }"
              >{{ WORKBUDDY_CAT_LABELS[p.category] || p.category }}</span>
            </div>
            <p class="text-sm text-white/75 leading-relaxed mb-2" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
              {{ p.tagline }}
            </p>
            <div class="text-xs text-purple-300/90 leading-snug mb-2">💡 {{ p.why }}</div>
            <div class="text-[11px] text-white/50 leading-snug mb-3 pt-2 border-t border-white/5">📦 {{ p.install }}</div>
            <div class="flex items-center justify-between gap-2 flex-wrap">
              <div class="flex gap-1 flex-wrap">
                <span
                  v-for="t in (p.tags || []).slice(0, 4)"
                  :key="t"
                  class="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/60 font-mono"
                >#{{ t }}</span>
              </div>
              <a :href="p.url" target="_blank" rel="noopener" @click.stop class="text-[10px] px-2 py-1 rounded bg-purple-500/20 text-purple-200 border border-purple-400/40 hover:bg-purple-500/30 transition shrink-0">↗ 详情</a>
            </div>
          </div>
        </div>
      </section>

      <!-- Hot Now -->
      <section id="hot" class="scroll-mt-24 mb-16">
        <div class="section-title">🔥 Top 24 · 全站最热</div>
        <p class="text-white/50 text-sm mb-5">按 ⭐ 排序，今日 GitHub 上最火的 AI 项目</p>
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="(r, i) in filteredHot.slice(0, 24)"
            :key="r.name"
            class="repo-card relative"
            :class="{ 'is-installed': r.local_installed }"
            @click="openRepo(r)"
          >
            <span class="absolute top-2 left-2 text-xs font-black text-purple-300/80 font-mono">#{{ i + 1 }}</span>
            <div class="flex items-start justify-between gap-2 mb-2 pl-7">
              <h3 class="font-bold text-base leading-tight flex-1 min-w-0 break-all">{{ r.name }}</h3>
              <div class="flex items-center gap-1.5 shrink-0">
                <span v-if="r.trending" class="top-card-trending-badge">🔥 Trending</span>
                <span v-if="r.local_installed" class="installed-badge">✓ 已装</span>
                <span class="text-amber-400 font-mono text-sm whitespace-nowrap">⭐ {{ starsFmt(r.stars) }}</span>
              </div>
            </div>
            <div class="text-sm font-medium text-purple-300 leading-snug mb-2 pl-7">
              💡 {{ whyFor(r) }}
            </div>
            <p class="text-sm text-white/65 leading-relaxed mb-3" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
              {{ (r.desc_zh || r.desc || '').slice(0, 140) }}
            </p>
            <div class="flex items-center justify-between flex-wrap gap-1">
              <div class="flex gap-1 flex-wrap">
                <el-tag
                  v-for="t in (r.topics || []).slice(0, 3)"
                  :key="t"
                  size="small"
                  effect="plain"
                  class="!text-xs"
                >{{ t }}</el-tag>
              </div>
              <span class="text-xs text-cyan-400 font-mono">{{ r.lang }}</span>
            </div>
          </div>
        </div>
        <p v-if="filteredHot.length === 0" class="text-center text-white/40 py-12">
          {{ trendingOnly ? '本次爬取没有 AI 相关 Trending 项目 — 关掉 🔥 仅看 Trending' : '没有匹配的项目' }}
        </p>
      </section>

      <!-- Categories -->
      <section
        v-for="cat in filteredCats"
        :key="cat.id"
        :id="'cat-' + cat.id"
        class="scroll-mt-24 mb-16"
      >
        <div class="flex items-end justify-between mb-5 flex-wrap gap-3">
          <div>
            <div class="flex items-center gap-2 mb-2">
              <el-icon :size="28" color="#a78bfa">
                <component :is="CAT_ICONS[cat.id] || Star" />
              </el-icon>
              <h2 class="text-3xl font-bold tracking-tight">{{ cat.name }}</h2>
            </div>
            <p class="text-white/60 max-w-2xl">{{ cat.desc_zh || cat.desc }}</p>
          </div>
          <span class="font-mono text-sm text-white/40">{{ cat.repos.length }} 个项目</span>
        </div>
        <div v-if="cat.repos.length === 0" class="text-center py-12 text-white/40 bg-white/2 rounded-lg border border-dashed border-white/10">
          <el-icon :size="28" class="mb-2 text-white/30"><Search /></el-icon>
          <p>该分类暂无 AI 项目</p>
          <p class="text-xs mt-1 text-white/30">GitHub API 限流或 topic 匹配空. 1 小时后重跑 <code class="text-purple-300/80">radar.py crawl</code></p>
        </div>
        <div v-else>
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div
              v-for="r in cat.repos.slice(0, catShowAll[cat.id] ? cat.repos.length : 30)"
              :key="r.name"
              class="repo-card"
              :class="{ 'is-installed': r.local_installed }"
              @click="openRepo(r)"
            >
              <div class="flex items-start justify-between gap-2 mb-2">
                <h3 class="font-bold text-base leading-tight flex-1 min-w-0 break-all">{{ r.name }}</h3>
                <div class="flex items-center gap-1.5 shrink-0">
                  <span v-if="r.trending" class="top-card-trending-badge">🔥 Trending</span>
                  <span v-if="r.local_installed" class="installed-badge">✓ 已装</span>
                  <span class="text-amber-400 font-mono text-sm whitespace-nowrap">⭐ {{ starsFmt(r.stars) }}</span>
                </div>
              </div>
              <div class="text-sm font-medium text-purple-300 leading-snug mb-2">
                💡 {{ whyFor(r) }}
              </div>
              <p class="text-sm text-white/65 leading-relaxed mb-3" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                {{ (r.desc_zh || r.desc || '').slice(0, 140) }}
              </p>
              <div class="flex items-center justify-between flex-wrap gap-1">
                <div class="flex gap-1 flex-wrap">
                  <el-tag
                    v-for="t in (r.topics || []).slice(0, 3)"
                    :key="t"
                    size="small"
                    effect="plain"
                    class="!text-xs"
                  >{{ t }}</el-tag>
                </div>
                <span class="text-xs text-cyan-400 font-mono">{{ r.lang }}</span>
              </div>
            </div>
          </div>
          <div v-if="cat.repos.length > 30" class="text-center mt-4">
            <el-button size="small" plain @click="catShowAll[cat.id] = !catShowAll[cat.id]">
              {{ catShowAll[cat.id] ? `收起 (显示 ${cat.repos.length} 个)` : `显示全部 (${cat.repos.length} 个)` }}
            </el-button>
          </div>
        </div>
      </section>

      <footer class="text-center py-12 mt-12 border-t border-white/5 text-white/40 text-sm">
        <div>Vue 3 + Vite + Element Plus 模式 · 数据源 <code class="px-2 py-0.5 rounded bg-white/5 text-purple-300">/api/data</code> · 自动 30s 轮询</div>
        <div class="mt-2">支持挂 cron / launchd 每日自动刷新（修改数据 → UI 自动更新）</div>
      </footer>
    </main>

    <!-- /top view: 1k+ star AI repos grid with pagination + sort -->
    <section v-if="view === 'top'" class="px-6 md:px-12 pt-12 pb-16 relative">
      <div class="max-w-7xl mx-auto">
        <!-- Top bar: back + sort -->
        <div class="flex items-center justify-between flex-wrap gap-4 mb-8">
          <div class="flex items-center gap-3">
            <el-button :icon="ArrowLeft" @click="goToMain" plain>返回主页</el-button>
            <div class="flex items-center gap-2">
              <el-icon :size="28" color="#fbbf24"><Sparkles /></el-icon>
              <h1 class="text-3xl md:text-4xl font-black gradient-text">1k+ 主流 AI 项目</h1>
            </div>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <span class="text-white/50 mr-1">排序:</span>
            <el-button
              v-for="s in [{v:'stars',l:'⭐ Star 数'}, {v:'recent',l:'🕒 最近更新'}, {v:'name',l:'🔤 名称'}]"
              :key="s.v"
              :type="topSort === s.v ? 'primary' : 'default'"
              size="small"
              @click="changeSort(s.v)"
              plain
            >{{ s.l }}</el-button>
          </div>
        </div>

        <!-- Stats -->
        <div v-if="topData" class="flex items-center justify-between flex-wrap gap-3 mb-5 text-sm text-white/50">
          <div>
            <span class="font-mono text-white/80">{{ topData.total }}</span> 个项目 · 第
            <span class="font-mono text-white/80">{{ topPage }}</span> /
            <span class="font-mono text-white/80">{{ topData.pages }}</span> 页
          </div>
        </div>

        <!-- Loading -->
        <div v-if="topLoading" class="text-center py-20 text-white/40">
          <el-icon :size="32" class="is-loading"><RefreshCw /></el-icon>
          <p class="mt-3">加载中…</p>
        </div>

        <!-- Empty -->
        <div v-else-if="!topData || !topData.repos?.length" class="text-center py-20 text-white/40">
          暂未发现 1k+ 星的 AI 项目。运行
          <code class="px-2 py-0.5 rounded bg-white/10 font-mono text-xs">python3 radar.py --crawl</code>
          即可生成。
        </div>

        <!-- q-filtered empty (DB has rows but none match current query) -->
        <div v-else-if="!_qFilter(topData.repos).length" class="text-center py-20 text-white/40">
          {{ trendingOnly ? '1k+ 项目里没有 Trending — 关掉 🔥 试试' : `没有匹配 \`${q}\` 的 1k+ 项目` }}
        </div>

        <!-- Cards grid -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="r in _qFilter(topData.repos)"
            :key="r.name"
            class="repo-card"
            :class="{ 'is-installed': r.local_installed }"
            @click="openRepo(r)"
          >
            <div class="flex items-start justify-between gap-2 mb-2">
              <h3 class="font-bold text-base leading-tight flex-1 min-w-0 break-all">{{ r.name }}</h3>
              <div class="flex items-center gap-1.5 shrink-0">
                <span v-if="r.trending" class="top-card-trending-badge">🔥 Trending</span>
                <span v-if="r.local_installed" class="installed-badge">✓ 已装</span>
                <span class="text-amber-400 font-mono text-sm whitespace-nowrap">⭐ {{ starsFmt(r.stars) }}</span>
              </div>
            </div>
            <div class="text-sm font-medium text-purple-300 leading-snug mb-2">
              💡 {{ whyFor(r) }}
            </div>
            <p class="text-sm text-white/65 leading-relaxed mb-3" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
              {{ (r.desc_zh || r.desc || '').slice(0, 140) }}
            </p>
            <div class="flex items-center justify-between flex-wrap gap-1">
              <div class="flex gap-1 flex-wrap">
                <el-tag
                  v-for="t in (r.topics || []).slice(0, 3)"
                  :key="t"
                  size="small"
                  effect="plain"
                  class="!text-xs"
                >{{ t }}</el-tag>
              </div>
              <span class="text-xs text-cyan-400 font-mono">{{ r.lang }}</span>
            </div>
          </div>
        </div>

        <!-- Pagination -->
        <div v-if="topData && topData.pages > 1" class="flex items-center justify-center gap-1 mt-8 flex-wrap">
          <el-button
            :disabled="topPage <= 1"
            @click="loadTop(topPage - 1)"
            size="small"
            plain
          >◀ 上一页</el-button>
          <template v-for="(p, idx) in pageNumbers()" :key="`${p}-${idx}`">
            <span v-if="p === -1" class="px-2 text-white/30">…</span>
            <el-button
              v-else
              :type="p === topPage ? 'primary' : 'default'"
              @click="loadTop(p)"
              size="small"
              plain
            >{{ p }}</el-button>
          </template>
          <el-button
            :disabled="topPage >= topData.pages"
            @click="loadTop(topPage + 1)"
            size="small"
            plain
          >下一页 ▶</el-button>
        </div>
      </div>
    </section>

    <!-- /gain view: repos with star delta ≥ gainMinDelta; 24h window only -->
    <section v-else-if="view === 'gain'" class="px-6 md:px-12 pt-12 pb-16 relative">
      <div class="max-w-7xl mx-auto">
        <div class="flex items-center justify-between flex-wrap gap-3 mb-6">
          <div>
            <h1 class="text-3xl md:text-4xl font-extrabold tracking-tight flex items-center gap-3">
              <el-icon :size="32" color="#34d399"><TrendingUp /></el-icon>
              今日星增
            </h1>
            <p class="text-sm text-white/50 mt-2">
              <template v-if="gainData?.total > 0">
                共 <span class="text-emerald-300 font-bold">{{ gainData.total }}</span> 个 AI 项目
                24h 增长 ≥ <span class="text-emerald-300 font-bold">+{{ gainMinDelta }}</span> 星
                <span v-if="gainData.pages > 1"> · 第 {{ gainData.page }} / {{ gainData.pages }} 页</span>
                · 来自 GitHub Trending
              </template>
              <template v-else>
                阈值 ≥ +{{ gainMinDelta }} 星的 AI 项目（24h 窗口）
              </template>
            </p>
          </div>
          <div class="flex items-center gap-2">
            <el-button :icon="ArrowLeft" @click="goToMain" plain>返回主页</el-button>
            <el-button :icon="RefreshCw" :loading="gainLoading" @click="loadGain" plain>刷新</el-button>
          </div>
        </div>

        <div v-if="gainData && _qFilter(gainData.gainers).length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="(r, i) in _qFilter(gainData.gainers)"
            :key="r.name"
            class="repo-card relative"
            :class="{ 'is-installed': r.local_installed }"
            @click="openRepo(r)"
          >
            <span class="absolute top-2 left-2 text-xs font-black text-emerald-300/80 font-mono">#{{ i + 1 }}</span>
            <div class="flex items-start justify-between gap-2 mb-2 pl-7">
              <h3 class="font-bold text-base leading-tight flex-1 min-w-0 break-all">{{ r.name }}</h3>
              <div class="flex flex-col items-end gap-1 shrink-0">
                <span :class="['gain-delta', r.cold_start ? 'cold' : (r.delta_24h && r.delta_24h <= 0 ? 'zero' : '')]">
                  <template v-if="r.cold_start">· 新</template>
                  <template v-else-if="r.delta_24h != null">+{{ r.delta_24h }}</template>
                  <template v-else-if="r.stars_today != null">+{{ r.stars_today }}</template>
                  <template v-else-if="r.recent_activity">🔥 近期活跃</template>
                  <template v-else>—</template>
                </span>
                <span class="text-amber-400 font-mono text-sm whitespace-nowrap">⭐ {{ r.stars.toLocaleString() }}</span>
              </div>
            </div>
            <div class="text-sm font-medium text-purple-300 leading-snug mb-2 pl-7">
              💡 {{ whyFor(r) }}
            </div>
            <p class="text-sm text-white/65 leading-relaxed mb-3" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
              {{ (r.desc_zh || r.description || '').slice(0, 140) }}
            </p>
            <div class="flex items-center justify-between flex-wrap gap-1">
              <div class="flex gap-1 flex-wrap">
                <el-tag
                  v-for="t in (r.topics || []).slice(0, 3)"
                  :key="t"
                  size="small"
                  effect="plain"
                  class="!text-xs"
                >{{ t }}</el-tag>
              </div>
              <span class="text-xs text-cyan-400 font-mono">{{ r.lang }}</span>
            </div>
          </div>
        </div>

        <div v-else-if="gainLoading" class="text-center py-20 text-white/40">
          <el-icon :size="32" class="mb-3 animate-spin text-purple-400"><RefreshCw /></el-icon>
          <p>正在从 <code class="text-purple-300">/api/gain</code> 加载…</p>
        </div>

        <div v-else class="text-center py-20 text-white/40">
          <template v-if="q.trim() && gainData && !_qFilter(gainData.gainers).length">
            <p>没有匹配 <code class="text-purple-300">{{ q }}</code> 的星增项目</p>
          </template>
          <template v-else-if="gainData && gainData.total === 0">
            <template v-if="gainData.note">
              <el-icon :size="32" class="mb-3 text-amber-400/70"><InfoFilled /></el-icon>
              <p>{{ gainData.note }}</p>
              <p class="text-sm mt-2 text-white/40">
                数据源 <code class="text-purple-300">github.com/trending</code> 需要走 Python urllib 抓取, JS-only 渲染时拿不到.
              </p>
            </template>
            <template v-else>
              <p>今天没有增幅 ≥ +{{ gainMinDelta }} 星的 AI 项目。</p>
              <p class="text-sm mt-2 text-white/30">
                说明：≥+{{ gainMinDelta }}/天 是真正的"爆款"信号，普通活跃项目达不到这个量级。
              </p>
            </template>
            <p class="text-sm mt-1 text-white/30">
              数据来源是 <code class="text-purple-300">github.com/trending</code>，运行 <code class="text-purple-300">./radar.py crawl</code> 重新拉取。
            </p>
          </template>
          <template v-else>
            <p>暂无星增数据 — 运行 <code class="text-purple-300">./radar.py crawl</code> 拉取首次 trending 数据。</p>
          </template>
        </div>

        <div v-if="gainData && gainData.pages > 1" class="flex justify-center mt-10">
          <el-pagination
            v-model:current-page="gainPage"
            :page-size="gainSize"
            :total="gainData.total"
            :pager-count="7"
            layout="prev, pager, next, jumper, total"
            background
            @current-change="changeGainPage"
          />
        </div>
      </div>
    </section>

    <!-- Repo detail drawer -->
    <el-drawer
      v-model="drawerOpen"
      direction="rtl"
      size="540px"
      :with-header="false"
      class="!bg-[#15131f]"
    >
      <div v-if="selected" class="p-6">
        <div class="flex items-start justify-between gap-3 mb-5">
          <div class="flex-1 min-w-0">
            <h2 class="text-2xl font-bold mb-2 break-all">{{ selected.name }}</h2>
            <div class="flex flex-wrap gap-1">
              <el-tag
                v-for="c in selected.categories"
                :key="c"
                size="small"
                type="primary"
                effect="plain"
              >{{ c }}</el-tag>
            </div>
          </div>
          <el-button type="primary" :icon="ExternalLink" @click="openUrl(selected.url)">
            GitHub
          </el-button>
        </div>

        <div class="rounded-xl bg-purple-500/10 border border-purple-500/30 p-4 mb-4">
          <div class="text-xs uppercase tracking-wider text-purple-300/70 mb-2 font-semibold">💡 这东西做什么</div>
          <div class="text-base font-medium leading-relaxed">{{ whyFor(selected) }}</div>
        </div>

        <div class="mb-4">
          <div class="text-xs uppercase tracking-wider text-white/50 mb-2 font-semibold">📝 中文简介</div>
          <p class="text-sm leading-relaxed text-white/85">{{ selected.desc_zh || selected.desc || '（暂无描述）' }}</p>
        </div>

        <details v-if="selected.desc && selected.desc !== selected.desc_zh" class="mb-4">
          <summary class="text-xs uppercase tracking-wider text-white/50 cursor-pointer font-semibold">🌐 英文原描述</summary>
          <p class="text-xs text-white/60 mt-2 leading-relaxed">{{ selected.desc }}</p>
        </details>

        <div class="flex items-center gap-3 flex-wrap pt-4 border-t border-white/5">
          <span class="text-amber-400 font-mono font-bold">⭐ {{ selected.stars.toLocaleString() }}</span>
          <el-tag size="small" effect="plain">{{ selected.lang }}</el-tag>
          <div class="flex flex-wrap gap-1">
            <el-tag
              v-for="t in (selected.topics || []).slice(0, 8)"
              :key="t"
              size="small"
              effect="plain"
            >{{ t }}</el-tag>
          </div>
        </div>

        <div class="mt-5 pt-5 border-t border-white/5">
          <el-button
            v-if="!selected.local_installed"
            type="success"
            :icon="Download"
            class="w-full"
            @click="installSkill(selected)"
          >
            一键安装为 Skill（Claude + Codex）
          </el-button>
          <div v-else class="rounded-xl bg-emerald-500/10 border border-emerald-400/30 p-3 text-center text-emerald-300 text-sm">
            ✓ 已安装在本机 · 重启 CLI 生效
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- Capability origin modal: tag a command/agent/plugin with its GitHub URL -->
    <el-dialog
      v-model="capOpen"
      title="设置 GitHub 出处"
      width="540px"
      class="!bg-[#15131f]"
      :close-on-click-modal="false"
    >
      <div v-if="capOpen" class="space-y-3">
        <div class="text-sm text-white/60">
          <span class="text-white/40">类型：</span>
          <span class="font-mono text-cyan-300">{{ capKind }}</span>
          <span class="text-white/40 ml-3">名称：</span>
          <span class="font-mono text-emerald-300">{{ capName }}</span>
        </div>
        <div v-if="capPath" class="text-xs text-white/40 font-mono break-all">
          📁 {{ capPath }}
        </div>
        <div>
          <label class="text-xs text-white/60 mb-1 block">GitHub URL <span class="text-white/30">（留空 = 清除出处）</span></label>
          <el-input
            v-model="capUrl"
            placeholder="https://github.com/owner/repo"
            clearable
          />
        </div>
        <div>
          <label class="text-xs text-white/60 mb-1 block">中文说明 <span class="text-white/30">（可选）</span></label>
          <el-input
            v-model="capDescZh"
            type="textarea"
            :rows="2"
            placeholder="一句话说明这个 command/agent/plugin 干什么的"
          />
        </div>
        <div>
          <label class="text-xs text-white/60 mb-1 block">English desc <span class="text-white/30">（可选）</span></label>
          <el-input
            v-model="capDescEn"
            type="textarea"
            :rows="2"
            placeholder="Original English description (used as fallback when zh is empty)"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="capOpen = false">取消</el-button>
        <el-button type="primary" :loading="capSaving" @click="saveCapabilityOrigin">保存</el-button>
      </template>
    </el-dialog>

    <!-- ponytail: group drill-in modal — list every item inside a source group with its description -->
    <el-dialog
      v-model="groupModalOpen"
      :title="`${groupModalSlug} · ${groupModalItems.length} 项`"
      width="820px"
      class="!bg-[#15131f]"
      top="6vh"
    >
      <div v-if="groupModalUrl" class="mb-4 flex items-center gap-3 flex-wrap">
        <a :href="groupModalUrl" target="_blank" rel="noopener" class="text-emerald-300 hover:text-emerald-200 text-sm font-mono break-all">
          ↗ {{ groupModalUrl }}
        </a>
        <span class="text-xs text-white/40">{{ groupModalItems.length }} 项已安装</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[68vh] overflow-y-auto pr-2">
        <div
          v-for="(it, i) in groupModalItems"
          :key="i"
          class="repo-card !p-3 hover:!border-purple-400/40 transition"
          @click.stop
        >
          <div class="flex items-start justify-between gap-2 mb-2">
            <div class="flex items-baseline gap-2 min-w-0 flex-1">
              <span
                class="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded shrink-0"
                :class="{
                  'bg-emerald-500/20 text-emerald-200 border border-emerald-400/30': it.type === 'skills',
                  'bg-orange-500/20 text-orange-200 border border-orange-400/30': it.type === 'commands',
                  'bg-cyan-500/20 text-cyan-200 border border-cyan-400/30': it.type === 'agents',
                  'bg-amber-500/20 text-amber-200 border border-amber-400/30': it.type === 'plugins',
                }"
              >{{ it.type === 'skills' ? 'SKILL' : it.type === 'commands' ? 'CMD' : it.type === 'agents' ? 'AGENT' : 'PLUGIN' }}</span>
              <h3 class="font-bold text-base leading-tight font-mono break-all min-w-0">
                {{ it.type === 'commands' ? '/' + it.name : it.name }}
              </h3>
            </div>
            <span v-if="it.stars" class="text-amber-400 font-mono text-xs whitespace-nowrap shrink-0">⭐ {{ starsFmt(it.stars) }}</span>
          </div>
          <div v-if="it.type === 'skills' && replacementFor(it.name)" class="mb-2">
            <button
              class="w-full text-left p-2 rounded-lg bg-gradient-to-r from-orange-500/15 to-amber-500/15 border border-orange-400/40 hover:border-orange-300/70 transition group/rep"
              @click.stop="openReplaceConfirm(it.name)"
              :title="`点击查看 ${replacementFor(it.name).recommended.name} 的详情并替换`"
            >
              <div class="flex items-center justify-between gap-2 mb-1">
                <span class="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-orange-500/30 text-orange-100 border border-orange-300/40">
                  🔥 找到更优替代
                </span>
                <span class="text-[10px] text-orange-200/70 group-hover/rep:text-orange-100">查看 / 选择 →</span>
              </div>
              <div class="flex items-baseline gap-2 text-sm">
                <span class="font-mono font-bold text-orange-100 break-all">{{ replacementFor(it.name).recommended.name }}</span>
                <span class="text-amber-300 font-mono text-xs shrink-0">⭐ {{ starsFmt(replacementFor(it.name).recommended.stars) }}</span>
              </div>
              <div class="text-[11px] text-white/60 mt-1 leading-snug">
                {{ replacementFor(it.name).recommended.reasons.join(' · ') }}
              </div>
            </button>
          </div>
          <p v-if="it.desc_zh" class="text-sm text-white/75 leading-relaxed mb-2" style="display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;">
            {{ it.desc_zh }}
          </p>
          <p v-else-if="it.desc_en" class="text-sm text-white/55 leading-relaxed mb-2" style="display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;">
            🌐 {{ it.desc_en }}
          </p>
          <p v-else class="text-sm text-white/30 italic mb-2">本地安装 · 无描述</p>
          <div class="flex items-center justify-between gap-2 flex-wrap mt-2 pt-2 border-t border-white/5">
            <div class="flex gap-1 flex-wrap min-w-0">
              <el-tag
                v-for="t in (it.topics || []).slice(0, 3)"
                :key="t"
                size="small"
                effect="plain"
                class="!text-[10px] !px-1.5 !py-0"
              >{{ t }}</el-tag>
              <span v-if="it.path" class="text-[10px] text-white/30 font-mono truncate" :title="it.path">
                📁 {{ it.path.split('/').slice(-2).join('/') }}
              </span>
            </div>
            <div class="flex gap-1 shrink-0">
              <el-button
                v-if="it.path && it.type !== 'plugins'"
                size="small"
                @click.stop="openUrl('file://' + it.path)"
                plain
                class="!text-[10px] !px-2 !py-0.5"
                title="打开本地文件"
              >📄 源文件</el-button>
              <el-button
                size="small"
                @click.stop="openUrl(it.url || groupModalUrl)"
                plain
                class="!text-[10px] !px-2 !py-0.5"
              >↗ GitHub</el-button>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="groupModalOpen = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- ponytail: replacement confirm modal — only ONE action button shown, AI-chosen -->
    <el-dialog
      v-model="replaceOpen"
      :title="replaceMode === 'replace' ? '🔥 替换为更优替代？' : '💡 推荐：并存安装'"
      width="540px"
      class="!bg-[#15131f]"
      top="18vh"
    >
      <div v-if="replaceOld && replaceNew" class="space-y-4">
        <div class="rounded-lg bg-white/5 border border-white/10 p-3">
          <div class="text-xs text-white/40 mb-1">当前已装</div>
          <div class="flex items-baseline gap-2">
            <span class="font-mono font-bold text-white/90 break-all">{{ replaceOld.name }}</span>
            <span v-if="replaceOld.stars" class="text-amber-400 font-mono text-xs shrink-0">⭐ {{ starsFmt(replaceOld.stars) }}</span>
          </div>
          <a v-if="replaceOld.url" :href="replaceOld.url" target="_blank" rel="noopener" class="text-[11px] text-white/40 font-mono break-all hover:text-emerald-300">↗ {{ replaceOld.url }}</a>
        </div>

        <div class="text-center text-orange-300 text-2xl">↓</div>

        <div class="rounded-lg bg-gradient-to-br from-orange-500/15 to-amber-500/15 border border-orange-400/40 p-3">
          <div class="text-xs text-orange-200/80 mb-1 font-bold">推荐{{ replaceMode === 'replace' ? '替换为' : '并存安装' }}</div>
          <div class="flex items-baseline gap-2 mb-1">
            <span class="font-mono font-bold text-orange-100 break-all">{{ replaceNew.name }}</span>
            <span class="text-amber-300 font-mono text-xs shrink-0">⭐ {{ starsFmt(replaceNew.stars) }}</span>
          </div>
          <p v-if="replaceNew.desc_zh" class="text-sm text-white/75 leading-relaxed mb-2">{{ replaceNew.desc_zh }}</p>
          <p v-else-if="replaceNew.desc_en" class="text-sm text-white/55 leading-relaxed mb-2">🌐 {{ replaceNew.desc_en }}</p>
          <div v-if="replaceNew.reasons" class="space-y-1 mt-2">
            <div v-for="rs in replaceNew.reasons" :key="rs" class="text-[11px] text-white/70">• {{ rs }}</div>
          </div>
          <a :href="replaceNew.url" target="_blank" rel="noopener" class="text-[11px] text-emerald-300 font-mono break-all hover:text-emerald-200 block mt-2">↗ {{ replaceNew.url }}</a>
        </div>

        <!-- ponytail: context banner explains WHY we picked this mode -->
        <div v-if="replaceMode === 'replace'" class="rounded-lg bg-amber-500/10 border border-amber-400/30 p-3 text-sm text-amber-100 leading-relaxed">
          ⚠️ 同为 <code class="font-mono text-amber-200">{{ replaceOld.best_category || '?' }}</code> 领域、共享 ≥2 个 vertical anchor，
          <code class="font-mono text-amber-200">{{ replaceNew.name }}</code> 在同类中明显更强，<b>建议直接替换</b>。
          替换 = 卸载 <code class="font-mono text-amber-200">{{ replaceOld.name }}</code> + 安装 <code class="font-mono text-amber-200">{{ replaceNew.name }}</code>
        </div>
        <div v-else class="rounded-lg bg-cyan-500/10 border border-cyan-400/30 p-3 text-sm text-cyan-100 leading-relaxed">
          💡 只共享 {{ replaceNew.anchors?.length || 1 }} 个 vertical anchor 或不在同一领域，<b>建议并存</b>——保留
          <code class="font-mono text-cyan-200">{{ replaceOld.name }}</code> 同时试用
          <code class="font-mono text-cyan-200">{{ replaceNew.name }}</code>，确认更优后再替换。
        </div>
      </div>
      <template #footer>
        <el-button @click="replaceOpen = false">取消</el-button>
        <el-button
          v-if="replaceMode === 'replace'"
          type="warning"
          :loading="replaceBusy"
          @click="confirmReplace"
        >确认替换</el-button>
        <el-button
          v-else
          type="success"
          :loading="alongsideBusy"
          @click="confirmInstallAlongside"
        >
          + 并存安装
          <span class="text-[10px] text-white/60 ml-1">保留旧的</span>
        </el-button>
      </template>
    </el-dialog>

  </el-config-provider>
</template>

<style>
/* ponytail: aurora background — dark base + corner blobs + grid + dark vignette over blobs. Text always wins. */
.aurora-bg {
  position: fixed; inset: 0; z-index: -10; overflow: hidden;
  background: #04020a;
}
.aurora-blob {
  position: absolute; border-radius: 50%; filter: blur(160px); opacity: 0.18;
  animation: drift 32s ease-in-out infinite alternate;
}
.aurora-1 { width: 60vw; height: 60vw; top: -35vw; left: -25vw; background: radial-gradient(circle, #7c3aed 0%, transparent 70%); }
.aurora-2 { width: 50vw; height: 50vw; top: 10vh; right: -30vw; background: radial-gradient(circle, #06b6d4 0%, transparent 70%); animation-delay: -10s; }
.aurora-3 { width: 55vw; height: 55vw; bottom: -30vw; left: 20vw; background: radial-gradient(circle, #ec4899 0%, transparent 70%); animation-delay: -20s; }
@keyframes drift { 0% { transform: translate(0, 0) scale(1); } 100% { transform: translate(3vw, -3vh) scale(1.08); } }
.aurora-grid {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: radial-gradient(ellipse 100% 100% at 50% 0%, black 0%, transparent 75%);
}
/* ponytail: dark vignette ABOVE blobs but BELOW content — keeps middle of page solid dark */
.aurora-vignette {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 120% 80% at 50% 30%, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 50%, transparent 100%),
    linear-gradient(180deg, rgba(0,0,0,0.5) 0%, transparent 30%);
}

/* ponytail: every card needs solid-enough dark backdrop so text stays crisp against aurora */
.repo-card, .hot-card {
  background: rgba(15, 12, 24, 0.78);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.08);
  padding: 14px;
  transition: all 0.15s ease;
  cursor: pointer;
}
.repo-card:hover, .hot-card:hover {
  border-color: rgba(167, 139, 250, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(124, 58, 237, 0.18);
}

/* ponytail: section titles — make them stand out as anchors */
.section-title {
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.5rem;
  background: linear-gradient(90deg, #e9d5ff, #67e8f9);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

/* ponytail: installed badge — bigger and more obvious than v1 */
.installed-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 9999px;
  background: rgba(16, 185, 129, 0.18);
  border: 1px solid rgba(52, 211, 153, 0.4);
  color: #6ee7b7;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
}
/* ponytail: dim installed cards slightly so they recede */
.repo-card.is-installed, .hot-card.is-installed {
  opacity: 0.92;
  border-color: rgba(52, 211, 153, 0.35);
  background: rgba(16, 185, 129, 0.04);
  position: relative;
}

/* ponytail: nav-tab styling */
.nav-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 9999px;
  font-size: 14px;
  color: rgba(255,255,255,0.55);
  text-decoration: none;
  transition: all 0.12s ease;
  white-space: nowrap;
}
.nav-tab:hover { color: rgba(255,255,255,0.9); background: rgba(255,255,255,0.06); }
.nav-tab.active {
  color: white;
  background: linear-gradient(90deg, rgba(124,58,237,0.4), rgba(6,182,212,0.3));
  border: 1px solid rgba(167,139,250,0.45);
}

.gradient-text {
  background: linear-gradient(90deg, #c4b5fd 0%, #67e8f9 50%, #f9a8d4 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.el-drawer__body { padding: 0; background: #15131f; }
.el-drawer { background: #15131f !important; }
</style>
