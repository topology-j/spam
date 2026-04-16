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
      const res = await fetch('http://localhost:8000/chat', {
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

  function clearMessages() {
    messages.value = []
  }

  return { messages, loading, sendMessage, clearMessages }
})
