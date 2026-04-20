<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = 'http://localhost:8000'

// ── 채팅 ─────────────────────────────────────────────
interface Msg {
  id: number
  role: string
  message: string
  is_spam: number | null
  created_at?: string
}

const messages = ref<Msg[]>([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatBody = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
let nextId = 0

async function loadHistory() {
  const res = await fetch(`${API}/chat/history`, { headers: auth.authHeader() })
  if (res.ok) messages.value = await res.json()
}

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value) return
  chatInput.value = ''
  const ta = document.querySelector('.chat-input') as HTMLTextAreaElement
  if (ta) ta.style.height = 'auto'

  messages.value.push({ id: nextId++, role: 'user', message: text, is_spam: null })
  chatLoading.value = true
  await nextTick()
  chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })

  try {
    const res = await fetch(`${API}/chat`, {
      method: 'POST',
      headers: auth.authHeader(),
      body: JSON.stringify({ message: text }),
    })
    const data = await res.json()
    messages.value.push({ id: nextId++, role: 'ai', message: data.reply, is_spam: data.is_spam ? 1 : 0 })
  } catch {
    messages.value.push({ id: nextId++, role: 'ai', message: '서버에 연결할 수 없습니다.', is_spam: null })
  } finally {
    chatLoading.value = false
    await nextTick()
    chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
  }
}

function onChatKey(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat() }
}

async function uploadFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file || chatLoading.value) return
  chatLoading.value = true
  messages.value.push({ id: nextId++, role: 'user', message: `📎 ${file.name} 업로드`, is_spam: null })
  await nextTick()
  chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API}/chat/file`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token}` },
      body: form,
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '업로드 실패')
    messages.value.push({ id: nextId++, role: 'ai', message: data.reply, is_spam: data.is_spam ? 1 : 0 })
  } catch (err: any) {
    messages.value.push({ id: nextId++, role: 'ai', message: err.message || '파일 처리 실패', is_spam: null })
  } finally {
    chatLoading.value = false
    if (fileInput.value) fileInput.value.value = ''
    await nextTick()
    chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
  }
}

function autoResize(e: Event) {
  const ta = e.target as HTMLTextAreaElement
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
}

// ── 스팸 신고 ─────────────────────────────────────────
interface Report {
  id: number
  email_content: string
  status: string
  counselor_note: string
  counselor_id: number | null
  counselor_nickname: string | null
  counselor_username: string | null
  created_at: string
  review_id: number | null
  review_stars: number | null
  review_comment: string | null
}

const reports = ref<Report[]>([])
const reportInput = ref('')
const reportLoading = ref(false)
const reportSuccess = ref(false)
const reportEnabled = ref(true)
const activeTab = ref<'chat' | 'report' | 'profile' | 'rules'>('chat')

async function loadReports() {
  const res = await fetch(`${API}/spam-reports/my`, { headers: auth.authHeader() })
  if (res.ok) reports.value = await res.json()
}

async function submitReport() {
  if (!reportInput.value.trim() || reportLoading.value) return
  reportLoading.value = true
  try {
    await fetch(`${API}/spam-reports`, {
      method: 'POST',
      headers: auth.authHeader(),
      body: JSON.stringify({ email_content: reportInput.value.trim() }),
    })
    reportInput.value = ''
    reportSuccess.value = true
    setTimeout(() => (reportSuccess.value = false), 3000)
    await loadReports()
  } finally {
    reportLoading.value = false
  }
}

const doneUnreviewed = computed(() =>
  reports.value.filter(r => r.status === 'done' && r.counselor_id && !r.review_id).length
)

const statusLabel: Record<string, string> = { pending: '대기중', processing: '처리중', done: '완료' }

// ── 별점 평가 모달 ────────────────────────────────────
const reviewModal = ref(false)
const reviewReport = ref<Report | null>(null)
const reviewComment = ref('')
const reviewLoading = ref(false)
const reviewSuccess = ref(false)

interface CategoryRating { stars: number; hover: number }
const categories = ref<Record<string, CategoryRating>>({
  accuracy:   { stars: 0, hover: 0 },
  processing: { stars: 0, hover: 0 },
  clarity:    { stars: 0, hover: 0 },
  speed:      { stars: 0, hover: 0 },
})
const categoryLabels: Record<string, string> = {
  accuracy:   '안내 정확도',
  processing: '처리 정확성',
  clarity:    '설명 이해도',
  speed:      '응답 속도',
}
const categoryDescs: Record<string, string> = {
  accuracy:   '정확한 정보로 안내했는지',
  processing: '스팸 처리가 제대로 됐는지',
  clarity:    '설명이 이해하기 쉬웠는지',
  speed:      '응답이 빠르게 왔는지',
}

function openReview(r: Report) {
  reviewReport.value = r
  categories.value = {
    accuracy:   { stars: 0, hover: 0 },
    processing: { stars: 0, hover: 0 },
    clarity:    { stars: 0, hover: 0 },
    speed:      { stars: 0, hover: 0 },
  }
  reviewComment.value = ''
  reviewSuccess.value = false
  reviewModal.value = true
}

