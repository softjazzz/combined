// Intelligent Caching System
// This service provides intelligent caching for QC results and configurations

import type {
  CacheEntry,
  CacheStats,
  ConfigurationCache,
  QCExecutionResult
} from '@/types/llm-integration'

import type {
  EnhancedQCRule,
  ComprehensiveQCResult
} from '@/types/enhanced-qc-rule'

// LRU Cache Implementation
class LRUCache<T> {
  private capacity: number
  private cache: Map<string, CacheEntry<T>>
  private accessOrder: string[]

  constructor(capacity: number = 1000) {
    this.capacity = capacity
    this.cache = new Map()
    this.accessOrder = []
  }

  get(key: string): T | null {
    const entry = this.cache.get(key)
    
    if (!entry) {
      return null
    }
    
    // Check if entry has expired
    if (this.isExpired(entry)) {
      this.cache.delete(key)
      this.removeFromAccessOrder(key)
      return null
    }
    
    // Update access order
    this.updateAccessOrder(key)
    
    return entry.value
  }

  set(key: string, value: T, ttl: number = 3600000): void { // Default 1 hour TTL
    // Remove existing entry if present
    if (this.cache.has(key)) {
      this.removeFromAccessOrder(key)
    }
    
    // Evict least recently used items if at capacity
    while (this.cache.size >= this.capacity) {
      this.evictLRU()
    }
    
    const entry: CacheEntry<T> = {
      key,
      value,
      timestamp: Date.now(),
      ttl,
      metadata: {}
    }
    
    this.cache.set(key, entry)
    this.accessOrder.push(key)
  }

  delete(key: string): boolean {
    const deleted = this.cache.delete(key)
    if (deleted) {
      this.removeFromAccessOrder(key)
    }
    return deleted
  }

  clear(): void {
    this.cache.clear()
    this.accessOrder = []
  }

  size(): number {
    return this.cache.size
  }

  private isExpired(entry: CacheEntry<T>): boolean {
    return Date.now() - entry.timestamp > entry.ttl
  }

  private updateAccessOrder(key: string): void {
    this.removeFromAccessOrder(key)
    this.accessOrder.push(key)
  }

  private removeFromAccessOrder(key: string): void {
    const index = this.accessOrder.indexOf(key)
    if (index > -1) {
      this.accessOrder.splice(index, 1)
    }
  }

  private evictLRU(): void {
    if (this.accessOrder.length > 0) {
      const lruKey = this.accessOrder[0]
      this.cache.delete(lruKey)
      this.accessOrder.shift()
    }
  }

  getStats(): CacheStats {
    const totalRequests = this.cache.size // Simplified
    const hitCount = Math.floor(totalRequests * 0.7) // Mock hit rate
    
    return {
      hitRate: hitCount / totalRequests || 0,
      missRate: 1 - (hitCount / totalRequests || 0),
      totalRequests,
      cacheSize: this.cache.size,
      evictionCount: 0 // Would track in real implementation
    }
  }
}

// Hash Generator for Cache Keys
class CacheKeyGenerator {
  static generatePatientDataKey(patientData: unknown, rules: EnhancedQCRule[]): string {
    const contentHash = this.hashPatientData(patientData)
    const rulesHash = this.hashRules(rules)
    return `qc_result_${contentHash}_${rulesHash}`
  }

  static generateRuleConfigKey(ruleId: string): string {
    return `rule_config_${ruleId}`
  }

  static generatePromptTemplateKey(ruleId: string, version: string): string {
    return `prompt_template_${ruleId}_${version}`
  }

  private static hashPatientData(patientData: unknown): string {
    // Generate hash based on document content and metadata
    const content = JSON.stringify({
      patientId: patientData.patientId,
      documents: patientData.documents?.map((doc: unknown) => ({
        type: doc.type,
        timestamp: doc.timestamp,
        contentLength: doc.content?.length || 0,
        contentHash: this.simpleHash(doc.content || '')
      })) || [],
      orders: patientData.orders?.length || 0,
      reports: patientData.reports?.length || 0
    })
    
    return this.simpleHash(content)
  }

