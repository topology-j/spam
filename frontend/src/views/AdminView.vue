<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = 'http://localhost:8000'

type Tab = 'reports' | 'keywords' | 'users' | 'chats' | 'reviews' | 'ai_eval' | 'profile'
const activeTab = ref<Tab>('reports')

// ── 스팸 신고 ─────────────────────────────────────────
interface Report {
  id: number; user_id: number; requester: string
  email_content: string; status: string
  counselor_note: string; created_at: string
}

const reports = ref<Report[]>([])
const selected = ref<Report | null>(null)
const note = ref('')
const keywords = ref('')
const submitting = ref(false)
const filterStatus = ref('all')

const filtered = computed(() =>
  filterStatus.value === 'all' ? reports.value : reports.value.filter(r => r.status === filterStatus.value)
)
const counts = computed(() => ({
  all: reports.value.length,
  pending: reports.value.filter(r => r.status === 'pending').length,
  processing: reports.value.filter(r => r.status === 'processing').length,
  done: reports.value.filter(r => r.status === 'done').length,
}))
const statusLabel: Record<string, string> = { pending: '대기중', processing: '처리중', done: '완료' }

async function loadReports() {
  const res = await fetch(`${API}/spam-reports`, { headers: auth.authHeader() })
  if (res.ok) reports.value = await res.json()
}
function selectReport(r: Report) { selected.value = r; note.value = r.counselor_note ?? ''; keywords.value = '' }
async function updateStatus(status: string) {
  if (!selected.value || submitting.value) return
  submitting.value = true
  const kwList = status === 'done' ? keywords.value.split('\n').map(k => k.trim()).filter(Boolean) : []
  await fetch(`${API}/spam-reports/${selected.value.id}`, {
    method: 'PATCH', headers: auth.authHeader(),
    body: JSON.stringify({ status, counselor_note: note.value, keywords: kwList }),
  })
  await loadReports()
  const updated = reports.value.find(r => r.id === selected.value!.id)
  if (updated) selected.value = updated
  if (kwList.length) await loadKeywords()
  submitting.value = false
}

// ── 스팸 키워드 ──────────────────────────────────────
interface Keyword { id: number; keyword: string; created_at: string }
const kwList = ref<Keyword[]>([])
const kwSearch = ref('')
const deletingId = ref<number | null>(null)

const filteredKw = computed(() =>
  kwSearch.value.trim() ? kwList.value.filter(k => k.keyword.includes(kwSearch.value.trim())) : kwList.value
)

async function loadKeywords() {
  const res = await fetch(`${API}/spam-keywords`, { headers: auth.authHeader() })
  if (res.ok) kwList.value = await res.json()
}
async function deleteKeyword(id: number) {
  if (deletingId.value !== null) return
  deletingId.value = id
  await fetch(`${API}/spam-keywords/${id}`, { method: 'DELETE', headers: auth.authHeader() })
  await loadKeywords()
  deletingId.value = null
}

// ── 시스템 설정 ───────────────────────────────────────
const reportEnabled = ref(true)

async function loadSettings() {
  const res = await fetch(`${API}/settings`, { headers: auth.authHeader() })
  if (res.ok) {
    const data = await res.json()
    reportEnabled.value = data.report_enabled !== 'false'
  }
}

async function toggleReport() {
  const newVal = !reportEnabled.value
  const res = await fetch(`${API}/settings/report_enabled`, {
    method: 'PATCH', headers: auth.authHeader(),
    body: JSON.stringify({ value: newVal ? 'true' : 'false' }),
  })
  if (res.ok) reportEnabled.value = newVal
}

// ── 사용자 목록 ──────────────────────────────────────
interface User { id: number; username: string; nickname: string; name: string; phone: string; email: string; address: string; postal_code: string; role: string; created_at: string }
const users = ref<User[]>([])
const roleLabel: Record<string, string> = { user: '사용자', counselor: '상담원', admin: '관리자', developer: '개발자' }

async function loadUsers() {
  const res = await fetch(`${API}/admin/users`, { headers: auth.authHeader() })
  if (res.ok) users.value = await res.json()
}

const roleChanging = ref<number | null>(null)
const pendingRoles = ref<Record<number, string>>({})

function onRoleSelect(userId: number, currentRole: string, newRole: string) {
  if (newRole === currentRole) {
    delete pendingRoles.value[userId]
  } else {
    pendingRoles.value[userId] = newRole
  }
}

async function confirmRoleChange(userId: number) {
  const newRole = pendingRoles.value[userId]
  if (!newRole) return
  roleChanging.value = userId
  try {
    const res = await fetch(`${API}/admin/users/${userId}/role`, {
      method: 'PATCH',
      headers: auth.authHeader(),
      body: JSON.stringify({ role: newRole }),
    })
    if (res.ok) {
      delete pendingRoles.value[userId]
      await loadUsers()
    }
  } finally {
    roleChanging.value = null
  }
}

const userRoleFilter = ref<string>('all')

const roleOptions = computed(() => {
  if (auth.role === 'developer') {
    return [
      { value: 'user', label: '사용자' },
      { value: 'counselor', label: '상담원' },
      { value: 'admin', label: '관리자' },
      { value: 'developer', label: '개발자' },
    ]
  }
  return [
    { value: 'user', label: '사용자' },
    { value: 'counselor', label: '상담원' },
    { value: 'admin', label: '관리자' },
  ]
})

const userFilterTabs = computed(() => {
  const base = [
    { value: 'all', label: '전체', count: users.value.length },
    { value: 'user', label: '사용자', count: users.value.filter(u => u.role === 'user').length },
    { value: 'counselor', label: '상담원', count: users.value.filter(u => u.role === 'counselor').length },
    { value: 'admin', label: '관리자', count: users.value.filter(u => u.role === 'admin').length },
  ]
  if (auth.role === 'developer') {
    base.push({ value: 'developer', label: '개발자', count: users.value.filter(u => u.role === 'developer').length })
  }
  return base
})

const filteredUsers = computed(() =>
  userRoleFilter.value === 'all' ? users.value : users.value.filter(u => u.role === userRoleFilter.value)
)

// ── 채팅 로그 ────────────────────────────────────────
interface ChatLog { id: number; username: string; role: string; message: string; is_spam: number | null; created_at: string }
const chatLogs = ref<ChatLog[]>([])
const chatFilter = ref<'all' | 'spam' | 'ham'>('all')

const filteredChats = computed(() => {
  if (chatFilter.value === 'spam') return chatLogs.value.filter(c => c.is_spam === 1)
  if (chatFilter.value === 'ham') return chatLogs.value.filter(c => c.is_spam === 0)
  return chatLogs.value
})

async function loadChats() {
  const res = await fetch(`${API}/chat/all`, { headers: auth.authHeader() })
  if (res.ok) chatLogs.value = await res.json()
}

// ── 상담사 평가 ───────────────────────────────────────
interface Review {
  id: number; stars: number; comment: string; created_at: string
  reviewer: string; counselor_name: string; email_content: string
  accuracy_stars: number | null; processing_stars: number | null
  clarity_stars: number | null; speed_stars: number | null
}

const reviews = ref<Review[]>([])
const reviewFilter = ref('all')

const counselorList = computed(() => [...new Set(reviews.value.map(r => r.counselor_name))])

const filteredReviews = computed(() =>
  reviewFilter.value === 'all' ? reviews.value : reviews.value.filter(r => r.counselor_name === reviewFilter.value)
)

const counselorStats = computed(() => {
  type CS = { name: string; avg: number; count: number; stars: number[]; acc: number[]; proc: number[]; clar: number[]; spd: number[] }
  const map: Record<string, CS> = {}
  reviews.value.forEach(r => {
    if (!map[r.counselor_name]) map[r.counselor_name] = { name: r.counselor_name, avg: 0, count: 0, stars: [], acc: [], proc: [], clar: [], spd: [] }
    const m = map[r.counselor_name]
    m.stars.push(r.stars); m.count++
    if (r.accuracy_stars != null) m.acc.push(r.accuracy_stars)
    if (r.processing_stars != null) m.proc.push(r.processing_stars)
    if (r.clarity_stars != null) m.clar.push(r.clarity_stars)
    if (r.speed_stars != null) m.spd.push(r.speed_stars)
  })
  const avg = (arr: number[]) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0
  return Object.values(map).map(s => ({
    ...s, avg: avg(s.stars),
    avgAcc: avg(s.acc), avgProc: avg(s.proc), avgClar: avg(s.clar), avgSpd: avg(s.spd),
  })).sort((a, b) => b.avg - a.avg)
})

const overallAvg = computed(() => {
  if (!reviews.value.length) return 0
  return reviews.value.reduce((s, r) => s + r.stars, 0) / reviews.value.length
})

