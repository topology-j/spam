<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const isDragging = ref(false)
const loading = ref(false)
const result = ref<null | {
  filename: string
  is_spam: boolean
  replies: { model: string; reply: string; is_spam: boolean }[]
  extracted_text: string
}>(null)
const error = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

function goHome() { router.push('/') }

function onDragover(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}
function onDragleave() { isDragging.value = false }
function onDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  const file = e.dataTransfer?.files[0]
  if (file) upload(file)
}
function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) upload(file)
  ;(e.target as HTMLInputElement).value = ''
}

async function upload(file: File) {
  const allowed = ['.pdf', '.txt', '.eml']
  if (!allowed.some(ext => file.name.toLowerCase().endsWith(ext))) {
    error.value = 'PDF, TXT, EML 파일만 지원합니다'
    return
  }
  error.value = ''
  result.value = null
  loading.value = true

  try {
    const token = auth.token || localStorage.getItem('token') || ''
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('http://127.0.0.1:8001/chat/file', {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: '서버 오류' }))
      throw new Error(err.detail ?? '업로드 실패')
    }
    const data = await res.json()
    result.value = {
      filename: file.name,
      is_spam: data.is_spam,
      replies: data.replies ?? [],
      extracted_text: data.text_preview ?? '',
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : '업로드 실패'
  } finally {
    loading.value = false
  }
}

function reset() {
  result.value = null
  error.value = ''
}
</script>

<template>
  <div class="page">
    <div class="card">
      <!-- Header -->
      <div class="header">
        <button class="back-btn" @click="goHome">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
        <div class="header-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div>
          <h1 class="header-title">파일 스팸 판별</h1>
          <p class="header-sub">PDF · TXT · EML 파일을 업로드하세요</p>
        </div>
      </div>

      <!-- Body -->
      <div class="body">
        <!-- Drop zone -->
        <div v-if="!result && !loading"
          class="dropzone"
          :class="{ dragging: isDragging }"
          @dragover="onDragover"
          @dragleave="onDragleave"
          @drop="onDrop"
          @click="fileInput?.click()"
        >
          <input ref="fileInput" type="file" accept=".pdf,.txt,.eml" style="display:none" @change="onFileChange" />
          <div class="drop-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <p class="drop-text">여기에 파일을 드래그하거나 클릭하여 선택</p>
          <p class="drop-hint">PDF · TXT · EML 지원</p>
          <div v-if="error" class="error-msg">{{ error }}</div>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="status-box">
          <div class="spinner" />
          <p>파일 분석 중...</p>
        </div>

        <!-- Result -->
        <div v-if="result" class="result-wrap">
          <div class="verdict-banner" :class="result.is_spam ? 'spam' : 'ham'">
            <span class="verdict-icon">{{ result.is_spam ? '🚨' : '✅' }}</span>
            <div>
              <div class="verdict-title">{{ result.is_spam ? '스팸 파일' : '정상 파일' }}</div>
              <div class="verdict-filename">{{ result.filename }}</div>
            </div>
          </div>

          <div class="model-cards">
            <div v-for="r in result.replies" :key="r.model" class="model-card" :class="r.is_spam ? 'spam' : 'ham'">
              <div class="model-label">{{ r.model }}</div>
              <div class="model-reply">{{ r.reply }}</div>
            </div>
          </div>

          <button class="reset-btn" @click="reset">다른 파일 검사</button>
        </div>
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
  max-width: 640px;
  background: #fff;
  border-radius: 24px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.18);
  overflow: hidden;
}

.header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid #f0f0f5;
}

.back-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #667eea;
  display: flex;
  align-items: center;
  padding: 4px;
  border-radius: 8px;
}

.back-btn:hover { background: #f0f0ff; }

.header-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.header-title { font-size: 18px; font-weight: 700; color: #1a1a2e; margin: 0; }
.header-sub { font-size: 12px; color: #888; margin: 2px 0 0; }

.body { padding: 32px 24px; }

.dropzone {
  border: 2px dashed #d1d5db;
  border-radius: 16px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.dropzone:hover, .dropzone.dragging {
  border-color: #667eea;
  background: #f5f3ff;
}

.drop-icon { color: #667eea; margin-bottom: 16px; }
.drop-text { font-size: 15px; color: #374151; font-weight: 500; margin: 0 0 6px; }
.drop-hint { font-size: 12px; color: #9ca3af; margin: 0; }
.error-msg { margin-top: 12px; color: #ef4444; font-size: 13px; }

.status-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 60px 0;
  color: #667eea;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e5e7eb;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.result-wrap { display: flex; flex-direction: column; gap: 16px; }

.verdict-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border-radius: 14px;
}

.verdict-banner.spam { background: #fef2f2; border: 1.5px solid #fca5a5; }
.verdict-banner.ham  { background: #f0fdf4; border: 1.5px solid #86efac; }

.verdict-icon { font-size: 32px; }
.verdict-title { font-size: 18px; font-weight: 700; color: #1a1a2e; }
.verdict-filename { font-size: 12px; color: #6b7280; margin-top: 2px; }

.model-cards { display: flex; flex-direction: column; gap: 10px; }

.model-card {
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
}

.model-card.spam { background: #fff7f7; }
.model-card.ham  { background: #f7fff9; }

.model-label { font-size: 12px; font-weight: 600; color: #667eea; margin-bottom: 6px; }
.model-reply { font-size: 13px; color: #374151; line-height: 1.6; white-space: pre-wrap; }

.reset-btn {
  margin-top: 8px;
  padding: 12px;
  border-radius: 12px;
  border: 1.5px solid #667eea;
  background: #fff;
  color: #667eea;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.reset-btn:hover { background: #f0f0ff; }
</style>
