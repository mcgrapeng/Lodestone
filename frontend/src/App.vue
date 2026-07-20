<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Search, ExternalLink, X, Bot, Brain, MessageSquareText,
  Code2, Workflow, Image, Dumbbell, BarChart3, Bookmark, Star,
  Flame, Sparkles, Download, RefreshCw, Folder, Terminal,
  Users, Plug, Hash, AtSign, ArrowLeft,
} from 'lucide-vue-next'

// ponytail: data layer is /api/* — Vue 3 is presentation only. No JSON import, no build-time snapshot.
const snap = ref(null)
const localSkills = ref({})   // legacy alias — skills only
const localCmds = ref({})
const localAgents = ref({})
const localPlugins = ref([])
const localClis = ref({})
const localTotal = ref(0)
const showAllAgents = ref(false)
const q = ref('')
const view = ref(window.location.search.includes('page=top') ? 'top' : 'main')
window.addEventListener('popstate', () => {
  view.value = window.location.search.includes('page=top') ? 'top' : 'main'
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
const crawling = ref(false)

const CAT_ICONS = {
  agent: Bot, memory: Brain, llm: MessageSquareText, devtool: Code2,
  workflow: Workflow, multimodal: Image, finetune: Dumbbell,
  eval: BarChart3, awesome: Bookmark,
}

async function fetchAll() {
  try {
    const [dataResp, localResp] = await Promise.all([
      fetch('/api/data'),
      fetch('/api/local'),
    ])
    if (dataResp.ok) snap.value = await dataResp.json()
    if (localResp.ok) {
      const d = await localResp.json()
      localSkills.value = d.skills || {}
      localCmds.value = d.commands || {}
      localAgents.value = d.agents || {}
      localPlugins.value = d.plugins || []
      localClis.value = d.clis || {}
      localTotal.value = d.total || 0
    }
  } catch (e) {
    console.error('fetchAll failed:', e)
  }
}

async function refreshAll() {
  refreshing.value = true
  await fetchAll()
  refreshing.value = false
  ElMessage.success('数据已刷新')
}

async function triggerCrawl() {
  crawling.value = true
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
    ElMessage.success('GitHub 数据已更新')
  } catch (e) {
    ElMessage.error('爬取失败：' + e.message)
  } finally {
    crawling.value = false
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

// ponytail: facts is the evidence-based line; plain is older topic-only fallback
const whyFor = r => r.facts || r.plain || ''

const installedCount = computed(() => localTotal.value)
const cmdCount = computed(() => Object.keys(localCmds.value).length)
const agentCount = computed(() => Object.keys(localAgents.value).length)
const pluginCount = computed(() => localPlugins.value.length)
const cliCount = computed(() => Object.keys(localClis.value).length)
const recommendedSkills = computed(() => {
  if (!snap.value) return []
  const installedSet = new Set(Object.keys(localSkills.value))
  const seen = new Set()
  const out = []
  for (const cat of snap.value.categories) {
    for (const r of cat.repos) {
      if (r.local_installed || installedSet.has(r.name.split('/').pop())) continue
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
  if (!q.value.trim()) return snap.value.hot_now
  const t = q.value.toLowerCase()
  return snap.value.hot_now.filter(r =>
    Object.values(r).some(v => String(v).toLowerCase().includes(t))
  )
})

const filteredCats = computed(() => {
  if (!snap.value) return []
  if (!q.value.trim()) return snap.value.categories
  const t = q.value.toLowerCase()
  return snap.value.categories.map(cat => ({
    ...cat,
    repos: cat.repos.filter(r =>
      Object.values(r).some(v => String(v).toLowerCase().includes(t))
    )
  })).filter(cat => cat.repos.length > 0)
})

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
  { id: 'hot', label: '今日最热', icon: Flame },
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
            <el-button :icon="RefreshCw" :loading="refreshing" @click="refreshAll" plain>
              刷新
            </el-button>
            <el-button type="primary" :icon="Download" :loading="crawling" @click="triggerCrawl" plain>
              重新爬取
            </el-button>
            <el-button :icon="Sparkles" @click="goToTop" plain>
              🌟 5k+ 顶级
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
            <div class="stat-label">本机 Skills</div>
          </div>
          <div class="stat-tile">
            <el-icon :size="20" color="#fbbf24"><Flame /></el-icon>
            <div class="stat-number">{{ snap.total_unique }}</div>
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
        <div class="relative mt-8 max-w-xl">
          <el-icon class="absolute left-3 top-1/2 -translate-y-1/2 text-white/40"><Search /></el-icon>
          <input
            v-model="q"
            type="text"
            placeholder="搜索项目名、描述、用途…"
            class="w-full pl-10 pr-4 py-3 rounded-full bg-white/5 border border-white/10 text-white placeholder-white/40 outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition"
            autofocus
          />
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
    <main v-if="view === 'main' && snap" class="max-w-7xl mx-auto px-6 md:px-12 py-12">

      <!-- 本机能力总览 -->
      <section id="local" class="scroll-mt-24 mb-16">
        <div class="section-title">
          <el-icon color="#34d399"><Folder /></el-icon>
          本机能力 · 共 {{ installedCount }} 项
        </div>
        <p class="text-white/50 text-sm mb-5">扫描 <code class="text-emerald-300">~/.claude/{skills,commands,agents,plugins}</code> + <code class="text-emerald-300">~/.codex/skills</code></p>

        <!-- 计数 chip 行 -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <a href="#cap-skills" class="system-cap-card group">
            <el-icon :size="24" color="#34d399"><Folder /></el-icon>
            <div class="system-cap-num">{{ Object.keys(localSkills).length }}</div>
            <div class="system-cap-label">Skills</div>
            <div class="system-cap-sub">任务型能力</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
          <a href="#cap-commands" class="system-cap-card group">
            <el-icon :size="24" color="#a78bfa"><Hash /></el-icon>
            <div class="system-cap-num">{{ cmdCount }}</div>
            <div class="system-cap-label">Commands</div>
            <div class="system-cap-sub">/ 斜杠命令</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
          <a href="#cap-agents" class="system-cap-card group">
            <el-icon :size="24" color="#22d3ee"><Users /></el-icon>
            <div class="system-cap-num">{{ agentCount }}</div>
            <div class="system-cap-label">Agents</div>
            <div class="system-cap-sub">Subagent 模板</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
          <a href="#cap-plugins" class="system-cap-card group">
            <el-icon :size="24" color="#fbbf24"><Plug /></el-icon>
            <div class="system-cap-num">{{ pluginCount }}</div>
            <div class="system-cap-label">Plugins</div>
            <div class="system-cap-sub">Marketplace 扩展</div>
            <span class="system-cap-link">↓ 查看</span>
          </a>
        </div>

        <!-- Skills -->
        <div v-if="Object.keys(localSkills).length > 0" id="cap-skills" class="scroll-mt-24 mb-8">
          <div class="flex items-center gap-2 mb-3">
            <el-icon color="#34d399"><Folder /></el-icon>
            <h3 class="text-lg font-bold text-white/90">Skills <span class="text-white/40 text-sm font-normal">— 任务型能力 (Claude / Codex 调用)</span></h3>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div
              v-for="(meta, name) in localSkills"
              :key="name"
              class="capability-card group"
            >
              <div class="flex items-start justify-between gap-3 mb-2">
                <h3 class="capability-name" :title="name">{{ name }}</h3>
                <div class="flex flex-col items-end gap-1 shrink-0">
                  <span v-if="meta.stars > 0" class="text-amber-400 font-mono text-xs whitespace-nowrap">⭐ {{ starsFmt(meta.stars) }}</span>
                  <el-button
                    v-if="meta.url"
                    size="small"
                    :icon="ExternalLink"
                    @click.stop="openUrl(meta.url)"
                    plain
                    class="!text-xs !px-2 !py-0.5"
                  >↗ GitHub</el-button>
                </div>
              </div>
              <div class="flex gap-1 mb-2">
                <span v-if="meta.claude" class="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-200 border border-orange-400/30">Claude</span>
                <span v-if="meta.codex" class="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-200 border border-blue-400/30">Codex</span>
                <span v-if="meta.source === 'skillmd'" class="text-[10px] px-1.5 py-0.5 rounded bg-slate-500/20 text-slate-300 border border-slate-400/30" title="无来源链接 — 仅本地 SKILL.md">本地</span>
                <span v-if="meta.source === 'none'" class="text-[10px] px-1.5 py-0.5 rounded bg-slate-500/20 text-slate-400 border border-slate-400/30">未知</span>
              </div>
              <p v-if="meta.desc_zh" class="capability-desc">{{ meta.desc_zh }}</p>
              <p v-else-if="meta.desc_en" class="capability-desc capability-desc-en">🌐 {{ meta.desc_en }}</p>
              <p v-else class="capability-desc capability-desc-empty">本地安装 · 无介绍</p>
              <div v-if="meta.topics && meta.topics.length" class="flex gap-1 flex-wrap mt-2">
                <span v-for="t in meta.topics.slice(0, 4)" :key="t" class="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/60 font-mono">#{{ t }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Commands -->
        <div v-if="cmdCount > 0" id="cap-commands" class="scroll-mt-24 mb-8">
          <div class="flex items-center gap-2 mb-3">
            <el-icon color="#a78bfa"><Hash /></el-icon>
            <h3 class="text-lg font-bold text-white/90">Commands <span class="text-white/40 text-sm font-normal">— /斜杠命令 (输入 / 触发)</span></h3>
          </div>
          <div class="flex flex-wrap gap-2">
            <code
              v-for="(_meta, name) in localCmds"
              :key="name"
              class="px-3 py-1.5 rounded-lg bg-purple-500/10 border border-purple-400/30 text-purple-200 font-mono text-sm hover:bg-purple-500/20 transition cursor-pointer"
              :title="`/${name} · ~/.claude/commands/${name}.md`"
            >/{{ name }}</code>
          </div>
        </div>

        <!-- Agents -->
        <div v-if="agentCount > 0" id="cap-agents" class="scroll-mt-24 mb-8">
          <div class="flex items-center gap-2 mb-3">
            <el-icon color="#22d3ee"><Users /></el-icon>
            <h3 class="text-lg font-bold text-white/90">
              Agents · {{ agentCount }}
              <span class="text-white/40 text-sm font-normal ml-2">— Subagent 模板（点击展开）</span>
            </h3>
            <button
              class="ml-auto text-xs text-cyan-300 hover:text-cyan-200"
              @click="showAllAgents = !showAllAgents"
            >{{ showAllAgents ? '收起' : `展开全部 ${agentCount}` }}</button>
          </div>
          <div class="flex flex-wrap gap-2">
            <code
              v-for="(_meta, name) in (showAllAgents ? localAgents : Object.fromEntries(Object.entries(localAgents).slice(0, 30)))"
              :key="name"
              class="px-2.5 py-1 rounded-md bg-cyan-500/10 border border-cyan-400/30 text-cyan-200 font-mono text-[11px] hover:bg-cyan-500/20 transition cursor-pointer"
              :title="`${name} · ~/.claude/agents/${name}.md`"
            >{{ name }}</code>
            <span v-if="!showAllAgents && agentCount > 30" class="text-white/40 text-xs px-2 py-1">+{{ agentCount - 30 }} more</span>
          </div>
        </div>

        <!-- CLI 工具 (PATH 中已装的命令) -->
        <div v-if="cliCount > 0" class="mb-8">
          <div class="flex items-center gap-2 mb-3">
            <el-icon color="#94a3b8"><Terminal /></el-icon>
            <h3 class="text-lg font-bold text-white/90">
              CLI 工具 · {{ cliCount }}
              <span class="text-white/40 text-sm font-normal ml-2">— PATH 中可直接调用</span>
            </h3>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            <div
              v-for="(meta, name) in localClis"
              :key="name"
              class="rounded-lg border border-slate-400/20 bg-slate-500/5 backdrop-blur px-3 py-2 hover:border-slate-400/50 transition"
            >
              <div class="flex items-center justify-between gap-2">
                <div class="font-mono text-sm font-bold text-slate-200 truncate flex-1" :title="meta.path">{{ name }}</div>
                <button
                  v-if="!localCmds[name]"
                  class="text-[10px] px-2 py-0.5 rounded bg-slate-400/20 border border-slate-400/40 text-slate-200 hover:bg-slate-400/30 transition shrink-0"
                  @click="wrapCli(name)"
                  :title="`创建 /${name} 斜杠命令包装 ${name}`"
                >📋 包成 /{{ name }}</button>
                <span v-else class="installed-badge text-[10px]">✓ /{{ name }}</span>
              </div>
              <div class="text-[11px] text-white/50 truncate font-mono mt-1" :title="meta.version">{{ meta.version || '—' }}</div>
            </div>
          </div>
        </div>

        <!-- Plugins -->
        <div v-if="pluginCount > 0" id="cap-plugins" class="scroll-mt-24 mb-8">
          <div class="flex items-center gap-2 mb-3">
            <el-icon color="#fbbf24"><Plug /></el-icon>
            <h3 class="text-lg font-bold text-white/90">Plugins <span class="text-white/40 text-sm font-normal">— 来自 marketplace 的扩展</span></h3>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            <div
              v-for="p in localPlugins"
              :key="p.name + '@' + p.marketplace"
              class="rounded-lg border border-amber-400/20 bg-amber-500/5 backdrop-blur px-3 py-2 hover:border-amber-400/50 transition"
            >
              <div class="font-mono text-sm font-bold text-amber-200 truncate" :title="p.name">{{ p.name }}</div>
              <div class="flex items-center justify-between text-[11px] mt-1">
                <span class="text-white/50">{{ p.marketplace }}</span>
                <span class="text-amber-300/80 font-mono">v{{ p.version }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 未安装推荐 (only for skills, since commands/agents/plugins aren't from GitHub) -->
        <div v-if="recommendedSkills.length > 0">
          <div class="text-sm font-semibold text-white/70 mb-3 mt-2">🔥 没装但很值得装的 Skills</div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div
              v-for="r in recommendedSkills"
              :key="r.name"
              class="rounded-xl border border-white/10 bg-white/[0.03] backdrop-blur p-4 hover:border-purple-400/50 transition group"
            >
              <div class="flex items-start justify-between gap-2 mb-2">
                <h3 class="font-bold text-base leading-tight cursor-pointer hover:text-purple-300" @click="openRepo(r)">{{ r.name }}</h3>
                <span class="text-amber-400 font-mono text-sm whitespace-nowrap">⭐ {{ starsFmt(r.stars) }}</span>
              </div>
              <div class="text-xs text-purple-300 leading-snug mb-3 line-clamp-2" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                💡 {{ whyFor(r) }}
              </div>
              <div class="flex gap-2">
                <el-button type="primary" size="small" :icon="Download" @click="installSkill(r)" plain>
                  一键安装
                </el-button>
                <el-button size="small" @click="openRepo(r)" plain>详情</el-button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Hot Now -->
      <section id="hot" class="scroll-mt-24 mb-16">
        <div class="section-title">🔥 Top 24 · 全站最热</div>
        <p class="text-white/50 text-sm mb-5">按 ⭐ 排序，今日 GitHub 上最火的 AI 项目</p>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
          <div
            v-for="(r, i) in filteredHot.slice(0, 24)"
            :key="r.name"
            class="hot-card"
            :class="{ 'is-installed': r.local_installed }"
            @click="openRepo(r)"
          >
            <div class="flex items-center justify-between mb-1">
              <span class="text-xl font-black text-purple-300">#{{ i + 1 }}</span>
              <span v-if="r.local_installed" class="installed-badge">✓ 已装</span>
              <span v-else class="text-amber-400 font-mono text-xs">⭐ {{ starsFmt(r.stars) }}</span>
            </div>
            <h3 class="font-bold text-sm leading-tight mb-1 truncate">{{ r.name }}</h3>
            <p class="text-xs text-white/60 line-clamp-2 leading-snug mb-2" style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">{{ whyFor(r) }}</p>
            <div class="flex items-center justify-between">
              <div class="flex gap-1 flex-wrap">
                <el-tag
                  v-for="c in (r.categories || []).slice(0, 2)"
                  :key="c"
                  size="small"
                  type="primary"
                  effect="plain"
                  class="!text-xs"
                >{{ c }}</el-tag>
              </div>
              <span class="text-xs text-white/40 font-mono">{{ r.lang }}</span>
            </div>
          </div>
        </div>
        <p v-if="filteredHot.length === 0" class="text-center text-white/40 py-12">没有匹配的项目</p>
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
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="r in cat.repos.slice(0, 18)"
            :key="r.name"
            class="repo-card"
            :class="{ 'is-installed': r.local_installed }"
            @click="openRepo(r)"
          >
            <div class="flex items-start justify-between gap-2 mb-2">
              <h3 class="font-bold text-base leading-tight flex-1 min-w-0 break-all">{{ r.name }}</h3>
              <span v-if="r.local_installed" class="installed-badge shrink-0">✓ 已装</span>
              <span v-else class="text-amber-400 font-mono text-sm whitespace-nowrap shrink-0">⭐ {{ starsFmt(r.stars) }}</span>
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
      </section>

      <footer class="text-center py-12 mt-12 border-t border-white/5 text-white/40 text-sm">
        <div>Vue 3 + Vite + Element Plus 模式 · 数据源 <code class="px-2 py-0.5 rounded bg-white/5 text-purple-300">/api/data</code> · 自动 30s 轮询</div>
        <div class="mt-2">支持挂 cron / launchd 每日自动刷新（修改数据 → UI 自动更新）</div>
      </footer>
    </main>

    <!-- /top view: 5k+ star AI repos grid with pagination + sort -->
    <section v-if="view === 'top'" class="px-6 md:px-12 pt-12 pb-16 relative">
      <div class="max-w-7xl mx-auto">
        <!-- Top bar: back + sort -->
        <div class="flex items-center justify-between flex-wrap gap-4 mb-8">
          <div class="flex items-center gap-3">
            <el-button :icon="ArrowLeft" @click="goToMain" plain>返回主页</el-button>
            <div class="flex items-center gap-2">
              <el-icon :size="28" color="#fbbf24"><Sparkles /></el-icon>
              <h1 class="text-3xl md:text-4xl font-black gradient-text">5k+ 顶级 AI 项目</h1>
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
          暂未发现 5k+ 星的 AI 项目。运行
          <code class="px-2 py-0.5 rounded bg-white/10 font-mono text-xs">python3 radar.py --crawl</code>
          即可生成。
        </div>

        <!-- Cards grid -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <a
            v-for="r in topData.repos"
            :key="r.name"
            :href="r.url"
            target="_blank"
            rel="noopener"
            class="top-card group"
          >
            <div class="flex items-start justify-between gap-3 mb-2">
              <h3 class="top-card-name">{{ r.name }}</h3>
              <span class="top-card-stars">⭐ {{ starsFmt(r.stars) }}</span>
            </div>
            <p class="top-card-desc">
              {{ (r.desc_zh || r.desc || '（暂无描述）').slice(0, 160) }}
            </p>
            <div v-if="r.lang || (r.topics && r.topics.length)" class="top-card-meta">
              <span v-if="r.lang" class="top-card-lang">📚 {{ r.lang }}</span>
              <span v-if="r.topics && r.topics.length" class="top-card-topics">
                🏷 {{ r.topics.slice(0, 3).join(' · ') }}
              </span>
            </div>
            <div class="top-card-actions">
              <span class="top-card-link">↗ GitHub</span>
              <span
                v-if="localSkills[r.name.split('/')[-1]] || localSkills[r.name]"
                class="top-card-installed"
              >✓ 已安装</span>
              <span v-else-if="!r.local_installed" class="top-card-install-hint">+ 一键安装</span>
            </div>
          </a>
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

    <main v-else-if="view === 'main'" class="max-w-7xl mx-auto px-6 py-32 text-center text-white/60">
      <el-icon :size="48" class="mb-4 text-purple-400 animate-spin"><RefreshCw /></el-icon>
      <p>正在从 <code class="text-purple-300">/api/data</code> 加载…</p>
      <p class="text-sm mt-2 text-white/40">若无数据，运行 <code class="text-purple-300">./radar.py crawl</code></p>
    </main>

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

/* ponytail: installed badge */
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
  opacity: 0.72;
  border-color: rgba(52, 211, 153, 0.18);
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