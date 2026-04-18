<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = 'http://127.0.0.1:8000'

type Tab = 'rag' | 'compare' | 'reports' | 'keywords' | 'users' | 'profile'
type Role = 'user' | 'counselor' | 'admin' | 'developer'
type Split = 'train' | 'val' | 'test'

interface Report {
  id: number
  requester: string
  email_content: string
  status: string
  counselor_note: string
  created_at: string
}

interface Keyword {
  id: number
  keyword: string
  created_at: string
}

interface UserRow {
  id: number
  username: string
  nickname: string
  name: string
  phone: string
  email: string
  address: string
  postal_code: string
  role: Role
  created_at: string
}

interface Profile {
  username: string
  nickname: string
  name: string
  phone: string
  email: string
  address: string
  detail_address: string
  postal_code: string
  role: string
  created_at: string
}

interface RagStatus {
  available: boolean
  vector_count: number
  spam_count: number
  ham_count: number
}

interface Metrics {
  model: string
  total: number
  accuracy: number
  precision: number
  recall: number
  f1: number
  tp: number
  tn: number
  fp: number
  fn: number
  fp_list: string[]
  fn_list: string[]
}

interface ValResult {
  split: Split
  gpt: Metrics
  qwen: Metrics
}

interface ImproveResult {
  iteration: number
  mode: string
  split: string
  total: number
  accuracy: number
  precision: number
  recall: number
  f1: number
  misclassified_count: number
  added_to_vectorstore: number
}

interface ImproveHistoryItem {
  iteration: number
  mode: string
  accuracy: number
  precision_score: number
  recall: number
  f1: number
  total: number
  tp: number
  tn: number
  fp: number
  fn: number
  added_count: number
  created_at?: string
}

interface CompareModelResult {
  is_spam: boolean
  raw_answer?: string
  retrieved_count?: number
}

interface CompareResult {
  final_is_spam: boolean
  agreement: boolean
  gpt: CompareModelResult
  qwen: CompareModelResult
}

const activeTab = ref<Tab>('rag')

const reports = ref<Report[]>([])
const selectedReport = ref<Report | null>(null)
const reportNote = ref('')
const reportKeywords = ref('')
const reportSaving = ref(false)

const keywords = ref<Keyword[]>([])
const keywordInput = ref('')
const keywordSaving = ref(false)
const keywordDeleting = ref<number | null>(null)
const keywordMsg = ref('')
const keywordErr = ref('')
const reportEnabled = ref(true)

const ragStatus = ref<RagStatus | null>(null)
const trainLoading = ref(false)
const trainMsg = ref('')
const trainErr = ref('')
const valLoading = ref(false)
const valSplit = ref<Split>('val')
const valMaxSamples = 120
const valResult = ref<ValResult | null>(null)
const valErr = ref('')
const improveLoading = ref(false)
const improveMsg = ref('')
const improveErr = ref('')
const improveResult = ref<ImproveResult | null>(null)
const improveHistory = ref<ImproveHistoryItem[]>([])
const bestModel = ref<'gpt' | 'qwen' | ''>('')
const bestScore = ref(0)
const testLocked = ref(localStorage.getItem('rag_test_locked') === 'true')

const compareText = ref('')
const compareLoading = ref(false)
const compareErr = ref('')
const compareResult = ref<CompareResult | null>(null)

const users = ref<UserRow[]>([])
const roleSavingId = ref<number | null>(null)
const roleDrafts = ref<Record<number, Role>>({})

const profile = ref<Profile | null>(null)
const profileEdit = ref(false)
const profileSaving = ref(false)
const profileMsg = ref('')
const profileErr = ref('')
const profileForm = ref({
  nickname: '',
  name: '',
  phone: '',
  email: '',
  address: '',
  detail_address: '',
  postal_code: '',
})
const profilePwForm = ref({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const statusLabel: Record<string, string> = {
  pending: '대기중',
  processing: '처리중',
  done: '완료',
}

const roleLabel: Record<Role, string> = {
  user: '사용자',
  counselor: '상담사',
  admin: '관리자',
  developer: '개발자',
}

const roleOptions = computed(() => {
  const base: Array<{ value: Role; label: string }> = [
    { value: 'user', label: '사용자' },
    { value: 'counselor', label: '상담사' },
    { value: 'admin', label: '관리자' },
  ]
  if (auth.role === 'developer') {
    base.push({ value: 'developer', label: '개발자' })
  }
  return base
})

const keywordPreview = computed(() => keywords.value.slice(0, 30))
const latestKeywordDate = computed(() => {
  if (!keywords.value.length) return '-'
  return formatDate(keywords.value[0].created_at)
})

const bestModelLabel = computed(() => {
  if (bestModel.value === 'gpt') return 'GPT'
  if (bestModel.value === 'qwen') return 'Qwen'
  return '미선택'
})

function authHeaders() {
  const token =
    localStorage.getItem('token') ||
    localStorage.getItem('access_token') ||
    localStorage.getItem('authToken')

  // 🔥 토큰 없으면 헤더 자체를 안 보냄
  if (!token) return {}

  return {
    Authorization: `Bearer ${token}`,
  }
}

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function formatDate(value?: string) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ko-KR')
}

function metricClass(value: number) {
  if (value >= 0.9) return 'good'
  if (value >= 0.75) return 'mid'
  return 'bad'
}

async function loadReports() {
  const res = await fetch(`${API}/spam-reports`, { headers: authHeaders() })
  if (!res.ok) return
  reports.value = await res.json()
  if (selectedReport.value) {
    selectedReport.value = reports.value.find((item) => item.id === selectedReport.value?.id) ?? null
    reportNote.value = selectedReport.value?.counselor_note ?? ''
  }
}

function selectReport(report: Report) {
  selectedReport.value = report
  reportNote.value = report.counselor_note ?? ''
  reportKeywords.value = ''
}

async function updateReport(status: 'processing' | 'done') {
  if (!selectedReport.value || reportSaving.value) return
  reportSaving.value = true
  try {
    const keywordList = reportKeywords.value
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)

    await fetch(`${API}/spam-reports/${selectedReport.value.id}`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({
        status,
        counselor_note: reportNote.value,
        keywords: keywordList,
      }),
    })

    await Promise.all([loadReports(), loadKeywords(), loadRagStatus()])
    reportKeywords.value = ''
  } finally {
    reportSaving.value = false
  }
}

