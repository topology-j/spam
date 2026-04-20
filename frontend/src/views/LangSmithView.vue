<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = 'http://127.0.0.1:8001'

interface Run {
  id: string
  name: string
  run_type: string
  status: string
  start_time: string | null
  end_time: string | null
  latency_ms: number | null
  total_tokens: number | null
  prompt_tokens: number | null
  completion_tokens: number | null
  inputs: any
  outputs: any
  error: string | null
}

interface Stats {
  total: number
  errors: number
  avg_latency_ms: number
  total_tokens: number
  by_name: Record<string, number>
}

const runs = ref<Run[]>([])
const stats = ref<Stats | null>(null)
const loading = ref(false)
const error = ref('')
const selected = ref<Run | null>(null)
const limit = ref(50)
const filterName = ref('')

const filtered = computed(() =>
  filterName.value
    ? runs.value.filter(r => r.name.toLowerCase().includes(filterName.value.toLowerCase()))
    : runs.value
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [runsRes, statsRes] = await Promise.all([
      fetch(`${API}/langsmith/runs?limit=${limit.value}`, { headers: auth.authHeader() }),
      fetch(`${API}/langsmith/stats`, { headers: auth.authHeader() }),
    ])
    if (!runsRes.ok) {
      const d = await runsRes.json().catch(() => ({}))
      throw new Error(d.detail || '데이터 로드 실패')
    }
    runs.value = await runsRes.json()
    if (statsRes.ok) stats.value = await statsRes.json()
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function fmt(iso: string | null) {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('ko-KR')
}

function statusClass(s: string | null) {
  if (s === 'success') return 'status-ok'
  if (s === 'error') return 'status-err'
  return 'status-pending'
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="bg-orb orb1" />
    <div class="bg-orb orb2" />

    <div class="layout">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div>
          <div class="brand">
            <span class="brand-icon">🔭</span>
            <span class="brand-name">LangSmith</span>
          </div>
          <p class="brand-sub">개발자 트레이싱 대시보드</p>

          <div class="meta-box">
            <div class="meta-row">
              <span class="meta-label">프로젝트</span>
              <span class="meta-val">spam-detector</span>
            </div>
            <div class="meta-row">
              <span class="meta-label">로그인</span>
              <span class="meta-val">{{ auth.username }}</span>
            </div>
          </div>

          <div class="filter-box">
            <label class="filter-label">표시 건수</label>
            <select v-model="limit" class="filter-select" @change="load">
              <option :value="20">20건</option>
              <option :value="50">50건</option>
              <option :value="100">100건</option>
              <option :value="200">200건</option>
            </select>
            <label class="filter-label" style="margin-top:10px">이름 필터</label>
            <input v-model="filterName" class="filter-input" placeholder="run name..." />
          </div>
        </div>

        <div class="sidebar-btns">
          <button class="refresh-btn" :disabled="loading" @click="load">
            {{ loading ? '로딩 중...' : '새로고침' }}
          </button>
          <button class="back-btn" @click="router.push('/admin')">← 어드민으로</button>
        </div>
      </aside>

      <!-- Main -->
      <main class="main">
        <div v-if="error" class="error-banner">{{ error }}</div>

        <!-- Stats -->
        <div v-if="stats" class="stats-row">
          <div class="stat-card">
            <span class="stat-label">총 런</span>
            <strong class="stat-val">{{ stats.total }}</strong>
          </div>
          <div class="stat-card">
            <span class="stat-label">에러</span>
            <strong class="stat-val err">{{ stats.errors }}</strong>
          </div>
          <div class="stat-card">
            <span class="stat-label">평균 레이턴시</span>
            <strong class="stat-val">{{ stats.avg_latency_ms }}ms</strong>
          </div>
          <div class="stat-card">
            <span class="stat-label">총 토큰</span>
            <strong class="stat-val">{{ stats.total_tokens.toLocaleString() }}</strong>
          </div>
        </div>

        <!-- Run name breakdown -->
        <div v-if="stats?.by_name && Object.keys(stats.by_name).length" class="breakdown">
          <span v-for="(cnt, name) in stats.by_name" :key="name" class="breakdown-chip">
            {{ name }} <em>{{ cnt }}</em>
          </span>
        </div>

        <!-- Run list -->
        <div class="table-wrap">
          <div v-if="loading" class="loading-msg">불러오는 중...</div>
          <div v-else-if="!filtered.length" class="empty-msg">런 데이터가 없습니다.</div>
          <table v-else class="run-table">
            <thead>
              <tr>
                <th>이름</th>
                <th>타입</th>
                <th>상태</th>
                <th>레이턴시</th>
                <th>토큰</th>
                <th>시작 시간</th>
                <th>상세</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in filtered"
                :key="r.id"
                :class="{ 'row-error': r.error, 'row-selected': selected?.id === r.id }"
                @click="selected = selected?.id === r.id ? null : r"
              >
                <td class="td-name">{{ r.name }}</td>
                <td><span class="type-pill">{{ r.run_type }}</span></td>
                <td><span :class="['status-dot', statusClass(r.status)]">{{ r.status ?? '-' }}</span></td>
                <td>{{ r.latency_ms != null ? r.latency_ms + 'ms' : '-' }}</td>
                <td>{{ r.total_tokens ?? '-' }}</td>
                <td class="td-time">{{ fmt(r.start_time) }}</td>
                <td><button class="detail-btn">{{ selected?.id === r.id ? '닫기' : '보기' }}</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Detail panel -->
        <Transition name="slide">
          <div v-if="selected" class="detail-panel">
            <div class="detail-header">
              <h3>{{ selected.name }}</h3>
              <button class="close-btn" @click="selected = null">✕</button>
            </div>
            <div class="detail-grid">
              <div class="detail-section">
                <h4>Input</h4>
                <pre class="code-block">{{ JSON.stringify(selected.inputs, null, 2) }}</pre>
              </div>
              <div class="detail-section">
                <h4>Output</h4>
                <pre class="code-block">{{ JSON.stringify(selected.outputs, null, 2) }}</pre>
              </div>
            </div>
            <div v-if="selected.error" class="error-block">
              <h4>Error</h4>
              <pre>{{ selected.error }}</pre>
            </div>
            <div class="detail-meta">
              <span>시작: {{ fmt(selected.start_time) }}</span>
              <span>종료: {{ fmt(selected.end_time) }}</span>
              <span>프롬프트 토큰: {{ selected.prompt_tokens ?? '-' }}</span>
              <span>컴플리션 토큰: {{ selected.completion_tokens ?? '-' }}</span>
            </div>
          </div>
        </Transition>
      </main>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
  display: flex; align-items: center; justify-content: center;
  padding: 20px; position: relative; overflow: hidden;
}
.bg-orb { position: absolute; border-radius: 50%; filter: blur(90px); opacity: 0.15; pointer-events: none; }
.orb1 { width: 500px; height: 500px; background: #6366f1; top: -150px; left: -100px; }
.orb2 { width: 350px; height: 350px; background: #8b5cf6; bottom: -100px; right: -80px; }

.layout {
  width: 100%; max-width: 1300px; height: min(900px, 95vh);
  display: flex; background: #fff; border-radius: 28px;
  box-shadow: 0 32px 80px rgba(0,0,0,0.35); overflow: hidden; position: relative; z-index: 1;
}

/* Sidebar */
.sidebar {
  width: 220px; flex-shrink: 0; background: #13111c;
  display: flex; flex-direction: column; justify-content: space-between;
  padding: 24px 16px;
}
.brand { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.brand-icon { font-size: 20px; }
.brand-name { font-size: 16px; font-weight: 700; color: #fff; }
.brand-sub { font-size: 11px; color: #6b7280; margin-bottom: 20px; }

.meta-box { background: #1e1b2e; border-radius: 10px; padding: 12px; margin-bottom: 16px; }
.meta-row { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 12px; }
.meta-label { color: #6b7280; }
.meta-val { color: #a78bfa; font-weight: 600; }

.filter-box { display: flex; flex-direction: column; gap: 4px; }
.filter-label { font-size: 11px; color: #6b7280; }
.filter-select, .filter-input {
  background: #1e1b2e; border: 1px solid #2d2a40; border-radius: 8px;
  color: #e5e7eb; padding: 6px 10px; font-size: 13px; width: 100%; box-sizing: border-box;
}

.sidebar-btns { display: flex; flex-direction: column; gap: 8px; }
.refresh-btn {
  background: #4f46e5; color: #fff; border: none; border-radius: 10px;
  padding: 10px; font-size: 13px; font-weight: 600; cursor: pointer;
}
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.back-btn {
  background: transparent; color: #6b7280; border: 1px solid #2d2a40;
  border-radius: 10px; padding: 8px; font-size: 12px; cursor: pointer;
}
.back-btn:hover { color: #fff; border-color: #4f46e5; }

/* Main */
.main {
  flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px;
}

.error-banner {
  background: #fee2e2; color: #dc2626; border-radius: 10px; padding: 12px 16px; font-size: 14px;
}

/* Stats */
.stats-row { display: flex; gap: 12px; flex-wrap: wrap; }
.stat-card {
  flex: 1; min-width: 120px; background: #f9fafb; border: 1px solid #e5e7eb;
  border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px;
}
.stat-label { font-size: 12px; color: #6b7280; }
.stat-val { font-size: 22px; font-weight: 700; color: #1e1b4b; }
.stat-val.err { color: #dc2626; }

/* Breakdown */
.breakdown { display: flex; flex-wrap: wrap; gap: 8px; }
.breakdown-chip {
  background: #ede9fe; color: #5b21b6; border-radius: 999px;
  padding: 4px 12px; font-size: 12px; font-weight: 500;
}
.breakdown-chip em { font-style: normal; font-weight: 700; margin-left: 4px; }

/* Table */
.table-wrap { flex: 1; overflow-x: auto; }
.loading-msg, .empty-msg { color: #9ca3af; padding: 24px; text-align: center; }
.run-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.run-table th {
  background: #f3f4f6; padding: 10px 12px; text-align: left;
  font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb; white-space: nowrap;
}
.run-table td { padding: 9px 12px; border-bottom: 1px solid #f3f4f6; vertical-align: middle; }
.run-table tbody tr { cursor: pointer; transition: background 0.1s; }
.run-table tbody tr:hover { background: #f5f3ff; }
.row-error td { background: #fff7f7; }
.row-selected td { background: #ede9fe !important; }
.td-name { font-weight: 600; color: #1e1b4b; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-time { font-size: 12px; color: #6b7280; white-space: nowrap; }
.type-pill { background: #e0e7ff; color: #3730a3; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 600; }
.status-dot { font-size: 12px; font-weight: 600; }
.status-ok { color: #10b981; }
.status-err { color: #ef4444; }
.status-pending { color: #f59e0b; }
.detail-btn {
  background: #4f46e5; color: #fff; border: none; border-radius: 6px;
  padding: 4px 10px; font-size: 12px; cursor: pointer;
}

/* Detail panel */
.detail-panel {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 14px; padding: 20px;
}
.detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.detail-header h3 { font-size: 15px; font-weight: 700; color: #1e1b4b; }
.close-btn { background: none; border: none; font-size: 16px; cursor: pointer; color: #6b7280; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px; }
.detail-section h4 { font-size: 12px; font-weight: 700; color: #6b7280; margin-bottom: 6px; text-transform: uppercase; }
.code-block {
  background: #1e1b2e; color: #a78bfa; border-radius: 8px;
  padding: 12px; font-size: 11px; overflow-x: auto; max-height: 200px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all;
}
.error-block { background: #fee2e2; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.error-block h4 { font-size: 12px; color: #dc2626; margin-bottom: 6px; }
.error-block pre { font-size: 12px; color: #7f1d1d; white-space: pre-wrap; }
.detail-meta { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: #6b7280; }

.slide-enter-active, .slide-leave-active { transition: all 0.2s; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(10px); }
</style>
