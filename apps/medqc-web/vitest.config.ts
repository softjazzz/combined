import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { fileURLToPath } from 'url'

const dirname = fileURLToPath(new URL('.', import.meta.url))

// 医院系统按 Asia/Shanghai 运行；固定测试进程时区，使日期断言不随开发机系统时区漂移（worker 继承此环境变量）。
process.env.TZ = 'Asia/Shanghai'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(dirname, 'src'),
      '@/components': resolve(dirname, 'src/components'),
      '@/views': resolve(dirname, 'src/views'),
      '@/stores': resolve(dirname, 'src/stores'),
      '@/utils': resolve(dirname, 'src/utils'),
      '@/types': resolve(dirname, 'src/types'),
      '@/lib': resolve(dirname, 'src/lib'),
      '@/assets': resolve(dirname, 'src/assets'),
      '@/styles': resolve(dirname, 'src/styles'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    clearMocks: true,
    include: ['tests/**/*.{test,spec}.{ts,tsx,js,jsx}', 'src/**/*.{test,spec}.{ts,tsx,vue}'],
    exclude: [
      '**/tests/e2e/**',
      '**/*.test.js',
      '**/node_modules/**',
      '**/.push-worktree/**',
      '.push-worktree/**',
      'src/services/document-category-service.test.ts',
    ],
    coverage: {
      provider: 'istanbul',
      reportsDirectory: 'coverage/unit',
      reporter: ['text', 'html', 'lcov'],
      include: ['src/**/*.{ts,tsx,vue}'],
      exclude: ['src/**/__mocks__/**', 'src/**/types.ts'],
    },
  },
})
