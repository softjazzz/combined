import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

const backendTarget = 'http://localhost:8001'
const normalizeId = (id) => id.replace(/\\/g, '/')
const cliPortArgIndex = process.argv.findIndex((arg) => arg === '--port')
const cliPort = cliPortArgIndex >= 0 ? Number(process.argv[cliPortArgIndex + 1]) : NaN
const devServerPort = Number.isFinite(cliPort) ? cliPort : 3000
const devServerHost = process.env.VITE_DEV_HOST || '127.0.0.1'
const publicHmrHost = process.env.VITE_HMR_HOST || undefined
const publicHmrClientPort = Number(process.env.VITE_HMR_CLIENT_PORT || devServerPort)

function createManualChunks(id) {
  const normalizedId = normalizeId(id)

  if (
    normalizedId.includes('/src/views/drg-grouper/sichuan2024Grouper.js')
    || normalizedId.includes('/src/views/drg-grouper/cnDrg2023Grouper.js')
  ) {
    return 'grouper-engines'
  }

  if (normalizedId.includes('node_modules')) {
    if (
      normalizedId.includes('/node_modules/vue/')
      || normalizedId.includes('/node_modules/@vue/')
      || normalizedId.includes('/node_modules/vue-router/')
      || normalizedId.includes('/node_modules/pinia/')
    ) {
      return 'vendor-core'
    }

    if (
      normalizedId.includes('/node_modules/ant-design-vue/')
      || normalizedId.includes('/node_modules/@ant-design/icons-vue/')
    ) {
      return 'vendor-antd'
    }

    if (
      normalizedId.includes('/node_modules/echarts/')
      || normalizedId.includes('/node_modules/vue-echarts/')
    ) {
      return 'vendor-echarts'
    }

    if (
      normalizedId.includes('/node_modules/xlsx/')
      || normalizedId.includes('/node_modules/jspdf/')
      || normalizedId.includes('/node_modules/jspdf-autotable/')
      || normalizedId.includes('/node_modules/html2canvas/')
    ) {
      return 'vendor-export'
    }
  }

  return undefined
}

// https://vitejs.dev/config/
export default defineConfig(async ({ command }) => {
  const plugins = [
    vue(),
    Components({
      dts: 'src/components.d.ts',
      resolvers: [
        AntDesignVueResolver({
          importStyle: false,
          resolveIcons: true,
        }),
      ],
    }),
  ]
  const shouldVisualize = process.env.ANALYZE_VISUALIZER === '1'

  if (shouldVisualize) {
    try {
      const { visualizer } = await import('rollup-plugin-visualizer')
      plugins.push(
        visualizer({
          filename: resolve(__dirname, 'docs/acceptance/build-visualizer.html'),
          template: 'treemap',
          gzipSize: true,
          brotliSize: true,
          open: false,
        })
      )
    } catch (error) {
      console.warn(
        '[build-analyze] ANALYZE_VISUALIZER=1 but rollup-plugin-visualizer is unavailable:',
        error?.message || error
      )
    }
  }

  const runtimeStylePath = resolve(
    __dirname,
    command === 'serve' ? 'src/styles/index.prebuilt.css' : 'src/styles/index.css'
  )

  return {
  plugins,
  // 使用 Vite 默认缓存目录，避免自定义 .tmp 缓存目录出现间歇性 EPERM/lstat
  cacheDir: 'node_modules/.vite',
  resolve: {
    alias: [
      { find: '@/styles/runtime.css', replacement: runtimeStylePath },
      { find: '@', replacement: resolve(__dirname, 'src') },
      { find: '@/components', replacement: resolve(__dirname, 'src/components') },
      { find: '@/views', replacement: resolve(__dirname, 'src/views') },
      { find: '@/stores', replacement: resolve(__dirname, 'src/stores') },
      { find: '@/utils', replacement: resolve(__dirname, 'src/utils') },
      { find: '@/types', replacement: resolve(__dirname, 'src/types') },
      { find: '@/lib', replacement: resolve(__dirname, 'src/lib') },
      { find: '@/assets', replacement: resolve(__dirname, 'src/assets') },
      { find: '@/styles', replacement: resolve(__dirname, 'src/styles') },
    ]
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
    host: devServerHost,
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
      protocol: 'ws',
      host: publicHmrHost,
      clientPort: publicHmrClientPort,
      overlay: false // 关闭错误覆盖层，避免 esbuild 偶发异常导致白屏
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
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
        manualChunks: createManualChunks,
      }
    }
  },
  optimizeDeps: {
    entries: ['index.html'],
    // 仅保留核心依赖预构建，避免 dev 首个请求前做过量依赖优化
    include: [
      'vue',
      'vue-router',
      'pinia',
    ]
  },
  worker: {
    format: 'es'
  },
  define: {
    __VUE_OPTIONS_API__: true,
    __VUE_PROD_DEVTOOLS__: false
  }
}
})
