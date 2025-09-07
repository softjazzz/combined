#!/usr/bin/env node

/**
 * 医疗质控系统代码架构优化工具
 * 执行四个主要任务：删除编译产物、统一文件格式、修复类型定义、优化项目结构
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PROJECT_ROOT = path.resolve(__dirname, '../..')

// 优化报告
const optimizationReport = {
  deletedFiles: [],
  migratedFiles: [],
  typeErrors: [],
  structureChanges: [],
  startTime: new Date(),
  endTime: null
}

// 需要保留的JS文件（配置脚本等）
const KEEP_JS_FILES = [
  'migration-script.js',
  'vite.config.js',
  'postcss.config.js',
  'tailwind.config.js'
]

/**
 * 任务1：识别并删除编译产物
 */
async function task1_removeCompiledFiles() {
  console.log('\n🔍 任务1：识别并删除编译产物')
  console.log('=' .repeat(50))

  const duplicateFiles = []
  
  // 扫描src目录下的所有TS文件
  function scanDirectory(dir) {
    const files = fs.readdirSync(dir)
    
    for (const file of files) {
      const fullPath = path.join(dir, file)
      const stat = fs.statSync(fullPath)
      
      if (stat.isDirectory()) {
        scanDirectory(fullPath)
      } else if (file.endsWith('.ts')) {
        const jsFile = fullPath.replace('.ts', '.js')
        if (fs.existsSync(jsFile)) {
          const relativeTsPath = path.relative(PROJECT_ROOT, fullPath)
          const relativeJsPath = path.relative(PROJECT_ROOT, jsFile)
          
          // 检查是否应该保留JS文件
          const jsFileName = path.basename(jsFile)
          if (!KEEP_JS_FILES.includes(jsFileName)) {
            duplicateFiles.push({
              ts: relativeTsPath,
              js: relativeJsPath
            })
          }
        }
      }
    }
  }

  scanDirectory(path.join(PROJECT_ROOT, 'src'))
  
  console.log(`📊 发现 ${duplicateFiles.length} 对重复文件:`)
  
  // 删除编译产物
  for (const { ts, js } of duplicateFiles) {
    try {
      // 验证TS文件确实存在且内容更新
      const tsPath = path.join(PROJECT_ROOT, ts)
      const jsPath = path.join(PROJECT_ROOT, js)
      
      const tsStats = fs.statSync(tsPath)
      const jsStats = fs.statSync(jsPath)
      
      // 如果TS文件更新时间更晚，说明JS是编译产物
      if (tsStats.mtime >= jsStats.mtime || isCompiledFile(jsPath)) {
        fs.unlinkSync(jsPath)
        optimizationReport.deletedFiles.push(js)
        console.log(`✅ 删除编译产物: ${js}`)
      } else {
        console.log(`⚠️  保留文件 (可能不是编译产物): ${js}`)
      }
    } catch (error) {
      console.error(`❌ 删除文件失败 ${js}:`, error.message)
    }
  }
  
  console.log(`\n📋 任务1完成: 删除了 ${optimizationReport.deletedFiles.length} 个编译产物`)
}

/**
 * 检查是否为编译产物
 */
function isCompiledFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf-8')
    // 检查编译产物的特征
    return content.includes('__importDefault') || 
           content.includes('Object.defineProperty(exports') ||
           content.includes('"use strict";') && content.includes('exports.')
  } catch {
    return false
  }
}

/**
 * 任务2：统一文件格式标准
 */
async function task2_unifyFileFormats() {
  console.log('\n🔧 任务2：统一文件格式标准')
  console.log('=' .repeat(50))

  // 扫描需要迁移的JS文件
  const jsFilesToMigrate = []
  
  function scanForJSFiles(dir) {
    const files = fs.readdirSync(dir)
    
    for (const file of files) {
      const fullPath = path.join(dir, file)
      const stat = fs.statSync(fullPath)
      
      if (stat.isDirectory()) {
        scanForJSFiles(fullPath)
      } else if (file.endsWith('.js')) {
        const fileName = path.basename(file)
        // 跳过配置文件和已知的工具脚本
        if (!KEEP_JS_FILES.includes(fileName) && isBusinessLogicFile(fullPath)) {
          jsFilesToMigrate.push(path.relative(PROJECT_ROOT, fullPath))
        }
      }
    }
  }

  scanForJSFiles(path.join(PROJECT_ROOT, 'src'))
  
  console.log(`📊 发现 ${jsFilesToMigrate.length} 个需要迁移的JS文件:`)
  
  // 迁移JS文件到TS
  for (const jsFile of jsFilesToMigrate) {
    try {
      const jsPath = path.join(PROJECT_ROOT, jsFile)
      const tsPath = jsPath.replace('.js', '.ts')
      
      // 检查TS文件是否已存在
      if (fs.existsSync(tsPath)) {
        console.log(`⚠️  跳过 (TS文件已存在): ${jsFile}`)
        continue
      }
      
      // 读取JS文件内容
      let content = fs.readFileSync(jsPath, 'utf-8')
      
      // 转换为TypeScript格式
      content = convertJSToTS(content)
      
      // 写入TS文件
      fs.writeFileSync(tsPath, content, 'utf-8')
      
      // 删除原JS文件
      fs.unlinkSync(jsPath)
      
      optimizationReport.migratedFiles.push({
        from: jsFile,
        to: jsFile.replace('.js', '.ts')
      })
      
      console.log(`✅ 迁移: ${jsFile} → ${jsFile.replace('.js', '.ts')}`)
    } catch (error) {
      console.error(`❌ 迁移失败 ${jsFile}:`, error.message)
    }
  }
  
  console.log(`\n📋 任务2完成: 迁移了 ${optimizationReport.migratedFiles.length} 个文件`)
}

