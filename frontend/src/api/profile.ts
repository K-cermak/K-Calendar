import { useMutation } from '@tanstack/vue-query'
import { api, call, type Me, type ProfileUpdate } from './client'
import { queryClient } from './queryClient'
import { meQuery } from './session'

/** Saves profile changes, showing them at once and putting the old values back if the server refuses. */
export function useUpdateProfile() {
  return useMutation({
    mutationFn: (patch: ProfileUpdate) => call(() => api.PATCH('/api/v1/me', { body: patch })),
    onMutate: (patch) => {
      const previous = queryClient.getQueryData(meQuery.queryKey)
      if (previous) queryClient.setQueryData(meQuery.queryKey, { ...previous, ...patch } as Me)
      return { previous }
    },
    onError: (_error, _patch, context) => {
      // A session that ended meanwhile has cleared the user; bringing it back would undo the sign-out.
      if (context?.previous && queryClient.getQueryData(meQuery.queryKey)) {
        queryClient.setQueryData(meQuery.queryKey, context.previous)
      }
    },
    onSuccess: (me) => {
      queryClient.setQueryData(meQuery.queryKey, me)
      // Occurrences are computed in the profile's zone, so a new zone changes every one of them.
      void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
    },
  })
}