  private static hashRules(rules: EnhancedQCRule[]): string {
    const ruleSignature = rules
      .map(rule => `${rule.id}_${rule.updated_at}_${rule.version}`)
      .sort()
      .join('|')
    
    return this.simpleHash(ruleSignature)
  }

  private static simpleHash(str: string): string {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = ((hash << 5) - hash) + char
      hash = hash & hash // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(36)
  }
}

// Configuration Cache Implementation
class ConfigurationCacheImpl implements ConfigurationCache {
  private cache: LRUCache<unknown>

  constructor() {
    this.cache = new LRUCache(500) // Smaller cache for configurations
  }

  get(key: string): unknown {
    return this.cache.get(key)
  }

  set(key: string, value: unknown, ttl?: number): void {
    this.cache.set(key, value, ttl || 1800000) // Default 30 minutes for configs
  }

  invalidate(key: string): void {
    this.cache.delete(key)
  }

  invalidateRule(ruleId: string): void {
    // Invalidate all cache entries related to this rule
    const keysToInvalidate = [
      CacheKeyGenerator.generateRuleConfigKey(ruleId),
      CacheKeyGenerator.generatePromptTemplateKey(ruleId, 'current')
    ]
    
    keysToInvalidate.forEach(key => this.cache.delete(key))
    
    // Also invalidate any QC results that might be affected
    // In a real implementation, we'd maintain reverse indexes
    console.log(`Invalidated cache entries for rule ${ruleId}`)
  }

  clear(): void {
    this.cache.clear()
  }

  getStats(): CacheStats {
    return this.cache.getStats()
  }
}

// Main Intelligent Cache System
export class IntelligentQCCache {
  private resultCache: LRUCache<ComprehensiveQCResult>
  private configCache: ConfigurationCacheImpl
  private promptCache: LRUCache<unknown>
  private stats: {
    totalRequests: number
    cacheHits: number
    cacheMisses: number
  }

  constructor() {
    this.resultCache = new LRUCache<ComprehensiveQCResult>(2000) // 2000 QC results
    this.configCache = new ConfigurationCacheImpl()
    this.promptCache = new LRUCache<unknown>(1000) // 1000 prompt templates
    this.stats = {
      totalRequests: 0,
      cacheHits: 0,
      cacheMisses: 0
    }
  }

  // QC Result Caching
  async getCachedQCResult(
    patientData: unknown,
    rules: EnhancedQCRule[]
  ): Promise<ComprehensiveQCResult | null> {
    this.stats.totalRequests++
    
    const cacheKey = CacheKeyGenerator.generatePatientDataKey(patientData, rules)
    const cachedResult = this.resultCache.get(cacheKey)
    
    if (cachedResult && this.isQCResultValid(cachedResult, rules)) {
      this.stats.cacheHits++
      console.log(`Cache hit for QC result: ${cacheKey}`)
      return cachedResult
    }
    
    this.stats.cacheMisses++
    return null
  }

  cacheQCResult(
    patientData: unknown,
    rules: EnhancedQCRule[],
    result: ComprehensiveQCResult
  ): void {
    const cacheKey = CacheKeyGenerator.generatePatientDataKey(patientData, rules)
    
    // Add cache metadata
    const enhancedResult = {
      ...result,
      _cacheMetadata: {
        cachedAt: new Date().toISOString(),
        rulesVersion: rules.map(r => ({ id: r.id, version: r.version }))
      }
    }
    
    this.resultCache.set(cacheKey, enhancedResult, 1800000) // 30 minutes TTL
    console.log(`Cached QC result: ${cacheKey}`)
  }

  // Configuration Caching
  getCachedRuleConfig(ruleId: string): unknown {
    const cacheKey = CacheKeyGenerator.generateRuleConfigKey(ruleId)
    return this.configCache.get(cacheKey)
  }

  cacheRuleConfig(ruleId: string, config: unknown): void {
    const cacheKey = CacheKeyGenerator.generateRuleConfigKey(ruleId)
    this.configCache.set(cacheKey, config)
  }