const canSubmitReview = computed(() =>
  categories.value.accuracy.stars > 0 &&
  categories.value.processing.stars > 0 &&
  categories.value.clarity.stars > 0 &&
  categories.value.speed.stars > 0
)

async function submitReview() {
  if (!canSubmitReview.value || !reviewReport.value || reviewLoading.value) return
  reviewLoading.value = true
  const c = categories.value
  const avg = Math.round((c.accuracy.stars + c.processing.stars + c.clarity.stars) / 3)
  try {
    const res = await fetch(`${API}/counselor-reviews`, {
      method: 'POST',
      headers: auth.authHeader(),
      body: JSON.stringify({
        report_id: reviewReport.value.id,
        stars: avg,
        comment: reviewComment.value.trim(),
        accuracy_stars: c.accuracy.stars,
        processing_stars: c.processing.stars,
        clarity_stars: c.clarity.stars,
        speed_stars: c.speed.stars,
      }),
    })
    if (res.ok) {
      reviewSuccess.value = true
      await loadReports()
      setTimeout(() => { reviewModal.value = false }, 1500)
    }
  } finally {
    reviewLoading.value = false
  }
}

// ── 내 정보 ───────────────────────────────────────────
interface Profile {
  username: string; nickname: string; name: string
  phone: string; email: string; address: string; detail_address: string
  postal_code: string; role: string; created_at: string
}
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
    // 하나라도 비어있으면 자동으로 수정 모드
    if (!p.nickname || !p.name || !p.phone || !p.email || !p.address || !p.postal_code) profileEdit.value = true
  }
}

