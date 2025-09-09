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
    port: 3008,
    host: '0.0.0.0',
    cors: true,
    proxy: {
      '/api': { target: 'http://localhost:8002', changeOrigin: true, secure: false },
      // Supabase REST (开发期仅用于本地调试；通过服务端代理注入 Service Role Header）
      '/rest': {
        target: 'https://apkvovxrsjzwmeuuzgnc.supabase.co/rest/v1',
        changeOrigin: true,
        secure: true,
        headers: {
          apikey: process.env.SUPABASE_SERVICE_ROLE_KEY || '',
          Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY || ''}`
        },
        rewrite: (p) => p.replace(/^\/rest/, '')
      },
      // Supabase Edge Functions 调用代理
      '/fn': {
        target: 'https://apkvovxrsjzwmeuuzgnc.supabase.co/functions/v1',
        changeOrigin: true,
        secure: true,
        headers: {
          apikey: process.env.SUPABASE_SERVICE_ROLE_KEY || '',
          Authorization: `Bearer ${process.env.SUPABASE_SERVICE_ROLE_KEY || ''}`
        },
        rewrite: (p) => p.replace(/^\/fn/, '')
      }
    },
    watch: {
      ignored: [
        '**/backend/.venv/**',
        '**/node_modules/**'
      ]
    }
  }
})


