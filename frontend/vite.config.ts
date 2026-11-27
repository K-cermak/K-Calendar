/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import VueI18nPlugin from '@intlify/unplugin-vue-i18n/vite'
import { VitePWA } from 'vite-plugin-pwa'

const brandingPath = fileURLToPath(new URL('../branding.json', import.meta.url))
const branding = JSON.parse(readFileSync(brandingPath, 'utf8')) as Record<string, string>

function escapeHtml(value: string): string {
  return value.replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`)
}

// index.html uses %BRANDING_NAME% and friends, so the name stays in branding.json only.
function brandingHtml(): Plugin {
  return {
    name: 'branding-html',
    transformIndexHtml: (html) =>
      html.replace(/%BRANDING_(\w+)%/g, (_, key: string) =>
        escapeHtml(branding[key.toLowerCase()] ?? ''),
      ),
  }
}

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    VueI18nPlugin({ include: [fileURLToPath(new URL('./src/locales/*.json', import.meta.url))] }),
    brandingHtml(),
    VitePWA({
      // injectManifest: the worker has code of its own, for offline reading and push (SPEC 12).
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      // The app shows "Update available" and reloads only when asked.
      registerType: 'prompt',
      injectRegister: false,
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,woff2,png,svg}'],
        // The captcha frame's Content-Security-Policy depends on its query, so it always comes from
        // the server rather than from a cached copy.
        globIgnores: ['captcha.html'],
      },
      manifest: {
        name: branding.name,
        short_name: branding.short_name,
        description: branding.description,
        theme_color: branding.theme_color,
        background_color: branding.theme_color,
        display: 'standalone',
        start_url: '/',
        scope: '/',
        icons: [
          { src: '/pwa-64x64.png', sizes: '64x64', type: 'image/png' },
          { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          {
            src: '/maskable-icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        captcha: fileURLToPath(new URL('./captcha.html', import.meta.url)),
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@branding': brandingPath,
    },
  },
  server: {
    fs: { allow: ['..'] },
    proxy: { '/api': 'http://localhost:8000', '/feeds': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
  },
})
