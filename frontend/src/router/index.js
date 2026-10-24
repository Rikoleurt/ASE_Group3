import { createRouter, createWebHistory } from 'vue-router'

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
    path: '/cluster',
    name: 'cluster',
    component: () => import('../views/ClusterView.vue'),
  },
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

export default router
