/**
 * 统一 LLM 服务导出
 * 提供所有 LLM 相关的类型和服务
 */

// 导出类型
export type {
  LLMConfig,
  CallOptions,
  LLMResponse,
  ExtractedMedicalData,
  ExtractedDocument,
  DocumentPosition,
  ParseOptions,
  ParseResult,
  BatchParseResult
} from './types'

export {
  DocumentCategory,
  DocumentType,
  LLMError,
  LLMConfigError,
  LLMAPIError,
  LLMParseError
} from './types'

// 导出客户端类
export { BaseLLMClient } from './BaseLLMClient'
export { OpenAIClient } from './OpenAIClient'
export { DeepSeekClient } from './DeepSeekClient'
export { AliyunClient } from './AliyunClient'

// 导出服务门面
export { LLMServiceFacade, llmService } from './LLMServiceFacade'

// 默认导出服务实例
import { llmService as defaultService } from './LLMServiceFacade'
export default defaultService

