<script setup lang="ts">
import { ref, onMounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = 'http://127.0.0.1:8000'

type Tab = 'reports' | 'spam-check' | 'keywords' | 'rules' | 'reviews' | 'profile'
const activeTab = ref<Tab>('reports')

interface Report {
  id: number
  user_id: number
  requester: string
  email_content: string
  status: string
  counselor_note: string
  created_at: string
}

interface ChatLog {
  id: number
  username: string
  role: string
  message: string
  is_spam: number | null
  created_at: string
}

interface Review {
  id: number
  stars: number
  comment: string
  created_at: string
  reviewer: string
  email_content: string
}

const reports = ref<Report[]>([])
const chatLogs = ref<ChatLog[]>([])
const reviews = ref<Review[]>([])
const loading = ref(false)
const selected = ref<Report | null>(null)
const note = ref('')
const keywords = ref('')
const submitting = ref(false)
const submitMsg = ref('')
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

const avgStars = computed(() => {
  if (!reviews.value.length) return 0
  return reviews.value.reduce((s, r) => s + r.stars, 0) / reviews.value.length
})

const starPercent = (n: number) => {
  const count = reviews.value.filter(r => r.stars === n).length
  return reviews.value.length ? Math.round((count / reviews.value.length) * 100) : 0
}

async function loadReports() {
  loading.value = true
  const res = await fetch(`${API}/spam-reports`, { headers: auth.authHeader() })
  if (res.ok) reports.value = await res.json()
  loading.value = false
}

const chatLogFilter = ref<'all' | 'spam' | 'ham'>('all')

const filteredChatLogs = computed(() => {
  if (chatLogFilter.value === 'spam') return chatLogs.value.filter(l => l.is_spam === 1)
  if (chatLogFilter.value === 'ham') return chatLogs.value.filter(l => l.is_spam === 0)
  return chatLogs.value
})

const spamCount = computed(() => chatLogs.value.filter(l => l.is_spam === 1).length)

async function loadChats() {
  const res = await fetch(`${API}/chat/all`, { headers: auth.authHeader() })
  if (res.ok) chatLogs.value = await res.json()
}

async function loadReviews() {
  const res = await fetch(`${API}/counselor-reviews/mine`, { headers: auth.authHeader() })
  if (res.ok) reviews.value = await res.json()
}

function select(r: Report) {
  selected.value = r
  note.value = r.counselor_note ?? ''
  keywords.value = ''
}

async function updateStatus(status: string) {
  if (!selected.value || submitting.value) return
  submitting.value = true
  submitMsg.value = ''
  const kwList = keywords.value.split('\n').map(k => k.trim()).filter(Boolean)
  await fetch(`${API}/spam-reports/${selected.value.id}`, {
    method: 'PATCH',
    headers: auth.authHeader(),
    body: JSON.stringify({ status, counselor_note: note.value, keywords: kwList }),
  })
  await loadReports()
  await loadKeywords()
  const updated = reports.value.find(r => r.id === selected.value!.id)
  if (updated) selected.value = updated
  submitting.value = false
  submitMsg.value = status === 'done' ? '처리 완료되었습니다!' : '처리중으로 변경되었습니다.'
  setTimeout(() => { submitMsg.value = '' }, 3000)
}

const statusLabel: Record<string, string> = { pending: '대기중', processing: '처리중', done: '완료' }

// ── AI 스팸 판별 (GPT + Qwen 두 모델) ────────────────────
interface ModelResult { is_spam: boolean; raw_answer: string; retrieved_count: number; model: string }
interface BothResult { gpt: ModelResult; qwen: ModelResult; final_is_spam: boolean; agreement: boolean }
interface CheckEntry { id: number; text: string; loading: boolean; result: BothResult | null; error: string }

const checkHistory = ref<CheckEntry[]>([])
const spamInput = ref('')
const spamLoading = ref(false)
const chatBody = ref<HTMLElement | null>(null)
let nextCheckId = 0

async function runSpamCheck() {
  const text = spamInput.value.trim()
  if (!text || spamLoading.value) return
  spamInput.value = ''
  spamLoading.value = true
  const idx = checkHistory.value.length
  checkHistory.value.push({ id: nextCheckId++, text, loading: true, result: null, error: '' })
  await nextTick()
  chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
  try {
    const res = await fetch(`${API}/rag/classify`, {
      method: 'POST',
      headers: auth.authHeader(),
      body: JSON.stringify({ text, model: 'both' }),
    })
    const d = await res.json()
    console.log('[spam-check] status:', res.status, 'body:', JSON.stringify(d))
    // 객체 전체 교체 → Vue 반응성 확실하게 트리거
    if (res.ok) checkHistory.value[idx] = { ...checkHistory.value[idx], loading: false, result: d }
    else checkHistory.value[idx] = { ...checkHistory.value[idx], loading: false, error: d.detail || '오류 발생' }
  } catch {
    checkHistory.value[idx] = { ...checkHistory.value[idx], loading: false, error: '서버 연결 실패' }
  } finally {
    spamLoading.value = false
    await nextTick()
    chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
  }
}

function onSpamKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runSpamCheck() }
}

function autoResizeChat(e: Event) {
  const ta = e.target as HTMLTextAreaElement
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
}

// ── 처리 요청 탭 키워드 즉시 등록 ────────────────────────
const kwInstantLoading = ref(false)
const kwInstantMsg = ref('')
const kwInstantErr = ref('')
const kwSingleInput = ref('')

async function addSingleKeyword() {
  kwInstantMsg.value = ''; kwInstantErr.value = ''
  const kw = kwSingleInput.value.trim()
  if (!kw) return
  kwInstantLoading.value = true
  try {
    const res = await fetch(`${API}/spam-keywords`, {
      method: 'POST', headers: auth.authHeader(),
      body: JSON.stringify({ keyword: kw }),
    })
    const d = await res.json()
    if (res.ok) {
      kwInstantMsg.value = `"${kw}" 등록 완료!`
      kwSingleInput.value = ''
      await loadKeywords()
    } else {
      kwInstantErr.value = d.detail || '등록 실패'
    }
  } catch {
    kwInstantErr.value = '서버 연결 실패'
  } finally {
    kwInstantLoading.value = false
  }
}

// ── 스팸 키워드 관리 (상담사 직접 등록) ─────────────────
interface Keyword { id: number; keyword: string; created_at: string }
const kwList = ref<Keyword[]>([])
const kwInput = ref('')
const kwLoading = ref(false)
const kwMsg = ref('')
const kwErr = ref('')
const kwSearch = ref('')
const kwDeletingId = ref<number | null>(null)

const filteredKw = computed(() =>
  kwSearch.value.trim() ? kwList.value.filter(k => k.keyword.includes(kwSearch.value.trim())) : kwList.value
)

