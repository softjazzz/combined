import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '@/services/apiService'
import {
  compareRuntimeBuild,
  fetchRuntimeBuild,
  getFrontendBuildIdentity,
  type RuntimeBuild,
} from '@/services/runtime-build-service'

vi.mock('@/services/apiService', () => ({ apiClient: { get: vi.fn() } }))
const backend: RuntimeBuild = {
  available: true,
  build_id: 'release-1',
  git_commit: 'commit-1',
  started_at: '2026-09-09T08:00:00Z',
  pid: 123,
}
const frontend = { development: false, buildId: 'release-1', gitCommit: 'commit-1' }
afterEach(() => vi.unstubAllEnvs())

describe('运行版本读取与比较', () => {
  it('当前前端身份只取编译常量', () => {
    vi.stubEnv('DEV', false)
    vi.stubEnv('VITE_MEDQC_BUILD_ID', 'loaded-build')
    vi.stubEnv('VITE_MEDQC_GIT_COMMIT', 'loaded-commit')
    expect(getFrontendBuildIdentity()).toEqual({
      development: false,
      buildId: 'loaded-build',
      gitCommit: 'loaded-commit',
    })
  })
  it('构建号和提交均相同时才一致', () => {
    expect(compareRuntimeBuild(frontend, { kind: 'ready', data: backend })).toBe('matching')
    expect(
      compareRuntimeBuild(frontend, { kind: 'ready', data: { ...backend, build_id: 'release-2' } }),
    ).toBe('mismatch')
    expect(
      compareRuntimeBuild(frontend, {
        kind: 'ready',
        data: { ...backend, git_commit: 'commit-2' },
      }),
    ).toBe('mismatch')
  })
  it('缺标记、后端不可用及开发环境都不会显示一致', () => {
    expect(
      compareRuntimeBuild({ ...frontend, buildId: null }, { kind: 'ready', data: backend }),
    ).toBe('unknown')
    expect(
      compareRuntimeBuild(frontend, { kind: 'ready', data: { ...backend, git_commit: null } }),
    ).toBe('unknown')
    expect(
      compareRuntimeBuild(frontend, { kind: 'ready', data: { ...backend, available: false } }),
    ).toBe('unknown')
    expect(
      compareRuntimeBuild({ ...frontend, development: true }, { kind: 'ready', data: backend }),
    ).toBe('development')
  })
  it('同源读取并禁缓存，重启后返回最新PID和启动时间', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ status: 200, data: backend })
    const first = await fetchRuntimeBuild()
    expect(first).toEqual({ kind: 'ready', data: backend })
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/runtime-build',
      expect.objectContaining({
        params: { _t: expect.any(Number) },
        headers: { 'Cache-Control': 'no-cache, no-store' },
      }),
    )
    const restarted = { ...backend, pid: 456, started_at: '2026-09-09T09:00:00+00:00' }
    vi.mocked(apiClient.get).mockResolvedValueOnce({ status: 200, data: restarted })
    expect(await fetchRuntimeBuild()).toEqual({ kind: 'ready', data: restarted })
  })
  it('404无法核对，网络失败不能当成一致', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ status: 404, data: {} })
    expect(compareRuntimeBuild(frontend, await fetchRuntimeBuild())).toBe('unknown')
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('offline'))
    expect(compareRuntimeBuild(frontend, await fetchRuntimeBuild())).toBe('error')
  })
  it.each([
    { pid: '123' },
    { started_at: '2026-09-09 08:00:00' },
    { available: 'true' },
    { git_commit: 123 },
  ])('拒绝不符合运行合同的字段 %s', async (patch) => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({ status: 200, data: { ...backend, ...patch } })
    expect((await fetchRuntimeBuild()).kind).toBe('unavailable')
  })
})
