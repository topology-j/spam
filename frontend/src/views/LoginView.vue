<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const API = 'http://127.0.0.1:8001'

const mode = ref<'login' | 'register'>('login')

// Login
const loginUsername = ref('')
const loginPassword = ref('')
const loginError = ref('')
const loginLoading = ref(false)

async function submitLogin() {
  loginError.value = ''
  if (!loginUsername.value || !loginPassword.value) {
    loginError.value = '아이디와 비밀번호를 입력해주세요.'
    return
  }
  loginLoading.value = true
  try {
    await auth.login(loginUsername.value, loginPassword.value)
    const dest = (auth.role === 'admin' || auth.role === 'developer') ? '/admin' : auth.role === 'counselor' ? '/counselor' : '/user'
    router.push(dest)
  } catch (e: any) {
    loginError.value = e.message
  } finally {
    loginLoading.value = false
  }
}

// Register
const regUsername = ref('')
const regPassword = ref('')
const regPasswordConfirm = ref('')
const regNickname = ref('')
const regName = ref('')
const regPhone = ref('')
const regEmail = ref('')
const regAddress = ref('')
const regDetailAddress = ref('')
const regPostalCode = ref('')
const regError = ref('')
const regSuccess = ref(false)
const regLoading = ref(false)

function formatPhone(e: Event) {
  const input = e.target as HTMLInputElement
  const digits = input.value.replace(/\D/g, '').slice(0, 11)
  if (digits.length <= 3) regPhone.value = digits
  else if (digits.length <= 7) regPhone.value = `${digits.slice(0,3)}-${digits.slice(3)}`
  else regPhone.value = `${digits.slice(0,3)}-${digits.slice(3,7)}-${digits.slice(7)}`
}

async function submitRegister() {
  regError.value = ''
  if (!regUsername.value || !regPassword.value || !regNickname.value ||
      !regName.value || !regPhone.value || !regEmail.value || !regAddress.value || !regPostalCode.value) {
    regError.value = '모든 항목을 입력해주세요.'
    return
  }
  if (regPassword.value !== regPasswordConfirm.value) {
    regError.value = '비밀번호가 일치하지 않습니다.'
    return
  }
  if (regPassword.value.length < 4) {
    regError.value = '비밀번호는 4자 이상이어야 합니다.'
    return
  }
  regLoading.value = true
  try {
    const res = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: regUsername.value,
        password: regPassword.value,
        nickname: regNickname.value,
        name: regName.value,
        phone: regPhone.value,
        email: regEmail.value,
        address: regAddress.value,
        detail_address: regDetailAddress.value,
        postal_code: regPostalCode.value,
      }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail ?? '회원가입 실패')
    regSuccess.value = true
    setTimeout(() => {
      regSuccess.value = false
      loginUsername.value = regUsername.value
      loginPassword.value = ''
      mode.value = 'login'
    }, 1500)
  } catch (e: any) {
    regError.value = e.message
  } finally {
    regLoading.value = false
  }
}

function fillAccount(u: string, p: string) {
  loginUsername.value = u
  loginPassword.value = p
}
</script>

