# 质控引擎优化实施计划

## 📋 基于 GPT-5 方案的改进建议

### 🎯 **短期优化（2周内）**

#### 1. 执行器内核重构
```typescript
// packages/rule-engine/src/core/executor.ts
export class QCRuleExecutor {
  private cache: LRUCache<string, CompiledRule>
  private metrics: MetricsCollector
  
  async evaluate(context: QCContext, rules: Rule[]): Promise<QCResult> {
    const traceId = generateTraceId()
    const startTime = Date.now()
    
    try {
      // 1. 规则预筛选（按事件类型、启用状态）
      const applicableRules = this.filterApplicableRules(rules, context.event)
      
      // 2. 并行执行规则
      const results = await Promise.allSettled(
        applicableRules.map(rule => this.executeRule(rule, context))
      )
      
      // 3. 聚合结果
      return this.aggregateResults(results, traceId)
    } finally {
      this.metrics.recordExecution(Date.now() - startTime, traceId)
    }
  }
  
  private async executeRule(rule: Rule, context: QCContext): Promise<RuleResult> {
    const compiled = this.getCompiledRule(rule)
    return compiled.evaluate(context)
  }
}
```

#### 2. Edge Function 增强
```typescript
// apps/edge-functions/evaluate-rule/index.ts
export default async function handler(req: Request): Promise<Response> {
  const { event, context, options = {} } = await req.json()
  const traceId = req.headers.get('x-trace-id') || generateTraceId()
  
  try {
    // 1. 参数验证
    const validatedContext = validateQCContext(context)
    
    // 2. 规则加载（带缓存）
    const rules = await loadRulesWithCache(event, options.version)
    
    // 3. 执行评估
    const executor = new QCRuleExecutor()
    const result = await executor.evaluate(validatedContext, rules)
    
    // 4. 可选持久化
    if (options.record) {
      await recordExecution(traceId, context, result)
    }
    
    return new Response(JSON.stringify({
      success: true,
      data: result,
      traceId,
      timestamp: new Date().toISOString()
    }), {
      headers: { 'Content-Type': 'application/json' }
    })
  } catch (error) {
    return handleError(error, traceId)
  }
}
```

#### 3. 缓存策略实现
```typescript
// packages/rule-engine/src/cache/rule-cache.ts
export class RuleCacheManager {
  private ruleSetCache: Map<string, CachedRuleSet> = new Map()
  private compiledRuleCache: LRUCache<string, CompiledRule>
  
  async getRuleSet(event: string, version?: string): Promise<Rule[]> {
    const cacheKey = `${event}:${version || 'latest'}`
    
    if (this.ruleSetCache.has(cacheKey)) {
      const cached = this.ruleSetCache.get(cacheKey)!
      if (!this.isExpired(cached)) {
        return cached.rules
      }
    }
    
    // 从数据库加载
    const rules = await this.loadRulesFromDB(event, version)
    this.ruleSetCache.set(cacheKey, {
      rules,
      timestamp: Date.now(),
      ttl: 5 * 60 * 1000 // 5分钟
    })
    
    return rules
  }
  
  invalidateRuleSet(ruleId: string): void {
    // 规则更新时清理相关缓存
    for (const [key, cached] of this.ruleSetCache) {
      if (cached.rules.some(r => r.id === ruleId)) {
        this.ruleSetCache.delete(key)
      }
    }
  }
}
```

### 🔧 **中期优化（4周内）**

#### 1. 数据模型扩展
```sql
-- 执行记录表（分区）
CREATE TABLE yibao_executions (
  id BIGSERIAL,
  trace_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(50) NOT NULL,
  context_snapshot JSONB NOT NULL,
  rules_version VARCHAR(20),
  result_summary JSONB NOT NULL,
  duration_ms INTEGER NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 违规记录表
CREATE TABLE yibao_violations (
  id BIGSERIAL PRIMARY KEY,
  execution_id BIGINT,
  rule_id BIGINT REFERENCES yibao_rules(id),
  rule_code VARCHAR(50) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  message TEXT NOT NULL,
  evidence JSONB,
  patient_id VARCHAR(50),
  visit_id VARCHAR(50),
  department_code VARCHAR(20),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引优化
CREATE INDEX idx_violations_rule_severity ON yibao_violations(rule_id, severity);
CREATE INDEX idx_violations_patient_time ON yibao_violations(patient_id, created_at);
CREATE INDEX idx_executions_trace ON yibao_executions(trace_id);
```

#### 2. 统计与报告 API
```typescript
// apps/edge-functions/statistics/index.ts
export async function getQCStatistics(params: StatisticsParams): Promise<QCStatistics> {
  const { timeRange, department, ruleType } = params
  
  // 并行查询多个维度
  const [
    totalExecutions,
    violationsByRule,
    violationsByDepartment,
    trendData
  ] = await Promise.all([
    getTotalExecutions(timeRange),
    getViolationsByRule(timeRange, ruleType),
    getViolationsByDepartment(timeRange, department),
    getTrendData(timeRange)
  ])
  
  return {
    summary: {
      totalExecutions,
      totalViolations: violationsByRule.reduce((sum, v) => sum + v.count, 0),
      averageResponseTime: await getAverageResponseTime(timeRange)
    },
    breakdown: {
      byRule: violationsByRule,
      byDepartment: violationsByDepartment
    },
    trends: trendData
  }
}
```

### 🚀 **长期规划（8周+）**

#### 1. 智能化增强
- LLM 辅助规则生成与优化
- 异常模式自动发现
- 规则效果评估与调优建议

#### 2. 企业级特性
- 多租户支持
- 规则市场与共享
- 高可用部署方案

## 📊 **实施优先级**

### P0（立即执行）
1. 执行器内核抽象与单元测试
2. Edge Function 错误处理增强
3. 基础监控指标接入

### P1（2周内）
1. 缓存层实现
2. 执行记录持久化
3. 统计 API 基础版本

### P2（4周内）
1. 报告导出功能
2. 性能优化与压测
3. 安全加固

## 🎯 **成功指标**

- **性能**：P95 响应时间 < 120ms
- **可用性**：99.9% 正常运行时间
- **准确性**：规则命中准确率 > 95%
- **可扩展性**：支持 10k+ 规则，1000+ 并发

---

## 📝 **GPT-5 方案评审总结**

### ✅ **优势**
1. **技术选型合理**：Edge Functions + TypeScript 同构设计
2. **性能目标明确**：P95 < 120ms 的指标切实可行
3. **分阶段实施**：短中长期规划清晰，风险可控

### ⚠️ **需要改进的方面**
1. **容错机制不足**：缺少降级策略和熔断机制
2. **安全方案简单**：HIS 集成的安全设计需要加强
3. **监控体系不完整**：缺少业务指标和告警机制
4. **数据模型待完善**：版本管理和分区策略需要补充

### 🎯 **建议采纳的核心思路**
1. **执行器内核抽象**：便于测试和复用
2. **缓存分层策略**：规则集缓存 + 编译结果缓存
3. **异步持久化**：避免影响实时响应性能
4. **traceId 全链路**：便于问题排查和性能分析

### 📋 **下一步行动建议**
1. 基于本优化计划，细化技术实现方案
2. 建立开发环境和测试数据集
3. 实施 P0 优先级任务，建立基础框架
4. 制定详细的测试和验收标准

*评审完成时间：2025-01-09*
