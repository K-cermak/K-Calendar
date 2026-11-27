import { queryOptions, useQuery } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api, call, isFailure, type AccountDelete, type Me, type PublicConfig } from './client'
import { queryClient } from './queryClient'
import { clearPersonalCaches, rememberUser } from '@/pwa'

export const configQuery = queryOptions({
  queryKey: ['config'],
  queryFn: () => call(() => api.GET('/api/v1/config')),
  staleTime: Infinity,
})

/** The signed-in user, or null when nobody is signed in. */
export const meQuery = queryOptions({
  queryKey: ['me'],
  queryFn: async (): Promise<Me | null> => {
    try {
      return await call(() => api.GET('/api/v1/me'))
    } catch (e) {
      if (isFailure(e) && e.status === 401) return null
      throw e
    }
  },
  staleTime: 5 * 60_000,
})

export function useMe() {
  const query = useQuery(meQuery)
  return computed(() => query.data.value ?? null)
}

export function useConfig() {
  const query = useQuery(configQuery)
  return computed<PublicConfig | null>(() => query.data.value ?? null)
}

/**
 * Adopts the account the server just signed in. Anything cached for another account is dropped
 * first: cached responses are personal data (SPEC 12).
 */
export function signedIn(me: Me): void {
  const previous = queryClient.getQueryData(meQuery.queryKey)
  if (previous && previous.id !== me.id) forgetEverything()
  void rememberUser(me.id)
  queryClient.setQueryData(meQuery.queryKey, me)
  // Someone is signed in, so setup is over; the router reads this before the refetch is back.
  queryClient.setQueryData(configQuery.queryKey, (config) =>
    config ? { ...config, setup_required: false } : config,
  )
  void queryClient.invalidateQueries({ queryKey: configQuery.queryKey })
}

export async function signOut(): Promise<void> {
  await call(() => api.POST('/api/v1/auth/logout')).catch((e: unknown) => {
    // An already invalid session is as good as signed out.
    if (!isFailure(e) || e.status !== 401) throw e
  })
  forgetEverything()
  queryClient.setQueryData(meQuery.queryKey, null)
}

/** Deletes the account on the server, then forgets everything of it in this browser. */
export async function deleteAccount(confirmation: AccountDelete): Promise<void> {
  await call(() => api.DELETE('/api/v1/me', { body: confirmation }))
  forgetEverything()
  queryClient.setQueryData(meQuery.queryKey, null)
}

/** Called when any request finds the session gone, so the app falls back to the login page. */
export function sessionEnded(): void {
  forgetEverything()
  queryClient.setQueryData(meQuery.queryKey, null)
}

function forgetEverything(): void {
  void clearPersonalCaches()
  const config = queryClient.getQueryData(configQuery.queryKey)
  queryClient.clear()
  if (config) queryClient.setQueryData(configQuery.queryKey, config)
}