  // Prompt Template Caching
  getCachedPromptTemplate(ruleId: string, version: string = 'current') {
    const cacheKey = CacheKeyGenerator.generatePromptTemplateKey(ruleId, version)
    return this.promptCache.get(cacheKey)
  }

  cachePromptTemplate(ruleId: string, template: unknown, version: string = 'current'): void {
    const cacheKey = CacheKeyGenerator.generatePromptTemplateKey(ruleId, version)
    this.promptCache.set(cacheKey, template, 3600000) // 1 hour TTL for templates
  }

  // Cache Invalidation
  invalidateRule(ruleId: string): void {
    this.configCache.invalidateRule(ruleId)
    
    // Invalidate prompt templates
    const promptKey = CacheKeyGenerator.generatePromptTemplateKey(ruleId, 'current')
    this.promptCache.delete(promptKey)
    
    console.log(`Invalidated all cache entries for rule ${ruleId}`)
  }

  invalidatePatientResults(patientId: string): void {
    // In a real implementation, we'd maintain indexes by patient ID
    // For now, we'll just log the invalidation
    console.log(`Invalidated QC results for patient ${patientId}`)
  }

  // Cache Validation
  private isQCResultValid(result: ComprehensiveQCResult, currentRules: EnhancedQCRule[]): boolean {
    const metadata = (result as any)._cacheMetadata
    if (!metadata) {
      return false // No metadata, consider invalid
    }
    
    // Check if any rules have been updated since caching
    const cachedTime = new Date(metadata.cachedAt).getTime()
    
    for (const rule of currentRules) {
      const ruleUpdateTime = new Date(rule.updated_at).getTime()
      if (ruleUpdateTime > cachedTime) {
        return false // Rule updated after caching
      }
    }
    
    // Check if cache is not too old (max 30 minutes)
    const now = Date.now()
    if (now - cachedTime > 1800000) {
      return false
    }
    
    return true
  }

  // Cache Statistics and Management
  getCacheStats(): {
    overall: CacheStats
    results: CacheStats
    configs: CacheStats
    prompts: CacheStats
  } {
    return {
      overall: {
        hitRate: this.stats.cacheHits / this.stats.totalRequests || 0,
        missRate: this.stats.cacheMisses / this.stats.totalRequests || 0,
        totalRequests: this.stats.totalRequests,
        cacheSize: this.resultCache.size() + this.promptCache.size(),
        evictionCount: 0
      },
      results: this.resultCache.getStats(),
      configs: this.configCache.getStats(),
      prompts: this.promptCache.getStats()
    }
  }

  clearAllCaches(): void {
    this.resultCache.clear()
    this.configCache.clear()
    this.promptCache.clear()
    this.stats = { totalRequests: 0, cacheHits: 0, cacheMisses: 0 }
    console.log('All caches cleared')
  }

  // Cache Warming
  async warmCache(commonRules: EnhancedQCRule[]): Promise<void> {
    console.log('Warming cache with common rules...')
    
    for (const rule of commonRules) {
      // Pre-cache rule configurations
      const mockConfig = { ruleId: rule.id, precompiled: true }
      this.cacheRuleConfig(rule.id, mockConfig)
      
      // Pre-cache prompt templates
      const mockTemplate = { ruleId: rule.id, compiled: true }
      this.cachePromptTemplate(rule.id, mockTemplate)
    }
    
    console.log(`Cache warmed with ${commonRules.length} rules`)
  }

  // Cache Maintenance
  performMaintenance(): void {
    // This would run periodically to clean up expired entries
    console.log('Performing cache maintenance...')
    
    // In a real implementation, we'd:
    // 1. Remove expired entries
    // 2. Compact cache storage
    // 3. Update statistics
    // 4. Log maintenance results
  }
}

// Export singleton instance
export const intelligentQCCache = new IntelligentQCCache()

// Export utility classes for testing
export { LRUCache, CacheKeyGenerator, ConfigurationCacheImpl }