async function loadKeywords() {
  const res = await fetch(`${API}/spam-keywords`, { headers: auth.authHeader() })
  if (res.ok) kwList.value = await res.json()
}

async function addKeyword() {
  kwMsg.value = ''; kwErr.value = ''
  const kw = kwInput.value.trim()
  if (!kw) { kwErr.value = '키워드를 입력해주세요'; return }
  kwLoading.value = true
  try {
    const res = await fetch(`${API}/spam-keywords`, {
      method: 'POST', headers: auth.authHeader(),
      body: JSON.stringify({ keyword: kw }),
    })
    const d = await res.json()
    if (res.ok) { kwMsg.value = `"${kw}" 등록 완료!`; kwInput.value = ''; await loadKeywords() }
    else kwErr.value = d.detail || '오류 발생'
  } catch { kwErr.value = '서버 연결 실패' }
  finally { kwLoading.value = false }
}

async function deleteKeyword(id: number) {
  if (kwDeletingId.value !== null) return
  kwDeletingId.value = id
  await fetch(`${API}/spam-keywords/${id}`, { method: 'DELETE', headers: auth.authHeader() })
  await loadKeywords()
  kwDeletingId.value = null
}

function onKwEnter(e: KeyboardEvent) {
  if (e.key === 'Enter') addKeyword()
}

// ── 스팸 규칙 ─────────────────────────────────────────
interface SpamRule { id: number; rule_type: string; value: string; created_at: string }
const spamRules = ref<SpamRule[]>([])
const ruleType = ref<'keyword' | 'sentence' | 'email'>('keyword')
const ruleValue = ref('')
const ruleLoading = ref(false)
const ruleMsg = ref('')
const ruleTypeLabels: Record<string, string> = { keyword: '단어', sentence: '문장', email: '이메일 주소' }

async function loadRules() {
  const res = await fetch(`${API}/user-spam-rules`, { headers: auth.authHeader() })
  if (res.ok) spamRules.value = await res.json()
}

async function addRule() {
  if (!ruleValue.value.trim() || ruleLoading.value) return
  ruleLoading.value = true; ruleMsg.value = ''
  try {
    const res = await fetch(`${API}/user-spam-rules`, {
      method: 'POST', headers: auth.authHeader(),
      body: JSON.stringify({ rule_type: ruleType.value, value: ruleValue.value.trim() }),
    })
    if (res.ok) { ruleValue.value = ''; await loadRules() }
    else { const d = await res.json(); ruleMsg.value = d.detail || '오류' }
  } finally { ruleLoading.value = false }
}

async function deleteRule(id: number) {
  await fetch(`${API}/user-spam-rules/${id}`, { method: 'DELETE', headers: auth.authHeader() })
  await loadRules()
}

// ── 내 정보 ───────────────────────────────────────────
interface Profile { username: string; nickname: string; name: string; phone: string; email: string; address: string; detail_address: string; postal_code: string; role: string; created_at: string }
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

async function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'reports') await loadReports()
  if (tab === 'reviews') await loadReviews()
  if (tab === 'profile') await loadProfile()
  if (tab === 'rules') await loadRules()
  if (tab === 'keywords') await loadKeywords()
}

function logout() { auth.logout(); router.push('/login') }

