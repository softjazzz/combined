// 规则结果的默认文案，任务阶段和执行错误仍使用各自的文案。
export const QC_RESULT_STATUS_LABELS = {
  non_compliant: '确定问题',
  data_gap: '资料待核实',
  uncertain: '待判断',
  technical_error: '结果校验异常',
} as const
