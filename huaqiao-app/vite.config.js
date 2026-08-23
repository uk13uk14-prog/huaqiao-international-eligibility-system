import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/saas-api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/saas-api/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1200
  }
})
