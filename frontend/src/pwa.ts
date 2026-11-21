import { registerSW } from 'virtual:pwa-register'
import { API_CACHE_NAME } from './offline'

const HOUR_MS = 60 * 60 * 1000
const LAST_USER_KEY = 'lastUserId'

/**
 * Registers the service worker. A new version waits until the user asks for it through
 * onUpdate's reload, since reloading by itself could throw away what they are typing (SPEC 12).
 */
export function registerServiceWorker(onUpdate: (reload: () => Promise<void>) => void): void {
  if (!('serviceWorker' in navigator) || import.meta.env.DEV) return
  const update = registerSW({
    onNeedRefresh: () => onUpdate(() => update(true)),
    onRegisteredSW: (_url, registration) => {
      if (!registration) return
      // An installed app can stay open for days; it looks for a new version now and then.
      const check = () => void registration.update().catch(() => undefined)
      setInterval(check, HOUR_MS)
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') check()
      })
    },
  })
}

/** Cached API responses are personal data: they go on sign-out and when the user changes. */
export async function clearPersonalCaches(): Promise<void> {
  if (!('caches' in window)) return
  await caches.delete(API_CACHE_NAME).catch(() => false)
}

/** Notices a different account than last time, even across restarts, and drops its caches. */
export async function rememberUser(userId: number | null): Promise<void> {
  let last: string | null = null
  try {
    last = localStorage.getItem(LAST_USER_KEY)
    if (userId === null) localStorage.removeItem(LAST_USER_KEY)
    else localStorage.setItem(LAST_USER_KEY, String(userId))
  } catch {
    // Without storage the caches are still cleared on sign-out.
  }
  if (last !== null && userId !== null && last !== String(userId)) await clearPersonalCaches()
}

export function isIosSafariTab(): boolean {
  const ios =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const standalone =
    ('standalone' in navigator && (navigator as { standalone?: boolean }).standalone === true) ||
    matchMedia('(display-mode: standalone)').matches
  return ios && !standalone
}

interface InstallPrompt extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let installPrompt: InstallPrompt | null = null

/** Browsers that offer installing announce it once, early; the event is kept for the button. */
export function captureInstallPrompt(): void {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault()
    installPrompt = event as InstallPrompt
  })
}

export function canInstall(): boolean {
  return installPrompt !== null
}

export async function install(): Promise<boolean> {
  if (!installPrompt) return false
  await installPrompt.prompt()
  const { outcome } = await installPrompt.userChoice
  installPrompt = null
  return outcome === 'accepted'
}

export function isInstalled(): boolean {
  return matchMedia('(display-mode: standalone)').matches
}