<template>
  <div class="page">
    <div class="bg-orb orb1" />
    <div class="bg-orb orb2" />
    <div class="bg-orb orb3" />

    <div class="card">
      <!-- Logo -->
      <div class="logo-wrap">
        <!-- 귀여운 로봇 -->
        <div class="robot-wrap">
          <svg class="robot-svg" viewBox="0 0 120 130" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- 안테나 -->
            <line x1="60" y1="2" x2="60" y2="18" stroke="#8b5cf6" stroke-width="3" stroke-linecap="round"/>
            <circle cx="60" cy="2" r="4" fill="#6366f1">
              <animate attributeName="r" values="4;5.5;4" dur="1.5s" repeatCount="indefinite"/>
              <animate attributeName="fill" values="#6366f1;#a78bfa;#6366f1" dur="1.5s" repeatCount="indefinite"/>
            </circle>
            <!-- 머리 -->
            <rect x="22" y="18" width="76" height="58" rx="18" fill="url(#headGrad)"/>
            <!-- 머리 광택 -->
            <ellipse cx="42" cy="28" rx="10" ry="5" fill="white" opacity="0.2"/>
            <!-- 눈 왼쪽 -->
            <g>
              <rect x="33" y="33" width="20" height="16" rx="6" fill="#1e1b4b"/>
              <rect x="36" y="36" width="8" height="8" rx="3" fill="white"/>
              <circle cx="40" cy="40" r="3" fill="#6366f1"/>
              <circle cx="42" cy="38" r="1" fill="white"/>
              <!-- 눈 깜빡임 -->
              <rect x="33" y="33" width="20" height="16" rx="6" fill="url(#headGrad)" opacity="0">
                <animate attributeName="opacity" values="0;0;0;0;0;0;0;0;1;0;0;0;0;0;0;0;0;0;0;0" dur="4s" repeatCount="indefinite"/>
              </rect>
            </g>
            <!-- 눈 오른쪽 -->
            <g>
              <rect x="67" y="33" width="20" height="16" rx="6" fill="#1e1b4b"/>
              <rect x="70" y="36" width="8" height="8" rx="3" fill="white"/>
              <circle cx="74" cy="40" r="3" fill="#6366f1"/>
              <circle cx="76" cy="38" r="1" fill="white"/>
              <!-- 눈 깜빡임 -->
              <rect x="67" y="33" width="20" height="16" rx="6" fill="url(#headGrad)" opacity="0">
                <animate attributeName="opacity" values="0;0;0;0;0;0;0;0;1;0;0;0;0;0;0;0;0;0;0;0" dur="4s" repeatCount="indefinite"/>
              </rect>
            </g>
            <!-- 입 -->
            <rect x="38" y="58" width="44" height="10" rx="5" fill="#1e1b4b"/>
            <rect x="40" y="60" width="8" height="6" rx="2" fill="#6366f1"/>
            <rect x="52" y="60" width="8" height="6" rx="2" fill="#8b5cf6"/>
            <rect x="64" y="60" width="8" height="6" rx="2" fill="#6366f1"/>
            <!-- 귀 왼쪽 -->
            <rect x="12" y="32" width="12" height="22" rx="6" fill="#7c3aed"/>
            <rect x="15" y="37" width="6" height="12" rx="3" fill="#4c1d95" opacity="0.4"/>
            <!-- 귀 오른쪽 -->
            <rect x="96" y="32" width="12" height="22" rx="6" fill="#7c3aed"/>
            <rect x="99" y="37" width="6" height="12" rx="3" fill="#4c1d95" opacity="0.4"/>
            <!-- 목 -->
            <rect x="50" y="76" width="20" height="10" rx="4" fill="#7c3aed"/>
            <!-- 몸통 -->
            <rect x="18" y="86" width="84" height="38" rx="16" fill="url(#bodyGrad)"/>
            <!-- 몸통 패널 -->
            <rect x="42" y="94" width="36" height="22" rx="8" fill="#1e1b4b" opacity="0.15"/>
            <!-- 하트 버튼 -->
            <path d="M60 99 C60 99 56 95 53 97 C50 99 50 103 53 105 L60 111 L67 105 C70 103 70 99 67 97 C64 95 60 99 60 99Z" fill="#f472b6">
              <animate attributeName="fill" values="#f472b6;#fb7185;#f472b6" dur="1.2s" repeatCount="indefinite"/>
            </path>
            <!-- 팔 왼쪽 -->
            <rect x="2" y="88" width="18" height="12" rx="6" fill="#7c3aed"/>
            <circle cx="5" cy="94" r="4" fill="#6d28d9"/>
            <!-- 팔 오른쪽 -->
            <rect x="100" y="88" width="18" height="12" rx="6" fill="#7c3aed"/>
            <circle cx="115" cy="94" r="4" fill="#6d28d9"/>
            <!-- 발 -->
            <rect x="32" y="120" width="22" height="10" rx="5" fill="#7c3aed"/>
            <rect x="66" y="120" width="22" height="10" rx="5" fill="#7c3aed"/>
            <defs>
              <linearGradient id="headGrad" x1="22" y1="18" x2="98" y2="76" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stop-color="#818cf8"/>
                <stop offset="100%" stop-color="#6366f1"/>
              </linearGradient>
              <linearGradient id="bodyGrad" x1="18" y1="86" x2="102" y2="124" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stop-color="#7c3aed"/>
                <stop offset="100%" stop-color="#6366f1"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <h1 class="logo-title">SpamGuard</h1>
        <p class="logo-sub">AI 기반 스팸 감지 시스템</p>
      </div>

      <!-- Tabs -->
      <div class="tab-bar">
        <button :class="['tab', { active: mode === 'login' }]" @click="mode = 'login'">로그인</button>
        <button :class="['tab', { active: mode === 'register' }]" @click="mode = 'register'">회원가입</button>
        <div class="tab-indicator" :class="{ right: mode === 'register' }" />
      </div>

      <!-- Login Form -->
      <Transition name="slide-fade" mode="out-in">
        <form v-if="mode === 'login'" key="login" class="form" @submit.prevent="submitLogin">
          <div class="field">
            <label class="label">아이디</label>
            <div class="input-wrap">
              <svg class="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              <input v-model="loginUsername" type="text" class="input" placeholder="아이디 입력" autocomplete="username" />
            </div>
          </div>
          <div class="field">
            <label class="label">비밀번호</label>
            <div class="input-wrap">
              <svg class="input-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              <input v-model="loginPassword" type="password" class="input" placeholder="비밀번호 입력" autocomplete="current-password" />
            </div>
          </div>

          <Transition name="fade">
            <div v-if="loginError" class="error-box">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {{ loginError }}
            </div>
          </Transition>

          <button type="submit" class="btn-primary" :disabled="loginLoading">
            <span v-if="loginLoading" class="spinner" />
            <span v-else>로그인</span>
          </button>

          <div class="divider"><span>테스트 계정</span></div>

          <div class="accounts">
            <div class="account" @click="fillAccount('user1','user123')">
              <span class="badge-role user">사용자</span>
              <span class="account-info">user1 / user123</span>
            </div>
            <div class="account" @click="fillAccount('counselor1','counselor123')">
              <span class="badge-role counselor">상담원</span>
              <span class="account-info">counselor1 / counselor123</span>
            </div>
            <div class="account" @click="fillAccount('admin','admin123')">
              <span class="badge-role admin">관리자</span>
              <span class="account-info">admin / admin123</span>
            </div>
          </div>
        </form>

        <!-- Register Form -->
        <form v-else key="register" class="form" @submit.prevent="submitRegister">
          <Transition name="fade">
            <div v-if="regSuccess" class="success-box">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              회원가입 완료! 로그인 페이지로 이동합니다.
            </div>
          </Transition>

          <div class="field-row">
            <div class="field">
              <label class="label">아이디 <span class="req">*</span></label>
              <div class="input-wrap">
                <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <input v-model="regUsername" type="text" class="input" placeholder="영문, 숫자 2~30자" autocomplete="username" />
              </div>
            </div>
            <div class="field">
              <label class="label">닉네임 <span class="req">*</span></label>
              <div class="input-wrap">
                <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                <input v-model="regNickname" type="text" class="input" placeholder="닉네임 입력" />
              </div>
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label class="label">비밀번호 <span class="req">*</span></label>
              <div class="input-wrap">
                <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <input v-model="regPassword" type="password" class="input" placeholder="4자 이상" autocomplete="new-password" />
              </div>
            </div>
            <div class="field">
              <label class="label">비밀번호 확인 <span class="req">*</span></label>
              <div class="input-wrap">
                <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <input v-model="regPasswordConfirm" type="password" class="input" placeholder="재입력" autocomplete="new-password" />
              </div>
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label class="label">이름 <span class="req">*</span></label>
              <div class="input-wrap">
                <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <input v-model="regName" type="text" class="input" placeholder="실명 입력" />
              </div>
            </div>
            <div class="field">
              <label class="label">휴대폰 <span class="req">*</span></label>
              <div class="input-wrap">
                <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                <input :value="regPhone" type="tel" class="input" placeholder="010-0000-0000" @input="formatPhone" />
              </div>
            </div>
          </div>

          <div class="field">
            <label class="label">이메일 <span class="req">*</span></label>
            <div class="input-wrap">
              <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
              <input v-model="regEmail" type="email" class="input" placeholder="example@email.com" autocomplete="email" />
            </div>
          </div>

          <div class="field">
            <label class="label">우편번호 <span class="req">*</span></label>
            <div class="input-wrap">
              <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              <input v-model="regPostalCode" type="text" class="input" placeholder="우편번호 5자리" maxlength="5" />
            </div>
          </div>

          <div class="field">
            <label class="label">주소 <span class="req">*</span></label>
            <div class="input-wrap">
              <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
              <input v-model="regAddress" type="text" class="input" placeholder="기본 주소 입력" />
            </div>
          </div>

          <div class="field">
            <label class="label">상세주소</label>
            <div class="input-wrap">
              <svg class="input-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
              <input v-model="regDetailAddress" type="text" class="input" placeholder="상세 주소 입력 (동, 호수 등)" />
            </div>
          </div>

          <Transition name="fade">
            <div v-if="regError" class="error-box">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              {{ regError }}
            </div>
          </Transition>

          <button type="submit" class="btn-primary" :disabled="regLoading || regSuccess">
            <span v-if="regLoading" class="spinner" />
            <span v-else>회원가입</span>
          </button>

          <p class="hint-text">가입 후 <strong>사용자</strong> 권한으로 시작합니다.</p>
        </form>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 40px 20px;
  background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
  position: relative;
  overflow-y: auto;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.3;
  pointer-events: none;
}
.orb1 { width: 400px; height: 400px; background: #6366f1; top: -100px; left: -100px; }
.orb2 { width: 300px; height: 300px; background: #8b5cf6; bottom: -80px; right: -60px; }
.orb3 { width: 200px; height: 200px; background: #06b6d4; top: 50%; left: 50%; transform: translate(-50%,-50%); }

.card {
  width: 100%;
  max-width: 520px;
  background: rgba(255, 255, 255, 0.97);
  backdrop-filter: blur(20px);
  border-radius: 28px;
  padding: 40px 38px 36px;
  box-shadow: 0 32px 80px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.1);
  position: relative;
  z-index: 1;
}

.logo-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 28px;
}

.robot-wrap {
  margin-bottom: 10px;
  animation: robot-float 3s ease-in-out infinite;
  filter: drop-shadow(0 10px 24px rgba(99,102,241,0.35));
}

.robot-svg {
  width: 100px;
  height: 108px;
}

@keyframes robot-float {
  0%, 100% { transform: translateY(0px); }
  50%       { transform: translateY(-8px); }
}

.logo-title {
  font-size: 22px;
  font-weight: 800;
  color: #1e1b4b;
  letter-spacing: -0.5px;
}

.logo-sub {
  font-size: 13px;
  color: #7c7c9a;
  margin-top: 4px;
}

/* Tabs */
.tab-bar {
  display: flex;
  position: relative;
  background: #f1f0f9;
  border-radius: 14px;
  padding: 4px;
  margin-bottom: 28px;
}

.tab {
  flex: 1;
  padding: 10px;
  border: none;
  background: transparent;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #7c7c9a;
  cursor: pointer;
  position: relative;
  z-index: 1;
  transition: color 0.25s;
}

.tab.active { color: #1e1b4b; }

.tab-indicator {
  position: absolute;
  top: 4px;
  left: 4px;
  width: calc(50% - 4px);
  height: calc(100% - 8px);
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.tab-indicator.right { transform: translateX(calc(100% + 0px)); }

/* Form */
.form { display: flex; flex-direction: column; gap: 16px; }

.field { display: flex; flex-direction: column; gap: 7px; }

.label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 14px;
  color: #9ca3af;
  pointer-events: none;
}

.input {
  width: 100%;
  padding: 12px 14px 12px 40px;
  border: 1.5px solid #e8e6f0;
  border-radius: 12px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  color: #1e1b4b;
  background: #faf9ff;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
}

.input:focus {
  border-color: #6366f1;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.12);
}

.input::placeholder { color: #c4c4cc; }

.error-box {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #dc2626;
  background: #fef2f2;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #fecaca;
}

.success-box {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #059669;
  background: #ecfdf5;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #a7f3d0;
}

.btn-primary {
  margin-top: 4px;
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
  transition: opacity 0.2s, transform 0.1s, box-shadow 0.2s;
  box-shadow: 0 4px 16px rgba(99,102,241,0.35);
  letter-spacing: 0.2px;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(99,102,241,0.45);
}

.btn-primary:active:not(:disabled) { transform: translateY(0); }
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; box-shadow: none; }

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.divider {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #c4c4cc;
  font-size: 12px;
}

.divider::before, .divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #f0eef8;
}

.accounts { display: flex; flex-direction: column; gap: 6px; }

.account {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 10px;
  background: #faf9ff;
  border: 1.5px solid #ede9fe;
  cursor: pointer;
  transition: all 0.15s;
}

.account:hover {
  background: #ede9fe;
  border-color: #6366f1;
  transform: translateX(2px);
}

.badge-role {
  font-size: 11px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 99px;
  white-space: nowrap;
  flex-shrink: 0;
}

.badge-role.user     { background: #ede9fe; color: #6d28d9; }
.badge-role.counselor { background: #dbeafe; color: #1d4ed8; }
.badge-role.admin    { background: #fce7f3; color: #be185d; }

.account-info {
  font-size: 12.5px;
  color: #6b7280;
  font-family: 'Courier New', monospace;
}

.hint-text {
  font-size: 12.5px;
  color: #9ca3af;
  text-align: center;
}

.hint-text strong { color: #6366f1; }

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.req {
  color: #ef4444;
  font-size: 12px;
}

/* Transitions */
.slide-fade-enter-active,
.slide-fade-leave-active { transition: all 0.2s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateX(16px); }
.slide-fade-leave-to { opacity: 0; transform: translateX(-16px); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
