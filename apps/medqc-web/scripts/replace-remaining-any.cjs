#!/usr/bin/env node

/**
 * 处理剩余的 any 类型 - 第二阶段
 * 
 * 针对特定模式进行更精确的替换
 */

const fs = require('fs');
const path = require('path');

// 特定文件的替换规则
const FILE_SPECIFIC_REPLACEMENTS = {
  'services/demoDataService.ts': [
    { from: 'ai_extraction_result: any', to: 'ai_extraction_result: Record<string, unknown>' },
    { from: 'check_logic: any', to: 'check_logic: Record<string, unknown>' },
  ],
  'services/llm/responseParser.ts': [
    { from: 'let data: any', to: 'let data: unknown' },
    { from: 'tryParseJsonLoose(raw: string): any', to: 'tryParseJsonLoose(raw: string): unknown' },
    { from: 'parseIndexResponse(response: unknown): any', to: 'parseIndexResponse(response: unknown): unknown' },
  ],
  'services/llm/documentClassifier.ts': [
    { from: 'let result: any', to: 'let result: unknown' },
  ],
  'services/llm/enhancedDocumentClassifier.ts': [
    { from: 'details?: any', to: 'details?: Record<string, unknown>' },
  ],
  'services/llm/configManager.ts': [
    { from: 'buildAPIRequest(prompt: string): any', to: 'buildAPIRequest(prompt: string): Record<string, unknown>' },
  ],
  'services/intelligent-cache.ts': [
    { from: 'get(key: string): any', to: 'get(key: string): unknown' },
    { from: 'getCachedRuleConfig(ruleId: string): any', to: 'getCachedRuleConfig(ruleId: string): unknown' },
  ],
  'services/llm-integrated-rules-service.ts': [
    { from: 'private createTestData(rule: EnhancedQCRule): any', to: 'private createTestData(rule: EnhancedQCRule): Record<string, unknown>' },
  ],
  'services/llmService.ts': [
    { from: 'private buildAPIRequest(prompt: string): any', to: 'private buildAPIRequest(prompt: string): Record<string, unknown>' },
    { from: 'private parseAPIResponse(data: unknown): any', to: 'private parseAPIResponse(data: unknown): unknown' },
  ],
  'services/kag-qc-service.ts': [
    { from: 'convertToLegacyFormat(kagResult: KAGQCResponse): any', to: 'convertToLegacyFormat(kagResult: KAGQCResponse): Record<string, unknown>' },
  ],
  'services/audit-task-service-adapter.ts': [
    { from: 'stats?: any', to: 'stats?: Record<string, unknown>' },
    { from: 'performance_stats: any', to: 'performance_stats: Record<string, unknown>' },
    { from: 'sampling_stats: any', to: 'sampling_stats: Record<string, unknown>' },
    { from: 'load_balancer_stats: any', to: 'load_balancer_stats: Record<string, unknown>' },
    { from: 'config: any', to: 'config: Record<string, unknown>' },
    { from: 'let result: { tasks: QCAuditTask[]; total: number; stats?: any }', to: 'let result: { tasks: QCAuditTask[]; total: number; stats?: Record<string, unknown> }' },
  ],
  'services/ai-assistance-adapter.ts': [
    { from: 'context?: any', to: 'context?: Record<string, unknown>' },
    { from: 'results_summary: any', to: 'results_summary: Record<string, unknown>' },
    { from: 'reviewer_feedback?: any', to: 'reviewer_feedback?: Record<string, unknown>' },
    { from: 'private getCachedAnalysis(cacheKey: string): any | null', to: 'private getCachedAnalysis(cacheKey: string): unknown | null' },
    { from: 'cache_stats: any', to: 'cache_stats: Record<string, unknown>' },
  ],
  'services/unified-api-client.ts': [
    { from: 'context?: any', to: 'context?: Record<string, unknown>' },
    { from: 'analysisConfig: any', to: 'analysisConfig: Record<string, unknown>' },
    { from: 'predictionConfig: any', to: 'predictionConfig: Record<string, unknown>' },
  ],
  'services/dynamic-prompt-generator.ts': [
    { from: 'private getNestedValue(obj: unknown, path: string): any', to: 'private getNestedValue(obj: unknown, path: string): unknown' },
    { from: '): any {', to: '): unknown {' },
  ],
  'services/notification-service.ts': [
    { from: 'context?: any', to: 'context?: Record<string, unknown>' },
    { from: 'private extractContentFromText(content: string, type: MessageType): any', to: 'private extractContentFromText(content: string, type: MessageType): Record<string, unknown>' },
  ],
  'services/llm-qc-demo.ts': [
    { from: 'static generateSamplePatientData(): any', to: 'static generateSamplePatientData(): Record<string, unknown>' },
  ],
  'services/llmConfigService.ts': [
    { from: 'parameters: any', to: 'parameters: Record<string, unknown>' },
    { from: 'custom_parameters: any', to: 'custom_parameters: Record<string, unknown>' },
    { from: 'custom_parameters?: any', to: 'custom_parameters?: Record<string, unknown>' },
  ],
  'services/audit-result-service.ts': [
    { from: 'template?: any', to: 'template?: Record<string, unknown>' },
    { from: 'modifications: any', to: 'modifications: Record<string, unknown>' },
  ],
  'services/integrated-qc-engine.ts': [
    { from: 'private buildDepartmentContext(rule: EnhancedQCRule, departmentId?: string): any', to: 'private buildDepartmentContext(rule: EnhancedQCRule, departmentId?: string): Record<string, unknown>' },
    { from: 'private performCrossRuleAnalysis(results: QCRuleResult[]): any', to: 'private performCrossRuleAnalysis(results: QCRuleResult[]): Record<string, unknown>' },
  ],
  'services/unified-data-service.ts': [
    { from: 'details?: any', to: 'details?: Record<string, unknown>' },
    { from: 'get(key: string): any | null', to: 'get(key: string): unknown | null' },
    { from: 'static sanitizePatientData(record, userRole: string): any', to: 'static sanitizePatientData(record: unknown, userRole: string): unknown' },
  ],
  'services/qc-execution-orchestrator.ts': [
    { from: 'private parseBatchResponse(response: string, tasks: QCTask[]): any', to: 'private parseBatchResponse(response: string, tasks: QCTask[]): unknown' },
  ],
  'services/supabaseMedicalRecordService.ts': [
    { from: 'raw_response?: any', to: 'raw_response?: Record<string, unknown>' },
  ],
  'components/medical-records/EnhancedRecordDetail.vue': [
    { from: 'delete: [record: any]', to: 'delete: [record: unknown]' },
  ],
  'components/qc/AnalysisProgress.vue': [
    { from: "'analysis-completed': [result: any]", to: "'analysis-completed': [result: unknown]" },
  ],
  'mr/components/DeleteDocumentModal.vue': [
    { from: "'success': [result: any]", to: "'success': [result: unknown]" },
  ],
};

