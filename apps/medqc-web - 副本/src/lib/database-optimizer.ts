type QueryFn<T> = () => Promise<T>

interface CachedQueryEntry<T> {
  value: T
  expiresAt: number
  createdAt: number
  hitCount: number
  responseTime: number
}

export interface DatabaseQueryStats {
  totalQueries: number
  cacheHits: number
  cacheMisses: number
  cacheHitRate: number
  averageResponseTime: number
  lastUpdated: string | null
}

export interface DatabaseCacheStats {
  size: number
  keys: string[]
  cacheHitRate: number
  totalQueries: number
  cacheHits: number
  cacheMisses: number
}

function cloneValue<T>(value: T): T {
  if (value === undefined) {
    return value
  }
  try {
    return JSON.parse(JSON.stringify(value)) as T
  } catch {
    return value
  }
}

class DatabaseOptimizer {
  private readonly cache = new Map<string, CachedQueryEntry<unknown>>()

  private totalQueries = 0

  private cacheHits = 0

  private cacheMisses = 0

  private totalResponseTime = 0

  private lastUpdated: string | null = null

  async executeOptimizedQuery<T>(
    queryFn: QueryFn<T>,
    cacheKey?: string,
    ttlMs = 30_000,
  ): Promise<T> {
    this.totalQueries += 1
    const startedAt = Date.now()

    if (cacheKey) {
      const cached = this.cache.get(cacheKey)
      if (cached && cached.expiresAt > Date.now()) {
        this.cacheHits += 1
        cached.hitCount += 1
        this.totalResponseTime += Date.now() - startedAt
        this.lastUpdated = new Date().toISOString()
        return cloneValue(cached.value as T)
      }

      this.cacheMisses += 1
    }

    const result = await queryFn()
    const responseTime = Date.now() - startedAt
    this.totalResponseTime += responseTime
    this.lastUpdated = new Date().toISOString()

    if (cacheKey) {
      this.cache.set(cacheKey, {
        value: cloneValue(result),
        expiresAt: Date.now() + Math.max(0, ttlMs),
        createdAt: Date.now(),
        hitCount: 0,
        responseTime,
      })
    }

    return result
  }

  getQueryStats(): DatabaseQueryStats {
    const hitRate = this.totalQueries > 0 ? this.cacheHits / this.totalQueries : 0
    const averageResponseTime =
      this.totalQueries > 0 ? this.totalResponseTime / this.totalQueries : 0

    return {
      totalQueries: this.totalQueries,
      cacheHits: this.cacheHits,
      cacheMisses: this.cacheMisses,
      cacheHitRate: hitRate,
      averageResponseTime,
      lastUpdated: this.lastUpdated,
    }
  }

  getCacheStats(): DatabaseCacheStats {
    const queryStats = this.getQueryStats()
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys()),
      cacheHitRate: queryStats.cacheHitRate,
      totalQueries: queryStats.totalQueries,
      cacheHits: queryStats.cacheHits,
      cacheMisses: queryStats.cacheMisses,
    }
  }

  clearCache(): void {
    this.cache.clear()
    this.totalQueries = 0
    this.cacheHits = 0
    this.cacheMisses = 0
    this.totalResponseTime = 0
    this.lastUpdated = new Date().toISOString()
  }
}

export const databaseOptimizer = new DatabaseOptimizer()
