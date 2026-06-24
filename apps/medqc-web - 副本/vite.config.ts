// Keep a single source of truth in vite.config.mjs.
// This wrapper exists only for tools that probe vite.config.ts by convention.
// @ts-ignore - TS may not infer declaration for .mjs config import.
import config from './vite.config.mjs'

export default config
