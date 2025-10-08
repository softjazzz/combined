#!/usr/bin/env node

/**
 * 处理剩余的 any 类型 - 第三阶段
 * 
 * 处理组件 props、emits 和类型定义中的 any
 */

const fs = require('fs');
const path = require('path');

// 通用替换规则
const GENERIC_REPLACEMENTS = [
  // 组件 props 和 emits
  { pattern: /: \[(\w+): any\]/g, replacement: ': [$1: unknown]', description: 'emit 参数' },
  { pattern: /\[(\w+): any\]/g, replacement: '[$1: unknown]', description: 'emit 参数（无冒号）' },
  
  // 对象属性
  { pattern: /(\w+)\?: any(?=\s*$)/gm, replacement: '$1?: Record<string, unknown>', description: '可选对象属性' },
  { pattern: /(\w+): any(?=\s*$)/gm, replacement: '$1: Record<string, unknown>', description: '必需对象属性' },
  
  // icon 类型（Ant Design Vue）
  { pattern: /icon\?: any/g, replacement: 'icon?: unknown', description: 'icon 属性' },
  
  // 函数返回值
  { pattern: /\): any \{/g, replacement: '): unknown {', description: '函数返回值' },
];

// 特定文件的精确替换
const FILE_SPECIFIC_REPLACEMENTS = {
  'services/audit-task-service-adapter.ts': [
    { from: '    stats: any', to: '    stats: Record<string, unknown>' },
  ],
  'services/ai-assistance-adapter.ts': [
    { from: '    performance_stats: any', to: '    performance_stats: Record<string, unknown>' },
  ],
  'services/supabaseMedicalRecordService.ts': [
    { from: '  extraction_result: any', to: '  extraction_result: Record<string, unknown>' },
  ],
  'services/database/documentClassificationAdapter.ts': [
    { from: '  position_info: any', to: '  position_info: Record<string, unknown>' },
    { from: '  metadata: any', to: '  metadata: Record<string, unknown>' },
    { from: 'getClassificationStats(documents: MedicalDocumentRecord[]): any', to: 'getClassificationStats(documents: MedicalDocumentRecord[]): Record<string, unknown>' },
  ],
  'api/qc-analysis-api.ts': [
    { from: '  details?: any ', to: '  details?: Record<string, unknown> ' },
  ],
  'api/qc-analysis-optimized.ts': [
    { from: '  analysis: any', to: '  analysis: Record<string, unknown>' },
    { from: '  database: any', to: '  database: Record<string, unknown>' },
    { from: '  cache: any', to: '  cache: Record<string, unknown>' },
  ],
  'components/demo/QCRulesDemoPanel.vue': [
    { from: '  testRecord: any', to: '  testRecord: Record<string, unknown>' },
  ],
  'components/BatchFileProcessor.vue': [
    { from: '  result?: any', to: '  result?: Record<string, unknown>' },
  ],
  'components/FilterModal.vue': [
    { from: '  currentConditions?: any', to: '  currentConditions?: Record<string, unknown>' },
  ],
  'components/SemanticRulesManager.vue': [
    { from: '  title: any', to: '  title: string' },
  ],
  'components/common/BatchProgressMonitor.vue': [
    { from: '  error_details?: any', to: '  error_details?: Record<string, unknown>' },
    { from: '  metadata?: any', to: '  metadata?: Record<string, unknown>' },
  ],
  'components/LLMResultModal.vue': [
    { from: '  data: any', to: '  data: Record<string, unknown>' },
    { from: '  result: any', to: '  result: Record<string, unknown>' },
  ],
  'stores/llmParse.ts': [
    { from: '  lastResult: any | null', to: '  lastResult: unknown | null' },
  ],
  'utils/api-wrapper.ts': [
    { from: '    details?: any', to: '    details?: Record<string, unknown>' },
  ],
  'utils/classificationTester.ts': [
    { from: '  details?: any', to: '  details?: Record<string, unknown>' },
    { from: 'generateTestReport(results: TestResult[]): any', to: 'generateTestReport(results: TestResult[]): Record<string, unknown>' },
  ],
  'composables/useBatchUpload.ts': [
    { from: '  error_details?: any', to: '  error_details?: Record<string, unknown>' },
  ],
  'composables/useBatchMonitor.ts': [
    { from: '  error_details?: any', to: '  error_details?: Record<string, unknown>' },
    { from: '  metadata?: any', to: '  metadata?: Record<string, unknown>' },
  ],
  'composables/useRealTimeQC.ts': [
    { from: '  analysisResult: any', to: '  analysisResult: Record<string, unknown>' },
  ],
  'types/quality-control.ts': [
    { from: '  data: any', to: '  data: Record<string, unknown>' },
    { from: '  result?: any', to: '  result?: Record<string, unknown>' },
    { from: '  testRecord: any', to: '  testRecord: Record<string, unknown>' },
  ],
  'types/enhanced-qc-rule.ts': [
    { from: '  expectedOutputSchema?: any', to: '  expectedOutputSchema?: Record<string, unknown>' },
    { from: '  data: any', to: '  data: Record<string, unknown>' },
    { from: '  templateConfig: any', to: '  templateConfig: Record<string, unknown>' },
    { from: '  oldData?: any', to: '  oldData?: Record<string, unknown>' },
  ],
};