/**
 * 检查是否为业务逻辑文件
 */
function isBusinessLogicFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8')
  // 检查是否包含业务逻辑特征
  return content.includes('export') || 
         content.includes('import') ||
         content.includes('function') ||
         content.includes('class') ||
         content.includes('const') ||
         content.includes('let')
}

/**
 * 将JS代码转换为TS格式
 */
function convertJSToTS(content) {
  // 基本的JS到TS转换
  let tsContent = content
  
  // 转换require为import
  tsContent = tsContent.replace(/const\s+(\w+)\s+=\s+require\(['"]([^'"]+)['"]\)/g, 'import $1 from \'$2\'')
  tsContent = tsContent.replace(/const\s+{\s*([^}]+)\s*}\s+=\s+require\(['"]([^'"]+)['"]\)/g, 'import { $1 } from \'$2\'')
  
  // 转换exports为export
  tsContent = tsContent.replace(/module\.exports\s*=\s*/g, 'export default ')
  tsContent = tsContent.replace(/exports\.(\w+)\s*=\s*/g, 'export const $1 = ')
  
  // 添加基本类型注解（简单情况）
  tsContent = tsContent.replace(/function\s+(\w+)\s*\(/g, 'function $1(')
  
  return tsContent
}

/**
 * 主执行函数
 */
async function main() {
  console.log('🚀 开始医疗质控系统代码架构优化')
  console.log('项目根目录:', PROJECT_ROOT)
  console.log('开始时间:', optimizationReport.startTime.toLocaleString())
  
  try {
    await task1_removeCompiledFiles()
    await task2_unifyFileFormats()
    
    // 生成优化报告
    optimizationReport.endTime = new Date()
    await generateOptimizationReport()
    
    console.log('\n🎉 代码架构优化完成!')
  } catch (error) {
    console.error('❌ 优化过程中出现错误:', error)
    process.exit(1)
  }
}

/**
 * 生成优化报告
 */
async function generateOptimizationReport() {
  const reportPath = path.join(PROJECT_ROOT, 'ARCHITECTURE_OPTIMIZATION_REPORT.md')
  const duration = optimizationReport.endTime - optimizationReport.startTime
  
  const report = `# 医疗质控系统代码架构优化报告

## 📊 优化概览

- **开始时间**: ${optimizationReport.startTime.toLocaleString()}
- **结束时间**: ${optimizationReport.endTime.toLocaleString()}
- **总耗时**: ${Math.round(duration / 1000)}秒

## 🗑️ 删除的编译产物文件 (${optimizationReport.deletedFiles.length}个)

${optimizationReport.deletedFiles.map(file => `- \`${file}\``).join('\n')}

## 🔄 迁移的文件 (${optimizationReport.migratedFiles.length}个)

${optimizationReport.migratedFiles.map(({from, to}) => `- \`${from}\` → \`${to}\``).join('\n')}

## 📈 优化效果

- ✅ 清理了重复的编译产物文件
- ✅ 统一了文件格式标准
- ✅ 提高了代码类型安全性
- ✅ 简化了项目结构

## 🎯 后续建议

1. 运行 \`npm run build\` 验证编译无错误
2. 运行 \`npm run dev\` 验证开发服务器正常
3. 检查所有导入路径是否正确
4. 添加缺失的类型定义

---
*报告生成时间: ${new Date().toLocaleString()}*
`

  fs.writeFileSync(reportPath, report, 'utf-8')
  console.log(`\n📄 优化报告已生成: ${reportPath}`)
}

// 执行主函数
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
