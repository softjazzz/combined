import { defineConfig } from 'vitest/config'
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
      '@/utils': resolve(__dirname, 'src/utils'),
      '@/types': resolve(__dirname, 'src/types'),
      '@/lib': resolve(__dirname, 'src/lib'),
      '@/assets': resolve(__dirname, 'src/assets'),
      '@/styles': resolve(__dirname, 'src/styles')
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    clearMocks: true,
    include: [
      'tests/audit-module.test.ts',
      'tests/utils/validation.test.ts',
      'tests/utils/date-utils.test.ts',
      'src/utils/dashboard.test.ts',
      'tests/unit/services/apiService.spec.ts'
    ],
    coverage: {
      provider: 'istanbul',
      reportsDirectory: 'coverage/acceptance',
      reporter: ['text', 'html', 'lcov'],
      all: false,
      include: ['src/utils/dashboard.ts', 'src/services/apiService.ts']
    }
  }
})