onMounted(() => { loadReports(); loadProfile(); loadKeywords() })
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
              <span class="role-pill counselor">상담원</span>
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
              처리 요청
              <span v-if="counts.pending" class="nav-badge">{{ counts.pending }}</span>
            </button>
            <button :class="['nav-item', { active: activeTab === 'spam-check' }]" @click="switchTab('spam-check')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </span>
              AI 스팸 판별
            </button>
            <button :class="['nav-item', { active: activeTab === 'keywords' }]" @click="switchTab('keywords')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
              </span>
              스팸 키워드
              <span v-if="kwList.length" class="nav-cnt">{{ kwList.length }}</span>
            </button>
            <button :class="['nav-item', { active: activeTab === 'rules' }]" @click="switchTab('rules')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </span>
              스팸 규칙
            </button>
            <button :class="['nav-item', { active: activeTab === 'reviews' }]" @click="switchTab('reviews')">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
              </span>
              내 평가
              <span v-if="reviews.length" class="nav-cnt">{{ reviews.length }}</span>
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

      <!-- 처리 요청 탭 -->
      <template v-if="activeTab === 'reports'">
        <div class="list-panel">
          <div class="list-header">
            <div class="list-header-top">
              <h2 class="list-title">처리 요청 목록</h2>
              <button class="refresh-btn" @click="loadReports">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="23 4 23 10 17 10"/>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
              </button>
            </div>
            <div class="filter-pills">
              <button
                v-for="[k,l] in [['all','전체'],['pending','대기'],['processing','처리중'],['done','완료']]"
                :key="k"
                :class="['pill', { active: filterStatus === k }]"
                @click="filterStatus = k"
              >
                {{ l }}
                <span class="pill-cnt">{{ counts[k as keyof typeof counts] }}</span>
              </button>
            </div>
          </div>

          <div v-if="loading" class="loading-state">
            <div class="spinner-ring" />
          </div>
          <div v-else-if="!filtered.length" class="empty-state-sm">요청이 없습니다.</div>

          <div v-else class="report-list">
            <div
              v-for="r in filtered" :key="r.id"
              :class="['report-card', { selected: selected?.id === r.id }]"
              @click="select(r)"
            >
              <div class="rc-top">
                <span :class="['status-pill', `st-${r.status}`]">{{ statusLabel[r.status] }}</span>
                <span class="rc-date">{{ new Date(r.created_at).toLocaleDateString('ko-KR') }}</span>
              </div>
              <p class="rc-user">{{ r.requester }}</p>
              <p class="rc-preview">{{ r.email_content.slice(0,60) }}{{ r.email_content.length > 60 ? '...' : '' }}</p>
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
                <p class="detail-user">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                  {{ selected.requester }}
                </p>
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

            <!-- 스팸 키워드 등록 -->
            <div class="kw-register-box">
              <div class="kw-register-header">
                <span class="kw-register-title">스팸 키워드 등록</span>
                <span class="kw-register-count">현재 {{ kwList.length }}개 등록됨</span>
              </div>
              <div class="kw-register-row">
                <input
                  v-model="kwSingleInput"
                  class="kw-register-input"
                  placeholder="스팸 단어 또는 문장 입력 후 Enter"
                  @keydown.enter="addSingleKeyword"
                />
                <button class="kw-register-btn" :disabled="!kwSingleInput.trim() || kwInstantLoading" @click="addSingleKeyword">
                  {{ kwInstantLoading ? '...' : '+ 등록' }}
                </button>
              </div>
              <p v-if="kwInstantMsg" class="kw-instant-msg ok">✅ {{ kwInstantMsg }}</p>
              <p v-if="kwInstantErr" class="kw-instant-msg err">⚠️ {{ kwInstantErr }}</p>
              <!-- 등록된 키워드 목록 (최근 10개) -->
              <div v-if="kwList.length" class="kw-register-list">
                <span v-for="kw in kwList.slice(0,10)" :key="kw.id" class="kw-mini-chip">{{ kw.keyword }}</span>
                <span v-if="kwList.length > 10" class="kw-mini-more">+{{ kwList.length - 10 }}개</span>
              </div>
            </div>

            <Transition name="fade">
              <div v-if="submitMsg" class="submit-msg" :class="{ done: submitMsg.includes('완료') }">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                {{ submitMsg }}
              </div>
            </Transition>

            <div class="action-btns">
              <button
                :class="['action-btn', 'btn-processing']"
                :disabled="submitting || selected.status === 'processing'"
                @click="updateStatus('processing')"
              >
                처리중으로 변경
              </button>
              <button
                :class="['action-btn', 'btn-done']"
                :disabled="submitting || selected.status === 'done'"
                @click="updateStatus('done')"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                처리 완료
              </button>
            </div>
          </div>
        </div>
      </template>
      <div v-if="activeTab === 'spam-check'" class="full-panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">AI 스팸 판별</h2>
            <p class="panel-desc">GPT + Qwen 두 AI가 각각 판단하고 결과를 비교합니다</p>
          </div>
          <div class="header-badge-active">
            <span class="dot-green" />
            <span>GPT + Qwen 활성화</span>
          </div>
        </div>

        <!-- 결과 히스토리 (스크롤 영역) -->
        <div class="sc-chat-body" ref="chatBody">
          <div v-if="!checkHistory.length" style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
            <p style="font-size:15px;font-weight:700;color:#1e1b4b">분석 준비 완료</p>
            <p style="font-size:13px;color:#9ca3af">의심스러운 단어나 문장을 입력해보세요</p>
          </div>

          <div v-for="entry in checkHistory" :key="entry.id" class="check-entry">
            <div class="check-query">
              <span class="check-query-label">입력</span>
              <span class="check-query-text">{{ entry.text }}</span>
            </div>
            <div v-if="entry.loading" style="display:flex;align-items:center;gap:8px;padding:8px 0">
              <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              <span style="font-size:13px;color:#6b7280">GPT + Qwen 분석 중...</span>
            </div>
            <p v-else-if="entry.error" style="color:#ef4444;font-size:13px;margin:4px 0">{{ entry.error }}</p>
            <div v-else-if="entry.result">
              <!-- 디버그: 임시 JSON 표시 -->
              <pre style="font-size:10px;background:#f3f4f6;padding:8px;border-radius:8px;overflow:auto;margin-bottom:12px;white-space:pre-wrap">{{ JSON.stringify(entry.result, null, 2) }}</pre>
              <!-- 최종 판정 -->
              <div :style="{
                display:'flex', alignItems:'center', gap:'12px', padding:'12px 16px',
                borderRadius:'10px', fontSize:'14px', fontWeight:'600', marginBottom:'12px',
                background: entry.result.final_is_spam ? '#fef2f2' : '#f0fdf4',
                border: '1.5px solid ' + (entry.result.final_is_spam ? '#fca5a5' : '#86efac'),
                color: entry.result.final_is_spam ? '#b91c1c' : '#15803d'
              }">
                <span style="font-size:18px">{{ entry.result.final_is_spam ? '🚨' : '✅' }}</span>
                <span style="flex:1">최종 판정: {{ entry.result.final_is_spam ? '스팸' : '정상' }}</span>
                <span :style="{
                  fontSize:'12px', padding:'2px 10px', borderRadius:'20px',
                  background: entry.result.agreement ? '#dcfce7' : '#fef9c3',
                  color: entry.result.agreement ? '#15803d' : '#b45309'
                }">{{ entry.result.agreement ? '두 모델 일치 ✓' : '두 모델 불일치 ⚠' }}</span>
              </div>
              <!-- 두 모델 카드 (인라인 grid) -->
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <!-- GPT 카드 -->
                <div :style="{
                  borderRadius:'10px', padding:'14px', border:'1.5px solid',
                  background: entry.result.gpt?.is_spam ? '#fef2f2' : '#f0fdf4',
                  borderColor: entry.result.gpt?.is_spam ? '#fca5a5' : '#86efac'
                }">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <span style="font-size:13px;font-weight:700;color:#374151">🤖 GPT-4o-mini</span>
                    <span :style="{
                      fontSize:'12px', fontWeight:'700', padding:'2px 10px', borderRadius:'20px',
                      background: entry.result.gpt?.is_spam ? '#fee2e2' : '#dcfce7',
                      color: entry.result.gpt?.is_spam ? '#b91c1c' : '#15803d'
                    }">{{ entry.result.gpt?.is_spam ? '스팸' : '정상' }}</span>
                  </div>
                  <div style="font-size:12.5px;color:#4b5563;line-height:1.6;white-space:pre-wrap;word-break:break-word;margin-bottom:6px">{{ entry.result.gpt?.raw_answer || '-' }}</div>
                  <div style="font-size:11px;color:#9ca3af">참조 예시 {{ entry.result.gpt?.retrieved_count ?? 0 }}개</div>
                </div>
                <!-- Qwen 카드 -->
                <div :style="{
                  borderRadius:'10px', padding:'14px', border:'1.5px solid',
                  background: entry.result.qwen?.is_spam ? '#fef2f2' : '#f0fdf4',
                  borderColor: entry.result.qwen?.is_spam ? '#fca5a5' : '#86efac'
                }">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <span style="font-size:13px;font-weight:700;color:#374151">🧠 Qwen2.5-1.5b</span>
                    <span :style="{
                      fontSize:'12px', fontWeight:'700', padding:'2px 10px', borderRadius:'20px',
                      background: entry.result.qwen?.is_spam ? '#fee2e2' : '#dcfce7',
                      color: entry.result.qwen?.is_spam ? '#b91c1c' : '#15803d'
                    }">{{ entry.result.qwen?.error ? 'Qwen 오류' : (entry.result.qwen?.is_spam ? '스팸' : '정상') }}</span>
                  </div>
                  <div style="font-size:12.5px;color:#4b5563;line-height:1.6;white-space:pre-wrap;word-break:break-word;margin-bottom:6px">{{ entry.result.qwen?.raw_answer || entry.result.qwen?.error || '-' }}</div>
                  <div style="font-size:11px;color:#9ca3af">참조 예시 {{ entry.result.qwen?.retrieved_count ?? 0 }}개</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 입력창 (하단 고정) -->
        <div class="sc-input-bar">
          <textarea
            v-model="spamInput" class="spam-check-input"
            placeholder="단어 또는 문장을 입력하세요... (Enter 전송)"
            rows="1" @keydown="onSpamKey" @input="autoResizeChat"
          ></textarea>
          <button class="sc-send-btn" :disabled="!spamInput.trim() || spamLoading" @click="runSpamCheck">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </div>
      <div v-if="activeTab === 'keywords'" class="full-panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">스팸 키워드 관리</h2>
            <p class="panel-desc">스팸 단어·문장을 직접 등록하고 관리합니다</p>
          </div>
          <span class="kw-total-badge">총 {{ kwList.length }}개</span>
        </div>
        <div class="kw-mgr-body">
          <!-- 등록 폼 -->
          <div class="kw-add-box">
            <div class="kw-add-row">
              <input
                v-model="kwInput"
                class="kw-add-input"
                placeholder="등록할 스팸 단어 또는 문장 입력..."
                @keydown="onKwEnter"
              />
              <button class="kw-add-btn" :disabled="kwLoading || !kwInput.trim()" @click="addKeyword">
                {{ kwLoading ? '등록 중...' : '+ 등록' }}
              </button>
            </div>
            <p v-if="kwMsg" class="kw-msg ok">✅ {{ kwMsg }}</p>
            <p v-if="kwErr" class="kw-msg err">⚠️ {{ kwErr }}</p>
          </div>

          <!-- 검색 + 목록 -->
          <div class="kw-list-section">
            <div class="kw-search-row">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;color:#9ca3af">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input v-model="kwSearch" class="kw-search-input" placeholder="키워드 검색..."/>
            </div>
            <div v-if="!filteredKw.length" class="empty-state-sm">
              {{ kwSearch ? '검색 결과가 없습니다.' : '등록된 키워드가 없습니다.' }}
            </div>
            <div class="kw-chip-grid">
              <div v-for="kw in filteredKw" :key="kw.id" class="kw-chip">
                <span class="kw-chip-text">{{ kw.keyword }}</span>
                <span class="kw-chip-date">{{ new Date(kw.created_at).toLocaleDateString('ko-KR') }}</span>
                <button class="kw-chip-del" :disabled="kwDeletingId === kw.id" @click="deleteKeyword(kw.id)" title="삭제">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="activeTab === 'rules'" class="full-panel">
        <div class="panel-header">
          <div>
            <h2 class="panel-title">내 스팸 규칙</h2>
            <p class="panel-desc">등록한 단어·문장·이메일이 포함된 메일은 스팸으로 판별됩니다</p>
          </div>
        </div>
        <div class="profile-body">
          <div class="rule-add-box">
            <div class="rule-type-tabs">
              <button v-for="t in ['keyword','sentence','email']" :key="t"
                :class="['rule-type-btn', { active: ruleType === t }]"
                @click="ruleType = (t as any)">
                {{ ruleTypeLabels[t] }}
              </button>
            </div>
            <div class="rule-input-row">
              <input
                v-model="ruleValue" class="rule-input"
                :placeholder="ruleType === 'email' ? '차단할 이메일 주소 입력' : ruleType === 'sentence' ? '차단할 문장 입력' : '차단할 단어 입력'"
                @keydown.enter="addRule"
              />
              <button class="btn-rule-add" :disabled="!ruleValue.trim() || ruleLoading" @click="addRule">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                추가
              </button>
            </div>
            <p v-if="ruleMsg" class="rule-err">{{ ruleMsg }}</p>
          </div>
          <div class="rule-list-wrap">
            <div v-if="!spamRules.length" class="empty-state-sm" style="padding:24px 0">등록된 규칙이 없습니다.</div>
            <div v-else>
              <div v-for="group in ['keyword','sentence','email']" :key="group">
                <div v-if="spamRules.filter(r=>r.rule_type===group).length" class="rule-group">
                  <div class="rule-group-title">{{ ruleTypeLabels[group] }}</div>
                  <div class="rule-chips">
                    <div v-for="r in spamRules.filter(x=>x.rule_type===group)" :key="r.id" class="rule-chip">
                      <span class="rule-chip-val">{{ r.value }}</span>
                      <button class="rule-chip-del" @click="deleteRule(r.id)">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="activeTab === 'reviews'" class="full-panel">
        <div class="panel-header">
          <h2 class="panel-title">내 평가</h2>
          <button class="refresh-btn" @click="loadReviews">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
        </div>

        <div class="reviews-body">
          <!-- 통계 카드 -->
          <div v-if="reviews.length" class="stats-card">
            <div class="stats-avg">
              <span class="avg-number">{{ avgStars.toFixed(1) }}</span>
              <div class="avg-stars">
                <span
                  v-for="i in 5" :key="i"
                  class="avg-star"
                  :class="{
                    full: i <= Math.floor(avgStars),
                    half: i === Math.ceil(avgStars) && avgStars % 1 >= 0.3 && avgStars % 1 < 0.8,
                    empty: i > Math.ceil(avgStars) || (i === Math.ceil(avgStars) && avgStars % 1 < 0.3)
                  }"
                >★</span>
              </div>
              <p class="avg-count">총 {{ reviews.length }}개 평가</p>
            </div>
            <div class="stats-bars">
              <div v-for="n in [5,4,3,2,1]" :key="n" class="bar-row">
                <span class="bar-label">{{ n }}점</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: starPercent(n) + '%', background: n >= 4 ? '#f59e0b' : n === 3 ? '#fb923c' : '#ef4444' }" />
                </div>
                <span class="bar-pct">{{ starPercent(n) }}%</span>
              </div>
            </div>
          </div>

          <div v-if="!reviews.length" class="empty-state-reviews">
            <div class="empty-star-icon">
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
            </div>
            <p>아직 받은 평가가 없습니다.</p>
            <span>상담을 완료하면 사용자로부터 평가를 받을 수 있어요.</span>
          </div>

          <div v-else class="review-list">
            <div v-for="rv in reviews" :key="rv.id" class="review-item">
              <div class="review-top">
                <div class="review-stars">
                  <span v-for="i in 5" :key="i" class="r-star" :class="{ filled: i <= rv.stars }">★</span>
                </div>
                <span class="review-date">{{ new Date(rv.created_at).toLocaleDateString('ko-KR') }}</span>
              </div>
              <p v-if="rv.comment" class="review-comment">{{ rv.comment }}</p>
              <p v-else class="review-no-comment">코멘트 없음</p>
              <div class="review-meta">
                <span class="reviewer-name">{{ rv.reviewer }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="activeTab === 'profile'" class="full-panel">
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
              <div class="pfield"><span class="pfield-label">역할</span><span class="pfield-val">{{ profile.role }}</span></div>
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
              <div class="pfield"><label class="pfield-label">이메일</label><input class="pfield-input" v-model="profileForm.email" placeholder="example@email.com" /></div>
              <div class="pfield"><label class="pfield-label">우편번호</label><input class="pfield-input" v-model="profileForm.postal_code" placeholder="우편번호 입력" /></div>
              <div class="pfield pfield-full"><label class="pfield-label">주소</label><input class="pfield-input" v-model="profileForm.address" placeholder="기본 주소 입력" /></div>
              <div class="pfield pfield-full"><label class="pfield-label">상세주소</label><input class="pfield-input" v-model="profileForm.detail_address" placeholder="상세 주소 입력 (동, 호수 등)" /></div>
            </div>
            <div class="profile-section-title" style="margin-top:28px">비밀번호 변경 <span style="font-weight:400;color:#b0b8c8;font-size:11px">(변경하지 않으려면 비워두세요)</span></div>
            <div class="profile-grid">
              <div class="pfield pfield-full"><label class="pfield-label">현재 비밀번호</label><input class="pfield-input" type="password" v-model="profilePwForm.current_password" placeholder="현재 비밀번호 입력" /></div>
              <div class="pfield"><label class="pfield-label">새 비밀번호</label><input class="pfield-input" type="password" v-model="profilePwForm.new_password" placeholder="새 비밀번호 (4자 이상)" /></div>
              <div class="pfield"><label class="pfield-label">새 비밀번호 확인</label><input class="pfield-input" type="password" v-model="profilePwForm.confirm_password" placeholder="새 비밀번호 재입력" /></div>
            </div>
            <p v-if="profileErr" style="color:#ef4444;font-size:13px;margin-top:8px">{{ profileErr }}</p>
            <p v-if="profileMsg" style="color:#10b981;font-size:13px;margin-top:8px">{{ profileMsg }}</p>
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
  background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  position: relative;
  overflow: hidden;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  opacity: 0.2;
  pointer-events: none;
}
.orb1 { width: 500px; height: 500px; background: #3b82f6; top: -150px; left: -100px; }
.orb2 { width: 350px; height: 350px; background: #6366f1; bottom: -100px; right: -80px; }

.layout {
  width: 100%;
  max-width: 1200px;
  height: min(880px, 94vh);
  display: flex;
  background: #fff;
  border-radius: 28px;
  box-shadow: 0 32px 80px rgba(0,0,0,0.35);
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* Sidebar */
.sidebar {
  width: 230px;
  flex-shrink: 0;
  background: #13111c;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 24px 16px;
}

.sidebar-top { display: flex; flex-direction: column; gap: 6px; }

.brand { display: flex; align-items: center; gap: 10px; padding: 0 8px; margin-bottom: 16px; }
.brand-icon {
  width: 36px; height: 36px; border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  display: flex; align-items: center; justify-content: center;
  color: #fff; box-shadow: 0 4px 12px rgba(59,130,246,0.4);
}
.brand-name { font-size: 15px; font-weight: 800; color: #fff; letter-spacing: -0.3px; }

.user-card {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 14px; background: rgba(255,255,255,0.06);
  border-radius: 14px; border: 1px solid rgba(255,255,255,0.08);
  margin-bottom: 12px;
}
.avatar {
  width: 38px; height: 38px; border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #1d4ed8);
  color: #fff; font-weight: 800; font-size: 15px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; box-shadow: 0 3px 10px rgba(59,130,246,0.35);
}
.user-info { display: flex; flex-direction: column; gap: 4px; }
.user-name { font-size: 13px; font-weight: 700; color: #fff; }
.role-pill { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 99px; width: fit-content; }
.role-pill.counselor { background: rgba(29,78,216,0.3); color: #93c5fd; border: 1px solid rgba(29,78,216,0.4); }

.nav { display: flex; flex-direction: column; gap: 3px; }

.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 12px; border: none;
  background: transparent; color: rgba(255,255,255,0.5);
  font-size: 13.5px; font-weight: 500; cursor: pointer;
  text-align: left; transition: all 0.2s; position: relative;
}
.nav-item:hover { background: rgba(255,255,255,0.07); color: rgba(255,255,255,0.85); }
.nav-item.active { background: linear-gradient(135deg, rgba(59,130,246,0.25), rgba(99,102,241,0.2)); color: #fff; }
.nav-icon { display: flex; align-items: center; color: rgba(255,255,255,0.35); transition: color 0.2s; }
.nav-item.active .nav-icon { color: #93c5fd; }

.nav-badge {
  margin-left: auto; background: #ef4444; color: #fff;
  font-size: 10px; font-weight: 800; padding: 2px 7px;
  border-radius: 99px; animation: pulse 2s infinite;
}
.nav-cnt {
  margin-left: auto; font-size: 10px; font-weight: 700;
  background: rgba(255,255,255,0.1); padding: 1px 7px; border-radius: 99px; color: rgba(255,255,255,0.6);
}

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }

.bottom-btns { display: flex; flex-direction: column; gap: 6px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.08); }

.home-btn { display: flex; align-items: center; gap: 8px; padding: 11px 14px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.12); background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.75); font-size: 13.5px; font-weight: 600; cursor: pointer; transition: all 0.2s; width: 100%; }
.home-btn:hover { background: rgba(255,255,255,0.12); color: #fff; }

.logout-btn { display: flex; align-items: center; gap: 8px; padding: 11px 14px; border-radius: 12px; border: 1px solid rgba(239,68,68,0.25); background: rgba(239,68,68,0.08); color: #f87171; font-size: 13.5px; font-weight: 600; cursor: pointer; transition: all 0.2s; width: 100%; }
.logout-btn:hover { background: rgba(239,68,68,0.2); border-color: rgba(239,68,68,0.5); color: #fca5a5; }

/* List panel */
.list-panel {
  width: 300px; flex-shrink: 0; border-right: 1px solid #f1f0f9;
  display: flex; flex-direction: column;
}

.list-header {
  padding: 20px 16px 14px;
  border-bottom: 1px solid #f1f0f9;
  flex-shrink: 0;
}
.list-header-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.list-title { font-size: 15px; font-weight: 800; color: #1e1b4b; }

.refresh-btn {
  width: 30px; height: 30px; border-radius: 8px;
  border: 1.5px solid #e8e6f0; background: #fff;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: #9ca3af; transition: all 0.15s;
}
.refresh-btn:hover { border-color: #6366f1; color: #6366f1; }

.filter-pills { display: flex; flex-wrap: wrap; gap: 4px; }
.pill {
  padding: 5px 10px; border-radius: 99px; border: 1.5px solid #e8e6f0;
  background: #fff; font-size: 11.5px; font-weight: 600; color: #6b7280;
  cursor: pointer; transition: all 0.15s;
}
.pill:hover { border-color: #6366f1; color: #6366f1; }
.pill.active { border-color: #6366f1; background: #ede9fe; color: #6366f1; }
.pill-spam.active { border-color: #dc2626; background: #fef2f2; color: #dc2626; }
.pill-spam:hover { border-color: #dc2626; color: #dc2626; }
.pill-ham.active { border-color: #059669; background: #f0fdf4; color: #059669; }
.pill-ham:hover { border-color: #059669; color: #059669; }
.log-spam { border-left: 3px solid #fca5a5 !important; background: #fff9f9 !important; }
.pill-cnt { font-size: 10.5px; margin-left: 3px; opacity: 0.7; }

.loading-state { flex: 1; display: flex; align-items: center; justify-content: center; }
.spinner-ring {
  width: 28px; height: 28px; border: 2.5px solid #e8e6f0;
  border-top-color: #6366f1; border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state-sm { padding: 40px 20px; text-align: center; font-size: 13.5px; color: #9ca3af; }

.report-list {
  flex: 1; overflow-y: auto; padding: 12px;
}
.report-list::-webkit-scrollbar { width: 4px; }
.report-list::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.report-card {
  padding: 13px; border-radius: 14px; border: 1.5px solid #f1f0f9;
  margin-bottom: 8px; cursor: pointer; transition: all 0.2s;
}
.report-card:hover { border-color: #c7d2fe; background: #f5f4ff; }
.report-card.selected { border-color: #6366f1; background: #ede9fe; }

.rc-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.rc-date { font-size: 11px; color: #9ca3af; }
.rc-user { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.rc-preview { font-size: 13px; color: #374151; line-height: 1.4; }

/* Detail panel */
.detail-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.detail-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  color: #9ca3af; font-size: 14px; gap: 12px;
}
.detail-empty-icon {
  width: 72px; height: 72px; border-radius: 20px;
  background: #f5f4ff; display: flex; align-items: center; justify-content: center;
}

.detail-content { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }

.detail-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 22px 26px 18px; border-bottom: 1px solid #f1f0f9; flex-shrink: 0;
}
.detail-title { font-size: 18px; font-weight: 800; color: #1e1b4b; }
.detail-user {
  display: flex; align-items: center; gap: 5px;
  font-size: 13px; color: #6b7280; margin-top: 4px;
}

.email-box { margin: 20px 26px; padding: 16px 18px; background: #faf9ff; border-radius: 16px; border: 1.5px solid #f1f0f9; flex-shrink: 0; }
.box-label { font-size: 11px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px; }
.email-content { font-size: 14px; color: #374151; line-height: 1.65; white-space: pre-wrap; }

.note-section { margin: 0 26px; flex-shrink: 0; }
.note-label { display: block; font-size: 13px; font-weight: 700; color: #374151; margin-bottom: 7px; }
.note-hint { font-size: 12px; font-weight: 400; color: #9ca3af; }
.note-input {
  width: 100%; padding: 12px 14px; border: 1.5px solid #e8e6f0;
  border-radius: 14px; font-size: 14px; font-family: inherit;
  resize: vertical; outline: none; background: #faf9ff;
  transition: border-color 0.2s, box-shadow 0.2s; box-sizing: border-box;
}
.note-input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); background: #fff; }

.action-btns { display: flex; gap: 10px; padding: 18px 26px; margin-top: auto; border-top: 1px solid #f1f0f9; flex-shrink: 0; }
.action-btn { flex: 1; padding: 12px; border: none; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px; }
.action-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-processing { background: #dbeafe; color: #1d4ed8; }
.btn-processing:hover:not(:disabled) { background: #bfdbfe; }
.btn-done { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; box-shadow: 0 3px 10px rgba(99,102,241,0.3); }
.btn-done:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); }

/* Status */
.status-pill { font-size: 11px; font-weight: 700; padding: 4px 11px; border-radius: 99px; }
.st-pending    { background: #fef3c7; color: #92400e; }
.st-processing { background: #dbeafe; color: #1d4ed8; }
.st-done       { background: #d1fae5; color: #065f46; }

/* Full panels */
.full-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 22px 26px 18px; border-bottom: 1px solid #f1f0f9; flex-shrink: 0;
}
.panel-title { font-size: 16px; font-weight: 800; color: #1e1b4b; }

/* Chat log */
.chat-log-list {
  flex: 1; overflow-y: auto; padding: 14px 20px;
  display: flex; flex-direction: column; gap: 8px;
}
.chat-log-list::-webkit-scrollbar { width: 4px; }
.chat-log-list::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.chat-log-item { padding: 13px 16px; border-radius: 14px; border: 1.5px solid #f1f0f9; }
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
.reviews-body { flex: 1; overflow-y: auto; padding: 20px 26px; }
.reviews-body::-webkit-scrollbar { width: 4px; }
.reviews-body::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.stats-card {
  display: flex;
  gap: 32px;
  padding: 24px 28px;
  background: linear-gradient(135deg, #faf9ff, #f5f4ff);
  border: 1.5px solid #ede9fe;
  border-radius: 20px;
  margin-bottom: 20px;
  align-items: center;
}

.stats-avg { display: flex; flex-direction: column; align-items: center; gap: 8px; flex-shrink: 0; }
.avg-number { font-size: 52px; font-weight: 900; color: #1e1b4b; line-height: 1; letter-spacing: -2px; }
.avg-stars { display: flex; gap: 4px; }
.avg-star { font-size: 22px; color: #e5e7eb; transition: color 0.15s; }
.avg-star.full { color: #f59e0b; }
.avg-star.half { color: #fcd34d; }
.avg-count { font-size: 13px; color: #7c7c9a; font-weight: 500; }

.stats-bars { flex: 1; display: flex; flex-direction: column; gap: 9px; }
.bar-row { display: flex; align-items: center; gap: 10px; }
.bar-label { font-size: 12px; font-weight: 600; color: #6b7280; width: 28px; text-align: right; flex-shrink: 0; }
.bar-track { flex: 1; height: 8px; background: #f1f0f9; border-radius: 99px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 99px; transition: width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
.bar-pct { font-size: 11.5px; color: #9ca3af; width: 32px; flex-shrink: 0; }

.empty-state-reviews {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 10px; padding: 60px 0; text-align: center; color: #9ca3af;
}
.empty-star-icon {
  width: 72px; height: 72px; border-radius: 20px;
  background: #f5f4ff; display: flex; align-items: center; justify-content: center;
  margin-bottom: 4px;
}
.empty-state-reviews p { font-size: 15px; font-weight: 600; color: #374151; }
.empty-state-reviews span { font-size: 13px; }

.review-list { display: flex; flex-direction: column; gap: 12px; }

.review-item {
  padding: 16px 18px; border: 1.5px solid #f1f0f9;
  border-radius: 16px; background: #faf9ff;
  transition: all 0.15s;
}
.review-item:hover { border-color: #c7d2fe; background: #f5f4ff; }

.review-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.review-stars { display: flex; gap: 3px; }
.r-star { font-size: 18px; color: #e5e7eb; transition: color 0.1s; }
.r-star.filled { color: #f59e0b; }
.review-date { font-size: 12px; color: #9ca3af; }

.review-comment { font-size: 14px; color: #374151; line-height: 1.6; margin-bottom: 10px; }
.review-no-comment { font-size: 13px; color: #c4c4cc; margin-bottom: 10px; font-style: italic; }

.review-meta { display: flex; align-items: center; }
.reviewer-name {
  font-size: 12px; font-weight: 600; color: #6b7280;
  background: #f3f4f6; padding: 3px 10px; border-radius: 99px;
}

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

/* AI 스팸 판별 */
.header-badge-active { display:flex;align-items:center;gap:7px;padding:7px 14px;background:#ecfdf5;border:1px solid #a7f3d0;border-radius:99px;font-size:12px;font-weight:600;color:#059669; }
.dot-green { width:7px;height:7px;border-radius:50%;background:#10b981;animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1}50%{opacity:0.7} }
.sc-chat-body { flex:1;overflow-y:auto;padding:24px 28px;display:flex;flex-direction:column; }
.sc-chat-body::-webkit-scrollbar{width:5px}.sc-chat-body::-webkit-scrollbar-thumb{background:#e8e6f0;border-radius:99px}
.sc-messages { display:flex;flex-direction:column;gap:14px; }
.sc-msg-row { display:flex;align-items:flex-end;gap:8px; }
.sc-msg-row.user { justify-content:flex-end; }
.sc-ai-avatar { width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0; }
.sc-bubble { max-width:68%;padding:12px 16px;border-radius:20px;font-size:14px;line-height:1.55;word-break:break-word; }
.sc-bubble.user { background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;border-bottom-right-radius:6px; }
.sc-bubble.ai:not(.bubble-spam):not(.bubble-ham) { background:#f0f4ff;color:#374151;border:1.5px solid #dbeafe;border-bottom-left-radius:6px; }
.sc-bubble.bubble-spam { background:#fef2f2;color:#374151;border:1.5px solid #fecaca;border-bottom-left-radius:6px; }
.sc-bubble.bubble-ham { background:#f0fdf4;color:#374151;border:1.5px solid #bbf7d0;border-bottom-left-radius:6px; }
.sc-label { display:block;font-size:11px;font-weight:700;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px; }
.sc-label.spam { color:#dc2626; } .sc-label.ham { color:#059669; }
.loading-bubble { display:flex;align-items:center;gap:5px;padding:14px 18px; }
.dot { width:7px;height:7px;border-radius:50%;background:#9ca3af;animation:bounce 1.2s infinite ease-in-out; }
.dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}
@keyframes bounce{0%,80%,100%{transform:scale(.8);opacity:.5}40%{transform:scale(1.2);opacity:1}}
.sc-input-bar { display:flex;align-items:flex-end;gap:10px;padding:16px 22px;border-top:1px solid #f1f0f9;background:#f8faff;flex-shrink:0; }
.sc-upload-btn { width:46px;height:46px;border-radius:14px;border:1.5px solid #dbeafe;background:#f0f4ff;color:#3b82f6;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all .2s; }
.sc-upload-btn:hover:not(:disabled) { background:#dbeafe;border-color:#3b82f6; }
.sc-upload-btn:disabled { opacity:.4;cursor:not-allowed; }
.spam-check-input { flex:1;padding:12px 16px;border:1.5px solid #e8e6f0;border-radius:16px;font-size:14px;font-family:inherit;resize:none;outline:none;background:#fff;color:#1e1b4b;min-height:46px;max-height:120px;transition:border-color .2s; }
.spam-check-input:focus { border-color:#3b82f6; }
.sc-send-btn { width:46px;height:46px;border-radius:14px;border:none;background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:opacity .2s;box-shadow:0 3px 12px rgba(59,130,246,.35); }
.sc-send-btn:disabled { opacity:.4;cursor:not-allowed; }
.msg-enter-active{transition:all .22s ease}.msg-enter-from{opacity:0;transform:translateY(12px)}
.fade-enter-active,.fade-leave-active{transition:opacity .25s}.fade-enter-from,.fade-leave-to{opacity:0}
.submit-msg { display:flex;align-items:center;gap:7px;margin:0 26px 10px;padding:10px 16px;border-radius:10px;font-size:13px;font-weight:600;background:#dbeafe;color:#1d4ed8;border:1px solid #bfdbfe; }
.submit-msg.done { background:#d1fae5;color:#065f46;border-color:#a7f3d0; }

/* 스팸 규칙 */
.profile-body { flex:1;overflow-y:auto;padding:28px 32px; }
.rule-add-box { background:#f0f4ff;border:1.5px solid #dbeafe;border-radius:16px;padding:18px 20px;margin-bottom:24px; }
.rule-type-tabs { display:flex;gap:6px;margin-bottom:14px; }
.rule-type-btn { padding:6px 16px;border-radius:99px;border:1.5px solid #e0d9f0;background:#fff;font-size:12.5px;font-weight:600;color:#6b7280;cursor:pointer;transition:all .15s; }
.rule-type-btn.active { background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;border-color:transparent; }
.rule-input-row { display:flex;gap:10px; }
.rule-input { flex:1;padding:10px 14px;border-radius:12px;border:1.5px solid #e0d9f0;font-size:13.5px;color:#1e1b4b;outline:none;background:#fff;transition:border .15s; }
.rule-input:focus { border-color:#3b82f6; }
.btn-rule-add { display:flex;align-items:center;gap:6px;padding:10px 18px;border-radius:12px;background:linear-gradient(135deg,#3b82f6,#6366f1);color:#fff;font-size:13px;font-weight:700;border:none;cursor:pointer;transition:opacity .15s;white-space:nowrap; }
.btn-rule-add:disabled { opacity:.4;cursor:not-allowed; }
.rule-err { font-size:12.5px;color:#ef4444;margin-top:8px; }
.rule-list-wrap { display:flex;flex-direction:column;gap:18px; }
.rule-group-title { font-size:11.5px;font-weight:700;color:#9ca3af;text-transform:uppercase;letter-spacing:.7px;margin-bottom:10px; }
.rule-chips { display:flex;flex-wrap:wrap;gap:8px; }
.rule-chip { display:flex;align-items:center;gap:6px;padding:6px 10px 6px 14px;background:#e0eaff;border:1.5px solid #bfdbfe;border-radius:99px; }
.rule-chip-val { font-size:13px;color:#1d4ed8;font-weight:600; }
.rule-chip-del { display:flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;border:none;background:rgba(59,130,246,.12);color:#3b82f6;cursor:pointer;transition:all .15s;padding:0; }
.rule-chip-del:hover { background:rgba(239,68,68,.15);color:#ef4444; }

/* ── 처리 요청 탭 키워드 등록 ── */
.kw-register-box { margin-top: 14px; background: #f8f7ff; border: 1.5px solid #e0daff; border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
.kw-register-header { display: flex; align-items: center; justify-content: space-between; }
.kw-register-title { font-size: 13px; font-weight: 700; color: #1e1b4b; }
.kw-register-count { font-size: 11px; color: #6366f1; font-weight: 600; background: #ede9fe; padding: 2px 8px; border-radius: 99px; }
.kw-register-row { display: flex; gap: 8px; }
.kw-register-input { flex: 1; padding: 9px 12px; border-radius: 9px; border: 1.5px solid #d1d5db; font-size: 13.5px; outline: none; transition: border-color .15s; }
.kw-register-input:focus { border-color: #6366f1; }
.kw-register-btn { padding: 9px 16px; border-radius: 9px; border: none; background: linear-gradient(135deg, #ec4899, #6366f1); color: #fff; font-size: 13px; font-weight: 700; cursor: pointer; white-space: nowrap; transition: opacity .15s; }
.kw-register-btn:disabled { opacity: .4; cursor: not-allowed; }
.kw-instant-msg { font-size: 12px; }
.kw-instant-msg.ok { color: #16a34a; }
.kw-instant-msg.err { color: #ef4444; }
.kw-register-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.kw-mini-chip { font-size: 11.5px; font-weight: 600; background: #fff; border: 1.5px solid #c4b5fd; color: #5b21b6; padding: 3px 10px; border-radius: 99px; }
.kw-mini-more { font-size: 11px; color: #9ca3af; align-self: center; }

/* ── 스팸 키워드 탭 ── */
.kw-total-badge { font-size:12px;font-weight:700;padding:4px 12px;background:#ede9fe;color:#6366f1;border-radius:99px;border:1.5px solid #c4b5fd; }
.kw-mgr-body { flex:1;overflow-y:auto;padding:22px 26px;display:flex;flex-direction:column;gap:18px; }
.kw-mgr-body::-webkit-scrollbar { width:4px; }
.kw-mgr-body::-webkit-scrollbar-thumb { background:#e8e6f0;border-radius:99px; }

.kw-add-box { background:#f8f7ff;border:1.5px solid #e0daff;border-radius:16px;padding:18px 20px; }
.kw-add-row { display:flex;gap:10px; }
.kw-add-input {
  flex:1;padding:10px 14px;border-radius:10px;border:1.5px solid #d1d5db;
  font-size:14px;outline:none;transition:border-color .15s;
}
.kw-add-input:focus { border-color:#6366f1; }
.kw-add-btn {
  padding:10px 20px;border-radius:10px;border:none;
  background:linear-gradient(135deg,#ec4899,#6366f1);color:#fff;
  font-size:13px;font-weight:700;cursor:pointer;white-space:nowrap;
  transition:opacity .15s;
}
.kw-add-btn:disabled { opacity:.45;cursor:not-allowed; }
.kw-msg { font-size:12.5px;margin-top:8px; }
.kw-msg.ok { color:#16a34a; }
.kw-msg.err { color:#ef4444; }

.kw-list-section { display:flex;flex-direction:column;gap:10px; }
.kw-search-row { display:flex;align-items:center;gap:8px;padding:8px 12px;background:#f9fafb;border:1.5px solid #e5e7eb;border-radius:10px; }
.kw-search-input { flex:1;border:none;background:transparent;font-size:13px;outline:none;color:#374151; }

.kw-chip-grid { display:flex;flex-wrap:wrap;gap:8px; }
.kw-chip {
  display:flex;align-items:center;gap:8px;
  padding:7px 10px 7px 14px;
  background:#fff;border:1.5px solid #e5e7eb;border-radius:99px;
  transition:border-color .15s;
}
.kw-chip:hover { border-color:#c4b5fd; }
.kw-chip-text { font-size:13px;font-weight:600;color:#1e1b4b; }
.kw-chip-date { font-size:10.5px;color:#9ca3af; }
.kw-chip-del {
  display:flex;align-items:center;justify-content:center;
  width:18px;height:18px;border-radius:50%;border:none;
  background:rgba(0,0,0,.06);color:#9ca3af;cursor:pointer;
  transition:all .15s;padding:0;
}
.kw-chip-del:hover { background:rgba(239,68,68,.15);color:#ef4444; }
.kw-chip-del:disabled { opacity:.4;cursor:not-allowed; }

/* ── AI 스팸 판별 (두 모델) ─────────────────────────── */
.check-entry { margin-bottom:20px;border:1px solid #e8e6f0;border-radius:14px;padding:16px;background:#fff; }
.check-query { display:flex;align-items:flex-start;gap:10px;margin-bottom:12px; }
.check-query-label { font-size:11px;font-weight:700;color:#6b7280;background:#f3f4f6;border-radius:6px;padding:2px 8px;white-space:nowrap;margin-top:1px; }
.check-query-text { font-size:14px;color:#1e1b4b;font-weight:500;line-height:1.5;word-break:break-all; }
.check-loading { display:flex;align-items:center;padding:12px 0; }
.check-loading .dot { width:7px;height:7px;border-radius:50%;background:#a78bfa;margin:0 3px;animation:bounce .9s infinite; }
.check-loading .dot:nth-child(2) { animation-delay:.15s; }
.check-loading .dot:nth-child(3) { animation-delay:.3s; }

.compare-final { display:flex;align-items:center;gap:12px;padding:12px 16px;border-radius:10px;font-size:14px;font-weight:600;margin-bottom:12px; }
.compare-final.spam { background:#fef2f2;border:1.5px solid #fca5a5;color:#b91c1c; }
.compare-final.ham  { background:#f0fdf4;border:1.5px solid #86efac;color:#15803d; }
.cf-icon { font-size:18px; }
.cf-label { flex:1; }
.cf-agree   { font-size:12px;color:#15803d;background:#dcfce7;padding:2px 10px;border-radius:20px; }
.cf-disagree{ font-size:12px;color:#b45309;background:#fef9c3;padding:2px 10px;border-radius:20px; }

.compare-models { display:grid;grid-template-columns:1fr 1fr;gap:12px; }
.compare-model-card { border-radius:10px;padding:14px;border:1.5px solid transparent; }
.compare-model-card.spam { background:#fef2f2;border-color:#fca5a5; }
.compare-model-card.ham  { background:#f0fdf4;border-color:#86efac; }
.cmc-header { display:flex;justify-content:space-between;align-items:center;margin-bottom:8px; }
.cmc-name  { font-size:13px;font-weight:700;color:#374151; }
.cmc-verdict { font-size:12px;font-weight:700;padding:2px 10px;border-radius:20px; }
.cmc-verdict.spam { background:#fee2e2;color:#b91c1c; }
.cmc-verdict.ham  { background:#dcfce7;color:#15803d; }
.cmc-answer { font-size:12.5px;color:#4b5563;line-height:1.6;white-space:pre-wrap;word-break:break-word;margin-bottom:6px; }
.cmc-ref { font-size:11px;color:#9ca3af; }
</style>
