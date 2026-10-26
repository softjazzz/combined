import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const baseline = 'f3196ac1a'
const files = [
  'src/components/qc/CaseCommunicationPanel.vue',
  'src/views/workstation/HomeCaseCommunications.vue',
]
function businessScript(source: string) {
  const script = parse(source).descriptor.scriptSetup!.content
  const ast = ts.createSourceFile('component.ts', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const printer = ts.createPrinter({ removeComments: true })
  return ast.statements.filter((statement) => {
    if (ts.isImportDeclaration(statement)) return false
    return !(ts.isVariableStatement(statement) && statement.declarationList.declarations.length === 1 &&
      statement.declarationList.declarations[0].name.getText(ast) === 'labels')
  }).map((statement) => printer.printNode(ts.EmitHint.Unspecified, statement, ast))
}
describe('病历沟通V7.1只改展示层', () => {
  it.each(files)('%s 的请求、状态、权限和事件处理保持原样', (file) => {
    const before = execFileSync('git', ['show', `${baseline}:apps/medqc-web/${file}`], { encoding: 'utf8' })
    expect(businessScript(readFileSync(file, 'utf8'))).toEqual(businessScript(before))
  })
  it('不覆盖上一批审核抽屉成果', () => {
    for (const file of ['src/components/qc/RecordReviewWorkflowDrawer.vue', 'src/components/qc/styles/record-review-workflow.css']) {
      const before = execFileSync('git', ['show', `${baseline}:apps/medqc-web/${file}`], { encoding: 'utf8' })
      expect(readFileSync(file, 'utf8').replace(/\r\n/g, '\n')).toBe(before.replace(/\r\n/g, '\n'))
    }
  })
})
