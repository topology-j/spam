import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

const API = 'http://localhost:8000'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') ?? '')
  const username = ref(localStorage.getItem('username') ?? '')
  const role = ref(localStorage.getItem('role') ?? '')

  const isLoggedIn = computed(() => !!token.value)

  async function login(user: string, password: string) {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail ?? '로그인 실패')

    token.value = data.token
    username.value = data.username
    role.value = data.role
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', data.username)
    localStorage.setItem('role', data.role)
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  function authHeader() {
    return { Authorization: `Bearer ${token.value}`, 'Content-Type': 'application/json' }
  }

  return { token, username, role, isLoggedIn, login, logout, authHeader }
})
