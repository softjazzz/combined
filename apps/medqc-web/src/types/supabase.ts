export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      medical_records: {
        Row: {
          id: string
          patient_name: string
          patient_id: string
          department: string
          content: string
          file_path: string | null
          file_size: number | null
          mime_type: string | null
          status: 'pending' | 'analyzing' | 'completed' | 'failed'
          qc_score: number | null
          created_at: string
          updated_at: string
          doctor_id: string | null
          hospital_id: string | null
        }
        Insert: {
          id?: string
          patient_name: string
          patient_id: string
          department: string
          content: string
          file_path?: string | null
          file_size?: number | null
          mime_type?: string | null
          status?: 'pending' | 'analyzing' | 'completed' | 'failed'
          qc_score?: number | null
          created_at?: string
          updated_at?: string
          doctor_id?: string | null
          hospital_id?: string | null
        }
        Update: {
          id?: string
          patient_name?: string
          patient_id?: string
          department?: string
          content?: string
          file_path?: string | null
          file_size?: number | null
          mime_type?: string | null
          status?: 'pending' | 'analyzing' | 'completed' | 'failed'
          qc_score?: number | null
          created_at?: string
          updated_at?: string
          doctor_id?: string | null
          hospital_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "medical_records_doctor_id_fkey"
            columns: ["doctor_id"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      qc_results: {
        Row: {
          id: string
          record_id: string
          score: number
          grade: 'A' | 'B' | 'C' | null
          issues: Json
          suggestions: Json
          summary: string | null
          raw_analysis: string | null
          category_scores: Json
          confidence_score: number | null
          rule_version: string
          analysis_time: string
          reviewer_id: string | null
          is_reviewed: boolean
          review_notes: string | null
        }
        Insert: {
          id?: string
          record_id: string
          score: number
          grade?: 'A' | 'B' | 'C' | null
          issues?: Json
          suggestions?: Json
          summary?: string | null
          raw_analysis?: string | null
          category_scores?: Json
          confidence_score?: number | null
          rule_version?: string
          analysis_time?: string
          reviewer_id?: string | null
          is_reviewed?: boolean
          review_notes?: string | null
        }
        Update: {
          id?: string
          record_id?: string
          score?: number
          grade?: 'A' | 'B' | 'C' | null
          issues?: Json
          suggestions?: Json
          summary?: string | null
          raw_analysis?: string | null
          category_scores?: Json
          confidence_score?: number | null
          rule_version?: string
          analysis_time?: string
          reviewer_id?: string | null
          is_reviewed?: boolean
          review_notes?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "qc_results_record_id_fkey"
            columns: ["record_id"]
            referencedRelation: "medical_records"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "qc_results_reviewer_id_fkey"
            columns: ["reviewer_id"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      qc_rules: {
        Row: {
          id: string
          rule_code: string | null
          name: string
          description: string
          category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
          rule_type: 'objective' | 'subjective' | 'hybrid'
          severity: 'critical' | 'major' | 'minor'
          max_score: number
          weight: number
          is_active: boolean
          prompt_template: string | null
          check_logic: Json
          version: string
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          rule_code?: string | null
          name: string
          description: string
          category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
          rule_type?: 'objective' | 'subjective' | 'hybrid'
          severity?: 'critical' | 'major' | 'minor'
          max_score?: number
          weight?: number
          is_active?: boolean
          prompt_template?: string | null
          check_logic?: Json
          version?: string
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          rule_code?: string | null
          name?: string
          description?: string
          category?: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
          rule_type?: 'objective' | 'subjective' | 'hybrid'
          severity?: 'critical' | 'major' | 'minor'
          max_score?: number
          weight?: number
          is_active?: boolean
          prompt_template?: string | null
          check_logic?: Json
          version?: string
          created_at?: string
          created_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "qc_rules_created_by_fkey"
            columns: ["created_by"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      user_roles: {
        Row: {
          id: string
          user_id: string
          role: 'admin' | 'qc_manager' | 'qc_staff' | 'doctor'
          hospital_id: string | null
          department: string | null
          created_at: string
        }
        Insert: {
          id?: string
          user_id: string
          role: 'admin' | 'qc_manager' | 'qc_staff' | 'doctor'
          hospital_id?: string | null
          department?: string | null
          created_at?: string
        }
        Update: {
          id?: string
          user_id?: string
          role?: 'admin' | 'qc_manager' | 'qc_staff' | 'doctor'
          hospital_id?: string | null
          department?: string | null
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "user_roles_user_id_fkey"
            columns: ["user_id"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      qc_rules_embeddings: {
        Row: {
          id: string
          rule_text: string
          embedding: number[] | null
          category: string
          updated_at: string
        }
        Insert: {
          id: string
          rule_text: string
          embedding?: number[] | null
          category: string
          updated_at?: string
        }
        Update: {
          id?: string
          rule_text?: string
          embedding?: number[] | null
          category?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "qc_rules_embeddings_id_fkey"
            columns: ["id"]
            referencedRelation: "qc_rules"
            referencedColumns: ["id"]
          }
        ]
      }
      qc_analysis_cache: {
        Row: {
          content_hash: string
          segment_type: string
          analysis_result: Json
          rule_version: string
          confidence_score: number | null
          created_at: string
          expires_at: string
          access_count: number
        }
        Insert: {
          content_hash: string
          segment_type: string
          analysis_result: Json
          rule_version: string
          confidence_score?: number | null
          created_at?: string
          expires_at: string
          access_count?: number
        }
        Update: {
          content_hash?: string
          segment_type?: string
          analysis_result?: Json
          rule_version?: string
          confidence_score?: number | null
          created_at?: string
          expires_at?: string
          access_count?: number
        }
        Relationships: []
      }
      qc_analysis_history: {
        Row: {
          id: string
          record_id: string
          version_number: number
          analysis_result: Json
          changes_from_previous: Json | null
          analyst_type: 'ai' | 'human' | 'hybrid'
          analysis_time_ms: number | null
          rule_version: string
          created_at: string
        }
        Insert: {
          id?: string
          record_id: string
          version_number: number
          analysis_result: Json
          changes_from_previous?: Json | null
          analyst_type?: 'ai' | 'human' | 'hybrid'
          analysis_time_ms?: number | null
          rule_version: string
          created_at?: string
        }
        Update: {
          id?: string
          record_id?: string
          version_number?: number
          analysis_result?: Json
          changes_from_previous?: Json | null
          analyst_type?: 'ai' | 'human' | 'hybrid'
          analysis_time_ms?: number | null
          rule_version?: string
          created_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "qc_analysis_history_record_id_fkey"
            columns: ["record_id"]
            referencedRelation: "medical_records"
            referencedColumns: ["id"]
          }
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      record_status: 'pending' | 'analyzing' | 'completed' | 'failed'
      qc_category: 'completeness' | 'consistency' | 'rationality' | 'timeliness'
      user_role: 'admin' | 'qc_manager' | 'qc_staff' | 'doctor'
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

export type Tables<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Row']

export type TablesInsert<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Insert']

export type TablesUpdate<T extends keyof Database['public']['Tables']> =
  Database['public']['Tables'][T]['Update']

export type Enums<T extends keyof Database['public']['Enums']> =
  Database['public']['Enums'][T]

// 具体类型别名
export type MedicalRecord = Tables<'medical_records'>
export type QCResult = Tables<'qc_results'>
export type QCRule = Tables<'qc_rules'>
export type QCRuleEmbedding = Tables<'qc_rules_embeddings'>
export type QCAnalysisCache = Tables<'qc_analysis_cache'>
export type QCAnalysisHistory = Tables<'qc_analysis_history'>
export type UserRole = Tables<'user_roles'>

// 扩展类型（包含关联数据）
export type MedicalRecordWithQC = MedicalRecord & {
  qc_results: QCResult[]
}

export type QCResultWithRecord = QCResult & {
  record: MedicalRecord
}

// 质控问题类型
export interface QCIssue {
  id: string
  rule_id: string
  rule_name: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  location?: string
  suggestion?: string
}

// 质控建议类型
export interface QCSuggestion {
  id: string
  category: string
  title: string
  description: string
  priority: 'low' | 'medium' | 'high'
}

// 统计数据类型
export interface QCStatistics {
  total_records: number
  completed_records: number
  pending_records: number
  analyzing_records: number
  failed_records: number
  average_score: number
  pass_rate: number
  by_department: Array<{
    department: string
    count: number
    average_score: number
  }>
  by_date: Array<{
    date: string
    count: number
    average_score: number
  }>
} 

// 增强的质控规则类型
export interface EnhancedQCRule extends Omit<QCRule, 'check_logic'> {
  rule_code: string | null
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  check_logic: QCRuleLogic
  version: string
}

// 质控规则逻辑配置
export interface QCRuleLogic {
  type: 'structure_check' | 'llm_analysis' | 'hybrid' | 'time_check' | 'conditional_check'
  patterns?: string[]
  criteria?: string[]
  required_sections?: string[]
  search_patterns?: string[]
  time_requirements?: {
    deadline_hours: number
    from_admission: boolean
  }
  trigger_patterns?: string[] // 用于条件检查
}

// 质控分析结果
export interface QCAnalysisResult {
  violations: QCViolation[]
  totalScore: number
  grade: 'A' | 'B' | 'C'
  categoryScores: CategoryScore[]
  analysisTime: number
  confidence: number
  version: string
  summary: string
}

// 质控违规记录
export interface QCViolation {
  ruleId: string
  ruleName: string
  ruleCode: string
  severity: 'critical' | 'major' | 'minor'
  score: number
  evidence: string[]
  location: string
  confidence: number
  reasoning?: string
  suggestion?: string
  isObjective: boolean
}

// 分类得分
export interface CategoryScore {
  category: string
  name: string
  score: number
  maxScore: number
  violations: number
}

// 改进计划
export interface ImprovementPlan {
  priority: 'high' | 'medium' | 'low'
  suggestions: ImprovementSuggestion[]
  estimatedTime: string
  complexity: 'simple' | 'moderate' | 'complex'
}

export interface ImprovementSuggestion {
  id: string
  title: string
  description: string
  category: string
  priority: 'high' | 'medium' | 'low'
  example?: string
  location: string
  effort: 'low' | 'medium' | 'high'
}

// RAG检索结果
export interface RAGSearchResult {
  ruleId: string
  ruleCode: string
  ruleName: string
  category: string
  similarity: number
  relevanceScore: number
}

// 缓存条目
export interface CacheEntry {
  contentHash: string
  segmentType: string
  result: QCAnalysisResult
  confidence: number
  timestamp: Date
  hits: number
}

// 分析会话
export interface AnalysisSession {
  id: string
  recordId: string
  status: 'pending' | 'analyzing' | 'completed' | 'failed'
  progress: number
  currentStage: string
  startTime: Date
  estimatedCompletion?: Date
  errors?: string[]
}