async function loadKeywords() {
  const res = await fetch(`${API}/spam-keywords`, { headers: authHeaders() })
  if (res.ok) keywords.value = await res.json()
}

async function addKeyword() {
  const keyword = keywordInput.value.trim()
  if (!keyword || keywordSaving.value) return
  keywordMsg.value = ''
  keywordErr.value = ''
  keywordSaving.value = true
  try {
    const res = await fetch(`${API}/spam-keywords`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ keyword }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      keywordErr.value = data.detail || '키워드 등록에 실패했습니다.'
      return
    }
    keywordInput.value = ''
    keywordMsg.value = '키워드를 등록했습니다.'
    await Promise.all([loadKeywords(), loadRagStatus()])
  } finally {
    keywordSaving.value = false
  }
}

async function deleteKeyword(id: number) {
  if (keywordDeleting.value !== null) return
  keywordDeleting.value = id
  keywordMsg.value = ''
  keywordErr.value = ''
  try {
    const res = await fetch(`${API}/spam-keywords/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      keywordErr.value = data.detail || '키워드 삭제에 실패했습니다.'
      return
    }
    keywordMsg.value = '키워드를 삭제했습니다.'
    await Promise.all([loadKeywords(), loadRagStatus()])
  } finally {
    keywordDeleting.value = null
  }
}

async function loadSettings() {
  const res = await fetch(`${API}/settings`, { headers: authHeaders() })
  if (!res.ok) return
  const data = await res.json()
  reportEnabled.value = data.report_enabled !== 'false'
}

async function toggleReportEnabled() {
  const nextValue = !reportEnabled.value
  const res = await fetch(`${API}/settings/report_enabled`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ value: nextValue ? 'true' : 'false' }),
  })
  if (res.ok) reportEnabled.value = nextValue
}

async function loadRagStatus() {
  const res = await fetch(`${API}/rag/status`, { headers: authHeaders() })
  if (res.ok) ragStatus.value = await res.json()
}

async function runTrain() {
  trainMsg.value = ''
  trainErr.value = ''
  trainLoading.value = true
  try {
    const res = await fetch(`${API}/rag/train`, {
      method: 'POST',
      headers: authHeaders(),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      trainErr.value = data.detail || '학습 실행에 실패했습니다.'
      return
    }
    trainMsg.value = `학습 완료: 벡터 ${Number(data.vector_count ?? 0).toLocaleString()}개`
    await loadRagStatus()
  } finally {
    trainLoading.value = false
  }
}

async function runVal() {
  valErr.value = ''
  valLoading.value = true

  try {
    const url = `${API}/rag/val?split=${valSplit.value}&mode=fast&max_samples=${valMaxSamples}`

    const res = await fetch(url, {
      method: 'GET',
      headers: authHeaders(),
    })

    const text = await res.text()

    let data: any = {}
    try {
      data = text ? JSON.parse(text) : {}
    } catch {
      data = { raw: text }
    }

    console.log('검증 결과:', data)

    if (!res.ok) {
      valErr.value = data.detail || data.raw || `실패 (${res.status})`
      return
    }

    valResult.value = {
      split: data.split || valSplit.value,
      gpt: data.gpt || data.gpt_result || {},
      qwen: data.qwen || data.qwen_result || {},
    }

  } catch (e: any) {
    valErr.value = `에러: ${e?.message || String(e)}`
  } finally {
    valLoading.value = false
  }
}

async function runSplitEval(split: Split) {
  alert(`👉 runSplitEval 호출됨: ${split}`)

  valSplit.value = split
  await runVal()
}

async function runTrainCheck() {
  if (trainLoading.value || valLoading.value) return
  await runTrain()
}

async function loadImproveHistory() {
  const res = await fetch(`${API}/rag/improve/history`, { headers: authHeaders() })
  if (res.ok) improveHistory.value = await res.json()
}

async function runImprove() {
  improveMsg.value = ''
  improveErr.value = ''
  improveLoading.value = true
  try {
    const res = await fetch(`${API}/rag/improve?split=val&mode=fast`, {
      method: 'POST',
      headers: authHeaders(),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      improveErr.value = data.detail || '개선 루프 실행에 실패했습니다.'
      return
    }
    improveResult.value = data
    improveMsg.value = `개선 ${data.iteration}회차 완료: F1 ${pct(Number(data.f1 ?? 0))}, 추가 예시 ${Number(data.added_to_vectorstore ?? 0)}건`
    await Promise.all([loadImproveHistory(), loadRagStatus()])
  } finally {
    improveLoading.value = false
  }
}

function resetTestLock() {
  testLocked.value = false
  localStorage.removeItem('rag_test_locked')
}

async function runCompare() {
  const text = compareText.value.trim()
  if (!text || compareLoading.value) return
  compareErr.value = ''
  compareLoading.value = true
  try {
    const res = await fetch(`${API}/rag/classify`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ text, model: 'both' }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      compareErr.value = data.detail || '판별 실행에 실패했습니다.'
      return
    }
    compareResult.value = data
  } finally {
    compareLoading.value = false
  }
}

async function loadUsers() {
  const res = await fetch(`${API}/admin/users`, { headers: authHeaders() })
  if (res.ok) users.value = await res.json()
}

function onRoleChange(userId: number, currentRole: Role, value: Role) {
  if (value === currentRole) {
    delete roleDrafts.value[userId]
    return
  }
  roleDrafts.value[userId] = value
}

async function saveRole(user: UserRow) {
  const nextRole = roleDrafts.value[user.id]
  if (!nextRole) return
  roleSavingId.value = user.id
  try {
    const res = await fetch(`${API}/admin/users/${user.id}/role`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ role: nextRole }),
    })
    if (res.ok) {
      delete roleDrafts.value[user.id]
      await loadUsers()
    }
  } finally {
    roleSavingId.value = null
  }
}

async function loadProfile() {
  const res = await fetch(`${API}/users/me`, { headers: authHeaders() })
  if (!res.ok) return
  profile.value = await res.json()
  profileForm.value = {
    nickname: profile.value.nickname ?? '',
    name: profile.value.name ?? '',
    phone: profile.value.phone ?? '',
    email: profile.value.email ?? '',
    address: profile.value.address ?? '',
    detail_address: profile.value.detail_address ?? '',
    postal_code: profile.value.postal_code ?? '',
  }
}

async function saveProfile() {
  profileMsg.value = ''
  profileErr.value = ''
  if (profilePwForm.value.new_password && profilePwForm.value.new_password !== profilePwForm.value.confirm_password) {
    profileErr.value = '새 비밀번호 확인이 일치하지 않습니다.'
    return
  }
  profileSaving.value = true
  try {
    const res = await fetch(`${API}/users/me`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({
        ...profileForm.value,
        current_password: profilePwForm.value.current_password,
        new_password: profilePwForm.value.new_password,
      }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      profileErr.value = data.detail || '프로필 저장에 실패했습니다.'
      return
    }
    profileMsg.value = '프로필을 저장했습니다.'
    profilePwForm.value = { current_password: '', new_password: '', confirm_password: '' }
    profileEdit.value = false
    await loadProfile()
  } finally {
    profileSaving.value = false
  }
}

async function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'rag') await Promise.all([loadRagStatus(), loadImproveHistory()])
  if (tab === 'reports') await loadReports()
  if (tab === 'keywords') await Promise.all([loadKeywords(), loadSettings()])
  if (tab === 'users') await loadUsers()
  if (tab === 'profile') await loadProfile()
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  await Promise.all([
    loadReports(),
    loadKeywords(),
    loadSettings(),
    loadRagStatus(),
    loadImproveHistory(),
    loadUsers(),
    loadProfile(),
  ])
})
</script>

<template>
  <div class="admin-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">SG</div>
        <div>
          <p class="brand-eyebrow">Admin Console</p>
          <h1>SpamGuard</h1>
        </div>
      </div>

      <div class="account-card">
        <div class="avatar">{{ auth.username[0]?.toUpperCase() }}</div>
        <div>
          <strong>{{ auth.username }}</strong>
          <p>{{ auth.role === 'developer' ? '개발자' : '관리자' }}</p>
        </div>
        <button class="account-logout" @click="logout">로그아웃</button>
      </div>

      <nav class="nav-list">
        <button :class="['nav-btn', { active: activeTab === 'rag' }]" @click="switchTab('rag')">RAG 평가</button>
        <button :class="['nav-btn', { active: activeTab === 'compare' }]" @click="switchTab('compare')">AI 비교 판별</button>
        <button :class="['nav-btn', { active: activeTab === 'reports' }]" @click="switchTab('reports')">신고 처리</button>
        <button :class="['nav-btn', { active: activeTab === 'keywords' }]" @click="switchTab('keywords')">스팸 키워드</button>
        <button :class="['nav-btn', { active: activeTab === 'users' }]" @click="switchTab('users')">사용자 관리</button>
        <button :class="['nav-btn', { active: activeTab === 'profile' }]" @click="switchTab('profile')">내 정보</button>
      </nav>

      <button class="logout-btn" @click="logout">로그아웃</button>
    </aside>

    <main class="content">
      <section v-if="activeTab === 'rag'" class="panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">RAG Control</p>
            <h2>RAG 평가</h2>
          </div>
        </div>

        <div class="stats-grid">
          <article class="stat-card">
            <span class="stat-label">RAG 상태</span>
            <strong>{{ ragStatus?.available ? 'ON' : 'OFF' }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">전체 벡터</span>
            <strong>{{ Number(ragStatus?.vector_count ?? 0).toLocaleString() }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">스팸 예시</span>
            <strong>{{ Number(ragStatus?.spam_count ?? 0).toLocaleString() }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">정상 예시</span>
            <strong>{{ Number(ragStatus?.ham_count ?? 0).toLocaleString() }}</strong>
          </article>
        </div>

        <div class="workflow-grid">
          <article class="workflow-card">
            <div class="workflow-top">
              <span class="step-badge">1</span>
              <div>
                <h3>평가 버튼</h3>
              </div>
            </div>

            <div class="split-actions">
              <button :class="['dataset-btn', 'train', { active: valSplit === 'train' }]" :disabled="trainLoading || valLoading" @click="runTrainCheck">
                {{ trainLoading || (valLoading && valSplit === 'train') ? '학습 중...' : '학습' }}
              </button>
              <button type="button" :class="['dataset-btn', 'val', { active: valSplit === 'val' }]" :disabled="valLoading" @click="runSplitEval('val')">
                {{ valLoading ? '검증 중...' : '검증' }}
              </button>
              <button :class="['dataset-btn', 'test', { active: valSplit === 'test' }]" :disabled="valLoading" @click="runSplitEval('test')">
                {{ valLoading && valSplit === 'test' ? '테스트 중...' : '테스트' }}
              </button>
            </div>
            <p v-if="trainMsg" class="msg ok">{{ trainMsg }}</p>
            <p v-if="trainErr" class="msg err">{{ trainErr }}</p>
            <p v-if="valErr" class="msg err">{{ valErr }}</p>
          </article>

          <article class="workflow-card">
            <div class="workflow-top">
              <span class="step-badge">2</span>
              <div>
                <h3>개선 반복</h3>
              </div>
            </div>
            <div class="action-row">
              <button class="secondary-btn" :disabled="improveLoading" @click="runImprove">
                {{ improveLoading ? '개선 중...' : '개선 실행' }}
              </button>
              <button class="ghost-btn" @click="resetTestLock">테스트 잠금 해제</button>
            </div>
            <p v-if="improveMsg" class="msg ok">{{ improveMsg }}</p>
            <p v-if="improveErr" class="msg err">{{ improveErr }}</p>
          </article>

          <article class="workflow-card">
            <div class="workflow-top">
              <span class="step-badge">3</span>
              <div>
                <h3>최종 선택</h3>
              </div>
            </div>
            <div class="selection-card">
              <div>
                <span class="stat-label">현재 선택</span>
                <strong>{{ bestModelLabel }}</strong>
              </div>
              <div>
                <span class="stat-label">Validation F1</span>
                <strong>{{ bestScore ? pct(bestScore) : '-' }}</strong>
              </div>
              <div>
                <span class="stat-label">Test 상태</span>
                <strong>{{ testLocked ? '실행 완료' : '실행 가능' }}</strong>
              </div>
            </div>
          </article>
        </div>

        <div v-if="valResult" class="metrics-grid">
          <article class="model-card">
            <div class="model-head">
              <h3>GPT</h3>
              <span>{{ valResult.gpt.model }}</span>
            </div>
            <p class="result-split">{{ valResult.split.toUpperCase() }} 결과</p>
            <div class="metric-list">
              <div :class="['metric-box', metricClass(valResult.gpt.accuracy)]">
                <span>정확도</span>
                <strong>{{ pct(valResult.gpt.accuracy) }}</strong>
              </div>
              <div :class="['metric-box', metricClass(valResult.gpt.precision)]">
                <span>정밀도</span>
                <strong>{{ pct(valResult.gpt.precision) }}</strong>
              </div>
              <div :class="['metric-box', metricClass(valResult.gpt.recall)]">
                <span>재현율</span>
                <strong>{{ pct(valResult.gpt.recall) }}</strong>
              </div>
              <div :class="['metric-box', metricClass(valResult.gpt.f1)]">
                <span>F1</span>
                <strong>{{ pct(valResult.gpt.f1) }}</strong>
              </div>
            </div>
            <p class="confusion">TP {{ valResult.gpt.tp }} · TN {{ valResult.gpt.tn }} · FP {{ valResult.gpt.fp }} · FN {{ valResult.gpt.fn }}</p>
            <div v-if="valResult.gpt.fp_list?.length" class="detail-section">
              <p class="detail-label fp-label">🚨 오탐 (정상 → 스팸 판정, {{ valResult.gpt.fp_list.length }}건)</p>
              <ul class="detail-list">
                <li v-for="(txt, i) in valResult.gpt.fp_list" :key="'gpt-fp-'+i" class="detail-item fp-item">{{ txt }}</li>
              </ul>
            </div>
            <div v-if="valResult.gpt.fn_list?.length" class="detail-section">
              <p class="detail-label fn-label">❌ 미탐 (스팸 → 정상 판정, {{ valResult.gpt.fn_list.length }}건)</p>
              <ul class="detail-list">
                <li v-for="(txt, i) in valResult.gpt.fn_list" :key="'gpt-fn-'+i" class="detail-item fn-item">{{ txt }}</li>
              </ul>
            </div>
          </article>

          <article class="model-card">
            <div class="model-head">
              <h3>Qwen</h3>
              <span>{{ valResult.qwen.model }}</span>
            </div>
            <p class="result-split">{{ valResult.split.toUpperCase() }} 결과</p>
            <div class="metric-list">
              <div :class="['metric-box', metricClass(valResult.qwen.accuracy)]">
                <span>정확도</span>
                <strong>{{ pct(valResult.qwen.accuracy) }}</strong>
              </div>
              <div :class="['metric-box', metricClass(valResult.qwen.precision)]">
                <span>정밀도</span>
                <strong>{{ pct(valResult.qwen.precision) }}</strong>
              </div>
              <div :class="['metric-box', metricClass(valResult.qwen.recall)]">
                <span>재현율</span>
                <strong>{{ pct(valResult.qwen.recall) }}</strong>
              </div>
              <div :class="['metric-box', metricClass(valResult.qwen.f1)]">
                <span>F1</span>
                <strong>{{ pct(valResult.qwen.f1) }}</strong>
              </div>
            </div>
            <p class="confusion">TP {{ valResult.qwen.tp }} · TN {{ valResult.qwen.tn }} · FP {{ valResult.qwen.fp }} · FN {{ valResult.qwen.fn }}</p>
            <div v-if="valResult.qwen.fp_list?.length" class="detail-section">
              <p class="detail-label fp-label">🚨 오탐 (정상 → 스팸 판정, {{ valResult.qwen.fp_list.length }}건)</p>
              <ul class="detail-list">
                <li v-for="(txt, i) in valResult.qwen.fp_list" :key="'qwen-fp-'+i" class="detail-item fp-item">{{ txt }}</li>
              </ul>
            </div>
            <div v-if="valResult.qwen.fn_list?.length" class="detail-section">
              <p class="detail-label fn-label">❌ 미탐 (스팸 → 정상 판정, {{ valResult.qwen.fn_list.length }}건)</p>
              <ul class="detail-list">
                <li v-for="(txt, i) in valResult.qwen.fn_list" :key="'qwen-fn-'+i" class="detail-item fn-item">{{ txt }}</li>
              </ul>
            </div>
          </article>
        </div>

        <div class="history-panel">
          <div class="panel-head compact">
            <div>
              <p class="panel-eyebrow">Improve History</p>
              <h2>반복 이력</h2>
            </div>
          </div>

          <div v-if="improveResult" class="improve-highlight">
            최근 개선 {{ improveResult.iteration }}회차 · F1 {{ pct(improveResult.f1) }} · 오분류 {{ improveResult.misclassified_count }}건 · 추가 예시 {{ improveResult.added_to_vectorstore }}건
          </div>

          <div v-if="improveHistory.length" class="history-grid">
            <article v-for="item in improveHistory.slice().reverse()" :key="item.iteration" class="history-card">
              <strong>{{ item.iteration }}회차</strong>
              <p>F1 {{ pct(item.f1) }} · 정확도 {{ pct(item.accuracy) }}</p>
              <p>추가 예시 {{ item.added_count }}건 · mode {{ item.mode }}</p>
            </article>
          </div>
          <div v-else class="empty-state">아직 개선 이력이 없습니다.</div>
        </div>
      </section>

      <section v-else-if="activeTab === 'compare'" class="panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">Model Compare</p>
            <h2>GPT / Qwen 비교 판별</h2>
          </div>
        </div>

        <textarea v-model="compareText" class="wide-textarea" rows="5" placeholder="비교할 문장이나 메시지를 입력하세요." />
        <button class="primary-btn fit" :disabled="compareLoading" @click="runCompare">
          {{ compareLoading ? '판별 중...' : '두 모델 동시에 판별' }}
        </button>
        <p v-if="compareErr" class="msg err">{{ compareErr }}</p>

        <div v-if="compareResult" class="compare-summary" :class="compareResult.final_is_spam ? 'spam' : 'ham'">
          최종 판정: {{ compareResult.final_is_spam ? '스팸' : '정상' }} · {{ compareResult.agreement ? '두 모델 일치' : '두 모델 불일치' }}
        </div>

        <div v-if="compareResult" class="compare-grid">
          <article class="model-card">
            <div class="model-head">
              <h3>GPT</h3>
              <span :class="['verdict', compareResult.gpt.is_spam ? 'spam' : 'ham']">{{ compareResult.gpt.is_spam ? '스팸' : '정상' }}</span>
            </div>
            <p class="raw-answer">{{ compareResult.gpt.raw_answer || '응답 없음' }}</p>
            <p class="confusion">참조 예시 {{ compareResult.gpt.retrieved_count ?? 0 }}개</p>
          </article>

          <article class="model-card">
            <div class="model-head">
              <h3>Qwen</h3>
              <span :class="['verdict', compareResult.qwen.is_spam ? 'spam' : 'ham']">{{ compareResult.qwen.is_spam ? '스팸' : '정상' }}</span>
            </div>
            <p class="raw-answer">{{ compareResult.qwen.raw_answer || '응답 없음' }}</p>
            <p class="confusion">참조 예시 {{ compareResult.qwen.retrieved_count ?? 0 }}개</p>
          </article>
        </div>
      </section>

      <section v-else-if="activeTab === 'reports'" class="panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">Report Queue</p>
            <h2>신고 처리</h2>
          </div>
        </div>

        <div class="split-layout">
          <div class="list-card">
            <article v-for="report in reports" :key="report.id" :class="['list-item', { active: selectedReport?.id === report.id }]" @click="selectReport(report)">
              <div class="list-top">
                <strong>#{{ report.id }} {{ report.requester }}</strong>
                <span :class="['chip', report.status]">{{ statusLabel[report.status] || report.status }}</span>
              </div>
              <p>{{ report.email_content.slice(0, 90) }}</p>
              <small>{{ formatDate(report.created_at) }}</small>
            </article>
          </div>

          <div class="detail-card">
            <template v-if="selectedReport">
              <h3>상세 내용</h3>
              <p class="detail-text">{{ selectedReport.email_content }}</p>
              <label class="field">
                <span>처리 메모</span>
                <textarea v-model="reportNote" rows="4" class="wide-textarea" />
              </label>
              <label class="field">
                <span>등록할 스팸 키워드</span>
                <textarea v-model="reportKeywords" rows="4" class="wide-textarea" placeholder="한 줄에 하나씩 입력하세요." />
              </label>
              <div class="action-row">
                <button class="secondary-btn" :disabled="reportSaving" @click="updateReport('processing')">처리중 저장</button>
                <button class="primary-btn fit" :disabled="reportSaving" @click="updateReport('done')">완료 처리</button>
              </div>
            </template>
            <div v-else class="empty-state">왼쪽 목록에서 신고를 선택하세요.</div>
          </div>
        </div>
      </section>

      <section v-else-if="activeTab === 'keywords'" class="panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">Keyword Library</p>
            <h2>스팸 키워드 관리</h2>
          </div>
          <button :class="['toggle-btn', { on: reportEnabled }]" @click="toggleReportEnabled">
            {{ reportEnabled ? '신고 기능 ON' : '신고 기능 OFF' }}
          </button>
        </div>

        <div class="stats-grid">
          <article class="stat-card">
            <span class="stat-label">전체 키워드</span>
            <strong>{{ keywords.length }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">미리보기</span>
            <strong>{{ keywordPreview.length }}</strong>
          </article>
          <article class="stat-card">
            <span class="stat-label">최근 등록</span>
            <strong>{{ latestKeywordDate }}</strong>
          </article>
        </div>

        <div class="keyword-form">
          <input v-model="keywordInput" class="text-input" placeholder="새 스팸 키워드를 입력하세요." @keyup.enter="addKeyword" />
          <button class="primary-btn fit" :disabled="keywordSaving" @click="addKeyword">
            {{ keywordSaving ? '등록 중...' : '키워드 등록' }}
          </button>
        </div>
        <p v-if="keywordMsg" class="msg ok">{{ keywordMsg }}</p>
        <p v-if="keywordErr" class="msg err">{{ keywordErr }}</p>

        <div class="keyword-grid">
          <article v-for="item in keywords" :key="item.id" class="keyword-card">
            <div>
              <strong>{{ item.keyword }}</strong>
              <p>{{ formatDate(item.created_at) }}</p>
            </div>
            <button class="ghost-btn" :disabled="keywordDeleting === item.id" @click="deleteKeyword(item.id)">삭제</button>
          </article>
        </div>
      </section>

      <section v-else-if="activeTab === 'users'" class="panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">Accounts</p>
            <h2>사용자 관리</h2>
          </div>
        </div>

        <div class="table-wrap">
          <table class="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>아이디</th>
                <th>닉네임</th>
                <th>이름</th>
                <th>역할</th>
                <th>변경</th>
                <th>가입일</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in users" :key="item.id">
                <td>#{{ item.id }}</td>
                <td>{{ item.username }}</td>
                <td>{{ item.nickname || '-' }}</td>
                <td>{{ item.name || '-' }}</td>
                <td>{{ roleLabel[item.role] }}</td>
                <td class="role-cell">
                  <select :value="roleDrafts[item.id] ?? item.role" @change="onRoleChange(item.id, item.role, ($event.target as HTMLSelectElement).value as Role)">
                    <option v-for="option in roleOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                  </select>
                  <button class="ghost-btn" :disabled="!roleDrafts[item.id] || roleSavingId === item.id" @click="saveRole(item)">저장</button>
                </td>
                <td>{{ formatDate(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-else class="panel">
        <div class="panel-head">
          <div>
            <p class="panel-eyebrow">Profile</p>
            <h2>내 정보</h2>
          </div>
          <button class="ghost-btn" @click="profileEdit = !profileEdit">{{ profileEdit ? '편집 취소' : '편집 시작' }}</button>
        </div>

        <div v-if="profile" class="profile-grid">
          <label class="field">
            <span>아이디</span>
            <input class="text-input" :value="profile.username" disabled />
          </label>
          <label class="field">
            <span>닉네임</span>
            <input v-model="profileForm.nickname" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field">
            <span>이름</span>
            <input v-model="profileForm.name" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field">
            <span>전화번호</span>
            <input v-model="profileForm.phone" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field">
            <span>이메일</span>
            <input v-model="profileForm.email" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field">
            <span>우편번호</span>
            <input v-model="profileForm.postal_code" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field full">
            <span>주소</span>
            <input v-model="profileForm.address" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field full">
            <span>상세 주소</span>
            <input v-model="profileForm.detail_address" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field">
            <span>현재 비밀번호</span>
            <input v-model="profilePwForm.current_password" type="password" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field">
            <span>새 비밀번호</span>
            <input v-model="profilePwForm.new_password" type="password" class="text-input" :disabled="!profileEdit" />
          </label>
          <label class="field">
            <span>새 비밀번호 확인</span>
            <input v-model="profilePwForm.confirm_password" type="password" class="text-input" :disabled="!profileEdit" />
          </label>
        </div>

        <div class="action-row">
          <button class="primary-btn fit" :disabled="!profileEdit || profileSaving" @click="saveProfile">
            {{ profileSaving ? '저장 중...' : '프로필 저장' }}
          </button>
        </div>
        <p v-if="profileMsg" class="msg ok">{{ profileMsg }}</p>
        <p v-if="profileErr" class="msg err">{{ profileErr }}</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
:global(body) {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(255, 214, 102, 0.24), transparent 26%),
    radial-gradient(circle at bottom right, rgba(57, 154, 245, 0.18), transparent 24%),
    #f7f4ec;
  color: #1f2937;
  font-family: "Segoe UI", "Noto Sans KR", sans-serif;
}

* {
  box-sizing: border-box;
}

.admin-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
}

.sidebar {
  padding: 28px 22px;
  background: rgba(22, 36, 58, 0.95);
  color: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.brand,
.account-card {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand h1,
.panel-head h2,
.workflow-top h3,
.model-head h3,
.detail-card h3 {
  margin: 0;
}

.brand-mark,
.avatar {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-weight: 800;
}

.brand-mark {
  background: linear-gradient(135deg, #f59e0b, #ef4444);
  color: #fff7ed;
}

.avatar {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.brand-eyebrow,
.panel-eyebrow {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.brand-eyebrow {
  color: #cbd5e1;
}

.panel-eyebrow {
  color: #b45309;
}

.account-card {
  padding: 14px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.08);
}

.account-card p {
  margin: 4px 0 0;
  color: #cbd5e1;
}

.account-logout {
  margin-left: auto;
  border: 0;
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(239, 68, 68, 0.18);
  color: #fee2e2;
  font-weight: 700;
  cursor: pointer;
}

.nav-list {
  display: grid;
  gap: 10px;
}

.nav-btn,
.logout-btn,
.primary-btn,
.secondary-btn,
.ghost-btn,
.toggle-btn {
  border: 0;
  cursor: pointer;
  transition: 0.2s ease;
}

.nav-btn {
  padding: 13px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.08);
  color: inherit;
  text-align: left;
  font-weight: 600;
}

.nav-btn.active,
.nav-btn:hover {
  background: rgba(245, 158, 11, 0.26);
}

.logout-btn {
  margin-top: auto;
  padding: 13px 16px;
  border-radius: 16px;
  background: rgba(239, 68, 68, 0.16);
  color: #fecaca;
  font-weight: 700;
}

.content {
  padding: 28px;
}

.panel,
.history-panel {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: 28px;
  padding: 28px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08);
}

.history-panel {
  margin-top: 18px;
  padding: 22px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 24px;
}

.panel-head.compact {
  margin-bottom: 18px;
}

.stats-grid,
.workflow-grid,
.metrics-grid,
.compare-grid,
.profile-grid,
.history-grid {
  display: grid;
  gap: 16px;
}

.stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 18px;
}

.workflow-grid,
.metrics-grid,
.compare-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.history-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.stat-card,
.workflow-card,
.model-card,
.list-card,
.detail-card,
.keyword-card,
.history-card {
  border-radius: 22px;
  background: #fff;
  border: 1px solid #ece7dd;
}

.workflow-top p,
.detail-text,
.raw-answer,
.history-card p {
  margin: 8px 0 0;
  line-height: 1.6;
  color: #4b5563;
}

.step-badge {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 800;
  color: white;
  flex: none;
  background: #f59e0b;
}

.stat-card,
.workflow-card,
.model-card,
.detail-card,
.list-card,
.history-card {
  padding: 20px;
}

.stat-card strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
}

.stat-label {
  color: #6b7280;
  font-size: 13px;
}

.workflow-top,
.model-head,
.list-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.primary-btn,
.secondary-btn,
.ghost-btn,
.toggle-btn {
  border-radius: 14px;
  padding: 12px 16px;
  font-weight: 700;
}

.primary-btn {
  background: linear-gradient(135deg, #2563eb, #0f766e);
  color: white;
}

.secondary-btn {
  background: #eef2ff;
  color: #1d4ed8;
}

.ghost-btn {
  background: #fff7ed;
  color: #c2410c;
}

.toggle-btn {
  background: #e5e7eb;
  color: #374151;
}

.toggle-btn.on {
  background: #dcfce7;
  color: #166534;
}

.fit {
  width: fit-content;
}

.split-actions,
.selection-card,
.metric-list,
.action-row,
.keyword-form,
.role-cell {
  display: grid;
  gap: 12px;
}

.split-actions {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 16px;
}

.selection-card {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 16px;
  padding: 16px;
  border-radius: 18px;
  background: #f8fafc;
}

.dataset-btn {
  border: 0;
  border-radius: 18px;
  padding: 14px 16px;
  font-weight: 800;
  cursor: pointer;
}

.dataset-btn.train {
  background: #fff7ed;
  color: #c2410c;
}

.dataset-btn.val {
  background: #eff6ff;
  color: #1d4ed8;
}

.dataset-btn.test {
  background: #ecfdf5;
  color: #166534;
}

.dataset-btn.active {
  box-shadow: inset 0 0 0 2px rgba(15, 23, 42, 0.14);
}

.dataset-btn:disabled {
  opacity: 0.75;
  cursor: default;
}

.result-split,
.confusion,
.keyword-card p,
.list-item p,
.list-item small {
  color: #6b7280;
}

.detail-section {
  margin-top: 14px;
}

.detail-label {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 6px;
}

.fp-label { color: #b45309; }
.fn-label { color: #dc2626; }

.detail-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
}

.detail-item {
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 8px;
  line-height: 1.5;
  word-break: break-word;
}

.fp-item {
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  color: #78350f;
}

.fn-item {
  background: #fee2e2;
  border-left: 3px solid #ef4444;
  color: #7f1d1d;
}

.metric-list {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 14px;
}

.metric-box {
  padding: 14px;
  border-radius: 18px;
  background: #f9fafb;
}

.metric-box strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
}

.metric-box.good {
  background: #ecfdf5;
}

.metric-box.mid {
  background: #eff6ff;
}

.metric-box.bad {
  background: #fef2f2;
}

.improve-highlight,
.compare-summary {
  margin-bottom: 16px;
  padding: 16px 18px;
  border-radius: 18px;
  font-weight: 700;
}

.improve-highlight {
  background: #fff7ed;
  color: #9a3412;
}

.compare-summary.spam,
.verdict.spam,
.chip.done {
  background: #fee2e2;
  color: #b91c1c;
}

.compare-summary.ham,
.verdict.ham {
  background: #dcfce7;
  color: #166534;
}

.verdict {
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 13px;
}

.wide-textarea,
.text-input,
.field select,
.role-cell select {
  width: 100%;
  border: 1px solid #d6d3d1;
  border-radius: 16px;
  padding: 14px 16px;
  background: white;
  font: inherit;
}

.wide-textarea {
  resize: vertical;
}

.split-layout {
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 18px;
}

.list-card {
  max-height: 70vh;
  overflow: auto;
}

.list-item {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid transparent;
  cursor: pointer;
}

.list-item + .list-item {
  margin-top: 12px;
}

.list-item.active {
  border-color: #93c5fd;
  background: #eff6ff;
}

.chip {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.chip.pending {
  background: #fef3c7;
  color: #92400e;
}

.chip.processing {
  background: #dbeafe;
  color: #1d4ed8;
}

.field {
  display: grid;
  gap: 8px;
}

.field span {
  font-size: 14px;
  font-weight: 700;
}

.detail-card {
  display: grid;
  gap: 16px;
}

.detail-text {
  white-space: pre-wrap;
  padding: 16px;
  border-radius: 18px;
  background: #f8fafc;
}

.action-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.empty-state {
  min-height: 180px;
  display: grid;
  place-items: center;
  color: #6b7280;
}

.keyword-form {
  grid-template-columns: minmax(0, 1fr) auto;
  margin-bottom: 16px;
}

.keyword-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.keyword-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.table-wrap {
  overflow-x: auto;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
}

.admin-table th,
.admin-table td {
  padding: 14px 12px;
  border-bottom: 1px solid #ece7dd;
  text-align: left;
}

.admin-table th {
  color: #6b7280;
  font-size: 13px;
}

.profile-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.profile-grid .full {
  grid-column: 1 / -1;
}

.msg {
  margin: 12px 0 0;
  font-weight: 600;
}

.msg.ok {
  color: #166534;
}

.msg.err {
  color: #b91c1c;
}

@media (max-width: 1120px) {
  .admin-shell {
    grid-template-columns: 1fr;
  }

  .stats-grid,
  .workflow-grid,
  .metrics-grid,
  .compare-grid,
  .selection-card,
  .history-grid,
  .keyword-grid,
  .profile-grid,
  .split-actions,
  .split-layout,
  .keyword-form {
    grid-template-columns: 1fr;
  }

  .content {
    padding: 18px;
  }
}
</style>
