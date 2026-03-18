import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

const backendTarget = 'http://localhost:8001'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@/components': resolve(__dirname, 'src/components'),
      '@/views': resolve(__dirname, 'src/views'),
      '@/stores': resolve(__dirname, 'src/stores'),
      '@/utils': resolve(__dirname, 'src/utils'),
      '@/types': resolve(__dirname, 'src/types'),
      '@/lib': resolve(__dirname, 'src/lib'),
      '@/assets': resolve(__dirname, 'src/assets'),
      '@/styles': resolve(__dirname, 'src/styles')
    }
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
        additionalData: `@import "@/styles/variables.less";`
      }
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0', // 允许外部访问
    open: false, // 不自动打开浏览器
    cors: true, // 启用CORS
    watch: {
      ignored: [
        '**/backend/.venv/**',
        '**/node_modules/**'
      ]
    },
    // https: false, // 开发环境使用HTTP，如需HTTPS可设为true
    hmr: {
      overlay: true // 显示错误覆盖层
    },
    strictPort: true, // 端口被占用时报错，不自动切换

    proxy: {
      // 流式接口（SSE）需要长连接，单独关闭超时避免 502
      '/api/v1/frontpage/auto-generate-draft-stream': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
        timeout: 0,
        proxyTimeout: 0,
        configure: (proxy) => {
          proxy.on('error', (err: any, req: any, res: any) => {
            const url = req?.url || ''
            const method = req?.method || ''
            // eslint-disable-next-line no-console
            console.error('[vite-proxy] error:', method, url, err?.code || '', err?.message || err)
            if (res && !res.headersSent) {
              res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' })
            }
            res?.end?.('Bad Gateway')
          })
        }
      },
      // DRG 相关接口需要转发到新的后端服务
      '/api/v1/drg': {
        target: backendTarget,
        changeOrigin: true,
        secure: false
      },
      // 所有 API 接口都转发到后端服务（端口 8001）
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        secure: false,
        timeout: 180000,
        proxyTimeout: 180000
        // 不需要rewrite，因为前端代码已经使用 /api/v1/* 路径
      }
    }
  },
  build: {
    target: 'es2015',
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    rollupOptions: {
      output: {
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]'
      }
    }
  },
  optimizeDeps: {
    include: [
      'vue',
      'vue-router',
      'pinia',
      '@supabase/supabase-js',
      'ant-design-vue',
      '@ant-design/icons-vue',
      'dayjs',
      'lodash-es'
    ]
  },
  worker: {
    format: 'es'
  },
  define: {
    __VUE_OPTIONS_API__: true,
    __VUE_PROD_DEVTOOLS__: false
  }
})
