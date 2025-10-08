/**
 * Supabase数据库类型定义
 * 自动生成的数据库Schema类型
 */

export interface Database {
  public: {
    Tables: {
      unstructured_medical_documents: {
        Row: {
          id: string
          title: string
          document_type: 'raw_text' | 'copied_record' | 'uploaded_file' | 'scanned_document'
          raw_content: string
          content_length: number
          source: 'manual_input' | 'copy_paste' | 'file_upload' | 'api_import'
          original_filename: string | null
          mime_type: string | null
          file_size: number | null
          processing_status: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped'
          structured_record_id: string | null
          extracted_data: Record<string, unknown>
          extraction_confidence: number | null
          qc_analysis_id: string | null
          qc_status: 'not_analyzed' | 'analyzing' | 'completed' | 'failed'
          tags: string[]
          category: string | null
          priority_level: number
          created_by: string | null
          department_id: string | null
          created_at: string
          updated_at: string
          processed_at: string | null
          is_deleted: boolean
          deleted_at: string | null
          deleted_by: string | null
        }
        Insert: {
          id?: string
          title?: string
          document_type?: 'raw_text' | 'copied_record' | 'uploaded_file' | 'scanned_document'
          raw_content: string
          source?: 'manual_input' | 'copy_paste' | 'file_upload' | 'api_import'
          original_filename?: string | null
          mime_type?: string | null
          file_size?: number | null
          processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped'
          structured_record_id?: string | null
          extracted_data?: Record<string, unknown>
          extraction_confidence?: number | null
          qc_analysis_id?: string | null
          qc_status?: 'not_analyzed' | 'analyzing' | 'completed' | 'failed'
          tags?: string[]
          category?: string | null
          priority_level?: number
          created_by?: string | null
          department_id?: string | null
          processed_at?: string | null
          is_deleted?: boolean
          deleted_at?: string | null
          deleted_by?: string | null
        }
        Update: {
          title?: string
          document_type?: 'raw_text' | 'copied_record' | 'uploaded_file' | 'scanned_document'
          raw_content?: string
          source?: 'manual_input' | 'copy_paste' | 'file_upload' | 'api_import'
          original_filename?: string | null
          mime_type?: string | null
          file_size?: number | null
          processing_status?: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped'
          structured_record_id?: string | null
          extracted_data?: Record<string, unknown>
          extraction_confidence?: number | null
          qc_analysis_id?: string | null
          qc_status?: 'not_analyzed' | 'analyzing' | 'completed' | 'failed'
          tags?: string[]
          category?: string | null
          priority_level?: number
          created_by?: string | null
          department_id?: string | null
          processed_at?: string | null
          is_deleted?: boolean
          deleted_at?: string | null
          deleted_by?: string | null
        }
      }
      medical_records: {
        Row: {
          id: string
          patient_name: string
          patient_age: number
          patient_gender: 'M' | 'F' | 'U'
          department: string
          admission_date: string
          record_type: 'inpatient' | 'outpatient' | 'emergency'
          content: string
          file_url: string | null
          file_name: string | null
          file_size: number | null
          status: 'pending' | 'analyzing' | 'completed' | 'failed'
          created_at: string
          updated_at: string
          hospital_id: string | null
          doctor_id: string | null
          qc_score: number | null
          qc_grade: 'A' | 'B' | 'C' | null
        }
        Insert: {
          id?: string
          patient_name: string
          patient_age: number
          patient_gender: 'M' | 'F' | 'U'
          department: string
          admission_date: string
          record_type: 'inpatient' | 'outpatient' | 'emergency'
          content: string
          file_url?: string | null
          file_name?: string | null
          file_size?: number | null
          status?: 'pending' | 'analyzing' | 'completed' | 'failed'
          created_at?: string
          updated_at?: string
          hospital_id?: string | null
          doctor_id?: string | null
          qc_score?: number | null
          qc_grade?: 'A' | 'B' | 'C' | null
        }
        Update: {
          id?: string
          patient_name?: string
          patient_age?: number
          patient_gender?: 'M' | 'F' | 'U'
          department?: string
          admission_date?: string
          record_type?: 'inpatient' | 'outpatient' | 'emergency'
          content?: string
          file_url?: string | null
          file_name?: string | null
          file_size?: number | null
          status?: 'pending' | 'analyzing' | 'completed' | 'failed'
          created_at?: string
          updated_at?: string
          hospital_id?: string | null
          doctor_id?: string | null
          qc_score?: number | null
          qc_grade?: 'A' | 'B' | 'C' | null
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
          ai_score: number | null
          rule_score: number | null
          score: number
          grade: 'A' | 'B' | 'C' | null
          issues: Record<string, unknown>
          suggestions: Record<string, unknown>
          summary: string | null
          raw_analysis: string | null
          category_scores: Record<string, unknown>
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
          ai_score?: number | null
          rule_score?: number | null
          score: number
          grade?: 'A' | 'B' | 'C' | null
          issues?: Record<string, unknown>
          suggestions?: Record<string, unknown>
          summary?: string | null
          raw_analysis?: string | null
          category_scores?: Record<string, unknown>
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
          ai_score?: number | null
          rule_score?: number | null
          score?: number
          grade?: 'A' | 'B' | 'C' | null
          issues?: Record<string, unknown>
          suggestions?: Record<string, unknown>
          summary?: string | null
          raw_analysis?: string | null
          category_scores?: Record<string, unknown>
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
          check_logic: Record<string, unknown>
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
          check_logic?: Record<string, unknown>
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
          check_logic?: Record<string, unknown>
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
      // 新增：数据立方体表
      data_cubes: {
        Row: {
          id: string
          cube_name: string
          dimensions: Record<string, unknown>
          measures: Record<string, unknown>
          aggregation_rules: Record<string, unknown> | null
          refresh_schedule: string | null
          last_refresh: string | null
          created_at: string
          updated_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          cube_name: string
          dimensions: Record<string, unknown>
          measures: Record<string, unknown>
          aggregation_rules?: Record<string, unknown> | null
          refresh_schedule?: string | null
          last_refresh?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          cube_name?: string
          dimensions?: Record<string, unknown>
          measures?: Record<string, unknown>
          aggregation_rules?: Record<string, unknown> | null
          refresh_schedule?: string | null
          last_refresh?: string | null
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "data_cubes_created_by_fkey"
            columns: ["created_by"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      // 新增：分析指标表
      analytics_metrics: {
        Row: {
          id: string
          metric_code: string
          metric_name: string
          metric_type: 'count' | 'sum' | 'avg' | 'ratio' | 'trend'
          category: 'department' | 'doctor' | 'time' | 'quality' | 'efficiency'
          calculation_formula: string | null
          unit: string | null
          target_value: number | null
          warning_threshold: number | null
          critical_threshold: number | null
          is_active: boolean
          display_order: number
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          metric_code: string
          metric_name: string
          metric_type: 'count' | 'sum' | 'avg' | 'ratio' | 'trend'
          category: 'department' | 'doctor' | 'time' | 'quality' | 'efficiency'
          calculation_formula?: string | null
          unit?: string | null
          target_value?: number | null
          warning_threshold?: number | null
          critical_threshold?: number | null
          is_active?: boolean
          display_order?: number
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          metric_code?: string
          metric_name?: string
          metric_type?: 'count' | 'sum' | 'avg' | 'ratio' | 'trend'
          category?: 'department' | 'doctor' | 'time' | 'quality' | 'efficiency'
          calculation_formula?: string | null
          unit?: string | null
          target_value?: number | null
          warning_threshold?: number | null
          critical_threshold?: number | null
          is_active?: boolean
          display_order?: number
          created_at?: string
          updated_at?: string
        }
        Relationships: []
      }
      // 新增：分析结果表
      analytics_results: {
        Row: {
          id: string
          metric_id: string
          dimension_values: Record<string, unknown>
          metric_value: number
          comparison_value: number | null
          trend_direction: 'up' | 'down' | 'stable' | null
          trend_percentage: number | null
          calculation_date: string
          calculation_time: string
          data_source: string | null
          confidence_level: number
        }
        Insert: {
          id?: string
          metric_id: string
          dimension_values: Record<string, unknown>
          metric_value: number
          comparison_value?: number | null
          trend_direction?: 'up' | 'down' | 'stable' | null
          trend_percentage?: number | null
          calculation_date: string
          calculation_time?: string
          data_source?: string | null
          confidence_level?: number
        }
        Update: {
          id?: string
          metric_id?: string
          dimension_values?: Record<string, unknown>
          metric_value?: number
          comparison_value?: number | null
          trend_direction?: 'up' | 'down' | 'stable' | null
          trend_percentage?: number | null
          calculation_date?: string
          calculation_time?: string
          data_source?: string | null
          confidence_level?: number
        }
        Relationships: [
          {
            foreignKeyName: "analytics_results_metric_id_fkey"
            columns: ["metric_id"]
            referencedRelation: "analytics_metrics"
            referencedColumns: ["id"]
          }
        ]
      }
      // 新增：报表模板表
      report_templates: {
        Row: {
          id: string
          template_code: string
          template_name: string
          template_type: 'qc_summary' | 'performance' | 'trend' | 'comparison'
          description: string | null
          layout_config: Record<string, unknown>
          chart_configs: Record<string, unknown>
          filters: Record<string, unknown> | null
          schedule_config: Record<string, unknown> | null
          output_formats: string[]
          is_active: boolean
          is_system_template: boolean
          created_at: string
          updated_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          template_code: string
          template_name: string
          template_type: 'qc_summary' | 'performance' | 'trend' | 'comparison'
          description?: string | null
          layout_config: Record<string, unknown>
          chart_configs: Record<string, unknown>
          filters?: Record<string, unknown> | null
          schedule_config?: Record<string, unknown> | null
          output_formats?: string[]
          is_active?: boolean
          is_system_template?: boolean
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          template_code?: string
          template_name?: string
          template_type?: 'qc_summary' | 'performance' | 'trend' | 'comparison'
          description?: string | null
          layout_config?: Record<string, unknown>
          chart_configs?: Record<string, unknown>
          filters?: Record<string, unknown> | null
          schedule_config?: Record<string, unknown> | null
          output_formats?: string[]
          is_active?: boolean
          is_system_template?: boolean
          created_at?: string
          updated_at?: string
          created_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "report_templates_created_by_fkey"
            columns: ["created_by"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      // 新增：报表实例表
      report_instances: {
        Row: {
          id: string
          template_id: string
          report_name: string
          report_period: string
          period_start: string
          period_end: string
          parameters: Record<string, unknown> | null
          status: 'pending' | 'generating' | 'completed' | 'failed'
          progress: number
          file_path: string | null
          file_size: number | null
          mime_type: string | null
          generation_time: number | null
          error_message: string | null
          generated_at: string | null
          expires_at: string | null
          download_count: number
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          template_id: string
          report_name: string
          report_period: string
          period_start: string
          period_end: string
          parameters?: Record<string, unknown> | null
          status?: 'pending' | 'generating' | 'completed' | 'failed'
          progress?: number
          file_path?: string | null
          file_size?: number | null
          mime_type?: string | null
          generation_time?: number | null
          error_message?: string | null
          generated_at?: string | null
          expires_at?: string | null
          download_count?: number
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          template_id?: string
          report_name?: string
          report_period?: string
          period_start?: string
          period_end?: string
          parameters?: Record<string, unknown> | null
          status?: 'pending' | 'generating' | 'completed' | 'failed'
          progress?: number
          file_path?: string | null
          file_size?: number | null
          mime_type?: string | null
          generation_time?: number | null
          error_message?: string | null
          generated_at?: string | null
          expires_at?: string | null
          download_count?: number
          created_at?: string
          created_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "report_instances_template_id_fkey"
            columns: ["template_id"]
            referencedRelation: "report_templates"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "report_instances_created_by_fkey"
            columns: ["created_by"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      // 新增：数据快照表
      data_snapshots: {
        Row: {
          id: string
          snapshot_name: string
          snapshot_type: 'daily' | 'weekly' | 'monthly'
          snapshot_date: string
          data_summary: Record<string, unknown>
          record_count: number
          avg_qc_score: number | null
          department_stats: Record<string, unknown> | null
          doctor_stats: Record<string, unknown> | null
          quality_indicators: Record<string, unknown> | null
          created_at: string
        }
        Insert: {
          id?: string
          snapshot_name: string
          snapshot_type: 'daily' | 'weekly' | 'monthly'
          snapshot_date: string
          data_summary: Record<string, unknown>
          record_count: number
          avg_qc_score?: number | null
          department_stats?: Record<string, unknown> | null
          doctor_stats?: Record<string, unknown> | null
          quality_indicators?: Record<string, unknown> | null
          created_at?: string
        }
        Update: {
          id?: string
          snapshot_name?: string
          snapshot_type?: 'daily' | 'weekly' | 'monthly'
          snapshot_date?: string
          data_summary?: Record<string, unknown>
          record_count?: number
          avg_qc_score?: number | null
          department_stats?: Record<string, unknown> | null
          doctor_stats?: Record<string, unknown> | null
          quality_indicators?: Record<string, unknown> | null
          created_at?: string
        }
        Relationships: []
      }
      // 新增：对比分析表
      comparison_analyses: {
        Row: {
          id: string
          analysis_name: string
          analysis_type: 'department_vs_department' | 'period_vs_period' | 'doctor_vs_doctor'
          baseline_criteria: Record<string, unknown>
          comparison_criteria: Record<string, unknown>
          analysis_results: Record<string, unknown>
          insights: Record<string, unknown> | null
          recommendations: Record<string, unknown> | null
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          analysis_name: string
          analysis_type: 'department_vs_department' | 'period_vs_period' | 'doctor_vs_doctor'
          baseline_criteria: Record<string, unknown>
          comparison_criteria: Record<string, unknown>
          analysis_results: Record<string, unknown>
          insights?: Record<string, unknown> | null
          recommendations?: Record<string, unknown> | null
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          analysis_name?: string
          analysis_type?: 'department_vs_department' | 'period_vs_period' | 'doctor_vs_doctor'
          baseline_criteria?: Record<string, unknown>
          comparison_criteria?: Record<string, unknown>
          analysis_results?: Record<string, unknown>
          insights?: Record<string, unknown> | null
          recommendations?: Record<string, unknown> | null
          created_at?: string
          created_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "comparison_analyses_created_by_fkey"
            columns: ["created_by"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      // 新增：预警规则表
      alert_rules: {
        Row: {
          id: string
          rule_name: string
          metric_id: string
          condition_type: 'threshold' | 'trend' | 'anomaly'
          condition_config: Record<string, unknown>
          alert_level: 'info' | 'warning' | 'critical'
          notification_config: Record<string, unknown> | null
          is_active: boolean
          created_at: string
          created_by: string | null
        }
        Insert: {
          id?: string
          rule_name: string
          metric_id: string
          condition_type: 'threshold' | 'trend' | 'anomaly'
          condition_config: Record<string, unknown>
          alert_level: 'info' | 'warning' | 'critical'
          notification_config?: Record<string, unknown> | null
          is_active?: boolean
          created_at?: string
          created_by?: string | null
        }
        Update: {
          id?: string
          rule_name?: string
          metric_id?: string
          condition_type?: 'threshold' | 'trend' | 'anomaly'
          condition_config?: Record<string, unknown>
          alert_level?: 'info' | 'warning' | 'critical'
          notification_config?: Record<string, unknown> | null
          is_active?: boolean
          created_at?: string
          created_by?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "alert_rules_metric_id_fkey"
            columns: ["metric_id"]
            referencedRelation: "analytics_metrics"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alert_rules_created_by_fkey"
            columns: ["created_by"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
      // 新增：预警记录表
      alert_records: {
        Row: {
          id: string
          rule_id: string
          alert_level: 'info' | 'warning' | 'critical'
          alert_message: string
          metric_value: number | null
          dimension_values: Record<string, unknown> | null
          triggered_at: string
          acknowledged_at: string | null
          acknowledged_by: string | null
          resolution_notes: string | null
          is_resolved: boolean
        }
        Insert: {
          id?: string
          rule_id: string
          alert_level: 'info' | 'warning' | 'critical'
          alert_message: string
          metric_value?: number | null
          dimension_values?: Record<string, unknown> | null
          triggered_at?: string
          acknowledged_at?: string | null
          acknowledged_by?: string | null
          resolution_notes?: string | null
          is_resolved?: boolean
        }
        Update: {
          id?: string
          rule_id?: string
          alert_level?: 'info' | 'warning' | 'critical'
          alert_message?: string
          metric_value?: number | null
          dimension_values?: Record<string, unknown> | null
          triggered_at?: string
          acknowledged_at?: string | null
          acknowledged_by?: string | null
          resolution_notes?: string | null
          is_resolved?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "alert_records_rule_id_fkey"
            columns: ["rule_id"]
            referencedRelation: "alert_rules"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "alert_records_acknowledged_by_fkey"
            columns: ["acknowledged_by"]
            referencedRelation: "users"
            referencedColumns: ["id"]
          }
        ]
      }
    }
    Views: {
      // 新增：科室分析视图
      v_department_analytics: {
        Row: {
          department: string
          total_records: number
          avg_qc_score: number | null
          grade_a_count: number
          grade_b_count: number
          grade_c_count: number
          avg_confidence: number | null
          month: string
        }
        Relationships: []
      }
      // 新增：医生绩效视图
      v_doctor_performance: {
        Row: {
          doctor_name: string | null
          department: string
          total_records: number
          avg_qc_score: number | null
          grade_a_count: number
          grade_b_count: number
          grade_c_count: number
          avg_processing_hours: number | null
          month: string
        }
        Relationships: []
      }
      // 新增：质量趋势视图
      v_quality_trends: {
        Row: {
          date: string
          daily_records: number
          avg_qc_score: number | null
          score_stddev: number | null
          grade_a_rate: number | null
          grade_b_rate: number | null
          grade_c_rate: number | null
          avg_confidence: number | null
        }
        Relationships: []
      }
    }
    Functions: {
      // 新增：科室排名计算函数
      calculate_department_ranking: {
        Args: {
          p_period_start?: string
          p_period_end?: string
        }
        Returns: {
          department: string
          total_records: number
          avg_score: number
          grade_a_rate: number
          rank_by_score: number
          rank_by_volume: number
        }[]
      }
      // 新增：质量洞察生成函数
      generate_quality_insight: {
        Args: {
          p_department?: string
          p_period_days?: number
        }
        Returns: {
          current_avg_score: number
          previous_avg_score: number
          trend_direction: string
          improvement_rate: number
          analysis_period_days: number
          department: string
        }
      }
      // 新增：每日分析调度函数
      schedule_daily_analytics: {
        Args: {}
        Returns: void
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

// 导出常用类型
export type MedicalRecord = Database['public']['Tables']['medical_records']['Row']
export type QCResult = Database['public']['Tables']['qc_results']['Row']
export type QCRule = Database['public']['Tables']['qc_rules']['Row']
export type UserRole = Database['public']['Tables']['user_roles']['Row']

// 新增：分析和报表相关类型
export type DataCube = Database['public']['Tables']['data_cubes']['Row']
export type AnalyticsMetric = Database['public']['Tables']['analytics_metrics']['Row']
export type AnalyticsResult = Database['public']['Tables']['analytics_results']['Row']
export type ReportTemplate = Database['public']['Tables']['report_templates']['Row']
export type ReportInstance = Database['public']['Tables']['report_instances']['Row']
export type DataSnapshot = Database['public']['Tables']['data_snapshots']['Row']
export type ComparisonAnalysis = Database['public']['Tables']['comparison_analyses']['Row']
export type AlertRule = Database['public']['Tables']['alert_rules']['Row']
export type AlertRecord = Database['public']['Tables']['alert_records']['Row']

// 视图类型
export type DepartmentAnalytics = Database['public']['Views']['v_department_analytics']['Row']
export type DoctorPerformance = Database['public']['Views']['v_doctor_performance']['Row']
export type QualityTrends = Database['public']['Views']['v_quality_trends']['Row'] 