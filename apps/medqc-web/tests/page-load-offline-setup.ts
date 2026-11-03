import http from 'node:http'
import https from 'node:https'
import net from 'node:net'
import tls from 'node:tls'
import { beforeEach, vi } from 'vitest'

const denied = () => { throw new Error('页面加载隔离验证禁止真实网络；请使用固定应答') }

function blockNetwork() {
  vi.spyOn(http, 'request').mockImplementation(denied)
  vi.spyOn(http, 'get').mockImplementation(denied)
  vi.spyOn(https, 'request').mockImplementation(denied)
  vi.spyOn(https, 'get').mockImplementation(denied)
  vi.spyOn(net.Socket.prototype, 'connect').mockImplementation(denied)
  vi.spyOn(tls, 'connect').mockImplementation(denied)
  globalThis.fetch = vi.fn(denied)
}

blockNetwork()
beforeEach(blockNetwork)
