import { QueryClient } from '@tanstack/vue-query'
import { isFailure } from './client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // A 4xx will not get better by asking again; network errors and 5xx might.
      retry: (count, error) =>
        count < 2 && !(isFailure(error) && error.status !== null && error.status < 500),
    },
  },
})
