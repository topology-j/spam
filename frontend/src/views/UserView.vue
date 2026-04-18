<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = 'http://127.0.0.1:8000'

type Tab = 'chat' | 'file' | 'report' | 'keywords' | 'rules' | 'profile'

interface Msg {
  id: number
  role: 'user' | 'ai'
  message: string
  is_spam: number | null
  created_at?: string
}

interface Report {
  id: number
  email_content: string
  status: string
  counselor_note: string
  counselor_nickname: string | null
  counselor_username: string | null
  created_at: string
}

interface SpamRule {
  id: number
  rule_type: 'keyword' | 'sentence' | 'email'
  value: string
  created_at: string
}

interface Keyword {
  id: number
  keyword: string
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

const activeTab = ref<Tab>('chat')

const messages = ref<Msg[]>([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatBody = ref<HTMLElement | null>(null)
let nextId = 1

// 파일 판별
interface FileResult {
  filename: string
  is_spam: boolean
  replies: { model: string; reply: string; is_spam: boolean }[]
  extracted_text?: string
}
const fileResult = ref<FileResult | null>(null)
const fileLoading = ref(false)
const fileError = ref('')
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

function onFileDragover(e: DragEvent) { e.preventDefault(); isDragging.value = true }
function onFileDragleave() { isDragging.value = false }
function onFileDrop(e: DragEvent) {
  e.preventDefault(); isDragging.value = false
  const f = e.dataTransfer?.files[0]
  if (f) uploadFile(f)
}
function onFileInputChange(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) uploadFile(f)
  ;(e.target as HTMLInputElement).value = ''
}
async function uploadFile(file: File) {
  fileError.value = ''; fileResult.value = null; fileLoading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${API}/chat/file`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${auth.token || localStorage.getItem('token') || ''}` },
      body: form,
    })
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail ?? '오류') }
    const data = await res.json()
    fileResult.value = {
      filename: file.name,
      is_spam: data.is_spam,
      replies: data.replies ?? [],
      extracted_text: data.text_preview ?? '',
    }
  } catch (e: unknown) {
    fileError.value = e instanceof Error ? e.message : '업로드 실패'
  } finally { fileLoading.value = false }
}

const reportInput = ref('')
const reportLoading = ref(false)
const reportSuccess = ref('')
const reports = ref<Report[]>([])
const reportEnabled = ref(true)

const spamRules = ref<SpamRule[]>([])
const keywords = ref<Keyword[]>([])
const ruleType = ref<'keyword' | 'sentence' | 'email'>('keyword')
const ruleValue = ref('')
const ruleLoading = ref(false)
const ruleMsg = ref('')

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

const ruleTypeLabel: Record<string, string> = {
  keyword: '단어',
  sentence: '문장',
  email: '이메일',
}

const groupedRules = computed(() => ({
  keyword: spamRules.value.filter((rule) => rule.rule_type === 'keyword'),
  sentence: spamRules.value.filter((rule) => rule.rule_type === 'sentence'),
  email: spamRules.value.filter((rule) => rule.rule_type === 'email'),
}))

const keywordPreview = computed(() => keywords.value.slice(0, 30))
const latestKeywordDate = computed(() => {
  if (!keywords.value.length) return ''
  return new Date(keywords.value[0].created_at).toLocaleString('ko-KR')
})

function parseAiMessage(message: string) {
  const match = message.match(/^\[(.+?)\]\s*(.*)$/s)
  if (!match) {
    return { model: 'AI', body: message }
  }
  return { model: match[1], body: match[2] || '' }
}

const chatEntries = computed(() => {
  const entries: Array<
    | { type: 'user'; id: number; message: Msg }
    | { type: 'ai-group'; id: number; messages: Array<Msg & { modelName: string; body: string }> }
  > = []

  for (let i = 0; i < messages.value.length; i += 1) {
    const current = messages.value[i]

    if (current.role === 'user') {
      entries.push({ type: 'user', id: current.id, message: current })
      continue
    }

    const aiGroup: Array<Msg & { modelName: string; body: string }> = []
    while (i < messages.value.length && messages.value[i].role === 'ai') {
      const msg = messages.value[i]
      const parsed = parseAiMessage(msg.message)
      aiGroup.push({ ...msg, modelName: parsed.model, body: parsed.body })
      i += 1
    }
    i -= 1

    entries.push({
      type: 'ai-group',
      id: aiGroup[0]?.id ?? i,
      messages: aiGroup,
    })
  }

  return entries
})

