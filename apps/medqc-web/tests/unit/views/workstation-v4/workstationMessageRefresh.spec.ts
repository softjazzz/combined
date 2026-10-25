import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'

function createRefreshHandler() {
  const source = readFileSync('src/views/workstation-v4/WorkstationV4View.vue', 'utf8')
  const script = parse(source).descriptor.scriptSetup?.content
  if (!script) throw new Error('Missing workstation setup script')
  const tree = ts.createSourceFile('workstation.ts', script, ts.ScriptTarget.Latest, true)
  const declaration = tree.statements.find(
    (node): node is ts.FunctionDeclaration =>
      ts.isFunctionDeclaration(node) && node.name?.text === 'handleAssistTabRefresh',
  )
  if (!declaration) throw new Error('Missing refresh dispatcher')
  const compiled = ts.transpileModule(declaration.getText(tree), {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText
  const notifications = vi.fn().mockResolvedValue(undefined)
  const form = vi.fn()
  const coding = vi.fn()
  const drg = vi.fn()
  const info = vi.fn()
  const handle: (tab: string) => unknown = new Function(
    'fetchAssistNotifications', 'assistViewRef', 'performDRGGrouping', 'message',
    `${compiled}; return handleAssistTabRefresh`,
  )(notifications, { value: { runFormQC: form, runCodingQC: coding } }, drg, { info })
  return { handle, notifications, form, coding, drg, info }
}

describe('workstation message refresh dispatch', () => {
  it('消息面板刷新调用真实通知加载入口并返回其完成状态', async () => {
    const state = createRefreshHandler()
    const pending = Promise.resolve()
    state.notifications.mockReturnValueOnce(pending)
    expect(state.handle('message')).toBe(pending)
    await pending
    expect(state.notifications).toHaveBeenCalledOnce()
    expect(state.form).not.toHaveBeenCalled()
    expect(state.coding).not.toHaveBeenCalled()
    expect(state.drg).not.toHaveBeenCalled()
  })

  it('通知加载失败不会被刷新分派伪装为成功', async () => {
    const state = createRefreshHandler()
    state.notifications.mockRejectedValueOnce(new Error('notification unavailable'))
    await expect(state.handle('message')).rejects.toThrow('notification unavailable')
  })

  it('保留其他页签原有刷新行为，不触发消息请求', () => {
    const state = createRefreshHandler()
    for (const tab of ['form', 'cost', 'coding', 'drg', 'content', 'unknown']) {
      state.handle(tab)
    }
    expect(state.form).toHaveBeenCalledTimes(2)
    expect(state.coding).toHaveBeenCalledOnce()
    expect(state.drg).toHaveBeenCalledOnce()
    expect(state.info).toHaveBeenCalledOnce()
    expect(state.notifications).not.toHaveBeenCalled()
  })
})