function processFile(filePath, replacements) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let modified = false;
    let changeCount = 0;
    
    replacements.forEach(({ from, to }) => {
      const before = content;
      content = content.replace(new RegExp(from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), to);
      if (content !== before) {
        modified = true;
        changeCount++;
      }
    });
    
    if (modified) {
      fs.writeFileSync(filePath, content, 'utf8');
      return { modified: true, changeCount };
    }
    
    return { modified: false, changeCount: 0 };
  } catch (error) {
    console.error(`Error processing ${filePath}:`, error.message);
    return { modified: false, changeCount: 0, error: error.message };
  }
}

function main() {
  const srcDir = path.join(__dirname, '../src');
  
  console.log('🔍 处理剩余的 any 类型（第二阶段）...\n');
  
  let totalModified = 0;
  let totalChanges = 0;
  const modifiedFiles = [];
  
  Object.entries(FILE_SPECIFIC_REPLACEMENTS).forEach(([relativePath, replacements]) => {
    const filePath = path.join(srcDir, relativePath);
    
    if (!fs.existsSync(filePath)) {
      console.log(`⚠️  文件不存在: ${relativePath}`);
      return;
    }
    
    const result = processFile(filePath, replacements);
    
    if (result.modified) {
      totalModified++;
      totalChanges += result.changeCount;
      modifiedFiles.push({
        path: relativePath,
        changes: result.changeCount
      });
      console.log(`✅ ${relativePath} (${result.changeCount} 处修改)`);
    } else if (result.error) {
      console.log(`❌ ${relativePath} - 错误: ${result.error}`);
    }
  });
  
  console.log('\n' + '='.repeat(80));
  console.log('📊 替换统计\n');
  console.log(`总文件数: ${Object.keys(FILE_SPECIFIC_REPLACEMENTS).length}`);
  console.log(`修改文件数: ${totalModified}`);
  console.log(`总替换次数: ${totalChanges}`);
  console.log('='.repeat(80) + '\n');
  
  if (modifiedFiles.length > 0) {
    console.log('📝 修改的文件列表:\n');
    modifiedFiles.forEach(({ path, changes }) => {
      console.log(`  ${path} (${changes} 处)`);
    });
  }
  
  console.log('\n✅ 完成！\n');
  console.log('⚠️  注意: 请运行以下命令检查类型错误:');
  console.log('   pnpm exec tsc --noEmit\n');
}

if (require.main === module) {
  main();
}

module.exports = { processFile, FILE_SPECIFIC_REPLACEMENTS };

