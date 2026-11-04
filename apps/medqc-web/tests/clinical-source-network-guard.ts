import { vi } from 'vitest'
import http from 'node:http'
import https from 'node:https'

const deny = (): never => {
  throw new Error('clinical-source isolated tests forbid real network')
}
// HTTP适配器和组件均须使用固定应答；遗漏Mock时立即失败。
vi.spyOn(XMLHttpRequest.prototype, 'send').mockImplementation(deny)
vi.spyOn(http, 'request').mockImplementation(deny)
vi.spyOn(https, 'request').mockImplementation(deny)
vi.stubGlobal('fetch', vi.fn(deny))
