import type { WorkflowStageKey } from '@/types/workflow'

export type BatchSummaryStage = WorkflowStageKey | ''

export function currentBatchActionText(stage: BatchSummaryStage, total: number) {
  switch (stage) {
    case 'frontpage_generate':
      return `正在批量生成参考首页：${total} 条`
    case 'coding_qc':
      return `正在批量执行编码质控：${total} 条`
    case 'frontpage_qc':
      return `正在批量执行首页质控：${total} 条`
    case 'settlement_qc':
      return `正在批量执行结算质控：${total} 条`
    default:
      return `正在批量处理：${total} 条`
  }
}

export function batchSuccessSummary(
  stage: BatchSummaryStage,
  successCount: number,
  totalCount: number,
) {
  const partialSuffix = `${successCount}/${totalCount} 条`
  switch (stage) {
    case 'frontpage_generate':
      return {
        success: `批量参考首页生成已提交：${successCount} 条`,
        partial: `批量参考首页生成部分成功：${partialSuffix}`,
        failure: '批量参考首页生成失败',
      }
    case 'coding_qc':
      return {
        success: `批量编码质控完成：${successCount} 条`,
        partial: `批量编码质控部分成功：${partialSuffix}`,
        failure: '批量编码质控失败',
      }
    case 'frontpage_qc':
      return {
        success: `批量首页质控完成：${successCount} 条`,
        partial: `批量首页质控部分成功：${partialSuffix}`,
        failure: '批量首页质控失败',
      }
    case 'settlement_qc':
      return {
        success: `批量结算质控完成：${successCount} 条`,
        partial: `批量结算质控部分成功：${partialSuffix}`,
        failure: '批量结算质控失败',
      }
    default:
      return {
        success: `批量处理完成：${successCount} 条`,
        partial: `批量处理部分成功：${partialSuffix}`,
        failure: '批量处理失败',
      }
  }
}
