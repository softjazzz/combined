import { access, rm } from 'node:fs/promises'
import { constants } from 'node:fs'
import { resolve } from 'node:path'

const cacheDirs = [
  'node_modules/.vite',
  '.tmp/vite-cache',
]

async function removeIfExists(target) {
  try {
    await access(target, constants.F_OK)
  } catch {
    return false
  }

  try {
    await rm(target, {
      recursive: true,
      force: true,
      maxRetries: 2,
    })
  } catch (error) {
    if (error && typeof error === 'object' && 'code' in error && error.code === 'EPERM') {
      throw new Error(`failed to remove ${target}; cache is locked by a running Node/Vite process`)
    }
    throw error
  }

  return true
}

async function main() {
  const removed = []

  for (const dir of cacheDirs) {
    const target = resolve(process.cwd(), dir)
    if (await removeIfExists(target)) {
      removed.push(dir)
    }
  }

  if (removed.length === 0) {
    console.log('[cache:clean] no Vite cache directories found')
    return
  }

  console.log(`[cache:clean] removed: ${removed.join(', ')}`)
}

main().catch((error) => {
  console.error('[cache:clean] failed:', error)
  process.exitCode = 1
})
