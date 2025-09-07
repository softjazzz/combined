import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import RulesList from '@/views/RulesList.vue'
import Sandbox from '@/views/Sandbox.vue'
import Audit from '@/views/Audit.vue'
import Dashboard from '@/views/Dashboard.vue'
import Login from '@/views/Login.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: Login },
    { path: '/', name: 'home', component: Home, meta: { requiresAuth: true } },
    { path: '/rules', name: 'rules', component: RulesList, meta: { requiresAuth: true } },
    { path: '/sandbox', name: 'sandbox', component: Sandbox, meta: { requiresAuth: true } },
    { path: '/audit', name: 'audit', component: Audit, meta: { requiresAuth: true } },
    { path: '/dashboard', name: 'dashboard', component: Dashboard, meta: { requiresAuth: true } }
  ]
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.user) await auth.fetchUser()
  if (to.meta?.requiresAuth && !auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router


