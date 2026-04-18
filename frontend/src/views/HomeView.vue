<script setup lang="ts">
import { ref, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSpamStore } from '@/stores/spam'
import { useAuthStore } from '@/stores/auth'

const store = useSpamStore()
const auth = useAuthStore()
const router = useRouter()
const input = ref('')
const chatBody = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)

function openFilePicker() {
  fileInput.value?.click()
}

async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  ;(e.target as HTMLInputElement).value = ''
  await store.sendFile(file)
  await nextTick()
  chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
}

function goDashboard() {
  const role = auth.role || localStorage.getItem('role')
  if (role === 'admin' || role === 'developer') router.push('/admin')
  else if (role === 'counselor') router.push('/counselor')
  else router.push('/user')
}

const isLoggedIn = computed(() => !!(auth.token || localStorage.getItem('token')))

const placeholders = [
  '메일 내용을 입력하세요...',
  '예: 무료 당첨 클릭하세요!',
  '예: 내일 회의 일정 안내드립니다.',
]
const placeholder = placeholders[Math.floor(Math.random() * placeholders.length)]

async function send() {
  const text = input.value.trim()
  if (!text || store.loading) return
  input.value = ''
  const ta = document.querySelector('.input') as HTMLTextAreaElement
  if (ta) ta.style.height = 'auto'
  await store.sendMessage(text)
  await nextTick()
  chatBody.value?.scrollTo({ top: chatBody.value.scrollHeight, behavior: 'smooth' })
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function autoResize(e: Event) {
  const ta = e.target as HTMLTextAreaElement
  ta.style.height = 'auto'
  ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
}

const hasMessages = computed(() => store.messages.length > 0)
</script>

<template>
  <div class="page">
    <div class="card">
      <!-- Header -->
      <div class="header">
        <div class="header-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
            <polyline points="22,6 12,13 2,6"/>
          </svg>
        </div>
        <div>
          <h1 class="header-title">스팸 감지기</h1>
          <p class="header-sub">메일 내용을 입력하면 스팸 여부를 판별합니다</p>
        </div>
        <div class="header-right">
          <button class="file-btn" @click="router.push('/file-check')" title="파일 스팸 판별">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            파일 판별
          </button>
          <button v-if="isLoggedIn" class="dash-btn" @click="goDashboard()">대시보드</button>
          <button v-else class="dash-btn" @click="router.push('/login')">로그인</button>
          <button v-if="hasMessages" class="clear-btn" @click="store.clearMessages()" title="대화 초기화">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14H6L5 6"/>
            <path d="M10 11v6"/><path d="M14 11v6"/>
            <path d="M9 6V4h6v2"/>
          </svg>
          </button>
        </div>
      </div>

      <!-- Chat body -->
      <div class="chat-body" ref="chatBody">
        <!-- Empty state -->
        <div v-if="!hasMessages" class="empty-state">
          <div class="empty-icon">
            <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
              <!-- 귀 (왼쪽) -->
              <ellipse cx="30" cy="38" rx="14" ry="20" fill="#c8a96e" transform="rotate(-15 30 38)"/>
              <ellipse cx="30" cy="38" rx="9" ry="14" fill="#e8c99e" transform="rotate(-15 30 38)"/>
              <!-- 귀 (오른쪽) -->
              <ellipse cx="90" cy="38" rx="14" ry="20" fill="#c8a96e" transform="rotate(15 90 38)"/>
              <ellipse cx="90" cy="38" rx="9" ry="14" fill="#e8c99e" transform="rotate(15 90 38)"/>
              <!-- 머리 -->
              <ellipse cx="60" cy="60" rx="36" ry="34" fill="#deb887"/>
              <!-- 얼굴 밝은 부분 -->
              <ellipse cx="60" cy="68" rx="22" ry="18" fill="#f5deb3"/>
              <!-- 눈 (왼쪽) -->
              <circle cx="46" cy="54" r="6" fill="white"/>
              <circle cx="46" cy="54" r="4" fill="#3b2a1a"/>
              <circle cx="44" cy="52" r="1.5" fill="white"/>
              <!-- 눈 (오른쪽) -->
              <circle cx="74" cy="54" r="6" fill="white"/>
              <circle cx="74" cy="54" r="4" fill="#3b2a1a"/>
              <circle cx="72" cy="52" r="1.5" fill="white"/>
              <!-- 코 -->
              <ellipse cx="60" cy="66" rx="7" ry="5" fill="#8b5e3c"/>
              <ellipse cx="58" cy="65" rx="2" ry="1.5" fill="#b07850" opacity="0.5"/>
              <!-- 입 -->
              <path d="M53 72 Q60 78 67 72" stroke="#8b5e3c" stroke-width="2" fill="none" stroke-linecap="round"/>
              <!-- 볼터치 -->
              <ellipse cx="38" cy="65" rx="7" ry="4" fill="#ffb6c1" opacity="0.5"/>
              <ellipse cx="82" cy="65" rx="7" ry="4" fill="#ffb6c1" opacity="0.5"/>
              <!-- 몸 -->
              <ellipse cx="60" cy="100" rx="28" ry="18" fill="#deb887"/>
              <!-- 앞발 -->
              <ellipse cx="44" cy="112" rx="10" ry="7" fill="#deb887"/>
              <ellipse cx="76" cy="112" rx="10" ry="7" fill="#deb887"/>
              <!-- 꼬리 -->
              <path d="M88 95 Q105 80 98 70" stroke="#c8a96e" stroke-width="8" fill="none" stroke-linecap="round"/>
            </svg>
          </div>
          <p class="empty-title">메일을 분석해드릴게요</p>
          <p class="empty-desc">아래에 메일 내용을 붙여넣거나 직접 입력해보세요</p>
          <div class="example-chips">
            <button class="chip" @click="input = '무료 경품 당첨! 지금 바로 클릭하세요'">스팸 예시</button>
            <button class="chip" @click="input = '내일 오후 2시 팀 회의 일정 안내드립니다'">정상 예시</button>
          </div>
        </div>

        <!-- Messages -->
        <TransitionGroup name="msg" tag="div" class="messages">
          <div
            v-for="msg in store.messages"
            :key="msg.id"
            class="message-row"
            :class="msg.role"
          >
            <div
              class="bubble"
              :class="[
                msg.role,
                { spam: msg.isSpam === true, ham: msg.isSpam === false, error: msg.isSpam === undefined && msg.role === 'result' }
              ]"
            >
              {{ msg.text }}
            </div>
          </div>
        </TransitionGroup>

        <!-- Loading -->
        <div v-if="store.loading" class="message-row result">
          <div class="bubble result loading-bubble">
            <span class="dot" /><span class="dot" /><span class="dot" />
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="input-area">
        <input ref="fileInput" type="file" accept=".pdf,.txt,.eml" style="display:none" @change="onFileChange" />
        <button class="upload-btn" :disabled="store.loading" @click="openFilePicker" title="파일 업로드 (PDF/TXT/EML)">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </button>
        <textarea
          v-model="input"
          class="input"
          :placeholder="placeholder"
          rows="1"
          @keydown="onKeydown"
          @input="autoResize"
        />
        <button class="send-btn" :disabled="!input.trim() || store.loading" @click="send">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.card {
  width: 100%;
  max-width: 680px;
  height: min(800px, 90vh);
  background: #fff;
  border-radius: 24px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 24px;
  border-bottom: 1px solid #f0f0f5;
}

