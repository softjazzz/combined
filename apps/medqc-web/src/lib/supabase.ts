/**
 * 兼容层：项目已下线 Supabase，旧代码仍有 import '@/lib/supabase'。
 * 此文件仅用于保证编译和历史功能回退，不再发起真实 Supabase 连接。
 */

type SupabaseResult<T = unknown> = { data: T | null; error: Error | null; count?: number }

const SUPABASE_DISABLED_MSG = 'Supabase 已停用，请迁移到后端 API 链路'
let warnedOnce = false

function warnSupabaseDisabled(context: string) {
  if (warnedOnce) return
  warnedOnce = true
  console.warn(`[supabase-compat] ${SUPABASE_DISABLED_MSG} (${context})`)
}

class MockQueryBuilder<T = unknown> implements PromiseLike<SupabaseResult<T>> {
  private mode: 'select' | 'insert' | 'update' | 'delete' | 'upsert' = 'select'
  private payload: unknown = null
  private isSingle = false

  select(_columns = '*', _options?: Record<string, unknown>) {
    this.mode = 'select'
    return this
  }

  insert(payload: unknown) {
    this.mode = 'insert'
    this.payload = payload
    return this
  }

  update(payload: unknown) {
    this.mode = 'update'
    this.payload = payload
    return this
  }

  delete() {
    this.mode = 'delete'
    return this
  }

  upsert(payload: unknown, _options?: Record<string, unknown>) {
    this.mode = 'upsert'
    this.payload = payload
    return this
  }

  eq(_column: string, _value: unknown) {
    return this
  }

  neq(_column: string, _value: unknown) {
    return this
  }

  in(_column: string, _values: unknown[]) {
    return this
  }

  contains(_column: string, _value: unknown) {
    return this
  }

  or(_filters: string) {
    return this
  }

  order(_column: string, _options?: Record<string, unknown>) {
    return this
  }

  range(_from: number, _to: number) {
    return this
  }

  limit(_count: number) {
    return this
  }

  gte(_column: string, _value: unknown) {
    return this
  }

  lte(_column: string, _value: unknown) {
    return this
  }

  like(_column: string, _pattern: string) {
    return this
  }

  ilike(_column: string, _pattern: string) {
    return this
  }

  is(_column: string, _value: unknown) {
    return this
  }

  not(_column: string, _operator: string, _value: unknown) {
    return this
  }

  single() {
    this.isSingle = true
    return this
  }

  maybeSingle() {
    this.isSingle = true
    return this
  }

  private async execute(): Promise<SupabaseResult<T>> {
    warnSupabaseDisabled(`query:${this.mode}`)

    if (this.mode === 'insert' || this.mode === 'update' || this.mode === 'upsert') {
      if (Array.isArray(this.payload)) {
        const first = this.payload[0] ?? null
        return { data: (this.isSingle ? first : this.payload) as T, error: null }
      }
      return { data: this.payload as T, error: null }
    }

    if (this.mode === 'delete') {
      return { data: null, error: null }
    }

    return { data: (this.isSingle ? null : []) as T, error: null, count: 0 }
  }

  then<TResult1 = SupabaseResult<T>, TResult2 = never>(
    onfulfilled?: ((value: SupabaseResult<T>) => TResult1 | PromiseLike<TResult1>) | null,
    onrejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null,
  ): PromiseLike<TResult1 | TResult2> {
    return this.execute().then(onfulfilled, onrejected)
  }
}

function buildRpcResponse(fn: string, args?: Record<string, unknown>): SupabaseResult<unknown> {
  warnSupabaseDisabled(`rpc:${fn}`)

  if (fn === 'batch_update_rule_status') {
    const ruleIds = Array.isArray(args?.rule_ids) ? args?.rule_ids : []
    return {
      data: {
        success_count: ruleIds.length,
        error_count: 0,
        errors: [],
      },
      error: null,
    }
  }

  if (fn === 'get_applicable_rules') {
    return { data: [], error: null }
  }

  return { data: null, error: null }
}

export const TABLES = {
  MEDICAL_RECORDS: 'medical_records',
  MEDICAL_RECORDS_TEST: 'medical_records_test',
  QC_RESULTS: 'qc_results',
  QC_RULES: 'qc_rules',
  BATCH_PROCESSING_TASKS: 'batch_processing_tasks',
} as const

export const STORAGE_BUCKETS = {
  MEDICAL_FILES: 'medical-files',
  QC_REPORTS: 'qc-reports',
} as const

export const supabase = {
  from<T = unknown>(_table: string) {
    return new MockQueryBuilder<T>()
  },
  rpc(fn: string, args?: Record<string, unknown>) {
    return Promise.resolve(buildRpcResponse(fn, args))
  },
  channel(_name: string, _options?: Record<string, unknown>) {
    return {
      on(_event: string, _filter: unknown, _callback: (payload: unknown) => void) {
        return this
      },
      subscribe(callback?: (status: string) => void) {
        callback?.('SUBSCRIBED')
        return this
      },
      unsubscribe() {
        return Promise.resolve('ok')
      },
    }
  },
  removeChannel(_channel: unknown) {
    return Promise.resolve('ok')
  },
  auth: {
    getUser: async () => ({ data: { user: null }, error: null }),
    getSession: async () => ({ data: { session: null }, error: null }),
  },
  storage: {
    from(_bucket: string) {
      warnSupabaseDisabled('storage')
      return {
        upload: async (_path: string, _file: unknown, _options?: Record<string, unknown>) => ({
          data: null,
          error: new Error(SUPABASE_DISABLED_MSG),
        }),
        getPublicUrl: (path: string) => ({ data: { publicUrl: path } }),
        download: async (_path: string) => ({
          data: null,
          error: new Error(SUPABASE_DISABLED_MSG),
        }),
        remove: async (_paths: string[]) => ({ data: null, error: null }),
        list: async (_path?: string) => ({ data: [], error: null }),
      }
    },
  },
}

export async function checkSupabaseConnection() {
  warnSupabaseDisabled('check-connection')
  return false
}
