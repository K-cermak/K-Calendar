import { api, call } from '@/api/client'

/** Web Push for this browser (SPEC 8). Permission is asked only from a button the user taps. */

export function pushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
}

function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = base64url
    .replace(/-/g, '+')
    .replace(/_/g, '/')
    .padEnd(Math.ceil(base64url.length / 4) * 4, '=')
  const raw = atob(padded)
  const bytes = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return bytes
}

async function current(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker.ready
  return registration.pushManager.getSubscription()
}

/** Whether this browser gets this user's reminders. */
export async function isSubscribed(): Promise<boolean> {
  if (!pushSupported()) return false
  const subscription = await current()
  if (!subscription) return false
  return call(() =>
    api.POST('/api/v1/me/push-subscriptions/check', { body: { endpoint: subscription.endpoint } }),
  )
}

export async function subscribe(vapidPublicKey: string): Promise<'granted' | 'denied'> {
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') return 'denied'
  const registration = await navigator.serviceWorker.ready
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes(vapidPublicKey),
    }))
  const json = subscription.toJSON()
  await call(() =>
    api.POST('/api/v1/me/push-subscriptions', {
      body: {
        endpoint: subscription.endpoint,
        keys: { p256dh: json.keys?.p256dh ?? '', auth: json.keys?.auth ?? '' },
      },
    }),
  )
  return 'granted'
}

export async function unsubscribe(): Promise<void> {
  const subscription = await current()
  if (!subscription) return
  await call(() =>
    api.POST('/api/v1/me/push-subscriptions/remove', { body: { endpoint: subscription.endpoint } }),
  )
  await subscription.unsubscribe()
}
