import { beforeEach, vi } from 'vitest'
import http from 'node:http'
import https from 'node:https'

const deny = (): never => {
  throw new Error('clinical-source isolated tests forbid real network')
}
// 每个用例重装保护，防止restoreMocks意外恢复真实传输。
function blockNetwork() {
  vi.spyOn(XMLHttpRequest.prototype, 'send').mockImplementation(deny)
  vi.spyOn(http, 'request').mockImplementation(deny)
  vi.spyOn(https, 'request').mockImplementation(deny)
  vi.stubGlobal('fetch', vi.fn(deny))
}
blockNetwork()
beforeEach(blockNetwork)
