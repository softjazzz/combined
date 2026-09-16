/* global process */
/**
 * Vite Dev Server 健康检查脚本
 * 用法：node scripts/dev-health-check.mjs [--timeout 30000] [--port 3000]
 *
 * 检查三个端点在超时时间内是否全部返回 200：
 *   - /
 *   - /@vite/client
 *   - /workstation-v5
 *
 * 注意：显式绕过 HTTP_PROXY 环境变量（Clash 等代理会劫持 localhost 请求）
 */
import http from 'node:http'

const args = process.argv.slice(2)
const timeout = parseInt(args.find((_, i, a) => a[i - 1] === '--timeout') || '30000', 10)
const port = parseInt(args.find((_, i, a) => a[i - 1] === '--port') || '3000', 10)
const host = '127.0.0.1'

// 显式创建无代理 agent，绕过 HTTP_PROXY 环境变量
const noProxyAgent = new http.Agent({ keepAlive: false })

const endpoints = ['/', '/@vite/client', '/workstation-v5']

function checkEndpoint(path) {
  return new Promise((resolve) => {
    const startMs = Date.now()
    const req = http.get({ host, port, path, timeout: 15000, agent: noProxyAgent }, (res) => {
      let bytes = 0
      res.on('data', (chunk) => { bytes += chunk.length })
      res.on('end', () => {
        const elapsed = Date.now() - startMs
        resolve({ path, status: res.statusCode, bytes, elapsed, error: null })
      })
    })
    req.on('timeout', () => {
      req.destroy()
      resolve({ path, status: null, bytes: 0, elapsed: Date.now() - startMs, error: 'timeout' })
    })
    req.on('error', (e) => {
      resolve({ path, status: null, bytes: 0, elapsed: Date.now() - startMs, error: e.message })
    })
  })
}

async function runWithRetry() {
  const startTime = Date.now()
  let attempt = 0

  while (Date.now() - startTime < timeout) {
    attempt++
    console.log(`\n--- 第 ${attempt} 次检查 (已用时 ${Math.round((Date.now() - startTime) / 1000)}s / ${timeout / 1000}s) ---`)

    const results = await Promise.all(endpoints.map(checkEndpoint))
    let allOk = true

    for (const r of results) {
      if (r.status === 200) {
        console.log(`  ✅ ${r.path}  →  200 OK  (${r.bytes} bytes, ${r.elapsed}ms)`)
      } else if (r.error) {
        console.log(`  ❌ ${r.path}  →  ${r.error}  (${r.elapsed}ms)`)
        allOk = false
      } else {
        console.log(`  ⚠️  ${r.path}  →  HTTP ${r.status}  (${r.bytes} bytes, ${r.elapsed}ms)`)
        allOk = false
      }
    }

    if (allOk) {
      console.log(`\n🎉 全部端点健康！总耗时 ${Math.round((Date.now() - startTime) / 1000)}s`)
      process.exit(0)
    }

    // 等 3 秒后重试
    await new Promise((r) => setTimeout(r, 3000))
  }

  console.error(`\n💥 超时 (${timeout / 1000}s)，仍有端点不可达。`)
  console.error('诊断建议：')
  console.error('  1. 检查 dev server 是否已启动: netstat -ano | findstr :3000')
  console.error('  2. 查看 vite 日志是否有错误')
  console.error('  3. 尝试删除 node_modules/.vite 后重启')
  console.error('  4. 检查 HTTP_PROXY 环境变量: echo $env:HTTP_PROXY')
  process.exit(1)
}

runWithRetry()
