import { defineConfig, mergeConfig } from 'vitest/config'
import base from './vitest.config'

export default mergeConfig(base, defineConfig({
  test: {
    setupFiles: ['./tests/page-load-offline-setup.ts'],
    maxWorkers: 1,
    minWorkers: 1,
  },
}))
