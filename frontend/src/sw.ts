/// <reference lib="webworker" />
/**
 * The service worker (SPEC 12): the app shell is precached, and the read endpoints are cached
 * network-first, so a calendar that was open before can be read without a network. It never
 * queues writes. Push notifications are handled here as well.
 */
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { API_CACHE_NAME, occurrencesWithin, type OccurrenceList } from './offline'

declare const self: ServiceWorkerGlobalScope

const API_CACHE = API_CACHE_NAME
const NETWORK_TIMEOUT_MS = 6000

precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//, /^\/feeds\//],
  }),
)

const READABLE = [
  /^\/api\/v1\/config$/,
  /^\/api\/v1\/me$/,
  /^\/api\/v1\/me\/clock$/,
  /^\/api\/v1\/calendars$/,
  /^\/api\/v1\/tags$/,
  /^\/api\/v1\/occurrences(\/[^/]+)?$/,
  /^\/api\/v1\/events\/\d+$/,
]

function withTimeout(request: Request): Promise<Response> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), NETWORK_TIMEOUT_MS)
  return fetch(request, { signal: controller.signal }).finally(() => clearTimeout(timer))
}

/**
 * Without a network, a range that was never loaded by itself is cut out of a wider one that was,
 * such as the months fetched ahead in the background.
 */
async function fromWiderRange(cache: Cache, url: URL): Promise<Response | undefined> {
  const start = url.searchParams.get('start')
  const end = url.searchParams.get('end')
  const tz = url.searchParams.get('tz')
  if (!start || !end) return undefined
  for (const key of await cache.keys()) {
    const cached = new URL(key.url)
    if (cached.pathname !== url.pathname || cached.searchParams.get('tz') !== tz) continue
    const from = cached.searchParams.get('start') ?? ''
    const to = cached.searchParams.get('end') ?? ''
    if (from > start || to < end) continue
    const response = await cache.match(key)
    if (!response) continue
    const list = (await response.json()) as OccurrenceList
    return new Response(JSON.stringify(occurrencesWithin(list, start, end)), {
      headers: { 'Content-Type': 'application/json' },
    })
  }
  return undefined
}

registerRoute(
  ({ url, request }) =>
    request.method === 'GET' &&
    url.origin === self.location.origin &&
    READABLE.some((pattern) => pattern.test(url.pathname)),
  async ({ request, url }) => {
    const cache = await caches.open(API_CACHE)
    try {
      const response = await withTimeout(request)
      if (response.ok) await cache.put(request, response.clone())
      // A refused session must not be answered from the cache later.
      if (response.status === 401) await caches.delete(API_CACHE)
      return response
    } catch {
      const cached =
        (await cache.match(request)) ??
        (url.pathname === '/api/v1/occurrences' ? await fromWiderRange(cache, url) : undefined)
      return cached ?? Response.error()
    }
  },
)

self.addEventListener('message', (event) => {
  const data = event.data as { type?: string } | undefined
  if (data?.type === 'SKIP_WAITING') void self.skipWaiting()
})

// Reminders (SPEC 8): the server sends title, body and the occurrence to open.
interface PushPayload {
  title?: string
  body?: string
  url?: string
  tag?: string
}

self.addEventListener('push', (event) => {
  let payload: PushPayload = {}
  try {
    payload = (event.data?.json() ?? {}) as PushPayload
  } catch {
    payload = { body: event.data?.text() }
  }
  event.waitUntil(
    self.registration.showNotification(payload.title ?? '', {
      body: payload.body,
      tag: payload.tag,
      icon: '/pwa-192x192.png',
      badge: '/pwa-64x64.png',
      data: { url: payload.url ?? '/' },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = new URL(
    (event.notification.data as { url?: string } | null)?.url ?? '/',
    self.location.origin,
  )
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      const open = windows.find((client) => new URL(client.url).origin === url.origin)
      if (open) {
        await open.focus()
        await open.navigate(url.href)
        return
      }
      await self.clients.openWindow(url.href)
    })(),
  )
})