function applyGenericReplacements(content) {
  let modified = false;
  let changeCount = 0;
  
  GENERIC_REPLACEMENTS.forEach(({ pattern, replacement }) => {
    const before = content;
    content = content.replace(pattern, replacement);
    if (content !== before) {
      modified = true;
      changeCount++;
    }
  });
  
  return { content, modified, changeCount };
}

function applySpecificReplacements(content, replacements) {
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
  
  return { content, modified, changeCount };
}

function processFile(filePath, specificReplacements = []) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let totalChanges = 0;
    let modified = false;
    
    // 应用特定替换
    if (specificReplacements.length > 0) {
      const result = applySpecificReplacements(content, specificReplacements);
      content = result.content;
      modified = result.modified || modified;
      totalChanges += result.changeCount;
    }
    
    // 应用通用替换
    const genericResult = applyGenericReplacements(content);
    content = genericResult.content;
    modified = genericResult.modified || modified;
    totalChanges += genericResult.changeCount;
    
    if (modified) {
      fs.writeFileSync(filePath, content, 'utf8');
      return { modified: true, changeCount: totalChanges };
    }
    
    return { modified: false, changeCount: 0 };
  } catch (error) {
    console.error(`Error processing ${filePath}:`, error.message);
    return { modified: false, changeCount: 0, error: error.message };
  }
}

function findFiles(dir, extensions = ['.ts', '.vue']) {
  let results = [];
  
  try {
    const files = fs.readdirSync(dir);
    
    for (const file of files) {
      const filePath = path.join(dir, file);
      const stat = fs.statSync(filePath);
      
      if (stat.isDirectory()) {
        if (file !== 'node_modules' && file !== '.git' && file !== 'dist') {
          results = results.concat(findFiles(filePath, extensions));
        }
      } else {
        const ext = path.extname(file);
        if (extensions.includes(ext) && !file.endsWith('.d.ts') && !file.endsWith('.vue.ts')) {
          results.push(filePath);
        }
      }
    }
  } catch (error) {
    console.error(`Error reading directory ${dir}:`, error.message);
  }
  
  return results;
}

function main() {
  const srcDir = path.join(__dirname, '../src');
  
  console.log('🔍 处理剩余的 any 类型（第三阶段）...\n');
  
  let totalModified = 0;
  let totalChanges = 0;
  const modifiedFiles = [];
  
  // 处理有特定规则的文件
  console.log('📝 处理特定文件...\n');
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
      modifiedFiles.push({ path: relativePath, changes: result.changeCount });
      console.log(`✅ ${relativePath} (${result.changeCount} 处修改)`);
    }
  });
  
  // 处理所有其他文件（应用通用规则）
  console.log('\n📝 应用通用规则到所有文件...\n');
  const allFiles = findFiles(srcDir);
  const processedPaths = new Set(Object.keys(FILE_SPECIFIC_REPLACEMENTS).map(p => path.join(srcDir, p)));
  
  allFiles.forEach(filePath => {
    if (processedPaths.has(filePath)) return;
    
    const result = processFile(filePath, []);
    
    if (result.modified) {
      totalModified++;
      totalChanges += result.changeCount;
      const relativePath = path.relative(srcDir, filePath);
      modifiedFiles.push({ path: relativePath, changes: result.changeCount });
      console.log(`✅ ${relativePath} (${result.changeCount} 处修改)`);
    }
  });
  
  console.log('\n' + '='.repeat(80));
  console.log('📊 替换统计\n');
  console.log(`修改文件数: ${totalModified}`);
  console.log(`总替换次数: ${totalChanges}`);
  console.log('='.repeat(80) + '\n');
  
  console.log('✅ 完成！\n');
}

if (require.main === module) {
  main();
}

module.exports = { processFile };

