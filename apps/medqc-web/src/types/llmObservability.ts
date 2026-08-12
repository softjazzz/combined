export interface LlmObservabilityRange {
  start_at: string | null
  end_at: string | null
  timezone: string
}

export interface LlmObservabilityKpis {
  logical_calls: number
  http_attempts: number
  record_count: number
  unbound_record_attempts: number
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  peak_concurrency: number
  retry_attempts: number
  successful_attempts: number
  failed_attempts: number
  unknown_usage_attempts: number
}

export interface LlmObservabilityScope {
  account_scope: 'all_accounts'
  record_scope: 'all_observed_records'
}

export interface LlmObservabilityTrendPoint {
  bucket: string
  logical_calls: number
  http_attempts: number
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  p95_latency_ms: number | null
  peak_concurrency: number
  unknown_usage_attempts: number
}

export interface LlmObservabilityModelSummary {
  provider_code: string
  model: string
  model_role: string
  logical_calls: number
  http_attempts: number
  total_tokens: number | null
  avg_latency_ms: number | null
  unknown_usage_attempts: number
}

export interface LlmObservabilitySafeError {
  safe_error_kind: string
  count: number
}

export interface LlmObservabilityRecordSummary {
  record_key_hash: string
  logical_calls: number
  http_attempts: number
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  p95_latency_ms: number | null
  unknown_usage_attempts: number
  last_called_at: string | null
  status: string
}

export interface LlmObservabilityRecordPage {
  items: LlmObservabilityRecordSummary[]
  total: number
  page: number
  page_size: number
}

export interface LlmObservabilityOverview {
  scope: LlmObservabilityScope
  range: LlmObservabilityRange
  kpis: LlmObservabilityKpis
  trends: LlmObservabilityTrendPoint[]
  models: LlmObservabilityModelSummary[]
  safe_errors: LlmObservabilitySafeError[]
  records: LlmObservabilityRecordPage
}

export interface LlmCallAttempt {
  logical_call_id: string
  attempt_no: number
  business_scene: string
  root_job_id: string | null
  executor_key: string | null
  provider_code: string
  model: string
  model_role: string
  status: string
  safe_error_kind: string | null
  usage_state: 'known' | 'unknown'
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  latency_ms: number | null
  started_at: string
  finished_at: string | null
}

export interface LlmRecordCallAttempts {
  record_key_hash: string
  items: LlmCallAttempt[]
  total: number
  page: number
  page_size: number
}

export interface LlmObservabilityQuery {
  start_at?: string
  end_at?: string
  provider_code?: string
  model?: string
  business_scene?: string
  page?: number
  page_size?: number
}

export interface LlmRecordCallsQuery {
  start_at?: string
  end_at?: string
  provider_code?: string
  model?: string
  business_scene?: string
  page?: number
  page_size?: number
}
