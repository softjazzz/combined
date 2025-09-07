#!/usr/bin/env node

/**
 * LLM服务迁移脚本
 * 自动将项目中的 llmService 导入从旧版本切换到新版本
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// 需要迁移的文件列表（相对于项目根目录）
const FILES_TO_MIGRATE = [
  // 高优先级文件
  '../views/medical-records/SmartImportSimple.vue',
  '../views/medical-records/SmartImportMedicalRecord.vue',
  '../views/medical-records/SmartImportMedicalRecordNew.vue',
  '../views/medical-records/LLMParseResultView.vue',
  '../components/LLMApiConfig.vue',
  '../components/LLMApiConfigDatabase.vue',
  '../components/LLMApiConfigStudio.vue',

  // 测试文件
  '../views/test/SimpleLLMTest.vue',
  '../views/test/LLMConfigTest.vue',

  // 服务文件
  'llmApiConfig.ts',
  'qc-execution-orchestrator.ts',

  // 工具文件
  '../utils/documentTypeUtils.ts',
  '../views/settings/SettingsView.vue'
]

// 迁移规则
const MIGRATION_RULES = [
  // 导入语句替换
  {
    pattern: /import\s+{\s*llmService\s*}\s+from\s+['"]@\/services\/llmService['"]/g,
    replacement: "import { llmService } from '@/services/llmServiceNew'"
  },
  {
    pattern: /import\s+{\s*LLMService\s*}\s+from\s+['"]@\/services\/llmService['"]/g,
    replacement: "import { LLMService } from '@/services/llmServiceNew'"
  },
  {
    pattern: /from\s+['"]@\/services\/llmService['"]/g,
    replacement: "from '@/services/llmServiceNew'"
  },
  
  // 动态导入替换
  {
    pattern: /import\(['"]@\/services\/llmService['"]\)/g,
    replacement: "import('@/services/llmServiceNew')"
  },
  
  // 类型导入替换
  {
    pattern: /import\s+type\s+{\s*([^}]+)\s*}\s+from\s+['"]@\/services\/llmService['"]/g,
    replacement: "import type { $1 } from '@/types/medical'"
  }
]

// 备份文件
function backupFile(filePath) {
  const backupPath = filePath + '.backup'
  if (!fs.existsSync(backupPath)) {
    fs.copyFileSync(filePath, backupPath)
    console.log(`📁 已备份: ${filePath}`)
  }
}

// 恢复文件
function restoreFile(filePath) {
  const backupPath = filePath + '.backup'
  if (fs.existsSync(backupPath)) {
    fs.copyFileSync(backupPath, filePath)
    fs.unlinkSync(backupPath)
    console.log(`🔄 已恢复: ${filePath}`)
  }
}

// 应用迁移规则
function migrateFile(filePath) {
  if (!fs.existsSync(filePath)) {
    console.log(`⚠️  文件不存在: ${filePath}`)
    return false
  }

  // 备份原文件
  backupFile(filePath)

  // 读取文件内容
  let content = fs.readFileSync(filePath, 'utf8')
  let modified = false

  // 应用迁移规则
  MIGRATION_RULES.forEach(rule => {
    const originalContent = content
    content = content.replace(rule.pattern, rule.replacement)
    if (content !== originalContent) {
      modified = true
    }
  })

  if (modified) {
    // 写入修改后的内容
    fs.writeFileSync(filePath, content, 'utf8')
    console.log(`✅ 已迁移: ${filePath}`)
    return true
  } else {
    console.log(`➡️  无需修改: ${filePath}`)
    return false
  }
}

// 验证迁移结果
function validateMigration(filePath) {
  if (!fs.existsSync(filePath)) {
    return false
  }

  const content = fs.readFileSync(filePath, 'utf8')
  
  // 检查是否还有旧的导入语句
  const oldImportPattern = /@\/services\/llmService['"]/
  if (oldImportPattern.test(content)) {
    console.log(`❌ 验证失败: ${filePath} 仍包含旧的导入语句`)
    return false
  }

  console.log(`✅ 验证通过: ${filePath}`)
  return true
}

// 主迁移函数
function runMigration() {
  console.log('🚀 开始LLM服务迁移...\n')
  
  let successCount = 0
  let failureCount = 0
  const failedFiles = []

  FILES_TO_MIGRATE.forEach(relativePath => {
    const fullPath = path.resolve(process.cwd(), relativePath)
    
    try {
      const migrated = migrateFile(fullPath)
      if (migrated) {
        // 验证迁移结果
        if (validateMigration(fullPath)) {
          successCount++
        } else {
          failureCount++
          failedFiles.push(relativePath)
        }
      }
    } catch (error) {
      console.error(`❌ 迁移失败: ${relativePath}`, error.message)
      failureCount++
      failedFiles.push(relativePath)
    }
  })

  console.log('\n📊 迁移结果统计:')
  console.log(`✅ 成功: ${successCount} 个文件`)
  console.log(`❌ 失败: ${failureCount} 个文件`)
  
  if (failedFiles.length > 0) {
    console.log('\n❌ 失败的文件:')
    failedFiles.forEach(file => console.log(`  - ${file}`))
  }

  console.log('\n🎉 迁移完成!')
  console.log('\n📝 后续步骤:')
  console.log('1. 检查迁移后的文件是否正常工作')
  console.log('2. 运行测试确保功能正常')
  console.log('3. 如有问题，可使用 --rollback 参数回滚')
}

// 回滚函数
function rollbackMigration() {
  console.log('🔄 开始回滚迁移...\n')
  
  let rollbackCount = 0

  FILES_TO_MIGRATE.forEach(relativePath => {
    const fullPath = path.resolve(process.cwd(), relativePath)
    const backupPath = fullPath + '.backup'
    
    if (fs.existsSync(backupPath)) {
      try {
        restoreFile(fullPath)
        rollbackCount++
      } catch (error) {
        console.error(`❌ 回滚失败: ${relativePath}`, error.message)
      }
    }
  })

  console.log(`\n✅ 已回滚 ${rollbackCount} 个文件`)
  console.log('🎉 回滚完成!')
}

// 清理备份文件
function cleanupBackups() {
  console.log('🧹 清理备份文件...\n')
  
  let cleanupCount = 0

  FILES_TO_MIGRATE.forEach(relativePath => {
    const fullPath = path.resolve(process.cwd(), relativePath)
    const backupPath = fullPath + '.backup'
    
    if (fs.existsSync(backupPath)) {
      try {
        fs.unlinkSync(backupPath)
        console.log(`🗑️  已删除备份: ${backupPath}`)
        cleanupCount++
      } catch (error) {
        console.error(`❌ 删除失败: ${backupPath}`, error.message)
      }
    }
  })

  console.log(`\n✅ 已清理 ${cleanupCount} 个备份文件`)
}

// 命令行参数处理
const args = process.argv.slice(2)

if (args.includes('--rollback')) {
  rollbackMigration()
} else if (args.includes('--cleanup')) {
  cleanupBackups()
} else if (args.includes('--help')) {
  console.log(`
LLM服务迁移脚本

用法:
  node migration-script.js          # 执行迁移
  node migration-script.js --rollback   # 回滚迁移
  node migration-script.js --cleanup    # 清理备份文件
  node migration-script.js --help       # 显示帮助

说明:
  该脚本会自动将项目中的 llmService 导入从旧版本切换到新版本。
  迁移前会自动备份原文件，如有问题可以回滚。
`)
} else {
  runMigration()
}
