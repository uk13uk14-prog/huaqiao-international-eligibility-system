import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5190,
    proxy: {
      '/api': {
        target: process.env.VITE_ADMIN_API_BASE || 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 1400,
  },
})