async function loadReviews() {
  const res = await fetch(`${API}/counselor-reviews`, { headers: auth.authHeader() })
  if (res.ok) reviews.value = await res.json()
}

// ── 내 정보 ───────────────────────────────────────────
interface Profile { username: string; nickname: string; name: string; phone: string; email: string; address: string; postal_code: string; role: string; created_at: string }
const profile = ref<Profile | null>(null)
const profileEdit = ref(false)
const profileForm = ref({ nickname: '', name: '', phone: '', email: '', address: '', detail_address: '', postal_code: '' })
const profilePwForm = ref({ current_password: '', new_password: '', confirm_password: '' })
const profileSaving = ref(false)
const profileMsg = ref('')
const profileErr = ref('')

async function loadProfile() {
  const res = await fetch(`${API}/users/me`, { headers: auth.authHeader() })
  if (res.ok) {
    profile.value = await res.json()
    const p = profile.value!
    profileForm.value = { nickname: p.nickname ?? '', name: p.name ?? '', phone: p.phone ?? '', email: p.email ?? '', address: p.address ?? '', detail_address: p.detail_address ?? '', postal_code: p.postal_code ?? '' }
  }
}

async function saveProfile() {
  profileMsg.value = ''; profileErr.value = ''
  const pw = profilePwForm.value
  if (pw.new_password && pw.new_password !== pw.confirm_password) { profileErr.value = '새 비밀번호가 일치하지 않습니다.'; return }
  if (pw.new_password && !pw.current_password) { profileErr.value = '현재 비밀번호를 입력해주세요.'; return }
  profileSaving.value = true
  try {
    const res = await fetch(`${API}/users/me`, { method: 'PATCH', headers: auth.authHeader(), body: JSON.stringify({ ...profileForm.value, current_password: pw.current_password, new_password: pw.new_password }) })
    if (res.ok) { profileMsg.value = '수정되었습니다!'; profilePwForm.value = { current_password: '', new_password: '', confirm_password: '' }; profileEdit.value = false; await loadProfile() }
    else { const d = await res.json(); profileErr.value = d.detail || '오류가 발생했습니다.' }
  } finally { profileSaving.value = false }
}

// ── AI 성능 평가 ─────────────────────────────────────
interface EvalResult {
  text: string; label: string; predicted: string; correct: boolean
}
interface EvalReport {
  total: number; accuracy: number; precision: number; recall: number; f1: number
  tp: number; tn: number; fp: number; fn: number
  results: EvalResult[]
  source?: string; note?: string
}

const evalRunning = ref(false)
const evalReport = ref<EvalReport | null>(null)
const evalError = ref('')
const evalResultFilter = ref<'all' | 'wrong'>('all')
const evalHistory = ref<Array<{ date: string; report: EvalReport }>>([])

const evalResultsFiltered = computed(() => {
  if (!evalReport.value) return []
  return evalResultFilter.value === 'wrong'
    ? evalReport.value.results.filter(r => !r.correct)
    : evalReport.value.results
})

function applyReport(report: EvalReport) {
  evalReport.value = report
  evalResultFilter.value = 'all'
  evalHistory.value.unshift({ date: new Date().toLocaleString('ko-KR'), report })
  if (evalHistory.value.length > 10) evalHistory.value.pop()
}

const evalRunningType = ref<string>('')

async function runEvalBy(type: 'test' | 'val' | 'chat') {
  evalError.value = ''
  evalRunning.value = true
  evalRunningType.value = type
  try {
    const url = type === 'chat'
      ? `${API}/ai/evaluate/auto`
      : `${API}/ai/evaluate/testset?split=${type}`
    const res = await fetch(url, { headers: auth.authHeader() })
    if (!res.ok) { const d = await res.json(); evalError.value = d.detail || '오류'; return }
    applyReport(await res.json())
  } catch { evalError.value = '서버 연결 실패' }
  finally { evalRunning.value = false; evalRunningType.value = '' }
}

function pct(v: number) { return (v * 100).toFixed(1) + '%' }

// ── 탭 전환 ──────────────────────────────────────────
async function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'reports' && !reports.value.length) await loadReports()
  if (tab === 'keywords') await loadKeywords()
  if (tab === 'users') await loadUsers()
  if (tab === 'chats') await loadChats()
  if (tab === 'reviews') await loadReviews()
  if (tab === 'profile') await loadProfile()
}

function logout() { auth.logout(); router.push('/login') }

onMounted(() => { loadReports(); loadProfile(); loadSettings() })
</script>

