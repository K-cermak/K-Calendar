import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'
import App from './App.vue'
import { router } from './router'
import { i18n } from './i18n'
import { isFailure } from './api/client'
import { queryClient } from './api/queryClient'
import { sessionEnded } from './api/session'
import { applyTheme, rememberedTheme } from './theme'
import { captureInstallPrompt } from './pwa'
import { blockPageZoom } from './zoom'
import './styles/main.css'

applyTheme(rememberedTheme())
captureInstallPrompt()
blockPageZoom()

// A session revoked elsewhere (another device, deactivation) shows up as a 401 on any request.
function onFailure(error: unknown): void {
  if (!isFailure(error) || error.status !== 401) return
  const route = router.currentRoute.value
  if (route.meta.public) return
  sessionEnded()
  void router.replace({ name: 'login', query: { next: route.fullPath } })
}
queryClient.getQueryCache().config.onError = onFailure
queryClient.getMutationCache().config.onError = onFailure

createApp(App)
  .use(createPinia())
  .use(router)
  .use(i18n)
  .use(VueQueryPlugin, { queryClient })
  .mount('#app')