async function loadHistory() {
  const res = await fetch(`${API}/chat/history`, { headers: auth.authHeader() })
  if (!res.ok) return
  messages.value = await res.json()
  nextId = messages.value.reduce((max, msg) => Math.max(max, Number(msg.id) || 0), 0) + 1
}

function appendAiReplies(data: any) {
  const replies = Array.isArray(data?.replies) && data.replies.length
    ? data.replies
    : [{ reply: data?.reply, is_spam: data?.is_spam }]

  for (const item of replies) {
    messages.value.push({
      id: nextId++,
      role: 'ai',
      message: item.reply,
      is_spam: typeof item.is_spam === 'boolean' ? (item.is_spam ? 1 : 0) : null,
    })
  }
}

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value) return

  messages.value.push({ id: nextId++, role: 'user', message: text, is_spam: null })
  chatInput.value = ''
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
    appendAiReplies(data)
  } catch {
    messages.value.push({
      id: nextId++,
      role: 'ai',
      message: '서버 연결에 실패했습니다.',
      is_spam: null,
    })
  } finally {
    chatLoading.value = false
    await nextTick()
    chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
  }
}

function onChatKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendChat()
  }
}

function autoResize(event: Event) {
  const target = event.target as HTMLTextAreaElement
  target.style.height = 'auto'
  target.style.height = `${Math.min(target.scrollHeight, 120)}px`
}

async function loadReports() {
  const res = await fetch(`${API}/spam-reports/my`, { headers: auth.authHeader() })
  if (res.ok) reports.value = await res.json()
}

async function loadSettings() {
  const res = await fetch(`${API}/settings`, { headers: auth.authHeader() })
  if (!res.ok) return
  const data = await res.json()
  reportEnabled.value = data.report_enabled !== 'false'
}

