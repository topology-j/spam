import { ref } from 'vue'
import { defineStore } from 'pinia'

export interface Message {
  id: number
  role: 'user' | 'result'
  text: string
  isSpam?: boolean
  timestamp: Date
}

export const useSpamStore = defineStore('spam', () => {
  const messages = ref<Message[]>([])
  const loading = ref(false)
  let nextId = 0

  async function sendMessage(text: string) {
    messages.value.push({
      id: nextId++,
      role: 'user',
      text,
      timestamp: new Date(),
    })

    loading.value = true

    try {
      const res = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const data = await res.json()
      const isSpam = data.result === 'Spam: Yes'

      messages.value.push({
        id: nextId++,
        role: 'result',
        text: isSpam ? '🚨 스팸 메일입니다' : '✅ 정상 메일입니다',
        isSpam,
        timestamp: new Date(),
      })
    } catch {
      messages.value.push({
        id: nextId++,
        role: 'result',
        text: '⚠️ 서버에 연결할 수 없습니다',
        isSpam: undefined,
        timestamp: new Date(),
      })
    } finally {
      loading.value = false
    }
  }

  async function sendFile(file: File) {
    messages.value.push({
      id: nextId++,
      role: 'user',
      text: `📎 ${file.name}`,
      timestamp: new Date(),
    })
    loading.value = true
    try {
      const token = localStorage.getItem('token') ?? ''
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('http://127.0.0.1:8000/chat/file', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '서버 오류' }))
        throw new Error(err.detail ?? '업로드 실패')
      }
      const data = await res.json()
      const isSpam = data.is_spam as boolean
      const modelLines = (data.replies as { model: string; reply: string }[])
        .map(r => r.reply).join('\n\n')
      messages.value.push({
        id: nextId++,
        role: 'result',
        text: (isSpam ? '🚨 스팸 파일입니다\n\n' : '✅ 정상 파일입니다\n\n') + modelLines,
        isSpam,
        timestamp: new Date(),
      })
    } catch (e: unknown) {
      messages.value.push({
        id: nextId++,
        role: 'result',
        text: `⚠️ ${e instanceof Error ? e.message : '업로드 실패'}`,
        timestamp: new Date(),
      })
    } finally {
      loading.value = false
    }
  }

  function clearMessages() {
    messages.value = []
  }

  return { messages, loading, sendMessage, sendFile, clearMessages }
})