<template>
  <div class="page">
    <div class="bg-orb orb1" />
    <div class="bg-orb orb2" />

    <div class="layout">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div class="sidebar-top">
          <div class="brand">
            <div class="brand-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                <polyline points="22,6 12,13 2,6"/>
              </svg>
            </div>
            <span class="brand-name">SpamGuard</span>
          </div>

          <div class="user-card">
            <div class="avatar">{{ auth.username[0]?.toUpperCase() }}</div>
            <div class="user-info">
              <span class="user-name">{{ auth.username }}</span>
              <span :class="['role-pill', auth.role === 'developer' ? 'developer' : 'admin']">{{ auth.role === 'developer' ? '개발자' : '관리자' }}</span>
            </div>
          </div>

          <nav class="nav">
            <button :class="['nav-item', { active: activeTab === 'reports' }]" @click="switchTab('reports')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </span>
              스팸 신고 처리
              <span class="nav-cnt">{{ counts.all }}</span>
            </button>
            <button :class="['nav-item', { active: activeTab === 'keywords' }]" @click="switchTab('keywords')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
              </span>
              키워드 관리
              <span class="nav-cnt">{{ kwList.length }}</span>
            </button>
            <button :class="['nav-item', { active: activeTab === 'users' }]" @click="switchTab('users')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                  <circle cx="9" cy="7" r="4"/>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                </svg>
              </span>
              사용자 관리
              <span class="nav-cnt">{{ users.length || '' }}</span>
            </button>
            <button :class="['nav-item', { active: activeTab === 'chats' }]" @click="switchTab('chats')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </span>
              채팅 로그
            </button>
            <button :class="['nav-item', { active: activeTab === 'reviews' }]" @click="switchTab('reviews')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
              </span>
              상담사 평가
              <span v-if="reviews.length" class="nav-cnt">{{ reviews.length }}</span>
            </button>
            <button :class="['nav-item', { active: activeTab === 'ai_eval' }]" @click="switchTab('ai_eval')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
              </span>
              AI 성능 평가
            </button>
            <button :class="['nav-item', { active: activeTab === 'profile' }]" @click="switchTab('profile')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
              </span>
              내 정보
            </button>
          </nav>
        </div>

        <div class="bottom-btns">
          <button class="home-btn" @click="switchTab('reports')">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            홈
          </button>
          <button class="logout-btn" @click="logout">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            로그아웃
          </button>
        </div>
      </aside>

      <!-- ── 신고 처리 탭 ── -->
      <template v-if="activeTab === 'reports'">
        <div class="list-panel">
          <div class="list-header">
            <div class="list-header-top">
              <h2 class="list-title">스팸 처리 요청</h2>
              <button class="refresh-btn" @click="loadReports">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="23 4 23 10 17 10"/>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
              </button>
            </div>
            <div class="filter-pills">
              <button v-for="[k,l] in [['all','전체'],['pending','대기'],['processing','처리중'],['done','완료']]"
                :key="k" :class="['pill', { active: filterStatus === k }]" @click="filterStatus = k">
                {{ l }} <span class="pill-cnt">{{ counts[k as keyof typeof counts] }}</span>
              </button>
            </div>
          </div>

          <div v-if="!filtered.length" class="empty-state-sm">요청이 없습니다.</div>
          <div class="report-list">
            <div v-for="r in filtered" :key="r.id"
              :class="['report-card', { selected: selected?.id === r.id }]"
              @click="selectReport(r)">
              <div class="rc-top">
                <span :class="['status-pill', `st-${r.status}`]">{{ statusLabel[r.status] }}</span>
                <span class="rc-date">{{ new Date(r.created_at).toLocaleDateString('ko-KR') }}</span>
              </div>
              <p class="rc-user">{{ r.requester }}</p>
              <p class="rc-preview">{{ r.email_content.slice(0,55) }}{{ r.email_content.length > 55 ? '...' : '' }}</p>
            </div>
          </div>
        </div>

        <div class="detail-panel">
          <div v-if="!selected" class="detail-empty">
            <div class="detail-empty-icon">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <p>요청을 선택해주세요</p>
          </div>
          <div v-else class="detail-content">
            <div class="detail-header">
              <div>
                <h3 class="detail-title">요청 #{{ selected.id }}</h3>
                <p class="detail-user">{{ selected.requester }}</p>
              </div>
              <span :class="['status-pill', `st-${selected.status}`]">{{ statusLabel[selected.status] }}</span>
            </div>
            <div class="email-box">
              <p class="box-label">메일 내용</p>
              <p class="email-content">{{ selected.email_content }}</p>
            </div>
            <div class="note-section">
              <label class="note-label">처리 메모</label>
              <textarea v-model="note" class="note-input" placeholder="처리 내용을 메모하세요..." rows="3" />
            </div>
            <div class="note-section" style="margin-top:14px">
              <label class="note-label">스팸 키워드 등록 <span class="note-hint">(한 줄에 하나씩 · 처리 완료 시 적용)</span></label>
              <textarea v-model="keywords" class="note-input" placeholder="예시:&#10;특별혜택&#10;지금바로클릭" rows="3" />
            </div>
            <div class="action-btns">
              <button class="action-btn btn-processing" :disabled="submitting || selected.status === 'processing'" @click="updateStatus('processing')">처리중으로 변경</button>
              <button class="action-btn btn-done" :disabled="submitting || selected.status === 'done'" @click="updateStatus('done')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                처리 완료
              </button>
            </div>
          </div>
        </div>
      </template>

      <!-- ── 키워드 관리 탭 ── -->
      <div v-else-if="activeTab === 'keywords'" class="full-panel">
        <div class="panel-header">
          <h2 class="panel-title">스팸 키워드 관리</h2>
          <!-- 상담 요청 활성화 토글 -->
          <div class="setting-toggle-card" :class="{ off: !reportEnabled }">
            <div class="setting-toggle-info">
              <span class="setting-toggle-title">상담 요청</span>
              <span class="setting-toggle-desc">{{ reportEnabled ? '사용자가 상담을 요청할 수 있습니다' : '상담 요청이 비활성화되어 있습니다' }}</span>
            </div>
            <button :class="['toggle-btn', { active: reportEnabled }]" @click="toggleReport">
              <span class="toggle-knob"/>
            </button>
          </div>
          <div class="header-right">
            <div class="search-wrap">
              <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input v-model="kwSearch" class="search-input" placeholder="키워드 검색..." />
            </div>
            <button class="refresh-btn" @click="loadKeywords">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="23 4 23 10 17 10"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="kw-grid">
          <div v-if="!filteredKw.length" class="empty-state-sm">등록된 키워드가 없습니다.</div>
          <div v-for="kw in filteredKw" :key="kw.id" class="kw-card">
            <div class="kw-word">{{ kw.keyword }}</div>
            <div class="kw-date">{{ new Date(kw.created_at).toLocaleDateString('ko-KR') }}</div>
            <button class="kw-delete" :disabled="deletingId === kw.id" @click="deleteKeyword(kw.id)">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6"/><path d="M14 11v6"/>
                <path d="M9 6V4h6v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- ── 사용자 관리 탭 ── -->
      <div v-else-if="activeTab === 'users'" class="full-panel">
        <div class="panel-header">
          <h2 class="panel-title">사용자 관리</h2>
          <button class="refresh-btn" @click="loadUsers">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
        </div>
        <div class="user-filter-bar">
          <button
            v-for="tab in userFilterTabs" :key="tab.value"
            :class="['user-filter-btn', `filter-${tab.value}`, { active: userRoleFilter === tab.value }]"
            @click="userRoleFilter = tab.value"
          >
            {{ tab.label }}
            <span class="filter-count">{{ tab.count }}</span>
          </button>
        </div>
        <div class="table-wrap">
          <table class="user-table">
            <thead>
              <tr><th>ID</th><th>아이디</th><th>닉네임</th><th>이름</th><th>휴대폰</th><th>이메일</th><th>주소</th><th>역할 지정</th><th>가입일</th></tr>
            </thead>
            <tbody>
              <tr v-if="!filteredUsers.length">
                <td colspan="9" style="text-align:center;padding:32px;color:#9ca3af;">해당 역할의 사용자가 없습니다.</td>
              </tr>
              <tr v-for="u in filteredUsers" :key="u.id">
                <td class="td-id">#{{ u.id }}</td>
                <td class="td-name">{{ u.username }}</td>
                <td>{{ u.nickname || '-' }}</td>
                <td>{{ u.name || '-' }}</td>
                <td>{{ u.phone || '-' }}</td>
                <td>{{ u.email || '-' }}</td>
                <td class="td-addr">{{ u.postal_code ? `(${u.postal_code}) ` : '' }}{{ u.address || '-' }}</td>
                <td>
                  <div class="role-cell">
                    <select
                      :class="['role-select', `role-${pendingRoles[u.id] ?? u.role}`]"
                      :value="pendingRoles[u.id] ?? u.role"
                      :disabled="roleChanging === u.id"
                      @change="onRoleSelect(u.id, u.role, ($event.target as HTMLSelectElement).value)"
                    >
                      <option v-for="opt in roleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                    <button
                      v-if="pendingRoles[u.id]"
                      class="btn-role-confirm"
                      :disabled="roleChanging === u.id"
                      @click="confirmRoleChange(u.id)"
                    >
                      <span v-if="roleChanging === u.id" class="spinner-xs"/>
                      <span v-else>변경</span>
                    </button>
                  </div>
                </td>
                <td class="td-date">{{ new Date(u.created_at).toLocaleDateString('ko-KR') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── 채팅 로그 탭 ── -->
      <div v-else-if="activeTab === 'chats'" class="full-panel">
        <div class="panel-header">
          <h2 class="panel-title">채팅 로그</h2>
          <div class="header-right">
            <div class="filter-pills">
              <button v-for="[k,l] in [['all','전체'],['spam','스팸만'],['ham','정상만']]"
                :key="k" :class="['pill', { active: chatFilter === k }]" @click="chatFilter = k as any">
                {{ l }}
              </button>
            </div>
            <button class="refresh-btn" @click="loadChats">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="23 4 23 10 17 10"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="chat-log-list">
          <div v-if="!filteredChats.length" class="empty-state-sm">채팅 기록이 없습니다.</div>
          <div v-for="log in filteredChats" :key="log.id" :class="['chat-log-item', log.role]">
            <div class="log-meta">
              <span class="log-user">{{ log.username }}</span>
              <span :class="['log-role-badge', log.role]">{{ log.role === 'user' ? '사용자' : 'AI' }}</span>
              <span v-if="log.is_spam === 1" class="badge-spam">스팸</span>
              <span v-else-if="log.is_spam === 0" class="badge-ham">정상</span>
              <span class="log-date">{{ new Date(log.created_at).toLocaleString('ko-KR') }}</span>
            </div>
            <p class="log-msg">{{ log.message }}</p>
          </div>
        </div>
      </div>

      <!-- ── 상담사 평가 탭 ── -->
      <div v-else-if="activeTab === 'reviews'" class="full-panel">
        <div class="panel-header">
          <h2 class="panel-title">상담사 평가 현황</h2>
          <button class="refresh-btn" @click="loadReviews">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
        </div>

        <div class="reviews-body">
          <!-- 총계 카드 -->
          <div v-if="reviews.length" class="overview-row">
            <div class="overview-card main">
              <div class="ov-label">전체 평균</div>
              <div class="ov-big">{{ overallAvg.toFixed(1) }}</div>
              <div class="ov-stars">
                <span v-for="i in 5" :key="i" class="ov-star" :class="{ filled: i <= Math.round(overallAvg) }">★</span>
              </div>
              <div class="ov-sub">{{ reviews.length }}개 평가</div>
            </div>
            <div v-for="cs in counselorStats" :key="cs.name" class="overview-card counselor">
              <div class="ov-label">{{ cs.name }}</div>
              <div class="ov-big">{{ cs.avg.toFixed(1) }}</div>
              <div class="ov-stars">
                <span v-for="i in 5" :key="i" class="ov-star" :class="{ filled: i <= Math.round(cs.avg) }">★</span>
              </div>
              <div class="ov-sub">{{ cs.count }}개 평가</div>
              <div class="ov-cats">
                <div class="ov-cat-row"><span class="ov-cat-label">안내 정확도</span><span class="ov-cat-bar-wrap"><span class="ov-cat-bar" :style="{width: (cs.avgAcc/5*100)+'%'}"/></span><span class="ov-cat-val">{{ cs.avgAcc.toFixed(1) }}</span></div>
                <div class="ov-cat-row"><span class="ov-cat-label">처리 정확성</span><span class="ov-cat-bar-wrap"><span class="ov-cat-bar" :style="{width: (cs.avgProc/5*100)+'%'}"/></span><span class="ov-cat-val">{{ cs.avgProc.toFixed(1) }}</span></div>
                <div class="ov-cat-row"><span class="ov-cat-label">설명 이해도</span><span class="ov-cat-bar-wrap"><span class="ov-cat-bar" :style="{width: (cs.avgClar/5*100)+'%'}"/></span><span class="ov-cat-val">{{ cs.avgClar.toFixed(1) }}</span></div>
                <div class="ov-cat-row"><span class="ov-cat-label">응답 속도</span><span class="ov-cat-bar-wrap"><span class="ov-cat-bar" :style="{width: (cs.avgSpd/5*100)+'%'}"/></span><span class="ov-cat-val">{{ cs.avgSpd.toFixed(1) }}</span></div>
              </div>
            </div>
          </div>

          <!-- 필터 -->
          <div v-if="reviews.length" class="review-filter-row">
            <div class="filter-pills">
              <button :class="['pill', { active: reviewFilter === 'all' }]" @click="reviewFilter = 'all'">전체</button>
              <button v-for="name in counselorList" :key="name" :class="['pill', { active: reviewFilter === name }]" @click="reviewFilter = name">{{ name }}</button>
            </div>
          </div>

          <div v-if="!reviews.length" class="empty-state-reviews">
            <div class="empty-star-icon">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
            </div>
            <p>아직 평가 데이터가 없습니다.</p>
          </div>

          <div class="review-list">
            <div v-for="rv in filteredReviews" :key="rv.id" class="review-item">
              <div class="review-top">
                <div class="review-left">
                  <span class="counselor-chip">{{ rv.counselor_name }}</span>
                  <span class="rv-overall">종합 {{ rv.stars.toFixed ? rv.stars : rv.stars }}점</span>
                </div>
                <span class="review-date">{{ new Date(rv.created_at).toLocaleDateString('ko-KR') }}</span>
              </div>
              <div class="rv-cat-rows">
                <div class="rv-cat-row">
                  <span class="rv-cat-label">안내 정확도</span>
                  <div class="review-stars">
                    <span v-for="i in 5" :key="i" class="r-star" :class="{ filled: i <= (rv.accuracy_stars ?? 0) }">★</span>
                  </div>
                  <span class="rv-cat-score">{{ rv.accuracy_stars ?? '-' }}</span>
                </div>
                <div class="rv-cat-row">
                  <span class="rv-cat-label">처리 정확성</span>
                  <div class="review-stars">
                    <span v-for="i in 5" :key="i" class="r-star" :class="{ filled: i <= (rv.processing_stars ?? 0) }">★</span>
                  </div>
                  <span class="rv-cat-score">{{ rv.processing_stars ?? '-' }}</span>
                </div>
                <div class="rv-cat-row">
                  <span class="rv-cat-label">설명 이해도</span>
                  <div class="review-stars">
                    <span v-for="i in 5" :key="i" class="r-star" :class="{ filled: i <= (rv.clarity_stars ?? 0) }">★</span>
                  </div>
                  <span class="rv-cat-score">{{ rv.clarity_stars ?? '-' }}</span>
                </div>
                <div class="rv-cat-row">
                  <span class="rv-cat-label">응답 속도</span>
                  <div class="review-stars">
                    <span v-for="i in 5" :key="i" class="r-star" :class="{ filled: i <= (rv.speed_stars ?? 0) }">★</span>
                  </div>
                  <span class="rv-cat-score">{{ rv.speed_stars ?? '-' }}</span>
                </div>
              </div>
              <p v-if="rv.comment" class="review-comment">{{ rv.comment }}</p>
              <p v-else class="review-no-comment">코멘트 없음</p>
              <div class="review-footer">
                <span class="reviewer-name">작성자: {{ rv.reviewer }}</span>
                <span class="email-preview" :title="rv.email_content">메일: {{ rv.email_content.slice(0,40) }}...</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <!-- ── AI 성능 평가 탭 ── -->
      <div v-else-if="activeTab === 'ai_eval'" class="full-panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">AI 스팸 감지 성능 평가</h2>
            <p class="panel-desc">테스트 데이터로 평가 → 결과 확인 → 개선 요청 사이클</p>
          </div>
        </div>

        <div class="eval-body">
          <!-- 평가 데이터셋 선택 -->
          <div class="eval-dataset-row">
            <div class="eval-dataset-card" @click="!evalRunning && runEvalBy('val')" :class="{running: evalRunningType==='val'}">
              <div class="eds-top">
                <span class="eds-badge val">검증셋</span>
                <span class="eds-pct">15%</span>
              </div>
              <div class="eds-title">Validation Data</div>
              <div class="eds-desc">개선 중 성능 확인용<br/>spam.csv에서 분할</div>
              <button class="btn-run-eval eds-btn" :disabled="evalRunning">
                <svg v-if="evalRunningType!=='val'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                <span v-else class="spinner-xs" style="border-color:rgba(255,255,255,0.4);border-top-color:#fff;width:10px;height:10px"/>
                {{ evalRunningType==='val' ? '평가 중...' : '평가 실행' }}
              </button>
            </div>

            <div class="eval-dataset-card" @click="!evalRunning && runEvalBy('test')" :class="{running: evalRunningType==='test'}">
              <div class="eds-top">
                <span class="eds-badge test">테스트셋</span>
                <span class="eds-pct">15%</span>
              </div>
              <div class="eds-title">Test Data</div>
              <div class="eds-desc">최종 성능 측정용<br/>spam.csv에서 분할</div>
              <button class="btn-run-eval eds-btn" :disabled="evalRunning">
                <svg v-if="evalRunningType!=='test'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                <span v-else class="spinner-xs" style="border-color:rgba(255,255,255,0.4);border-top-color:#fff;width:10px;height:10px"/>
                {{ evalRunningType==='test' ? '평가 중...' : '평가 실행' }}
              </button>
            </div>
          </div>

          <p v-if="evalError" class="eval-error">{{ evalError }}</p>
          <p v-if="evalReport?.note" class="eval-note">{{ evalReport.note }}</p>

          <!-- 결과 영역 -->
          <div v-if="evalReport" class="eval-result-area">
            <!-- 지표 카드 -->
            <div class="eval-metrics-row">
              <div class="eval-metric-card acc">
                <div class="em-label">정확도 (Accuracy)</div>
                <div class="em-val">{{ pct(evalReport.accuracy) }}</div>
                <div class="em-bar-wrap"><div class="em-bar" :style="{width: pct(evalReport.accuracy)}"/></div>
              </div>
              <div class="eval-metric-card prec">
                <div class="em-label">정밀도 (Precision)</div>
                <div class="em-val">{{ pct(evalReport.precision) }}</div>
                <div class="em-bar-wrap"><div class="em-bar" :style="{width: pct(evalReport.precision)}"/></div>
              </div>
              <div class="eval-metric-card rec">
                <div class="em-label">재현율 (Recall)</div>
                <div class="em-val">{{ pct(evalReport.recall) }}</div>
                <div class="em-bar-wrap"><div class="em-bar" :style="{width: pct(evalReport.recall)}"/></div>
              </div>
              <div class="eval-metric-card f1">
                <div class="em-label">F1 Score</div>
                <div class="em-val">{{ pct(evalReport.f1) }}</div>
                <div class="em-bar-wrap"><div class="em-bar" :style="{width: pct(evalReport.f1)}"/></div>
              </div>
            </div>

            <!-- 혼동 행렬 -->
            <div class="eval-section-row">
              <div class="eval-confusion">
                <div class="eval-section-title">혼동 행렬 (Confusion Matrix)</div>
                <div class="confusion-grid">
                  <div class="cm-head-blank"/>
                  <div class="cm-head">예측: 스팸</div>
                  <div class="cm-head">예측: 정상</div>
                  <div class="cm-side">실제: 스팸</div>
                  <div class="cm-cell tp">
                    <span class="cm-num">{{ evalReport.tp }}</span>
                    <span class="cm-tag">TP</span>
                  </div>
                  <div class="cm-cell fn">
                    <span class="cm-num">{{ evalReport.fn }}</span>
                    <span class="cm-tag">FN</span>
                  </div>
                  <div class="cm-side">실제: 정상</div>
                  <div class="cm-cell fp">
                    <span class="cm-num">{{ evalReport.fp }}</span>
                    <span class="cm-tag">FP</span>
                  </div>
                  <div class="cm-cell tn">
                    <span class="cm-num">{{ evalReport.tn }}</span>
                    <span class="cm-tag">TN</span>
                  </div>
                </div>
                <div class="cm-legend">
                  <span class="cm-leg tp">TP: 스팸을 스팸으로</span>
                  <span class="cm-leg tn">TN: 정상을 정상으로</span>
                  <span class="cm-leg fp">FP: 정상을 스팸으로 (오탐)</span>
                  <span class="cm-leg fn">FN: 스팸을 정상으로 (미탐)</span>
                </div>
              </div>

              <!-- 평가 히스토리 -->
              <div v-if="evalHistory.length > 1" class="eval-history">
                <div class="eval-section-title">평가 이력</div>
                <div class="history-list">
                  <div v-for="(h, idx) in evalHistory" :key="idx" class="history-item" :class="{current: idx===0}">
                    <span class="h-date">{{ h.date }}</span>
                    <span class="h-metrics">
                      정확도 {{ pct(h.report.accuracy) }} &nbsp;|&nbsp; F1 {{ pct(h.report.f1) }}
                    </span>
                    <span class="h-total">{{ h.report.total }}건</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 개별 결과 -->
            <div class="eval-detail">
              <div class="eval-detail-header">
                <span class="eval-section-title">개별 결과</span>
                <div class="filter-pills">
                  <button :class="['pill', {active: evalResultFilter==='all'}]" @click="evalResultFilter='all'">전체 {{ evalReport.total }}</button>
                  <button :class="['pill', {active: evalResultFilter==='wrong'}]" @click="evalResultFilter='wrong'">오분류만 {{ evalReport.fp + evalReport.fn }}</button>
                </div>
              </div>
              <div class="eval-result-list">
                <div v-for="(r, i) in evalResultsFiltered" :key="i" :class="['eval-result-row', r.correct ? 'correct' : 'wrong']">
                  <span :class="['result-icon', r.correct ? 'ok' : 'err']">{{ r.correct ? '✓' : '✗' }}</span>
                  <span class="result-text">{{ r.text }}</span>
                  <span class="result-label-badge" :class="r.label">{{ r.label === 'spam' ? '스팸' : '정상' }}</span>
                  <span class="result-arrow">→</span>
                  <span class="result-pred-badge" :class="[r.predicted, !r.correct ? 'wrong-pred' : '']">{{ r.predicted === 'spam' ? '스팸' : '정상' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="activeTab === 'profile'" class="full-panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">내 정보</h2>
            <p class="panel-desc">계정 정보를 확인하고 수정할 수 있습니다</p>
          </div>
          <button v-if="!profileEdit" class="btn-edit-toggle" @click="profileEdit = true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
            </svg>
            정보 수정
          </button>
        </div>
        <div v-if="profile" class="profile-wrapper">
          <div v-if="!profileEdit" class="profile-view">
            <div class="profile-section-title">기본 정보</div>
            <div class="profile-grid">
              <div class="pfield"><span class="pfield-label">아이디</span><span class="pfield-val">{{ profile.username }}</span></div>
              <div class="pfield"><span class="pfield-label">닉네임</span><span class="pfield-val">{{ profile.nickname }}</span></div>
              <div class="pfield"><span class="pfield-label">이름</span><span class="pfield-val">{{ profile.name }}</span></div>
              <div class="pfield"><span class="pfield-label">휴대폰</span><span class="pfield-val">{{ profile.phone }}</span></div>
              <div class="pfield"><span class="pfield-label">이메일</span><span class="pfield-val">{{ profile.email }}</span></div>
              <div class="pfield"><span class="pfield-label">우편번호</span><span class="pfield-val">{{ profile.postal_code }}</span></div>
              <div class="pfield pfield-full"><span class="pfield-label">주소</span><span class="pfield-val">{{ profile.address }}</span></div>
              <div class="pfield pfield-full"><span class="pfield-label">상세주소</span><span class="pfield-val">{{ profile.detail_address }}</span></div>
              <div class="pfield"><span class="pfield-label">역할</span><span class="pfield-val">{{ roleLabel[profile.role] ?? profile.role }}</span></div>
              <div class="pfield"><span class="pfield-label">가입일</span><span class="pfield-val">{{ new Date(profile.created_at).toLocaleDateString('ko-KR') }}</span></div>
            </div>
          </div>
          <div v-else class="profile-edit-form">
            <div class="profile-section-title">기본 정보 수정</div>
            <div class="profile-grid">
              <div class="pfield"><label class="pfield-label">아이디</label><input class="pfield-input" :value="profile.username" disabled style="background:#f5f5f5;color:#9ca3af;cursor:not-allowed;" /></div>
              <div class="pfield"><label class="pfield-label">닉네임</label><input class="pfield-input" v-model="profileForm.nickname" placeholder="닉네임 입력" /></div>
              <div class="pfield"><label class="pfield-label">이름</label><input class="pfield-input" v-model="profileForm.name" placeholder="이름 입력" /></div>
              <div class="pfield"><label class="pfield-label">휴대폰</label><input class="pfield-input" v-model="profileForm.phone" placeholder="010-0000-0000" /></div>
              <div class="pfield pfield-full"><label class="pfield-label">이메일</label><input class="pfield-input" v-model="profileForm.email" placeholder="example@email.com" /></div>
              <div class="pfield"><label class="pfield-label">우편번호</label><input class="pfield-input" v-model="profileForm.postal_code" placeholder="우편번호 5자리" /></div>
              <div class="pfield pfield-full"><label class="pfield-label">주소</label><input class="pfield-input" v-model="profileForm.address" placeholder="기본 주소 입력" /></div>
              <div class="pfield pfield-full"><label class="pfield-label">상세주소</label><input class="pfield-input" v-model="profileForm.detail_address" placeholder="상세 주소 입력 (동, 호수 등)" /></div>
            </div>
            <div class="profile-section-title" style="margin-top:28px">비밀번호 변경 <span style="font-weight:400;color:#b0b8c8;font-size:11px">(변경하지 않으려면 비워두세요)</span></div>
            <div class="profile-grid">
              <div class="pfield pfield-full"><label class="pfield-label">현재 비밀번호</label><input class="pfield-input" type="password" v-model="profilePwForm.current_password" placeholder="현재 비밀번호 입력" /></div>
              <div class="pfield"><label class="pfield-label">새 비밀번호</label><input class="pfield-input" type="password" v-model="profilePwForm.new_password" placeholder="새 비밀번호 (4자 이상)" /></div>
              <div class="pfield"><label class="pfield-label">새 비밀번호 확인</label><input class="pfield-input" type="password" v-model="profilePwForm.confirm_password" placeholder="새 비밀번호 재입력" /></div>
            </div>
            <p v-if="profileErr" style="color:#ef4444;font-size:13px;margin-top:12px;padding:10px 14px;background:rgba(239,68,68,0.06);border-radius:8px;border:1px solid rgba(239,68,68,0.2)">{{ profileErr }}</p>
            <p v-if="profileMsg" style="color:#059669;font-size:13px;margin-top:12px;padding:10px 14px;background:rgba(16,185,129,0.06);border-radius:8px;border:1px solid rgba(16,185,129,0.2)">{{ profileMsg }}</p>
            <div class="profile-actions">
              <button class="btn-cancel" @click="profileEdit = false; profileErr = ''; profileMsg = ''">취소</button>
              <button class="btn-save" :disabled="profileSaving" @click="saveProfile">{{ profileSaving ? '저장 중...' : '저장하기' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  background: linear-gradient(135deg, #0f0c29 0%, #1e1b4b 50%, #312e81 100%);
  display: flex; align-items: center; justify-content: center; padding: 20px;
  position: relative; overflow: hidden;
}

.bg-orb { position: absolute; border-radius: 50%; filter: blur(90px); opacity: 0.18; pointer-events: none; }
.orb1 { width: 500px; height: 500px; background: #ec4899; top: -150px; right: -100px; }
.orb2 { width: 350px; height: 350px; background: #8b5cf6; bottom: -100px; left: -80px; }

.layout {
  width: 100%; max-width: 1240px; height: min(880px, 94vh);
  display: flex; background: #fff; border-radius: 28px;
  box-shadow: 0 32px 80px rgba(0,0,0,0.35); overflow: hidden;
  position: relative; z-index: 1;
}

/* Sidebar */
.sidebar {
  width: 230px; flex-shrink: 0; background: #13111c;
  display: flex; flex-direction: column; justify-content: space-between; padding: 24px 16px;
}
.sidebar-top { display: flex; flex-direction: column; gap: 6px; }
.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px; margin-bottom: 16px; }
.brand-icon {
  width: 36px; height: 36px; border-radius: 12px;
  background: linear-gradient(135deg, #ec4899, #be185d);
  display: flex; align-items: center; justify-content: center;
  color: #fff; box-shadow: 0 4px 12px rgba(236,72,153,0.4);
}
.brand-name { font-size: 15px; font-weight: 800; color: #fff; letter-spacing: -0.3px; }

.user-card {
  display: flex; align-items: center; gap: 10px; padding: 12px 14px;
  background: rgba(255,255,255,0.06); border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.08); margin-bottom: 12px;
}
.avatar {
  width: 38px; height: 38px; border-radius: 50%;
  background: linear-gradient(135deg, #ec4899, #be185d);
  color: #fff; font-weight: 800; font-size: 15px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; box-shadow: 0 3px 10px rgba(236,72,153,0.35);
}
.user-info { display: flex; flex-direction: column; gap: 4px; }
.user-name { font-size: 13px; font-weight: 700; color: #fff; }
.role-pill { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 99px; width: fit-content; }
.role-pill.admin { background: rgba(190,24,93,0.3); color: #f9a8d4; border: 1px solid rgba(190,24,93,0.4); }
.role-pill.developer { background: rgba(5,150,105,0.3); color: #6ee7b7; border: 1px solid rgba(5,150,105,0.4); }

.nav { display: flex; flex-direction: column; gap: 3px; }
.nav-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 12px;
  border-radius: 12px; border: none; background: transparent;
  color: rgba(255,255,255,0.5); font-size: 13.5px; font-weight: 500;
  cursor: pointer; text-align: left; transition: all 0.2s; position: relative;
}
.nav-item:hover { background: rgba(255,255,255,0.07); color: rgba(255,255,255,0.85); }
.nav-item.active { background: linear-gradient(135deg, rgba(236,72,153,0.2), rgba(139,92,246,0.2)); color: #fff; }
.nav-icon { display: flex; align-items: center; color: rgba(255,255,255,0.35); transition: color 0.2s; }
.nav-item.active .nav-icon { color: #f9a8d4; }
.nav-cnt { margin-left: auto; font-size: 10px; font-weight: 700; background: rgba(255,255,255,0.1); padding: 1px 7px; border-radius: 99px; color: rgba(255,255,255,0.6); }

.bottom-btns { display: flex; flex-direction: column; gap: 6px; padding: 0 12px 8px; }
.home-btn { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.15); background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.75); font-size: 13px; cursor: pointer; transition: all 0.2s; width: 100%; }
.home-btn:hover { background: rgba(255,255,255,0.1); color: #fff; border-color: rgba(255,255,255,0.3); }
.logout-btn { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(239,68,68,0.25); background: rgba(239,68,68,0.08); color: #f87171; font-size: 13px; cursor: pointer; transition: all 0.2s; width: 100%; }
.logout-btn:hover { background: rgba(239,68,68,0.18); color: #fca5a5; border-color: rgba(239,68,68,0.45); }

/* List panel */
.list-panel { width: 300px; flex-shrink: 0; border-right: 1px solid #f1f0f9; display: flex; flex-direction: column; }
.list-header { padding: 20px 16px 14px; border-bottom: 1px solid #f1f0f9; flex-shrink: 0; }
.list-header-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.list-title { font-size: 15px; font-weight: 800; color: #1e1b4b; }

.refresh-btn { width: 30px; height: 30px; border-radius: 8px; border: 1.5px solid #e8e6f0; background: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #9ca3af; transition: all 0.15s; }
.refresh-btn:hover { border-color: #6366f1; color: #6366f1; }

.filter-pills { display: flex; flex-wrap: wrap; gap: 4px; }
.pill { padding: 5px 10px; border-radius: 99px; border: 1.5px solid #e8e6f0; background: #fff; font-size: 11.5px; font-weight: 600; color: #6b7280; cursor: pointer; transition: all 0.15s; }
.pill:hover { border-color: #6366f1; color: #6366f1; }
.pill.active { border-color: #6366f1; background: #ede9fe; color: #6366f1; }
.pill-cnt { font-size: 10.5px; margin-left: 2px; opacity: 0.7; }

.empty-state-sm { padding: 40px 20px; text-align: center; font-size: 13.5px; color: #9ca3af; }

.report-list { flex: 1; overflow-y: auto; padding: 10px; }
.report-list::-webkit-scrollbar { width: 4px; }
.report-list::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.report-card { padding: 13px; border-radius: 14px; border: 1.5px solid #f1f0f9; margin-bottom: 8px; cursor: pointer; transition: all 0.2s; }
.report-card:hover { border-color: #c7d2fe; background: #f5f4ff; }
.report-card.selected { border-color: #6366f1; background: #ede9fe; }
.rc-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.rc-date { font-size: 11px; color: #9ca3af; }
.rc-user { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.rc-preview { font-size: 13px; color: #374151; line-height: 1.4; }

/* Detail panel */
.detail-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.detail-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #9ca3af; font-size: 14px; gap: 12px; }
.detail-empty-icon { width: 72px; height: 72px; border-radius: 20px; background: #f5f4ff; display: flex; align-items: center; justify-content: center; }
.detail-content { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
.detail-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 22px 26px 18px; border-bottom: 1px solid #f1f0f9; flex-shrink: 0; }
.detail-title { font-size: 18px; font-weight: 800; color: #1e1b4b; }
.detail-user { font-size: 13px; color: #6b7280; margin-top: 4px; }
.email-box { margin: 20px 26px; padding: 16px 18px; background: #faf9ff; border-radius: 16px; border: 1.5px solid #f1f0f9; flex-shrink: 0; }
.box-label { font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }
.email-content { font-size: 14px; color: #374151; line-height: 1.65; white-space: pre-wrap; }
.note-section { margin: 0 26px; flex-shrink: 0; }
.note-label { display: block; font-size: 13px; font-weight: 700; color: #374151; margin-bottom: 7px; }
.note-hint { font-size: 12px; font-weight: 400; color: #9ca3af; }
.note-input { width: 100%; padding: 12px 14px; border: 1.5px solid #e8e6f0; border-radius: 14px; font-size: 14px; font-family: inherit; resize: vertical; outline: none; background: #faf9ff; transition: border-color 0.2s; box-sizing: border-box; }
.note-input:focus { border-color: #6366f1; background: #fff; }
.action-btns { display: flex; gap: 10px; padding: 18px 26px; margin-top: auto; border-top: 1px solid #f1f0f9; flex-shrink: 0; }
.action-btn { flex: 1; padding: 12px; border: none; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px; }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-processing { background: #dbeafe; color: #1d4ed8; }
.btn-processing:hover:not(:disabled) { background: #bfdbfe; }
.btn-done { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; box-shadow: 0 3px 10px rgba(99,102,241,0.3); }
.btn-done:hover:not(:disabled) { opacity: 0.9; }

.status-pill { font-size: 11px; font-weight: 700; padding: 4px 11px; border-radius: 99px; }
.st-pending { background: #fef3c7; color: #92400e; }
.st-processing { background: #dbeafe; color: #1d4ed8; }
.st-done { background: #d1fae5; color: #065f46; }

/* Full panels */
.full-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.panel-header { display: flex; align-items: center; justify-content: space-between; padding: 22px 26px 18px; border-bottom: 1px solid #f1f0f9; flex-shrink: 0; flex-wrap: wrap; gap: 12px; }
.panel-title { font-size: 16px; font-weight: 800; color: #1e1b4b; }
.header-right { display: flex; align-items: center; gap: 10px; }

/* 상담 요청 토글 */
.setting-toggle-card {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 16px; border-radius: 14px;
  background: #ecfdf5; border: 1.5px solid #a7f3d0;
  transition: all 0.2s;
}
.setting-toggle-card.off { background: #fef2f2; border-color: #fecaca; }
.setting-toggle-info { display: flex; flex-direction: column; gap: 2px; }
.setting-toggle-title { font-size: 13px; font-weight: 700; color: #1e1b4b; }
.setting-toggle-desc { font-size: 11.5px; color: #6b7280; }
.toggle-btn {
  width: 44px; height: 24px; border-radius: 99px; border: none; cursor: pointer;
  background: #d1d5db; position: relative; transition: background 0.2s; flex-shrink: 0;
}
.toggle-btn.active { background: #10b981; }
.toggle-knob {
  position: absolute; top: 3px; left: 3px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #fff; transition: transform 0.2s;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  display: block;
}
.toggle-btn.active .toggle-knob { transform: translateX(20px); }

.search-wrap { position: relative; display: flex; align-items: center; }
.search-icon { position: absolute; left: 12px; color: #9ca3af; pointer-events: none; }
.search-input { padding: 8px 14px 8px 34px; border: 1.5px solid #e8e6f0; border-radius: 10px; font-size: 13px; outline: none; background: #faf9ff; transition: border-color 0.2s; }
.search-input:focus { border-color: #6366f1; background: #fff; }

/* Keywords */
.kw-grid { flex: 1; overflow-y: auto; padding: 16px 22px; display: flex; flex-wrap: wrap; align-content: flex-start; gap: 10px; }
.kw-grid::-webkit-scrollbar { width: 4px; }
.kw-grid::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.kw-card { display: flex; flex-direction: column; gap: 5px; padding: 13px 14px; border: 1.5px solid #f1f0f9; border-radius: 14px; background: #faf9ff; width: calc(25% - 8px); min-width: 120px; position: relative; transition: all 0.15s; }
.kw-card:hover { border-color: #c7d2fe; background: #f5f4ff; }
.kw-word { font-size: 14px; font-weight: 700; color: #1e1b4b; padding-right: 24px; }
.kw-date { font-size: 11px; color: #9ca3af; }
.kw-delete { position: absolute; top: 10px; right: 10px; width: 26px; height: 26px; border-radius: 8px; border: none; background: transparent; color: #d1d5db; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
.kw-delete:hover:not(:disabled) { background: #fee2e2; color: #ef4444; }

/* Users */
.table-wrap { flex: 1; overflow-y: auto; padding: 16px 26px; }
.table-wrap::-webkit-scrollbar { width: 4px; }
.table-wrap::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }
.user-table { width: 100%; border-collapse: collapse; }
.user-table th { padding: 10px 14px; text-align: left; font-size: 11.5px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #f1f0f9; }
.user-table td { padding: 13px 14px; font-size: 13.5px; color: #374151; border-bottom: 1px solid #f9f8ff; }
.user-table tr:hover td { background: #faf9ff; }
.td-id { color: #9ca3af; font-size: 12px; }
.td-name { font-weight: 700; color: #1e1b4b; }
.td-date { font-size: 12.5px; color: #9ca3af; }
.td-addr { font-size: 12.5px; color: #6b7280; max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.role-chip { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 99px; }
.user-filter-bar {
  display: flex; gap: 8px; padding: 14px 20px 0;
  border-bottom: 1.5px solid #f1f0f9; flex-shrink: 0; flex-wrap: wrap;
}
.user-filter-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 16px; border-radius: 10px 10px 0 0;
  border: 1.5px solid transparent; border-bottom: none;
  background: transparent; font-size: 13px; font-weight: 600;
  color: #9ca3af; cursor: pointer; transition: all 0.15s;
  margin-bottom: -1.5px;
}
.user-filter-btn:hover { color: #6366f1; background: #f5f4ff; }
.user-filter-btn.active { background: #fff; border-color: #f1f0f9; color: #1e1b4b; }
.user-filter-btn.active.filter-user { color: #6d28d9; }
.user-filter-btn.active.filter-counselor { color: #1d4ed8; }
.user-filter-btn.active.filter-admin { color: #be185d; }
.user-filter-btn.active.filter-developer { color: #065f46; }
.filter-count {
  font-size: 11px; font-weight: 800; padding: 1px 7px;
  border-radius: 99px; background: #f1f0f9; color: #6b7280;
}
.user-filter-btn.active .filter-count { background: #ede9fe; color: #6366f1; }
.role-cell { display: flex; align-items: center; gap: 6px; }
.role-select {
  font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 99px;
  border: 1.5px solid transparent; cursor: pointer; outline: none; appearance: none;
  -webkit-appearance: none; text-align: center; transition: border-color 0.15s;
}
.role-select:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-role-confirm {
  padding: 4px 10px; border-radius: 99px; border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; font-size: 11px; font-weight: 700; cursor: pointer;
  white-space: nowrap; transition: opacity 0.15s;
  display: flex; align-items: center; gap: 4px;
}
.btn-role-confirm:hover:not(:disabled) { opacity: 0.85; }
.btn-role-confirm:disabled { opacity: 0.5; cursor: not-allowed; }
.spinner-xs {
  width: 10px; height: 10px;
  border: 1.5px solid rgba(255,255,255,0.4);
  border-top-color: #fff; border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.role-select.role-user { background: #ede9fe; color: #6d28d9; }
.role-select.role-counselor { background: #dbeafe; color: #1d4ed8; }
.role-select.role-admin { background: #fce7f3; color: #be185d; }
.role-select.role-developer { background: #d1fae5; color: #065f46; }
.role-user { background: #ede9fe; color: #6d28d9; }
.role-counselor { background: #dbeafe; color: #1d4ed8; }
.role-admin { background: #fce7f3; color: #be185d; }

/* Chats */
.chat-log-list { flex: 1; overflow-y: auto; padding: 12px 22px; display: flex; flex-direction: column; gap: 8px; }
.chat-log-list::-webkit-scrollbar { width: 4px; }
.chat-log-list::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }
.chat-log-item { padding: 12px 16px; border-radius: 14px; border: 1.5px solid #f1f0f9; }
.chat-log-item.user { background: #faf9ff; border-color: #ede9fe; }
.chat-log-item.ai { background: #f9fafb; }
.log-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.log-user { font-size: 12px; font-weight: 700; color: #374151; }
.log-date { font-size: 11px; color: #9ca3af; margin-left: auto; }
.log-role-badge { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 99px; }
.log-role-badge.user { background: #ede9fe; color: #6d28d9; }
.log-role-badge.ai { background: #f3f4f6; color: #6b7280; }
.badge-spam { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 99px; background: #fee2e2; color: #991b1b; }
.badge-ham { font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 99px; background: #d1fae5; color: #065f46; }
.log-msg { font-size: 13.5px; color: #374151; line-height: 1.5; white-space: pre-wrap; }

/* Reviews */
.reviews-body { flex: 1; overflow-y: auto; padding: 20px 26px; display: flex; flex-direction: column; gap: 16px; }
.reviews-body::-webkit-scrollbar { width: 4px; }
.reviews-body::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.overview-row { display: flex; gap: 12px; flex-wrap: wrap; }

.overview-card {
  padding: 18px 22px; border-radius: 18px; border: 1.5px solid #f1f0f9;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  flex: 1; min-width: 130px; transition: all 0.15s;
}
.overview-card:hover { border-color: #c7d2fe; background: #f5f4ff; }
.overview-card.main { background: linear-gradient(135deg, #faf9ff, #f0eeff); border-color: #ede9fe; }

.ov-label { font-size: 12px; font-weight: 700; color: #7c7c9a; }
.ov-big { font-size: 36px; font-weight: 900; color: #1e1b4b; line-height: 1; letter-spacing: -1px; }
.ov-stars { display: flex; gap: 3px; }
.ov-star { font-size: 14px; color: #e5e7eb; }
.ov-star.filled { color: #f59e0b; }
.ov-sub { font-size: 11.5px; color: #9ca3af; }

.review-filter-row { flex-shrink: 0; }

.empty-state-reviews { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 50px 0; text-align: center; color: #9ca3af; }
.empty-star-icon { width: 72px; height: 72px; border-radius: 20px; background: #f5f4ff; display: flex; align-items: center; justify-content: center; }
.empty-state-reviews p { font-size: 15px; font-weight: 600; color: #374151; }

.review-list { display: flex; flex-direction: column; gap: 10px; }

.review-item { padding: 16px 18px; border: 1.5px solid #f1f0f9; border-radius: 16px; background: #faf9ff; transition: all 0.15s; }
.review-item:hover { border-color: #c7d2fe; background: #f5f4ff; }

.review-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.review-left { display: flex; align-items: center; gap: 10px; }
.review-stars { display: flex; gap: 3px; }
.r-star { font-size: 17px; color: #e5e7eb; }
.r-star.filled { color: #f59e0b; }
.review-date { font-size: 12px; color: #9ca3af; }

.counselor-chip { font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 99px; background: #dbeafe; color: #1d4ed8; }

.review-comment { font-size: 14px; color: #374151; line-height: 1.6; margin-bottom: 10px; }
.review-no-comment { font-size: 13px; color: #c4c4cc; margin-bottom: 10px; font-style: italic; }

.review-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.reviewer-name { font-size: 12px; font-weight: 600; color: #6b7280; }
.email-preview { font-size: 12px; color: #9ca3af; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 300px; }

/* 카테고리 bar (overview card) */
.ov-cats { width: 100%; display: flex; flex-direction: column; gap: 5px; margin-top: 8px; border-top: 1px solid #f1f0f9; padding-top: 8px; }
.ov-cat-row { display: flex; align-items: center; gap: 6px; }
.ov-cat-label { font-size: 10px; color: #9ca3af; width: 52px; flex-shrink: 0; text-align: right; }
.ov-cat-bar-wrap { flex: 1; height: 5px; background: #f1f0f9; border-radius: 99px; overflow: hidden; }
.ov-cat-bar { display: block; height: 100%; background: linear-gradient(90deg, #6366f1, #8b5cf6); border-radius: 99px; transition: width 0.4s; }
.ov-cat-val { font-size: 10.5px; font-weight: 700; color: #6366f1; width: 24px; text-align: right; }

/* 리뷰 아이템 카테고리 별점 행 */
.rv-overall { font-size: 12px; font-weight: 700; color: #6b7280; padding: 2px 8px; background: #f1f0f9; border-radius: 99px; }
.rv-cat-rows { display: flex; flex-direction: column; gap: 6px; margin: 10px 0; padding: 12px 14px; background: #f9f8ff; border-radius: 12px; }
.rv-cat-row { display: flex; align-items: center; gap: 8px; }
.rv-cat-label { font-size: 12px; color: #6b7280; width: 72px; flex-shrink: 0; }
.rv-cat-score { font-size: 12px; font-weight: 700; color: #6366f1; width: 14px; text-align: right; }

.profile-wrapper { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.profile-view, .profile-edit-form { flex: 1; padding: 28px 32px; overflow-y: auto; }
.profile-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 24px; margin-bottom: 10px; }
.pfield { display: flex; flex-direction: column; gap: 7px; }
.pfield-full { grid-column: 1 / -1; }
.pfield-label { font-size: 11.5px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
.pfield-val { font-size: 14px; color: #1e1b4b; font-weight: 500; padding: 11px 15px; background: #f9f8ff; border-radius: 10px; border: 1.5px solid #ede9fe; min-height: 42px; }
.pfield-input { font-size: 14px; color: #1e1b4b; padding: 11px 15px; background: #fff; border-radius: 10px; border: 1.5px solid #e0d9f0; outline: none; width: 100%; box-sizing: border-box; min-height: 42px; }
.pfield-input:focus { border-color: #6366f1; }
.profile-section-title { font-size: 11.5px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1.5px solid #f1f0f9; }
.btn-edit-toggle { display: flex; align-items: center; gap: 7px; padding: 9px 18px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 13px; font-weight: 700; border: none; cursor: pointer; }
.profile-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 28px; padding-top: 20px; border-top: 1.5px solid #f1f0f9; }
.btn-cancel { padding: 11px 24px; border-radius: 12px; border: 1.5px solid #e0d9f0; background: #fff; color: #6b7280; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-save { padding: 11px 24px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 13px; font-weight: 700; border: none; cursor: pointer; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.panel-desc { font-size: 13px; color: #9ca3af; margin-top: 4px; }

/* ── AI 성능 평가 ── */
.eval-body { flex: 1; overflow-y: auto; padding: 20px 26px; display: flex; flex-direction: column; gap: 18px; }
.eval-body::-webkit-scrollbar { width: 4px; }
.eval-body::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.eval-note { font-size: 12px; color: #6b7280; background: #f5f4ff; border-radius: 8px; padding: 8px 12px; margin: 0; }
.eval-error { font-size: 12.5px; color: #ef4444; background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.2); border-radius: 8px; padding: 8px 12px; margin: 0; }

/* 데이터셋 카드 */
.eval-dataset-row { display: flex; gap: 14px; flex-wrap: wrap; }
.eval-dataset-card { flex: 1; min-width: 170px; border: 1.5px solid #e8e6f0; border-radius: 18px; padding: 18px 18px 14px; background: #faf9ff; display: flex; flex-direction: column; gap: 8px; cursor: pointer; transition: all 0.2s; }
.eval-dataset-card:hover { border-color: #a5b4fc; background: #f5f4ff; }
.eval-dataset-card.running { border-color: #6366f1; background: #f0eeff; }
.eds-top { display: flex; align-items: center; justify-content: space-between; }
.eds-badge { font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 99px; }
.eds-badge.test  { background: #fee2e2; color: #991b1b; }
.eds-badge.val   { background: #fef3c7; color: #92400e; }
.eds-badge.chat  { background: #dcfce7; color: #166534; }
.eds-pct { font-size: 11px; color: #9ca3af; font-weight: 600; }
.eds-title { font-size: 14px; font-weight: 800; color: #1e1b4b; }
.eds-desc { font-size: 12px; color: #6b7280; line-height: 1.5; flex: 1; }
.eds-btn { margin-top: 4px; padding: 8px 14px; font-size: 12px; width: 100%; justify-content: center; }
.btn-run-eval { display: flex; align-items: center; gap: 7px; padding: 10px 22px; border: none; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 14px; font-weight: 700; cursor: pointer; transition: opacity 0.2s; }
.btn-run-eval:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-run-eval:not(:disabled):hover { opacity: 0.88; }

/* 지표 카드 */
.eval-metrics-row { display: flex; gap: 12px; flex-wrap: wrap; }
.eval-metric-card { flex: 1; min-width: 120px; padding: 16px 18px; border-radius: 16px; border: 1.5px solid #f1f0f9; display: flex; flex-direction: column; gap: 6px; }
.eval-metric-card.acc { background: #f0fdf4; border-color: #bbf7d0; }
.eval-metric-card.prec { background: #eff6ff; border-color: #bfdbfe; }
.eval-metric-card.rec { background: #fdf4ff; border-color: #e9d5ff; }
.eval-metric-card.f1 { background: #fff7ed; border-color: #fed7aa; }
.em-label { font-size: 11px; font-weight: 700; color: #6b7280; }
.em-val { font-size: 28px; font-weight: 900; color: #1e1b4b; letter-spacing: -0.5px; line-height: 1; }
.em-bar-wrap { height: 5px; background: rgba(0,0,0,0.06); border-radius: 99px; overflow: hidden; }
.em-bar { height: 100%; background: linear-gradient(90deg, #6366f1, #8b5cf6); border-radius: 99px; transition: width 0.5s; }
.eval-metric-card.acc .em-bar { background: linear-gradient(90deg, #22c55e, #16a34a); }
.eval-metric-card.prec .em-bar { background: linear-gradient(90deg, #3b82f6, #1d4ed8); }
.eval-metric-card.rec .em-bar { background: linear-gradient(90deg, #a855f7, #7c3aed); }
.eval-metric-card.f1 .em-bar { background: linear-gradient(90deg, #f97316, #ea580c); }

/* 혼동 행렬 + 이력 */
.eval-section-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
.eval-section-title { font-size: 13px; font-weight: 700; color: #374151; margin-bottom: 12px; display: block; }
.eval-confusion { flex: 1; min-width: 260px; }
.confusion-grid { display: grid; grid-template-columns: 90px 1fr 1fr; gap: 4px; }
.cm-head-blank { }
.cm-head { font-size: 11.5px; font-weight: 700; color: #6b7280; text-align: center; padding: 6px; }
.cm-side { font-size: 11.5px; font-weight: 700; color: #6b7280; display: flex; align-items: center; padding: 6px; }
.cm-cell { display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 12px; padding: 16px 10px; gap: 4px; }
.cm-cell.tp { background: #dcfce7; border: 1.5px solid #86efac; }
.cm-cell.tn { background: #dcfce7; border: 1.5px solid #86efac; }
.cm-cell.fp { background: #fef3c7; border: 1.5px solid #fde68a; }
.cm-cell.fn { background: #fee2e2; border: 1.5px solid #fca5a5; }
.cm-num { font-size: 26px; font-weight: 900; color: #1e1b4b; }
.cm-tag { font-size: 10px; font-weight: 700; color: #6b7280; }
.cm-legend { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.cm-leg { font-size: 11px; padding: 3px 8px; border-radius: 6px; }
.cm-leg.tp, .cm-leg.tn { background: #dcfce7; color: #166534; }
.cm-leg.fp { background: #fef3c7; color: #92400e; }
.cm-leg.fn { background: #fee2e2; color: #991b1b; }

/* 평가 이력 */
.eval-history { flex: 1; min-width: 220px; }
.history-list { display: flex; flex-direction: column; gap: 6px; }
.history-item { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 10px; border: 1.5px solid #f1f0f9; background: #faf9ff; font-size: 12px; flex-wrap: wrap; }
.history-item.current { border-color: #6366f1; background: #f0eeff; }
.h-date { color: #9ca3af; flex-shrink: 0; }
.h-metrics { flex: 1; color: #374151; font-weight: 600; }
.h-total { color: #9ca3af; font-size: 11px; flex-shrink: 0; }

/* 개별 결과 */
.eval-detail { display: flex; flex-direction: column; gap: 10px; }
.eval-detail-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.eval-result-list { display: flex; flex-direction: column; gap: 6px; max-height: 300px; overflow-y: auto; }
.eval-result-list::-webkit-scrollbar { width: 4px; }
.eval-result-list::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }
.eval-result-row { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 10px; font-size: 13px; }
.eval-result-row.correct { background: #f0fdf4; border: 1px solid #bbf7d0; }
.eval-result-row.wrong { background: #fef2f2; border: 1px solid #fecaca; }
.result-icon { font-size: 14px; font-weight: 900; flex-shrink: 0; width: 18px; text-align: center; }
.result-icon.ok { color: #16a34a; }
.result-icon.err { color: #dc2626; }
.result-text { flex: 1; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-label-badge, .result-pred-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 99px; flex-shrink: 0; }
.result-label-badge.spam { background: #fee2e2; color: #991b1b; }
.result-label-badge.ham { background: #dcfce7; color: #166534; }
.result-pred-badge.spam { background: #fee2e2; color: #991b1b; }
.result-pred-badge.ham { background: #dcfce7; color: #166534; }
.result-pred-badge.wrong-pred { outline: 2px solid #ef4444; }
.result-arrow { color: #9ca3af; flex-shrink: 0; }
.eval-result-area { display: flex; flex-direction: column; gap: 18px; }
</style>