async function submitReport() {
  const text = reportInput.value.trim()
  if (!text || reportLoading.value || !reportEnabled.value) return

  reportLoading.value = true
  reportSuccess.value = ''
  try {
    const res = await fetch(`${API}/spam-reports`, {
      method: 'POST',
      headers: auth.authHeader(),
      body: JSON.stringify({ email_content: text }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      reportSuccess.value = data.detail || '신고 등록에 실패했습니다.'
      return
    }
    reportInput.value = ''
    reportSuccess.value = '신고가 접수되었습니다.'
    await loadReports()
  } finally {
    reportLoading.value = false
  }
}

async function loadRules() {
  const res = await fetch(`${API}/user-spam-rules`, { headers: auth.authHeader() })
  if (res.ok) spamRules.value = await res.json()
}

async function loadKeywords() {
  const res = await fetch(`${API}/spam-keywords`, { headers: auth.authHeader() })
  if (res.ok) keywords.value = await res.json()
}

async function addRule() {
  const value = ruleValue.value.trim()
  if (!value || ruleLoading.value) return

  ruleLoading.value = true
  ruleMsg.value = ''
  try {
    const res = await fetch(`${API}/user-spam-rules`, {
      method: 'POST',
      headers: auth.authHeader(),
      body: JSON.stringify({ rule_type: ruleType.value, value }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      ruleMsg.value = data.detail || '규칙 추가에 실패했습니다.'
      return
    }
    ruleValue.value = ''
    await loadRules()
  } finally {
    ruleLoading.value = false
  }
}

async function deleteRule(id: number) {
  await fetch(`${API}/user-spam-rules/${id}`, {
    method: 'DELETE',
    headers: auth.authHeader(),
  })
  await loadRules()
}

async function loadProfile() {
  const res = await fetch(`${API}/users/me`, { headers: auth.authHeader() })
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

  if (
    profilePwForm.value.new_password &&
    profilePwForm.value.new_password !== profilePwForm.value.confirm_password
  ) {
    profileErr.value = '새 비밀번호가 일치하지 않습니다.'
    return
  }

  profileSaving.value = true
  try {
    const res = await fetch(`${API}/users/me`, {
      method: 'PATCH',
      headers: auth.authHeader(),
      body: JSON.stringify({
        ...profileForm.value,
        current_password: profilePwForm.value.current_password,
        new_password: profilePwForm.value.new_password,
      }),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) {
      profileErr.value = data.detail || '정보 저장에 실패했습니다.'
      return
    }
    profileMsg.value = '정보가 저장되었습니다.'
    profilePwForm.value = { current_password: '', new_password: '', confirm_password: '' }
    profileEdit.value = false
    await loadProfile()
  } finally {
    profileSaving.value = false
  }
}

function logout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  await Promise.all([loadHistory(), loadReports(), loadKeywords(), loadRules(), loadProfile(), loadSettings()])
})
</script>

<template>
  <div class="page">
    <aside class="sidebar">
      <div>
        <h1 class="brand">SpamGuard</h1>
        <p class="welcome">{{ auth.username }} 님</p>

        <nav class="nav">
          <button :class="['nav-btn', { active: activeTab === 'chat' }]" @click="activeTab = 'chat'">AI 판별</button>
          <button :class="['nav-btn', { active: activeTab === 'file' }]" @click="activeTab = 'file'">파일 판별</button>
          <button :class="['nav-btn', { active: activeTab === 'report' }]" @click="activeTab = 'report'">상담 요청</button>
          <button :class="['nav-btn', { active: activeTab === 'keywords' }]" @click="activeTab = 'keywords'">스팸 단어 목록</button>
          <button :class="['nav-btn', { active: activeTab === 'rules' }]" @click="activeTab = 'rules'">내 규칙</button>
          <button :class="['nav-btn', { active: activeTab === 'profile' }]" @click="activeTab = 'profile'">내 정보</button>
        </nav>
      </div>

      <button class="logout-btn" @click="logout">로그아웃</button>
    </aside>

    <main class="main">
      <section v-if="activeTab === 'chat'" class="panel">
<div class="panel-header">
          <div>
            <h2>AI 스팸 판별</h2>
            <p>문장을 입력하면 GPT와 Qwen이 각각 판별합니다.</p>
            <p class="debug-line">AI 판별 입력은 LangSmith에 기록됩니다.</p>
          </div>
        </div>

        <div ref="chatBody" class="chat-body">
          <div v-if="!messages.length" class="empty">대화를 시작해보세요.</div>
          <div v-for="entry in chatEntries" :key="entry.id">
            <div v-if="entry.type === 'user'" class="msg-row user">
              <div class="msg-bubble user">
                {{ entry.message.message }}
              </div>
            </div>

            <div v-else class="ai-compare-row">
              <div
                v-for="msg in entry.messages"
                :key="msg.id"
                class="ai-compare-card"
                :class="{ spam: msg.is_spam === 1, ham: msg.is_spam === 0 }"
              >
                <div class="ai-compare-head">
                  <span class="ai-model">{{ msg.modelName }}</span>
                  <span v-if="msg.is_spam === 1" class="msg-badge spam-text">스팸</span>
                  <span v-else-if="msg.is_spam === 0" class="msg-badge ham-text">정상</span>
                </div>
                <div class="ai-compare-body">{{ msg.body || msg.message }}</div>
              </div>
            </div>
          </div>
          <div v-if="chatLoading" class="loading">판별 중...</div>
        </div>

        <div class="chat-input-row">
          <textarea
            v-model="chatInput"
            class="chat-input"
            rows="1"
            placeholder="문장을 입력하세요"
            @keydown="onChatKey"
            @input="autoResize"
          />
          <button class="primary-btn" :disabled="!chatInput.trim() || chatLoading" @click="sendChat">전송</button>
        </div>
      </section>

      <section v-else-if="activeTab === 'file'" class="panel">
        <div class="panel-header">
          <div>
            <h2>파일 스팸 판별</h2>
            <p>PDF · TXT · EML 파일을 업로드하면 스팸 여부를 판별합니다.</p>
          </div>
        </div>

        <!-- Drop zone -->
        <div v-if="!fileResult && !fileLoading"
          class="file-dropzone"
          :class="{ dragging: isDragging }"
          @dragover="onFileDragover"
          @dragleave="onFileDragleave"
          @drop="onFileDrop"
          @click="fileInputRef?.click()"
        >
          <input ref="fileInputRef" type="file" accept="*" style="display:none" @change="onFileInputChange" />
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#667eea" stroke-width="1.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <p class="drop-main">여기에 파일을 드래그하거나 클릭하여 선택</p>
          <p class="drop-sub">PDF · DOCX · XLSX · PPTX · HWP · TXT · EML 등 모든 파일</p>
          <p v-if="fileError" class="file-err">{{ fileError }}</p>
        </div>

        <!-- Loading -->
        <div v-if="fileLoading" class="file-loading">
          <div class="file-spinner" />
          <p>파일 분석 중...</p>
        </div>

        <!-- Result -->
        <div v-if="fileResult" class="file-result">
          <div class="file-verdict" :class="fileResult.is_spam ? 'spam' : 'ham'">
            <span>{{ fileResult.is_spam ? '🚨 스팸 파일' : '✅ 정상 파일' }}</span>
            <span class="file-name">{{ fileResult.filename }}</span>
          </div>
          <div v-for="r in fileResult.replies" :key="r.model" class="file-model-card" :class="r.is_spam ? 'spam' : 'ham'">
            <div class="file-model-label">{{ r.model }}</div>
            <div class="file-model-body">{{ r.reply }}</div>
          </div>
          <div v-if="fileResult.extracted_text" class="file-model-card">
            <div class="file-model-label">추출 텍스트 미리보기</div>
            <div class="file-model-body">{{ fileResult.extracted_text }}</div>
          </div>
          <button class="secondary-btn" @click="fileResult = null; fileError = ''">다른 파일 검사</button>
        </div>
      </section>

      <section v-else-if="activeTab === 'report'" class="panel">
        <div class="panel-header">
          <div>
            <h2>상담 요청</h2>
            <p>판별이 애매한 메일은 상담사에게 전달할 수 있습니다.</p>
          </div>
        </div>

        <div class="content">
          <div v-if="!reportEnabled" class="notice error">현재 상담 요청이 비활성화되어 있습니다.</div>
          <textarea
            v-model="reportInput"
            class="report-input"
            rows="5"
            :disabled="!reportEnabled"
            placeholder="상담이 필요한 메일 내용을 입력하세요"
          />
          <div class="actions">
            <button class="primary-btn" :disabled="!reportInput.trim() || reportLoading || !reportEnabled" @click="submitReport">
              {{ reportLoading ? '등록 중...' : '상담 요청 보내기' }}
            </button>
          </div>
          <div v-if="reportSuccess" class="notice">{{ reportSuccess }}</div>

          <h3 class="section-title">요청 내역</h3>
          <div v-if="!reports.length" class="empty">상담 요청 내역이 없습니다.</div>
          <div v-for="report in reports" :key="report.id" class="card">
            <div class="card-top">
              <span class="pill">{{ statusLabel[report.status] ?? report.status }}</span>
              <span>{{ new Date(report.created_at).toLocaleString('ko-KR') }}</span>
            </div>
            <p class="card-body">{{ report.email_content }}</p>
            <p v-if="report.counselor_note" class="card-note">
              상담사 답변: {{ report.counselor_note }}
            </p>
          </div>
        </div>
      </section>

      <section v-else-if="activeTab === 'keywords'" class="panel">
        <div class="panel-header">
          <div>
            <h2>스팸 단어 목록</h2>
            <p>상담사와 관리자가 등록한 공용 스팸 키워드입니다.</p>
          </div>
          <button class="primary-btn" @click="loadKeywords">새로고침</button>
        </div>

        <div class="content">
          <div v-if="!keywords.length" class="empty">등록된 스팸 단어가 없습니다.</div>
          <template v-else>
            <div class="keyword-summary">
              <div class="summary-card">
                <span class="summary-label">전체 키워드</span>
                <strong class="summary-value">{{ keywords.length }}</strong>
              </div>
              <div class="summary-card">
                <span class="summary-label">현재 표시</span>
                <strong class="summary-value">{{ keywordPreview.length }}</strong>
              </div>
              <div class="summary-card wide">
                <span class="summary-label">최근 등록</span>
                <strong class="summary-value small">{{ latestKeywordDate }}</strong>
              </div>
            </div>

            <div class="keyword-grid">
              <div v-for="keyword in keywordPreview" :key="keyword.id" class="keyword-card">
                <span class="keyword-text">{{ keyword.keyword }}</span>
                <span class="keyword-date">{{ new Date(keyword.created_at).toLocaleDateString('ko-KR') }}</span>
              </div>
            </div>

            <div v-if="keywords.length > keywordPreview.length" class="notice">
              총 {{ keywords.length }}개 중 {{ keywordPreview.length }}개를 먼저 보여주고 있습니다.
            </div>
          </template>
        </div>
      </section>

      <section v-else-if="activeTab === 'rules'" class="panel">
        <div class="panel-header">
          <div>
            <h2>내 스팸 규칙</h2>
            <p>내가 직접 차단하고 싶은 단어, 문장, 이메일을 등록할 수 있습니다.</p>
          </div>
        </div>

        <div class="content">
          <div class="rule-row">
            <select v-model="ruleType" class="select">
              <option value="keyword">단어</option>
              <option value="sentence">문장</option>
              <option value="email">이메일</option>
            </select>
            <input v-model="ruleValue" class="text-input" placeholder="차단 규칙 입력" @keydown.enter="addRule" />
            <button class="primary-btn" :disabled="!ruleValue.trim() || ruleLoading" @click="addRule">추가</button>
          </div>
          <div v-if="ruleMsg" class="notice error">{{ ruleMsg }}</div>

          <div v-for="group in ['keyword', 'sentence', 'email']" :key="group" class="rule-group">
            <h3 class="section-title">{{ ruleTypeLabel[group] }}</h3>
            <div v-if="!groupedRules[group as keyof typeof groupedRules].length" class="empty">등록된 규칙이 없습니다.</div>
            <div v-else class="chips">
              <span v-for="rule in groupedRules[group as keyof typeof groupedRules]" :key="rule.id" class="chip">
                {{ rule.value }}
                <button class="chip-del" @click="deleteRule(rule.id)">x</button>
              </span>
            </div>
          </div>
        </div>
      </section>

      <section v-else class="panel">
        <div class="panel-header">
          <div>
            <h2>내 정보</h2>
            <p>회원 정보를 확인하고 수정할 수 있습니다.</p>
          </div>
          <button v-if="!profileEdit" class="primary-btn" @click="profileEdit = true">수정</button>
        </div>

        <div v-if="profile" class="content">
          <template v-if="!profileEdit">
            <div class="profile-grid">
              <div class="profile-item"><strong>아이디</strong><span>{{ profile.username }}</span></div>
              <div class="profile-item"><strong>닉네임</strong><span>{{ profile.nickname }}</span></div>
              <div class="profile-item"><strong>이름</strong><span>{{ profile.name }}</span></div>
              <div class="profile-item"><strong>전화번호</strong><span>{{ profile.phone }}</span></div>
              <div class="profile-item"><strong>이메일</strong><span>{{ profile.email }}</span></div>
              <div class="profile-item"><strong>우편번호</strong><span>{{ profile.postal_code }}</span></div>
              <div class="profile-item full"><strong>주소</strong><span>{{ profile.address }}</span></div>
              <div class="profile-item full"><strong>상세주소</strong><span>{{ profile.detail_address }}</span></div>
            </div>
          </template>

          <template v-else>
            <div class="profile-grid">
              <label class="field"><span>닉네임</span><input v-model="profileForm.nickname" class="text-input" /></label>
              <label class="field"><span>이름</span><input v-model="profileForm.name" class="text-input" /></label>
              <label class="field"><span>전화번호</span><input v-model="profileForm.phone" class="text-input" /></label>
              <label class="field"><span>이메일</span><input v-model="profileForm.email" class="text-input" /></label>
              <label class="field"><span>우편번호</span><input v-model="profileForm.postal_code" class="text-input" /></label>
              <label class="field full"><span>주소</span><input v-model="profileForm.address" class="text-input" /></label>
              <label class="field full"><span>상세주소</span><input v-model="profileForm.detail_address" class="text-input" /></label>
              <label class="field full"><span>현재 비밀번호</span><input v-model="profilePwForm.current_password" type="password" class="text-input" /></label>
              <label class="field"><span>새 비밀번호</span><input v-model="profilePwForm.new_password" type="password" class="text-input" /></label>
              <label class="field"><span>새 비밀번호 확인</span><input v-model="profilePwForm.confirm_password" type="password" class="text-input" /></label>
            </div>

            <div class="actions">
              <button class="ghost-btn" @click="profileEdit = false">취소</button>
              <button class="primary-btn" :disabled="profileSaving" @click="saveProfile">
                {{ profileSaving ? '저장 중...' : '저장' }}
              </button>
            </div>
          </template>

          <div v-if="profileMsg" class="notice">{{ profileMsg }}</div>
          <div v-if="profileErr" class="notice error">{{ profileErr }}</div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
  background: linear-gradient(180deg, #f7f9fc 0%, #eef3ff 100%);
  color: #1f2937;
}

.sidebar {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 24px 18px;
  background: #111827;
  color: #fff;
}

.brand {
  margin: 0 0 6px;
  font-size: 28px;
}

.welcome {
  margin: 0 0 24px;
  color: #cbd5e1;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-btn,
.logout-btn,
.primary-btn,
.ghost-btn,
.chip-del {
  cursor: pointer;
}

.nav-btn,
.logout-btn {
  border: 0;
  border-radius: 12px;
  padding: 12px 14px;
  text-align: left;
  background: transparent;
  color: inherit;
  font: inherit;
}

.nav-btn.active {
  background: #2563eb;
}

.logout-btn {
  background: rgba(255, 255, 255, 0.08);
}

.main {
  padding: 24px;
}

.panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 48px);
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 24px;
  border-bottom: 1px solid #e5e7eb;
}

.panel-header h2 {
  margin: 0;
}

.panel-header p {
  margin: 6px 0 0;
  color: #6b7280;
}

.chat-body,
.content {
  flex: 1;
  overflow: auto;
  padding: 24px;
}

.chat-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.msg-row {
  display: flex;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-bubble {
  max-width: 70%;
  padding: 12px 14px;
  border-radius: 16px;
  background: #eef2ff;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-row.user .msg-bubble {
  background: #2563eb;
  color: #fff;
}

.ai-compare-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.ai-compare-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 132px;
  padding: 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, #eef2ff 0%, #f8faff 100%);
  border: 1px solid #c7d2fe;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.08);
}

.ai-compare-card.spam {
  background: linear-gradient(180deg, #fff1f2 0%, #fff7f7 100%);
  border-color: #fecaca;
}

.ai-compare-card.ham {
  background: linear-gradient(180deg, #f0fdf4 0%, #f7fff9 100%);
  border-color: #bbf7d0;
}

.ai-compare-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ai-model {
  font-size: 14px;
  font-weight: 800;
  color: #1e3a8a;
}

.ai-compare-card.spam .ai-model {
  color: #b91c1c;
}

.ai-compare-card.ham .ai-model {
  color: #15803d;
}

.ai-compare-body {
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-bubble.spam {
  background: #fef2f2;
  border: 1px solid #fecaca;
}

.msg-bubble.ham {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}

.msg-badge {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
}

.spam-text {
  color: #b91c1c;
}

.ham-text {
  color: #15803d;
}

.chat-input-row,
.rule-row,
.actions {
  display: flex;
  gap: 12px;
}

.chat-input-row {
  padding: 0 24px 24px;
}

.chat-input,
.report-input,
.text-input,
.select {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 12px;
  padding: 12px 14px;
  font: inherit;
  box-sizing: border-box;
}

.chat-input {
  resize: none;
}

.report-input {
  margin-bottom: 12px;
}

.primary-btn,
.ghost-btn {
  border: 0;
  border-radius: 12px;
  padding: 12px 16px;
  font: inherit;
  white-space: nowrap;
}

.primary-btn {
  background: #2563eb;
  color: #fff;
}

.ghost-btn {
  background: #e5e7eb;
}

.notice {
  margin-top: 12px;
  border-radius: 12px;
  padding: 12px 14px;
  background: #eff6ff;
  color: #1d4ed8;
}

.notice.error {
  background: #fef2f2;
  color: #b91c1c;
}

.section-title {
  margin: 24px 0 12px;
}

.card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 12px;
}

.card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #6b7280;
  font-size: 14px;
}

.card-body,
.card-note {
  margin: 12px 0 0;
  white-space: pre-wrap;
}

.pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  background: #e0e7ff;
  color: #3730a3;
  font-size: 12px;
  font-weight: 700;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.keyword-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #eff6ff, #eef2ff);
  border: 1px solid #c7d2fe;
}

.summary-card.wide {
  background: linear-gradient(135deg, #f8fafc, #eef2ff);
}

.summary-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.summary-value {
  font-size: 28px;
  font-weight: 800;
  color: #1e3a8a;
  line-height: 1;
}

.summary-value.small {
  font-size: 16px;
  line-height: 1.35;
}

.keyword-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.keyword-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 104px;
  padding: 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid #dbeafe;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.06);
}

.keyword-text {
  font-size: 18px;
  font-weight: 800;
  color: #1e293b;
  word-break: break-word;
}

.keyword-date {
  margin-top: auto;
  font-size: 12px;
  color: #64748b;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 8px 12px;
  background: #eef2ff;
}

.chip-del {
  border: 0;
  background: transparent;
  color: #6b7280;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.profile-item,
.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.profile-item span {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 14px;
  background: #f8fafc;
}

.full {
  grid-column: 1 / -1;
}

.empty,
.loading {
  color: #6b7280;
}

@media (max-width: 900px) {
  .page {
    grid-template-columns: 1fr;
  }

  .sidebar {
    gap: 16px;
  }

  .panel {
    height: auto;
    min-height: calc(100vh - 220px);
  }

  .profile-grid {
    grid-template-columns: 1fr;
  }

  .msg-bubble {
    max-width: 100%;
  }

  .keyword-summary {
    grid-template-columns: 1fr;
  }

  .ai-compare-row {
    grid-template-columns: 1fr;
  }
}

/* 파일 판별 */
.file-dropzone {
  border: 2px dashed #d1d5db;
  border-radius: 14px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  margin-bottom: 16px;
}
.file-dropzone:hover, .file-dropzone.dragging {
  border-color: #667eea;
  background: #f5f3ff;
}
.drop-main { font-size: 14px; font-weight: 500; color: #374151; margin: 12px 0 4px; }
.drop-sub  { font-size: 12px; color: #9ca3af; margin: 0; }
.file-err  { color: #ef4444; font-size: 13px; margin-top: 10px; }
.file-loading {
  display: flex; flex-direction: column; align-items: center;
  gap: 14px; padding: 48px 0; color: #667eea;
}
.file-spinner {
  width: 36px; height: 36px;
  border: 3px solid #e5e7eb;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.file-result { display: flex; flex-direction: column; gap: 12px; }
.file-verdict {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-radius: 12px; font-weight: 700; font-size: 15px;
}
.file-verdict.spam { background: #fef2f2; border: 1.5px solid #fca5a5; color: #dc2626; }
.file-verdict.ham  { background: #f0fdf4; border: 1.5px solid #86efac; color: #16a34a; }
.file-name { font-size: 12px; font-weight: 400; color: #6b7280; }
.file-model-card {
  padding: 14px 16px; border-radius: 12px; border: 1px solid #e5e7eb;
}
.file-model-card.spam { background: #fff7f7; }
.file-model-card.ham  { background: #f7fff9; }
.file-model-label { font-size: 12px; font-weight: 600; color: #667eea; margin-bottom: 6px; }
.file-model-body  { font-size: 13px; color: #374151; line-height: 1.6; white-space: pre-wrap; }
.secondary-btn {
  padding: 10px 20px; border-radius: 10px;
  border: 1.5px solid #667eea; background: #fff;
  color: #667eea; font-size: 14px; font-weight: 600;
  cursor: pointer; transition: background 0.2s;
}
.secondary-btn:hover { background: #f0f0ff; }
</style>
