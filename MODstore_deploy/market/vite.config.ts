import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const apiProxyTarget =
  (process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8765').trim() ||
  'http://127.0.0.1:8765'

export function normalizeBase(raw: string | undefined): string {
  const t = (raw || '').trim()
  if (!t) return '/'
  const withSlash = t.endsWith('/') ? t : `${t}/`
  return withSlash.startsWith('/') ? withSlash : `/${withSlash}`
}

export default defineConfig(({ command }) => {
  const envRaw = (process.env.VITE_PUBLIC_BASE || '').trim()
  const base =
    command === 'build'
      ? normalizeBase(envRaw || '/market/')
      : envRaw
        ? normalizeBase(envRaw)
        : '/'

  return {
    plugins: [vue()],
    base,
    build: {
      emptyOutDir: false,
    },
    server: {
      port: 5176,
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          ws: true,
        },
        '/v1': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/dev-docs': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'happy-dom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.ts', 'src/**/*.spec.ts'],
      exclude: ['src/e2e/**', 'dist/**', 'node_modules/**'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'html', 'json-summary'],
        reportsDirectory: './coverage',
        include: ['src/**/*.{ts,vue}'],
        exclude: [
          'src/main.ts',
          'src/**/*.d.ts',
          'src/test/**',
          'src/e2e/**',
          'src/**/*.test.ts',
          'src/**/*.spec.ts',
        ],
        // Ratchet target: 80% globally. Current measured baseline is ~7%
        // because most Vue views lack component tests. The thresholds below
        // are the "do not regress" floor; raise them as we add tests.
        // Per-file thresholds on contract-critical client modules ensure the
        // payment surface is properly tested even before the rest of the app.
        thresholds: {
          statements: 7,
          branches: 6,
          functions: 4,
          lines: 7,
          'src/application/paymentApi.ts': {
            statements: 80,
            branches: 70,
            functions: 80,
            lines: 80,
          },
        },
      },
    },
  }
})
