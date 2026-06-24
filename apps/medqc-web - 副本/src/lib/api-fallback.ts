export type ServiceHealthStatus = 'healthy' | 'degraded' | 'unavailable' | 'unknown'

export interface ServiceHealth {
  service: string
  status: ServiceHealthStatus
  responseTime: number
  lastCheck: number
  error?: string
}

class ApiFallbackManager {
  private readonly serviceHealth = new Map<string, ServiceHealth>()

  constructor() {
    const now = Date.now()
    this.serviceHealth.set('deepseek-api', {
      service: 'deepseek-api',
      status: 'healthy',
      responseTime: 0,
      lastCheck: now,
    })
    this.serviceHealth.set('supabase-db', {
      service: 'supabase-db',
      status: 'degraded',
      responseTime: 0,
      lastCheck: now,
      error: '已切换到后端 API 兼容层',
    })
    this.serviceHealth.set('file-storage', {
      service: 'file-storage',
      status: 'healthy',
      responseTime: 0,
      lastCheck: now,
    })
  }

  getServiceHealth(): Map<string, ServiceHealth> {
    return new Map(this.serviceHealth)
  }

  setServiceHealth(next: ServiceHealth): void {
    this.serviceHealth.set(next.service, {
      ...next,
      lastCheck: next.lastCheck || Date.now(),
    })
  }

  recordSuccess(service: string, responseTime: number): void {
    const previous = this.serviceHealth.get(service)
    this.serviceHealth.set(service, {
      service,
      status: 'healthy',
      responseTime: Math.max(0, Math.round(responseTime)),
      lastCheck: Date.now(),
      error: undefined,
      ...(previous ? { service: previous.service } : {}),
    })
  }

  recordFailure(service: string, error: string, responseTime = 0): void {
    const previous = this.serviceHealth.get(service)
    const nextStatus: ServiceHealthStatus =
      previous?.status === 'unavailable' ? 'unavailable' : 'degraded'
    this.serviceHealth.set(service, {
      service,
      status: nextStatus,
      responseTime: Math.max(0, Math.round(responseTime)),
      lastCheck: Date.now(),
      error,
    })
  }

  markUnavailable(service: string, reason: string): void {
    this.serviceHealth.set(service, {
      service,
      status: 'unavailable',
      responseTime: 0,
      lastCheck: Date.now(),
      error: reason,
    })
  }
}

export const apiFallbackManager = new ApiFallbackManager()
