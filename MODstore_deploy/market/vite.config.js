import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 生产 base：默认 ``/market/``（与 FastAPI 挂载一致）；站点子路径如 ``/new/`` 可设环境变量 ``VITE_PUBLIC_BASE=/new/`` 后执行 build
const productionBase = () => {
  const raw = (process.env.VITE_PUBLIC_BASE || '/market/').trim()
  const withSlash = raw.endsWith('/') ? raw : `${raw}/`
  return withSlash.startsWith('/') ? withSlash : `/${withSlash}`
}

export default defineConfig(({ command }) => ({
  plugins: [vue()],
  base: command === 'build' ? productionBase() : '/',
  server: {
    port: 5176,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
}))