async function saveProfile() {
  profileMsg.value = ''; profileErr.value = ''
  const pw = profilePwForm.value
  if (pw.new_password && pw.new_password !== pw.confirm_password) {
    profileErr.value = '새 비밀번호가 일치하지 않습니다.'; return
  }
  profileSaving.value = true
  try {
    const body = { ...profileForm.value, current_password: pw.current_password, new_password: pw.new_password }
    const res = await fetch(`${API}/users/me`, {
      method: 'PATCH', headers: auth.authHeader(),
      body: JSON.stringify(body),
    })
    if (res.ok) {
      profileMsg.value = '수정되었습니다!'
      profilePwForm.value = { current_password: '', new_password: '', confirm_password: '' }
      profileEdit.value = false
      await loadProfile()
    } else {
      const d = await res.json()
      profileErr.value = d.detail || '오류가 발생했습니다.'
    }
  } finally { profileSaving.value = false }
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

function logout() {
  auth.logout()
  router.push('/login')
}

async function loadSettings() {
  const res = await fetch(`${API}/settings`, { headers: auth.authHeader() })
  if (res.ok) {
    const data = await res.json()
    reportEnabled.value = data.report_enabled !== 'false'
  }
}

onMounted(async () => {
  await Promise.all([loadHistory(), loadReports(), loadProfile(), loadRules(), loadSettings()])
})
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
              <span class="role-pill user">사용자</span>
            </div>
          </div>

          <nav class="nav">
            <button :class="['nav-item', { active: activeTab === 'chat' }]" @click="activeTab = 'chat'">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </span>
              AI 스팸 판별
            </button>
            <button :class="['nav-item', { active: activeTab === 'report' }]" @click="activeTab = 'report'; loadReports()">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </span>
              상담 요청
              <span v-if="doneUnreviewed" class="nav-badge">{{ doneUnreviewed }}</span>
            </button>
            <button :class="['nav-item', { active: activeTab === 'rules' }]" @click="activeTab = 'rules'; loadRules()">
              <span class="nav-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
              </span>
              스팸 규칙
            </button>
            <button :class="['nav-item', { active: activeTab === 'profile' }]" @click="activeTab = 'profile'; loadProfile()">
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
          <button class="home-btn" @click="activeTab = 'chat'">
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

      <!-- Main Content -->
      <main class="main">
        <!-- AI Chat Tab -->
        <div v-if="activeTab === 'chat'" class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">AI 스팸 판별</h2>
              <p class="panel-desc">메일 내용을 입력하면 스팸 여부를 즉시 분석합니다</p>
            </div>
            <div class="header-badge">
              <span class="dot-green" />
              <span>AI 분석 활성화</span>
            </div>
          </div>

          <div class="chat-body" ref="chatBody">
            <div v-if="!messages.length" class="empty-state">
              <div class="empty-graphic">
                <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.35">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <p class="empty-title">분석 준비 완료</p>
              <p class="empty-desc">의심스러운 메일 내용을 아래에 붙여넣어 보세요</p>
              <div class="quick-chips">
                <span class="chip" @click="chatInput = '무료 경품 당첨! 지금 클릭하세요'">스팸 예시</span>
                <span class="chip" @click="chatInput = '내일 오후 3시 회의 일정 안내드립니다'">정상 예시</span>
              </div>
            </div>

            <TransitionGroup name="msg" tag="div" class="messages">
              <div v-for="msg in messages" :key="msg.id" class="msg-row" :class="msg.role">
                <div v-if="msg.role === 'ai'" class="ai-avatar">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                </div>
                <div class="bubble" :class="[
                  msg.role,
                  { 'bubble-spam': msg.is_spam === 1, 'bubble-ham': msg.is_spam === 0 }
                ]">
                  <span v-if="msg.is_spam === 1" class="bubble-label spam">스팸 감지</span>
                  <span v-else-if="msg.is_spam === 0" class="bubble-label ham">정상 메일</span>
                  {{ msg.message }}
                </div>
              </div>
            </TransitionGroup>

            <div v-if="chatLoading" class="msg-row ai">
              <div class="ai-avatar">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                </svg>
              </div>
              <div class="bubble ai loading-bubble">
                <span class="dot" /><span class="dot" /><span class="dot" />
              </div>
            </div>
          </div>

          <div class="input-bar">
            <input ref="fileInput" type="file" accept=".pdf,.txt,.eml" style="display:none" @change="uploadFile" />
            <button class="upload-btn" :disabled="chatLoading" @click="fileInput?.click()" title="파일 업로드 (PDF, TXT, EML)">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
              </svg>
            </button>
            <textarea
              v-model="chatInput"
              class="chat-input"
              placeholder="메일 내용을 입력하거나 파일을 업로드하세요... (Enter 전송)"
              rows="1"
              @keydown="onChatKey"
              @input="autoResize"
            />
            <button class="send-btn" :disabled="!chatInput.trim() || chatLoading" @click="sendChat">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="22" y1="2" x2="11" y2="13"/>
                <polygon points="22 2 15 22 11 13 2 9 22 2"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Report Tab -->
        <div v-if="activeTab === 'report'" class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">상담 요청</h2>
              <p class="panel-desc">상담원에게 직접 스팸 분석을 요청하고 평가할 수 있어요</p>
            </div>
          </div>

          <div class="report-form">
            <div v-if="!reportEnabled" class="report-disabled-banner">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
              </svg>
              현재 상담 요청이 비활성화되어 있습니다. 관리자에게 문의해주세요.
            </div>
            <textarea
              v-model="reportInput"
              class="report-textarea"
              :class="{ disabled: !reportEnabled }"
              placeholder="상담원에게 분석을 요청할 메일 내용을 입력하세요..."
              rows="4"
              :disabled="!reportEnabled"
            />
            <div class="report-form-footer">
              <Transition name="fade">
                <div v-if="reportSuccess" class="success-chip">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                  접수 완료!
                </div>
              </Transition>
              <button class="btn-submit" :disabled="!reportInput.trim() || reportLoading || !reportEnabled" @click="submitReport">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="22" y1="2" x2="11" y2="13"/>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
                {{ reportLoading ? '접수 중...' : '상담 요청 보내기' }}
              </button>
            </div>
          </div>

          <div class="report-list">
            <div class="list-header">
              <h3 class="list-title">요청 내역</h3>
              <button class="refresh-btn" @click="loadReports">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="23 4 23 10 17 10"/>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
              </button>
            </div>
            <div v-if="!reports.length" class="empty-list">요청 내역이 없습니다.</div>
            <TransitionGroup name="card" tag="div" class="cards">
              <div v-for="r in reports" :key="r.id" class="report-card">
                <div class="rc-top">
                  <span :class="['status-pill', `st-${r.status}`]">{{ statusLabel[r.status] }}</span>
                  <span class="rc-date">{{ new Date(r.created_at).toLocaleDateString('ko-KR') }}</span>
                </div>
                <p class="rc-content">{{ r.email_content }}</p>
                <div v-if="r.counselor_note" class="rc-note">
                  <div class="rc-note-header">
                    <div class="rc-note-who">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                      </svg>
                      <span class="rc-note-label">상담원 답변</span>
                      <span class="rc-note-name">{{ r.counselor_nickname || r.counselor_username || '상담원' }}</span>
                    </div>
                  </div>
                  <p class="rc-note-text">{{ r.counselor_note }}</p>
                </div>
                <div v-else-if="r.status === 'pending'" class="rc-waiting">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                  </svg>
                  상담원 배정 대기 중...
                </div>
                <div v-else-if="r.status === 'processing'" class="rc-waiting processing">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                  상담원이 검토 중입니다...
                </div>
                <!-- 평가 -->
                <div class="rc-review">
                  <div v-if="r.review_id" class="review-done">
                    <div class="review-stars-row">
                      <span v-for="i in 5" :key="i" class="star" :class="{ filled: i <= (r.review_stars ?? 0) }">★</span>
                    </div>
                    <span class="review-done-label">평가 완료</span>
                  </div>
                  <button
                    v-else-if="r.status === 'done' && r.counselor_id"
                    class="btn-review"
                    @click="openReview(r)"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    상담사 평가하기
                  </button>
                </div>
              </div>
            </TransitionGroup>
          </div>
        </div>

        <!-- 스팸 규칙 Tab -->
        <div v-if="activeTab === 'rules'" class="panel">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">내 스팸 규칙</h2>
              <p class="panel-desc">직접 지정한 단어·문장·이메일 주소가 포함된 메일은 스팸으로 판별됩니다</p>
            </div>
          </div>
          <div class="profile-body">
            <!-- 규칙 추가 폼 -->
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
                  v-model="ruleValue"
                  class="rule-input"
                  :placeholder="ruleType === 'email' ? '차단할 이메일 주소 입력' : ruleType === 'sentence' ? '차단할 문장 입력' : '차단할 단어 입력'"
                  @keydown.enter="addRule"
                />
                <button class="btn-rule-add" :disabled="!ruleValue.trim() || ruleLoading" @click="addRule">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                  </svg>
                  추가
                </button>
              </div>
              <p v-if="ruleMsg" class="rule-err">{{ ruleMsg }}</p>
            </div>

            <!-- 규칙 목록 -->
            <div class="rule-list-wrap">
              <div v-if="!spamRules.length" class="empty-list" style="padding:24px 0">등록된 규칙이 없습니다.</div>
              <div v-else>
                <div v-for="group in ['keyword','sentence','email']" :key="group">
                  <div v-if="spamRules.filter(r=>r.rule_type===group).length" class="rule-group">
                    <div class="rule-group-title">{{ ruleTypeLabels[group] }}</div>
                    <div class="rule-chips">
                      <div v-for="r in spamRules.filter(x=>x.rule_type===group)" :key="r.id" class="rule-chip">
                        <span class="rule-chip-val">{{ r.value }}</span>
                        <button class="rule-chip-del" @click="deleteRule(r.id)" title="삭제">
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 내 정보 Tab -->
        <div v-if="activeTab === 'profile'" class="panel">
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

          <div class="profile-body" v-if="profile">
            <!-- 보기 모드 -->
            <div v-if="!profileEdit" class="profile-view">
              <div class="profile-section-title">기본 정보</div>
              <div class="profile-grid">
                <div class="pfield"><span class="pfield-label">아이디</span><span class="pfield-val readonly">{{ profile.username }}</span></div>
                <div class="pfield"><span class="pfield-label">닉네임</span><span class="pfield-val">{{ profile.nickname }}</span></div>
                <div class="pfield"><span class="pfield-label">이름</span><span class="pfield-val">{{ profile.name }}</span></div>
                <div class="pfield"><span class="pfield-label">휴대폰</span><span class="pfield-val">{{ profile.phone }}</span></div>
                <div class="pfield"><span class="pfield-label">이메일</span><span class="pfield-val">{{ profile.email }}</span></div>
                <div class="pfield"><span class="pfield-label">우편번호</span><span class="pfield-val">{{ profile.postal_code }}</span></div>
                <div class="pfield pfield-full"><span class="pfield-label">주소</span><span class="pfield-val">{{ profile.address }}</span></div>
                <div class="pfield pfield-full"><span class="pfield-label">상세주소</span><span class="pfield-val">{{ profile.detail_address }}</span></div>
                <div class="pfield"><span class="pfield-label">역할</span><span class="pfield-val">{{ profile.role }}</span></div>
                <div class="pfield"><span class="pfield-label">가입일</span><span class="pfield-val readonly">{{ new Date(profile.created_at).toLocaleDateString('ko-KR') }}</span></div>
              </div>
            </div>

            <!-- 수정 모드 -->
            <div v-else class="profile-edit-form">
              <div class="profile-section-title">기본 정보 수정</div>
              <div class="profile-grid">
                <div class="pfield">
                  <label class="pfield-label">아이디</label>
                  <input class="pfield-input" :value="profile.username" disabled style="background:#f5f5f5;color:#9ca3af;cursor:not-allowed;" />
                </div>
                <div class="pfield">
                  <label class="pfield-label">닉네임</label>
                  <input class="pfield-input" v-model="profileForm.nickname" placeholder="닉네임 입력" />
                </div>
                <div class="pfield">
                  <label class="pfield-label">이름</label>
                  <input class="pfield-input" v-model="profileForm.name" placeholder="이름 입력" />
                </div>
                <div class="pfield">
                  <label class="pfield-label">휴대폰 번호</label>
                  <input class="pfield-input" v-model="profileForm.phone" placeholder="010-0000-0000" />
                </div>
                <div class="pfield">
                  <label class="pfield-label">이메일</label>
                  <input class="pfield-input" v-model="profileForm.email" placeholder="example@email.com" />
                </div>
                <div class="pfield">
                  <label class="pfield-label">우편번호</label>
                  <input class="pfield-input" v-model="profileForm.postal_code" placeholder="우편번호 입력" />
                </div>
                <div class="pfield pfield-full">
                  <label class="pfield-label">주소</label>
                  <input class="pfield-input" v-model="profileForm.address" placeholder="기본 주소 입력" />
                </div>
                <div class="pfield pfield-full">
                  <label class="pfield-label">상세주소</label>
                  <input class="pfield-input" v-model="profileForm.detail_address" placeholder="상세 주소 입력 (동, 호수 등)" />
                </div>
              </div>

              <div class="profile-section-title" style="margin-top:28px">비밀번호 변경 <span style="font-weight:400;text-transform:none;letter-spacing:0;color:#b0b8c8;font-size:11px">(변경하지 않으려면 비워두세요)</span></div>
              <div class="profile-grid">
                <div class="pfield pfield-full">
                  <label class="pfield-label">현재 비밀번호</label>
                  <input class="pfield-input" type="password" v-model="profilePwForm.current_password" placeholder="현재 비밀번호 입력" />
                </div>
                <div class="pfield">
                  <label class="pfield-label">새 비밀번호</label>
                  <input class="pfield-input" type="password" v-model="profilePwForm.new_password" placeholder="새 비밀번호 (4자 이상)" />
                </div>
                <div class="pfield">
                  <label class="pfield-label">새 비밀번호 확인</label>
                  <input class="pfield-input" type="password" v-model="profilePwForm.confirm_password" placeholder="새 비밀번호 재입력" />
                </div>
              </div>

              <p v-if="profileErr" class="profile-err">{{ profileErr }}</p>
              <p v-if="profileMsg" class="profile-ok">{{ profileMsg }}</p>

              <div class="profile-actions">
                <button class="btn-cancel" @click="profileEdit = false; profileErr = ''; profileMsg = ''">취소</button>
                <button class="btn-save" :disabled="profileSaving" @click="saveProfile">
                  <span v-if="profileSaving" class="spinner-sm" />
                  {{ profileSaving ? '저장 중...' : '저장하기' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- 별점 평가 모달 -->
    <Transition name="modal">
      <div v-if="reviewModal" class="modal-overlay" @click.self="reviewModal = false">
        <div class="modal-card">
          <div class="modal-header">
            <h3 class="modal-title">상담사 평가</h3>
            <button class="modal-close" @click="reviewModal = false">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <Transition name="fade">
            <div v-if="reviewSuccess" class="review-success">
              <div class="success-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
              <p>평가해주셔서 감사합니다!</p>
            </div>
            <div v-else class="modal-body">
              <p class="modal-desc">항목별로 평가해주세요</p>
              <div class="category-list">
                <div v-for="(key) in ['accuracy','processing','clarity','speed']" :key="key" class="category-row">
                  <div class="cat-info">
                    <span class="cat-name">{{ categoryLabels[key] }}</span>
                    <span class="cat-desc">{{ categoryDescs[key] }}</span>
                  </div>
                  <div class="cat-stars">
                    <span
                      v-for="i in 5" :key="i"
                      class="cat-star"
                      :class="{ filled: i <= (categories[key].hover || categories[key].stars) }"
                      @mouseenter="categories[key].hover = i"
                      @mouseleave="categories[key].hover = 0"
                      @click="categories[key].stars = i"
                    >★</span>
                  </div>
                </div>
              </div>
              <textarea
                v-model="reviewComment"
                class="review-textarea"
                placeholder="추가 의견을 남겨주세요 (선택)"
                rows="2"
              />
              <button
                class="btn-submit-review"
                :disabled="!canSubmitReview || reviewLoading"
                @click="submitReview"
              >
                <span v-if="reviewLoading" class="spinner-sm" />
                {{ reviewLoading ? '제출 중...' : '평가 제출하기' }}
              </button>
            </div>
          </Transition>
        </div>
      </div>
    </Transition>
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
.orb1 { width: 500px; height: 500px; background: #6366f1; top: -150px; left: -100px; }
.orb2 { width: 350px; height: 350px; background: #8b5cf6; bottom: -100px; right: -80px; }

/* Layout */
.layout {
  width: 100%;
  max-width: 1140px;
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

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px;
  margin-bottom: 16px;
}

.brand-icon {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 4px 12px rgba(99,102,241,0.4);
}

.brand-name {
  font-size: 15px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.3px;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: rgba(255,255,255,0.06);
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.08);
  margin-bottom: 12px;
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-weight: 800;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 3px 10px rgba(99,102,241,0.35);
}

.user-info { display: flex; flex-direction: column; gap: 4px; }
.user-name { font-size: 13px; font-weight: 700; color: #fff; }
.role-pill { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 99px; width: fit-content; }
.role-pill.user { background: rgba(109,40,217,0.3); color: #c4b5fd; border: 1px solid rgba(109,40,217,0.4); }

.nav { display: flex; flex-direction: column; gap: 3px; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: none;
  background: transparent;
  color: rgba(255,255,255,0.5);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
  position: relative;
}

.nav-item:hover { background: rgba(255,255,255,0.07); color: rgba(255,255,255,0.85); }
.nav-item.active { background: linear-gradient(135deg, rgba(99,102,241,0.25), rgba(139,92,246,0.2)); color: #fff; }
.nav-item.active .nav-icon { color: #a5b4fc; }

.nav-icon { display: flex; align-items: center; color: rgba(255,255,255,0.35); transition: color 0.2s; }

.nav-badge {
  margin-left: auto;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  font-weight: 800;
  padding: 2px 7px;
  border-radius: 99px;
  animation: pulse 2s infinite;
}

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }

.bottom-btns {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.08);
}

.home-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.75);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
}
.home-btn:hover { background: rgba(255,255,255,0.12); color: #fff; }

.logout-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  border-radius: 12px;
  border: 1px solid rgba(239,68,68,0.25);
  background: rgba(239,68,68,0.08);
  color: #f87171;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  width: 100%;
}
.logout-btn:hover { background: rgba(239,68,68,0.2); border-color: rgba(239,68,68,0.5); color: #fca5a5; }

/* Main */
.main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0; }

.panel { display: flex; flex-direction: column; flex: 1; min-height: 0; }

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26px 30px 20px;
  border-bottom: 1px solid #f1f0f9;
  flex-shrink: 0;
}

.panel-title { font-size: 18px; font-weight: 800; color: #1e1b4b; letter-spacing: -0.3px; }
.panel-desc { font-size: 13px; color: #7c7c9a; margin-top: 3px; }

.header-badge {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 14px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 600;
  color: #059669;
}

.dot-green {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
  animation: pulse 2s infinite;
}

/* Chat body */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
}

.chat-body::-webkit-scrollbar { width: 5px; }
.chat-body::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
}

.empty-graphic {
  width: 80px;
  height: 80px;
  border-radius: 24px;
  background: #f5f4ff;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 4px;
}

.empty-title { font-size: 16px; font-weight: 700; color: #1e1b4b; }
.empty-desc { font-size: 13px; color: #9ca3af; }

.quick-chips { display: flex; gap: 8px; margin-top: 8px; }
.chip {
  padding: 7px 14px;
  background: #f5f4ff;
  border: 1.5px solid #ede9fe;
  border-radius: 99px;
  font-size: 12.5px;
  color: #6366f1;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.chip:hover { background: #ede9fe; border-color: #6366f1; }

.messages { display: flex; flex-direction: column; gap: 14px; }

.msg-row { display: flex; align-items: flex-end; gap: 8px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.ai { justify-content: flex-start; }

.ai-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.bubble {
  max-width: 68%;
  padding: 12px 16px;
  border-radius: 20px;
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
  position: relative;
}

.bubble.user {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 3px 12px rgba(99,102,241,0.3);
}

.bubble-label {
  display: block;
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.bubble-label.spam { color: #dc2626; }
.bubble-label.ham  { color: #059669; }

.bubble.bubble-spam {
  background: #fef2f2;
  color: #374151;
  border: 1.5px solid #fecaca;
  border-bottom-left-radius: 6px;
}

.bubble.bubble-ham {
  background: #f0fdf4;
  color: #374151;
  border: 1.5px solid #bbf7d0;
  border-bottom-left-radius: 6px;
}

.bubble.ai:not(.bubble-spam):not(.bubble-ham) {
  background: #f5f4ff;
  color: #374151;
  border: 1.5px solid #ede9fe;
  border-bottom-left-radius: 6px;
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 14px 18px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #9ca3af;
  animation: bounce 1.2s infinite ease-in-out;
}
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,80%,100%{transform:scale(0.8);opacity:0.5} 40%{transform:scale(1.2);opacity:1} }

.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 16px 22px;
  border-top: 1px solid #f1f0f9;
  background: #faf9ff;
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  padding: 12px 16px;
  border: 1.5px solid #e8e6f0;
  border-radius: 16px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  background: #fff;
  color: #1e1b4b;
  min-height: 46px;
  max-height: 120px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.chat-input:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
.chat-input::placeholder { color: #c4c4cc; }

.upload-btn {
  width: 46px; height: 46px; border-radius: 14px; border: 1.5px solid #e8e6f0;
  background: #faf9ff; color: #6366f1; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: all 0.2s;
}
.upload-btn:hover:not(:disabled) { background: #ede9fe; border-color: #6366f1; }
.upload-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.send-btn {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s, transform 0.1s, box-shadow 0.2s;
  box-shadow: 0 3px 12px rgba(99,102,241,0.35);
}
.send-btn:hover:not(:disabled) { opacity: 0.9; transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; }

/* Report */
.report-form {
  padding: 22px 28px 18px;
  border-bottom: 1px solid #f1f0f9;
  flex-shrink: 0;
  background: #faf9ff;
}

.report-textarea {
  width: 100%;
  padding: 14px 16px;
  border: 1.5px solid #e8e6f0;
  border-radius: 16px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  outline: none;
  background: #fff;
  color: #1e1b4b;
  min-height: 100px;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}
.report-textarea:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
.report-textarea::placeholder { color: #c4c4cc; }
.report-textarea.disabled { background: #f5f5f5; color: #9ca3af; cursor: not-allowed; resize: none; }
.report-disabled-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; border-radius: 12px; margin-bottom: 12px;
  background: #fef2f2; border: 1.5px solid #fecaca;
  color: #dc2626; font-size: 13px; font-weight: 600;
}

.report-form-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
}

.success-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  border-radius: 99px;
  font-size: 13px;
  font-weight: 600;
  color: #059669;
}

.btn-submit {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 20px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 13.5px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
  box-shadow: 0 3px 10px rgba(99,102,241,0.3);
}
.btn-submit:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); }
.btn-submit:disabled { opacity: 0.45; cursor: not-allowed; box-shadow: none; }

.report-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px;
}
.report-list::-webkit-scrollbar { width: 5px; }
.report-list::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.list-title { font-size: 14px; font-weight: 700; color: #1e1b4b; }

.refresh-btn {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1.5px solid #e8e6f0;
  background: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  transition: all 0.15s;
}
.refresh-btn:hover { border-color: #6366f1; color: #6366f1; }

.empty-list { text-align: center; font-size: 14px; color: #9ca3af; padding: 32px 0; }

.cards { display: flex; flex-direction: column; gap: 10px; }

.report-card {
  padding: 16px 18px;
  border: 1.5px solid #f1f0f9;
  border-radius: 16px;
  background: #faf9ff;
  transition: all 0.15s;
}
.report-card:hover { border-color: #c7d2fe; background: #f5f4ff; }

.rc-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.rc-date { font-size: 12px; color: #9ca3af; }

.status-pill { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 99px; }
.st-pending    { background: #fef3c7; color: #92400e; }
.st-processing { background: #dbeafe; color: #1d4ed8; }
.st-done       { background: #d1fae5; color: #065f46; }

.rc-content { font-size: 13.5px; color: #374151; line-height: 1.5; white-space: pre-wrap; margin-bottom: 8px; }

.rc-note {
  font-size: 12.5px;
  color: #374151;
  background: #f0f4ff;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #c7d2fe;
  margin-bottom: 8px;
}
.rc-note-header { margin-bottom: 6px; }
.rc-note-who {
  display: flex; align-items: center; gap: 5px;
  color: #4338ca; font-weight: 700; font-size: 11.5px;
}
.rc-note-label { color: #4338ca; }
.rc-note-name {
  background: #e0e7ff; color: #3730a3;
  padding: 1px 8px; border-radius: 99px;
  font-size: 11px; font-weight: 700;
}
.rc-note-text { color: #374151; line-height: 1.55; margin: 0; }
.rc-waiting {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: #9ca3af;
  padding: 7px 10px; border-radius: 8px;
  background: #f9fafb; border: 1px dashed #e5e7eb;
  margin-bottom: 8px;
}
.rc-waiting.processing { color: #6366f1; background: #f5f4ff; border-color: #c7d2fe; }

.rc-review { display: flex; align-items: center; }

.review-done {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-stars-row .star { font-size: 16px; color: #d1d5db; transition: color 0.15s; }
.review-stars-row .star.filled { color: #f59e0b; }

.review-done-label { font-size: 12px; color: #9ca3af; }

.btn-review {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 1.5px solid #6366f1;
  border-radius: 99px;
  background: transparent;
  color: #6366f1;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-review:hover { background: #6366f1; color: #fff; }

/* ── Modal ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 12, 41, 0.7);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 20px;
}

.modal-card {
  width: 100%;
  max-width: 440px;
  background: #fff;
  border-radius: 24px;
  box-shadow: 0 24px 60px rgba(0,0,0,0.3);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22px 24px 18px;
  border-bottom: 1px solid #f1f0f9;
}

.modal-title { font-size: 17px; font-weight: 800; color: #1e1b4b; }

.modal-close {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: #f5f4ff;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.modal-close:hover { background: #fee2e2; color: #ef4444; }

.modal-body { padding: 24px; display: flex; flex-direction: column; gap: 18px; }

.modal-desc { font-size: 13px; color: #6b7280; text-align: center; }
.modal-desc .muted { color: #c4c4cc; font-size: 12px; }

.category-list { display: flex; flex-direction: column; gap: 12px; }

.category-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #faf9ff;
  border: 1.5px solid #ede9fe;
  border-radius: 12px;
  gap: 12px;
}

.cat-info { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.cat-name { font-size: 13px; font-weight: 700; color: #1e1b4b; }
.cat-desc { font-size: 11px; color: #9ca3af; }

.cat-stars { display: flex; gap: 3px; flex-shrink: 0; }
.cat-star {
  font-size: 24px;
  color: #e5e7eb;
  cursor: pointer;
  transition: color 0.1s, transform 0.1s;
  user-select: none;
}
.cat-star.filled { color: #f59e0b; }
.cat-star:hover { transform: scale(1.15); }

.review-textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1.5px solid #e8e6f0;
  border-radius: 14px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  outline: none;
  background: #faf9ff;
  color: #1e1b4b;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}
.review-textarea:focus { border-color: #6366f1; box-shadow: 0 0 0 3px rgba(99,102,241,0.1); }
.review-textarea::placeholder { color: #c4c4cc; }

.btn-submit-review {
  padding: 14px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: opacity 0.2s;
  box-shadow: 0 4px 14px rgba(99,102,241,0.35);
}
.btn-submit-review:hover:not(:disabled) { opacity: 0.9; }
.btn-submit-review:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; }

.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.review-success {
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  font-size: 16px;
  font-weight: 600;
  color: #1e1b4b;
}

.success-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 20px rgba(16,185,129,0.4);
}

/* Transitions */
.msg-enter-active { transition: all 0.22s ease; }
.msg-enter-from { opacity: 0; transform: translateY(12px); }

.card-enter-active { transition: all 0.2s ease; }
.card-enter-from { opacity: 0; transform: translateY(8px); }

.modal-enter-active, .modal-leave-active { transition: all 0.25s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-card, .modal-leave-to .modal-card { transform: scale(0.95) translateY(10px); }

.fade-enter-active, .fade-leave-active { transition: opacity 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ── 프로필 / 규칙 공통 ───────────────────────────────── */
.profile-body {
  flex: 1;
  overflow-y: auto;
  padding: 32px 36px;
}
.profile-body::-webkit-scrollbar { width: 5px; }
.profile-body::-webkit-scrollbar-thumb { background: #e8e6f0; border-radius: 99px; }

.profile-section-title {
  font-size: 11.5px;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  margin-bottom: 16px;
  padding-bottom: 10px;
  border-bottom: 1.5px solid #f1f0f9;
}

.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 24px;
  margin-bottom: 10px;
}
.pfield { display: flex; flex-direction: column; gap: 7px; }
.pfield-full { grid-column: 1 / -1; }
.pfield-label { font-size: 11.5px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; }
.pfield-val { font-size: 14px; color: #1e1b4b; font-weight: 500; padding: 11px 15px; background: #f9f8ff; border-radius: 10px; border: 1.5px solid #ede9fe; min-height: 42px; }
.pfield-val.readonly { color: #9ca3af; background: #f5f5f5; border-color: #e5e7eb; }
.pfield-input { font-size: 14px; color: #1e1b4b; padding: 11px 15px; background: #fff; border-radius: 10px; border: 1.5px solid #e0d9f0; outline: none; transition: border 0.15s; min-height: 42px; }
.pfield-input:focus { border-color: #6366f1; }

.btn-edit-toggle {
  display: flex; align-items: center; gap: 7px;
  padding: 9px 18px; border-radius: 12px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; font-size: 13px; font-weight: 700;
  border: none; cursor: pointer; transition: opacity 0.15s;
}
.btn-edit-toggle:hover { opacity: 0.88; }

.profile-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 28px; padding-top: 20px; border-top: 1.5px solid #f1f0f9; }
.btn-cancel { padding: 11px 24px; border-radius: 12px; border: 1.5px solid #e0d9f0; background: #fff; color: #6b7280; font-size: 13px; font-weight: 600; cursor: pointer; }
.btn-cancel:hover { border-color: #6366f1; color: #6366f1; }
.btn-save { display: flex; align-items: center; gap: 8px; padding: 11px 24px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 13px; font-weight: 700; border: none; cursor: pointer; transition: opacity 0.15s; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-save:not(:disabled):hover { opacity: 0.88; }

.profile-err { font-size: 13px; color: #ef4444; margin-top: 10px; padding: 8px 12px; background: rgba(239,68,68,0.06); border-radius: 8px; border: 1px solid rgba(239,68,68,0.2); }
.profile-ok { font-size: 13px; color: #059669; margin-top: 10px; padding: 8px 12px; background: rgba(16,185,129,0.06); border-radius: 8px; border: 1px solid rgba(16,185,129,0.2); }

/* 스팸 규칙 */
.rule-add-box { background: #f9f8ff; border: 1.5px solid #ede9fe; border-radius: 16px; padding: 18px 20px; margin-bottom: 24px; }
.rule-type-tabs { display: flex; gap: 6px; margin-bottom: 14px; }
.rule-type-btn { padding: 6px 16px; border-radius: 99px; border: 1.5px solid #e0d9f0; background: #fff; font-size: 12.5px; font-weight: 600; color: #6b7280; cursor: pointer; transition: all 0.15s; }
.rule-type-btn.active { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; border-color: transparent; }
.rule-input-row { display: flex; gap: 10px; }
.rule-input { flex: 1; padding: 10px 14px; border-radius: 12px; border: 1.5px solid #e0d9f0; font-size: 13.5px; color: #1e1b4b; outline: none; background: #fff; transition: border 0.15s; }
.rule-input:focus { border-color: #6366f1; }
.btn-rule-add { display: flex; align-items: center; gap: 6px; padding: 10px 18px; border-radius: 12px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; font-size: 13px; font-weight: 700; border: none; cursor: pointer; transition: opacity 0.15s; white-space: nowrap; }
.btn-rule-add:disabled { opacity: 0.4; cursor: not-allowed; }
.rule-err { font-size: 12.5px; color: #ef4444; margin-top: 8px; }

.rule-list-wrap { display: flex; flex-direction: column; gap: 18px; }
.rule-group-title { font-size: 11.5px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.7px; margin-bottom: 10px; }
.rule-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.rule-chip { display: flex; align-items: center; gap: 6px; padding: 6px 10px 6px 14px; background: #f0eeff; border: 1.5px solid #ddd6fe; border-radius: 99px; }
.rule-chip-val { font-size: 13px; color: #4338ca; font-weight: 600; }
.rule-chip-del { display: flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; border: none; background: rgba(99,102,241,0.12); color: #6366f1; cursor: pointer; transition: all 0.15s; padding: 0; }
.rule-chip-del:hover { background: rgba(239,68,68,0.15); color: #ef4444; }
</style>
