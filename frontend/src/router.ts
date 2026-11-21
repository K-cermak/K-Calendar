import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { queryClient } from '@/api/queryClient'
import { configQuery, meQuery } from '@/api/session'

declare module 'vue-router' {
  interface RouteMeta {
    /** Reachable without signing in. */
    public?: boolean
    /** Only for visitors who are not signed in; signed-in users go to the calendar. */
    guestOnly?: boolean
    admin?: boolean
  }
}

const AppShell = () => import('@/views/AppShell.vue')

export const VIEWS = ['month', 'week', 'day', 'agenda'] as const
export type CalendarView = (typeof VIEWS)[number]

export const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: AppShell },
  {
    path: `/:view(${VIEWS.join('|')})/:date(\\d{4}-\\d{2}-\\d{2})?`,
    name: 'calendar',
    component: AppShell,
  },
  { path: '/event/:occurrenceId', name: 'event', component: AppShell },
  {
    path: '/settings',
    component: () => import('@/views/SettingsView.vue'),
    children: [
      { path: '', redirect: '/settings/profile' },
      {
        path: 'profile',
        name: 'settings-profile',
        component: () => import('@/views/settings/ProfileSettings.vue'),
      },
      {
        path: 'security',
        name: 'settings-security',
        component: () => import('@/views/settings/SecuritySettings.vue'),
      },
    ],
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/AdminView.vue'),
    meta: { admin: true },
  },
  {
    path: '/setup',
    name: 'setup',
    component: () => import('@/views/auth/SetupView.vue'),
    meta: { public: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { public: true, guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { public: true, guestOnly: true },
  },
  {
    path: '/invite/:token',
    name: 'invite',
    component: () => import('@/views/auth/InviteView.vue'),
    meta: { public: true },
  },
  {
    path: '/reset/:token',
    name: 'reset',
    component: () => import('@/views/auth/ResetView.vue'),
    meta: { public: true },
  },
  {
    path: '/showcase',
    name: 'showcase',
    component: () => import('@/views/ShowcaseView.vue'),
    meta: { public: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { public: true },
  },
]

export const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  let config
  try {
    config = await queryClient.ensureQueryData(configQuery)
  } catch {
    // Without the server there is nothing to decide with; the page shows its own error.
    return true
  }
  if (config.setup_required) {
    return to.name === 'setup' || to.name === 'showcase' ? true : { name: 'setup' }
  }
  const me = await queryClient.ensureQueryData(meQuery).catch(() => null)
  if (to.name === 'setup') return { name: me ? 'home' : 'login' }
  if (to.meta.guestOnly && me) return { name: 'home' }
  if (!to.meta.public && !me) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { next: to.fullPath } }
  }
  if (to.meta.admin && !me?.is_admin) return { name: 'home' }
  return true
})

/** Where to go after signing in: the page that sent the user to the login screen, if it is ours. */
export function afterSignIn(next: unknown): string {
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}
