/**
 * CN-DRG 2023 引擎占位文件
 *
 * 当前仓库缺少原始自动生成引擎文件。为了保证生产构建可通过，
 * 这里提供最小兼容实现：
 * - 保持与真实引擎相同的导出结构
 * - 在页面真正调用时返回“未入组/引擎未部署”
 *
 * 如果后续需要启用 CN-DRG 2023 正式分组能力，应使用真实生成文件替换本文件。
 */

export const CC = {}
export const CCE = {}
export const MCC = {}
export const SS_VALID = []

export function group_record() {
  return {
    status: '未入组',
    mdc: '',
    adrg: '',
    drg: '',
    messages: ['CN-DRG 2023 分组引擎未部署，当前使用占位实现。'],
  }
}
