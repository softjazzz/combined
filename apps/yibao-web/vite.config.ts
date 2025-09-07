import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@/components': resolve(__dirname, 'src/components'),
      '@/views': resolve(__dirname, 'src/views'),
      '@/stores': resolve(__dirname, 'src/stores'),
      '@/lib': resolve(__dirname, 'src/lib'),
      '@/assets': resolve(__dirname, 'src/assets'),
      '@/styles': resolve(__dirname, 'src/styles')
    }
  },
  server: {
    port: 3001,
    host: '0.0.0.0',
    cors: true,
    proxy: {
      '/api': { target: 'http://localhost:8001', changeOrigin: true, secure: false }
    },
    watch: {
      ignored: [
        '**/backend/.venv/**',
        '**/node_modules/**'
      ]
    }
  }
})


