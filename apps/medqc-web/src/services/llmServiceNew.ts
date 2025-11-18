/**
 * 兼容旧引用的 LLMServiceNew 封装
 *
 * 说明：
 * - 部分组件仍引用 `@/services/llmServiceNew`
 * - 当前项目已有 `llmService.ts` 提供完整实现
 * - 这里简单地重新导出，避免 TS 类型缺失与重复实现
 */

import { LLMService, llmService } from './llmService'

export { LLMService, llmService }

export default LLMService
