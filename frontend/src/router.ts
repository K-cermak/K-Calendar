import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
  { path: '/showcase', name: 'showcase', component: () => import('@/views/ShowcaseView.vue') },
]

export const router = createRouter({ history: createWebHistory(), routes })
