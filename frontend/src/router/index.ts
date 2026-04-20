import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
    },

    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
    },
    {
      path: '/file-check',
      name: 'file-check',
      component: () => import('../views/FileCheckView.vue'),
    },

    {
      path: '/user',
      name: 'user',
      component: () => import('../views/UserView.vue'),
      meta: { requiresAuth: true, role: 'user' },
    },

    {
      path: '/counselor',
      name: 'counselor',
      component: () => import('../views/CounselorView.vue'),
      meta: { requiresAuth: true, role: 'counselor' },
    },

    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAuth: true, role: 'admin' },
    },
    {
      path: '/langsmith',
      name: 'langsmith',
      component: () => import('../views/LangSmithView.vue'),
      meta: { requiresAuth: true, role: 'developer' },
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  const token = auth.token || localStorage.getItem('token')
  const role = auth.role || localStorage.getItem('role')

  // 1. 로그인 필요 페이지인데 로그인 안됨
  if (to.meta.requiresAuth && !token) {
    return { path: '/login' }
  }

  // 2. 로그인 상태인데 login 접근
  if (to.path === '/login' && token) {
    if (role === 'admin' || role === 'developer') return { path: '/admin' }
    if (role === 'counselor') return { path: '/counselor' }
    return { path: '/user' }
  }

  // 3. 권한 체크
  if (to.meta.requiresAuth && to.meta.role) {
    const effectiveRole = role === 'developer' ? 'admin' : role
    const allowed = Array.isArray(to.meta.role)
      ? to.meta.role
      : [to.meta.role]

    if (!allowed.includes(effectiveRole) && !allowed.includes(role)) {
      if (effectiveRole === 'admin') return { path: '/admin' }
      if (effectiveRole === 'counselor') return { path: '/counselor' }
      return { path: '/user' }
    }
  }

  return true
})

export default router