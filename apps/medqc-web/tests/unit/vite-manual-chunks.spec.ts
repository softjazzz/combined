import { execFileSync } from 'node:child_process'
import { describe, expect, it } from 'vitest'

const classifyChunks = (ids: string[]): Array<string | null> => {
  const script = `
    import { createManualChunks } from './vite.config.mjs';
    const ids = JSON.parse(process.env.MEDQC_CHUNK_IDS || '[]');
    process.stdout.write(JSON.stringify(ids.map((id) => createManualChunks(id) ?? null)));
  `
  const output = execFileSync(process.execPath, ['--input-type=module', '-e', script], {
    cwd: process.cwd(),
    env: { ...process.env, MEDQC_CHUNK_IDS: JSON.stringify(ids) },
    encoding: 'utf8',
  })
  return JSON.parse(output) as Array<string | null>
}

describe('Vite ECharts 分包合同', () => {
  it('所有 ECharts 内部模块必须进入同一 chunk，避免循环初始化', () => {
    const ids = [
      'D:/repo/node_modules/echarts/core.js',
      'D:/repo/node_modules/echarts/shared.js',
      'D:/repo/node_modules/echarts/charts.js',
      'D:/repo/node_modules/echarts/components.js',
      'D:/repo/node_modules/echarts/renderers.js',
      'D:/repo/node_modules/echarts/lib/core/echarts.js',
      'D:/repo/node_modules/echarts/lib/chart/bar/BarView.js',
      'D:/repo/node_modules/echarts/lib/component/grid/install.js',
      'D:/repo/node_modules/echarts/lib/renderer/installCanvasRenderer.js',
    ]

    expect(new Set(classifyChunks(ids))).toEqual(new Set(['vendor-echarts']))
  })

  it('vue-echarts 继续保持独立适配层', () => {
    expect(classifyChunks(['D:/repo/node_modules/vue-echarts/dist/index.esm.js'])).toEqual([
      'vendor-echarts-vue',
    ])
  })
})
