/**
 * 智能编码顾问 API
 */

import { ApiService } from '@/services/apiService'
import { extractApiErrorMessageFromError, unwrapApiEnvelope } from '@/utils/api-envelope'
import type {
    ShadowGroupingBatchRequest,
    ShadowGroupingBatchResponse,
    CodingCompletenessAnalysisRequest,
    CodingCompletenessResponse
} from '@/types/advisor'

const USE_MOCK_DATA = (import.meta as any).env?.VITE_USE_DRG_MOCK !== 'false'
const API_V1_PREFIX = '/api/v1'

async function requestOrThrow<T>(
    config: Parameters<typeof ApiService.requestRaw>[0]
): Promise<T> {
    try {
        const response = await ApiService.requestRaw<T>(config)
        return unwrapApiEnvelope<T>(response.data)
    } catch (error) {
        throw new Error(extractApiErrorMessageFromError(error, '请求失败'))
    }
}

/**
 * 模拟数据：编码完整性分析响应
 */
const mockAnalysisResponse: CodingCompletenessResponse = {
    structure_extraction: {
        explicit_diagnoses: [
            {
                text: '急性肾衰竭',
                category: 'diagnosis',
                evidence: {
                    source: 'admission_note',
                    text: '肌酐显著升高，考虑急性肾衰',
                    evidence_type: 'explicit_statement',
                    strength: 'strong'
                }
            }
        ],
        clinical_indicators: [
            {
                text: '肌酐 450umol/L',
                category: 'indicator',
                evidence: {
                    source: 'lab_report',
                    text: 'Cr 450',
                    evidence_type: 'lab_indicator',
                    strength: 'strong'
                }
            }
        ],
        procedure_mentions: []
    },
    suggestions: [
        {
            id: 'gap_mock_1',
            category: 'diagnosis',
            subtype: 'missing_code',
            action: 'add_code',
            risk_level: 'medium',
            target_code: 'N17.900',
            target_name: '急性肾功能衰竭',
            confidence: 0.95,
            evidence: [
                {
                    source: 'admission_note',
                    text: '考虑急性肾衰',
                    evidence_type: 'explicit_statement',
                    strength: 'strong'
                }
            ],
            justification_points: ['病历明确提及', '检验指标支持'],
            required_documentation: []
        }
    ]
}

/**
 * 编码完整性分析 (Layer A/B)
 */
export async function analyzeCodingCompleteness(
    request: CodingCompletenessAnalysisRequest
): Promise<CodingCompletenessResponse> {
    if (USE_MOCK_DATA) {
        // 延迟 1.5 秒模拟 LLM 思考
        await new Promise(resolve => setTimeout(resolve, 1500))
        return Promise.resolve(mockAnalysisResponse)
    }

    return requestOrThrow<CodingCompletenessResponse>({
        method: 'POST',
        url: `${API_V1_PREFIX}/advisor/coding-completeness/analyze`,
        data: request
    })
}

/**
 * 影子分组批处理
 */
export async function batchShadowGrouping(
    request: ShadowGroupingBatchRequest
): Promise<ShadowGroupingBatchResponse> {
    if (USE_MOCK_DATA) {
        await new Promise(resolve => setTimeout(resolve, 800))
        // 简单的 Mock 响应
        return Promise.resolve({
            baseline: {
                drg: 'FB11',
                drg_name: '急性心肌梗死',
                rw: 2.1
            },
            results: request.candidates.map(candidate => ({
                id: candidate.id,
                status: 'computed',
                drg_change_type: candidate.add_secondary_diagnoses?.some(c => c.includes('E11')) ? 'cc_to_mcc' : 'no_change',
                rw_delta: candidate.add_secondary_diagnoses?.some(c => c.includes('E11')) ? 1.05 : 0,
                impact_description: candidate.add_secondary_diagnoses?.some(c => c.includes('E11'))
                    ? '升级：分入伴严重并发症或合并症组 (MCC)'
                    : '分组无变化',
                notes: []
            }))
        } as any) // 临时 bypass 类型检查，因为 ShadowGroupingBatchResponse 定义可能有差异
    }

    return requestOrThrow<ShadowGroupingBatchResponse>({
        method: 'POST',
        url: `${API_V1_PREFIX}/advisor/shadow-grouping/batch`,
        data: request
    })
}
