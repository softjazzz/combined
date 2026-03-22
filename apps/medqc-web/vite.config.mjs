import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

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
    host: '127.0.0.1', // 仅本机访问，避免 Clash/TUN 网卡干扰
    open: false, // 不自动打开浏览器
    cors: true, // 启用CORS
    watch: {
      ignored: [
        '**/backend/**',
        '**/node_modules/**',
        '**/.git/**',
        '**/.tmp/**',
        '**/docs/**'
      ]
    },
    // https: false, // 开发环境使用HTTP，如需HTTPS可设为true
    hmr: {
      host: '127.0.0.1',
      clientPort: 3000,
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
          proxy.on('error', (err, req, res) => {
            const url = req?.url || ''
            const method = req?.method || ''
             
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
    },
    // 预热核心入口文件，减少首次请求延迟
    warmup: {
      clientFiles: ['./src/main.ts', './src/router/index.ts']
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
    // 让 Vite 自动扫描源码发现依赖（默认行为），仅显式 include 已知大包加速首次加载
    include: [
      'vue',
      'vue-router',
      'pinia',
      'axios',
      'ant-design-vue',
      '@ant-design/icons-vue',
      'dayjs',
      'lodash-es',
      'echarts',
      'vue-echarts',
      'dayjs/plugin/quarterOfYear.js',
      'dayjs/plugin/weekOfYear.js',
      'dayjs/plugin/weekYear.js',
      'dayjs/plugin/weekday.js',
      'dayjs/plugin/advancedFormat.js',
      'dayjs/plugin/customParseFormat.js',
      'dayjs/plugin/localeData.js'
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
