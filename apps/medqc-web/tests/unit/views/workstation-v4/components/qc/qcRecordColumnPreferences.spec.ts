import { describe, expect, it } from 'vitest'

import {
  defaultQcRecordColumns,
  loadQcRecordColumns,
  qcRecordColumnStorageKey,
  saveQcRecordColumns,
  sanitizeQcRecordColumns,
  type QcRecordOptionalColumn,
} from '@/views/workstation-v4/components/qc/qcRecordColumnPreferences'

describe('qcRecordColumnPreferences', () => {
  it('按用户和病历阶段生成相互隔离的版本化存储键', () => {
    const inpatientA = qcRecordColumnStorageKey('qc user/甲', 'inpatient')

    expect(inpatientA).toBe('medqc:qc-record-columns:v1:qc%20user%2F%E7%94%B2:inpatient')
    expect(qcRecordColumnStorageKey('qc user/甲', 'discharged')).not.toBe(inpatientA)
    expect(qcRecordColumnStorageKey('qc-user-b', 'inpatient')).not.toBe(inpatientA)
  })

  it('坏 JSON、旧版本和未知列经读取后均回到当前默认列', () => {
    const allowed: QcRecordOptionalColumn[] = [
      'department',
      'time',
      'summary',
      'latestQc',
      'score',
    ]
    const defaults = defaultQcRecordColumns({ compactReview: false, showScore: true })

    for (const raw of [
      '{bad-json',
      JSON.stringify({ version: 0, columns: ['summary'] }),
      JSON.stringify({ version: 1, columns: ['summary', 'retired-column'] }),
    ]) {
      expect(loadQcRecordColumns({ getItem: () => raw }, 'key', allowed, defaults)).toEqual(defaults)
    }
  })

  it('去重并保留允许的选配列顺序，空数组是有效的全部隐藏配置', () => {
    const allowed: QcRecordOptionalColumn[] = ['time', 'summary', 'latestQc']
    const defaults: QcRecordOptionalColumn[] = ['time', 'summary']

    expect(sanitizeQcRecordColumns(['summary', 'summary', 'time'], allowed, defaults)).toEqual([
      'summary',
      'time',
    ])
    expect(sanitizeQcRecordColumns([], allowed, defaults)).toEqual([])
  })

  it('默认列严格保持 showScore=false 和 compactReview 的历史布局', () => {
    expect(defaultQcRecordColumns({ compactReview: false, showScore: false })).toEqual([
      'department',
      'time',
      'summary',
      'latestQc',
    ])
    expect(defaultQcRecordColumns({ compactReview: true, showScore: false })).toEqual([
      'summary',
      'latestQc',
    ])
    expect(defaultQcRecordColumns({ compactReview: true, showScore: true })).toEqual([
      'summary',
      'latestQc',
      'score',
    ])
  })

  it('无稳定用户 id 不生成持久化键，写存储异常显式返回失败', () => {
    expect(qcRecordColumnStorageKey('', 'inpatient')).toBeNull()
    expect(qcRecordColumnStorageKey('unknown', 'discharged')).toBeNull()
    expect(
      saveQcRecordColumns(
        {
          setItem: () => {
            throw new Error('quota exceeded')
          },
        },
        'key',
        ['summary'],
      ),
    ).toBe(false)
  })
})
