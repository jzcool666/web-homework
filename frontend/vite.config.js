import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // SPEC-000 第 4 节第 2 条：开发时由 Vite 代理 /api 到后端
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    // 前端单元测试与源码同目录；仓库根 tests/frontend/ 留给 SPEC-012/013 的仿真逻辑测试
    include: ['src/**/__tests__/*.spec.js'],
  },
})
