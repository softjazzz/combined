import { defineConfig, mergeConfig } from 'vite'
import baseConfig from './vite.config.mjs'
import { customerBuildIdentityPlugin } from './scripts/customer-build-identity.mjs'

export default defineConfig(async (env) => {
  const base = await (typeof baseConfig === 'function' ? baseConfig(env) : baseConfig)
  return mergeConfig(base, { plugins: [customerBuildIdentityPlugin()] })
})
