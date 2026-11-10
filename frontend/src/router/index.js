import { createRouter, createWebHistory } from 'vue-router'
import { loadSession } from '../state/session'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue'),
  },
  {
    path: '/tablet-demo',
    name: 'tablet-demo',
    component: () => import('../views/TabletDemoView.vue'),
  },
  {
    path: '/tablet-reading',
    name: 'tablet-reading',
    component: () => import('../views/TabletReadingView.vue'),
  },
  {
    path: '/analysis',
    name: 'analysis',
    component: () => import('../views/AnalysisView.vue'),
  },
  { path: '/profile/history', name: 'history', component: () => import('../views/HistoryView.vue') },
  { path: '/profile/history/:id', name: 'history-detail', component: () => import('../views/HistoryDetailView.vue') },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
  },
  {
    path: '/signup',
    name: 'signup',
    component: () => import('../views/SignupView.vue'),
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('../views/ProfileView.vue'),
  },
]


const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: routes,
})

router.beforeEach(async (to) => {
  if (to.path === '/analysis' || to.path.startsWith('/profile')) {
    try {
      await loadSession()
    } catch (error) {
      if (error.status === 401) return { path: '/login', query: { redirect: to.fullPath } }
      // Let the page display a retryable error if the server is unavailable.
    }
  }
})

export default router
