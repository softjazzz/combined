/**
 * 智能编码顾问类型定义
 */

// ==========================================
// 影子分组相关
// ==========================================

export interface ShadowGroupingCandidate {
    id: string;
    add_secondary_diagnoses?: string[];
    replace_secondary_diagnoses?: { from_code?: string; to_code: string }[];
    add_procedures?: string[];
    eligible?: boolean;
}

export interface ShadowGroupingBatchRequest {
    request_id: string;
    baseline: {
        primary_diagnosis: string;
        secondary_diagnoses: string[];
        procedures: string[];
        patient_age: number;
        patient_gender: string;
        total_hospital_days?: number;
    };
    candidates: ShadowGroupingCandidate[];
    options?: any;
}

export interface ShadowGroupingResultData {
    drg: string;
    drg_name: string;
    adrg?: string;
    rw?: number;
}

export interface ShadowGroupingResultItem {
    id: string;
    status: 'computed' | 'skipped' | 'error';
    with_candidate?: ShadowGroupingResultData;
    drg_change_type: 'base_to_cc' | 'cc_to_mcc' | 'no_change' | 'drg_changed' | 'error';
    rw_delta?: number;
    impact_description?: string;
    notes: string[];
    error_message?: string;
}

export interface ShadowGroupingBatchResponse {
    baseline: ShadowGroupingResultData;
    results: ShadowGroupingResultItem[];
}

// ==========================================
// 实体抽取与差距分析相关 (Layer A/B)
// ==========================================

export type EvidenceType = 'explicit_statement' | 'lab_indicator' | 'medication_indicator' | 'procedure_indicator';
export type EvidenceStrength = 'strong' | 'medium' | 'weak';

export interface Evidence {
    source: string;
    text: string;
    start?: number;
    end?: number;
    evidence_type: EvidenceType;
    strength: EvidenceStrength;
}

export interface ClinicalEntity {
    text: string;
    category: 'diagnosis' | 'procedure' | 'indicator';
    evidence: Evidence;
}

export interface ExtractionResult {
    explicit_diagnoses: ClinicalEntity[];
    clinical_indicators: ClinicalEntity[];
    procedure_mentions: ClinicalEntity[];
}

export type GapAction = 'add_code' | 'needs_doc_update' | 'ignore';
export type GapSubtype = 'missing_code' | 'code_refinement' | 'needs_doc_update';

export interface CodingGap {
    id: string;
    category: 'diagnosis' | 'procedure';
    subtype: GapSubtype;
    action: GapAction;
    risk_level: 'low' | 'medium' | 'high';
    target_code?: string;
    target_name: string;
    confidence: number;
    evidence: Evidence[];
    justification_points: string[];
    required_documentation: string[];
    shadow_grouping?: ShadowGroupingResultItem; // 可选的预计算影子分组结果
}

export interface CodingCompletenessResponse {
    structure_extraction: ExtractionResult;
    suggestions: CodingGap[];
}

export interface CodingCompletenessAnalysisRequest {
    medical_record: string;
    current_data: {
        primary_diagnosis?: { code: string; name: string };
        secondary_diagnoses: { code: string; name: string }[];
        procedures: { code: string; name: string }[];
    };
}
