#!/usr/bin/env node

/**
 * Workstation V4 P0 验收清单输出脚本
 * 仅用于统一执行口径与记录，不依赖外部服务。
 */

const checks = [
  {
    id: 'BASE',
    name: '基础校验',
    commands: ['npx vue-tsc --noEmit', 'npm run build']
  },
  {
    id: '4.1.2-01',
    name: '当天问题聚合时效',
    target: 'P95 <= 60s'
  },
  {
    id: '4.1.2-02',
    name: '概览点击跳转成功率',
    target: '>= 99%'
  },
  {
    id: '4.1.2-03',
    name: '未读状态准确率',
    target: '>= 99%'
  },
  {
    id: '6.2.2-01',
    name: '配置保存/发布/回滚',
    target: '100% 通过'
  },
  {
    id: '6.2.2-02',
    name: '审计字段完整性',
    target: 'version_id/operator/operated_at/change_summary'
  },
  {
    id: '6.2.2-03',
    name: '一致率达标',
    target: '>= 95%'
  }
]

console.log('=== Workstation V4 P0 验收清单 ===')
for (const item of checks) {
  console.log(`- [${item.id}] ${item.name}${item.target ? ` | 目标: ${item.target}` : ''}`)
  if (item.commands) {
    for (const cmd of item.commands) {
      console.log(`  - 执行: ${cmd}`)
    }
  }
}

console.log('\n报告模板: docs/acceptance/workstation-v4-p0-acceptance-template.md')