.header-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.header-title {
  font-size: 17px;
  font-weight: 700;
  color: #1a1a2e;
  line-height: 1.2;
}

.header-sub {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

.header-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1.5px solid #e5e7eb;
  background: transparent;
  color: #6b7280;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.file-btn:hover {
  border-color: #667eea;
  color: #667eea;
  background: #f5f3ff;
}

.dash-btn {
  padding: 8px 16px;
  border-radius: 10px;
  border: 1.5px solid #667eea;
  background: transparent;
  color: #667eea;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.dash-btn:hover {
  background: #667eea;
  color: #fff;
}

.clear-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: #f5f5f8;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
}

.clear-btn:hover {
  background: #fee2e2;
  color: #ef4444;
}

/* Chat body */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.chat-body::-webkit-scrollbar {
  width: 4px;
}
.chat-body::-webkit-scrollbar-track {
  background: transparent;
}
.chat-body::-webkit-scrollbar-thumb {
  background: #e5e7eb;
  border-radius: 99px;
}

/* Empty state */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
}

.empty-icon {
  margin-bottom: 8px;
  filter: drop-shadow(0 4px 12px rgba(0,0,0,0.12));
  animation: wag 2s ease-in-out infinite;
}

@keyframes wag {
  0%, 100% { transform: rotate(-3deg); }
  50% { transform: rotate(3deg); }
}

.empty-title {
  font-size: 17px;
  font-weight: 600;
  color: #374151;
}

.empty-desc {
  font-size: 13px;
  color: #9ca3af;
}

.example-chips {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
  justify-content: center;
}

.chip {
  padding: 8px 16px;
  border-radius: 99px;
  border: 1.5px solid #e5e7eb;
  background: #fff;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.chip:hover {
  border-color: #667eea;
  color: #667eea;
  background: #ede9fe;
}

/* Messages */
.messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-row {
  display: flex;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.result {
  justify-content: flex-start;
}

.bubble {
  max-width: 75%;
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 14.5px;
  line-height: 1.5;
  word-break: break-word;
}

.bubble.user {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-bottom-right-radius: 5px;
}

.bubble.result.spam {
  background: #fee2e2;
  color: #991b1b;
  border: 1.5px solid #fecaca;
  border-bottom-left-radius: 5px;
  font-weight: 600;
}

.bubble.result.ham {
  background: #d1fae5;
  color: #065f46;
  border: 1.5px solid #a7f3d0;
  border-bottom-left-radius: 5px;
  font-weight: 600;
}

.bubble.result.error {
  background: #fff7ed;
  color: #92400e;
  border: 1.5px solid #fed7aa;
  border-bottom-left-radius: 5px;
}

/* Loading dots */
.loading-bubble {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 14px 18px;
  background: #f3f4f6;
  border: 1.5px solid #e5e7eb;
  border-bottom-left-radius: 5px;
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

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
  40% { transform: scale(1.2); opacity: 1; }
}

/* Input area */
.input-area {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid #f0f0f5;
}

.input {
  flex: 1;
  padding: 11px 16px;
  border: 1.5px solid #e5e7eb;
  border-radius: 14px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  line-height: 1.5;
  color: #1a1a2e;
  background: #f9fafb;
  transition: border-color 0.2s, background 0.2s;
  min-height: 44px;
  max-height: 120px;
  overflow-y: auto;
}

.input:focus {
  border-color: #667eea;
  background: #fff;
}

.input::placeholder {
  color: #c4c4cc;
}

.upload-btn {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  border: 1.5px solid #e5e7eb;
  background: #f9fafb;
  color: #667eea;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.2s, border-color 0.2s;
}

.upload-btn:hover:not(:disabled) {
  background: #f0f0ff;
  border-color: #667eea;
}

.upload-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  border: none;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: opacity 0.2s, transform 0.1s;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.88;
  transform: scale(1.05);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Transition */
.msg-enter-active {
  transition: all 0.25s ease;
}
.msg-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
</style>
