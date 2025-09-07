#!/usr/bin/env tsx

/**
 * Augment工作规则检查工具
 * 
 * 此脚本用于检查代码是否遵循Augment工作规则
 * 包括代码质量、命名规范、文档完整性等检查
 */

import { readFileSync, readdirSync, statSync } from 'fs'
import { join, extname, basename } from 'path'

// 检查结果接口
interface CheckResult {
  file: string
  rule: string
  level: 'error' | 'warning' | 'info'
  message: string
  line?: number
}

// 检查器类
class WorkRulesChecker {
  private results: CheckResult[] = []
  private projectRoot: string

  constructor(projectRoot: string) {
    this.projectRoot = projectRoot
  }

  /**
   * 执行所有检查
   */
  async checkAll(): Promise<CheckResult[]> {
    console.log('🔍 开始执行Augment工作规则检查...\n')
    
    this.results = []
    
    // 检查项目结构
    this.checkProjectStructure()
    
    // 检查Vue组件
    this.checkVueComponents()
    
    // 检查TypeScript文件
    this.checkTypeScriptFiles()
    
    // 检查服务层文件
    this.checkServiceFiles()
    
    // 检查配置文件
    this.checkConfigFiles()
    
    // 检查文档文件
    this.checkDocumentationFiles()
    
    return this.results
  }

  /**
   * 添加检查结果
   */
  private addResult(file: string, rule: string, level: 'error' | 'warning' | 'info', message: string, line?: number) {
    this.results.push({ file, rule, level, message, line })
  }

  /**
   * 检查项目结构
   */
  private checkProjectStructure() {
    console.log('📁 检查项目结构...')
    
    const requiredDirs = [
      'src/views/rules',
      'src/services',
      'src/utils',
      'src/config',
      'src/types',
      'docs',
      'scripts'
    ]
    
    for (const dir of requiredDirs) {
      const fullPath = join(this.projectRoot, dir)
      try {
        const stat = statSync(fullPath)
        if (!stat.isDirectory()) {
          this.addResult(dir, 'project-structure', 'error', `必需目录不存在: ${dir}`)
        }
      } catch (error) {
        this.addResult(dir, 'project-structure', 'error', `必需目录不存在: ${dir}`)
      }
    }
  }

  /**
   * 检查Vue组件
   */
  private checkVueComponents() {
    console.log('🎨 检查Vue组件...')
    
    const vueFiles = this.findFiles('src', '.vue')
    
    for (const file of vueFiles) {
      this.checkVueFile(file)
    }
  }

  /**
   * 检查单个Vue文件
   */
  private checkVueFile(filePath: string) {
    try {
      const content = readFileSync(filePath, 'utf-8')
      const lines = content.split('\n')
      
      // 检查是否使用Composition API
      if (!content.includes('<script setup lang="ts">')) {
        this.addResult(filePath, 'vue-composition-api', 'warning', 'Vue组件应使用Composition API和TypeScript')
      }
      
      // 检查是否有适当的样式作用域
      if (content.includes('<style>') && !content.includes('<style scoped>')) {
        this.addResult(filePath, 'vue-scoped-styles', 'warning', '样式应使用scoped作用域')
      }
      
      // 检查组件命名
      const fileName = basename(filePath, '.vue')
      if (!/^[A-Z][a-zA-Z]*View$|^[A-Z][a-zA-Z]*Component$/.test(fileName)) {
        this.addResult(filePath, 'vue-naming', 'warning', 'Vue组件应使用PascalCase命名，以View或Component结尾')
      }
      
      // 检查是否有错误处理
      if (content.includes('await ') && !content.includes('try {')) {
        this.addResult(filePath, 'error-handling', 'warning', '异步操作应包含错误处理')
      }
      
    } catch (error) {
      this.addResult(filePath, 'file-read', 'error', `无法读取文件: ${error}`)
    }
  }

  /**
   * 检查TypeScript文件
   */
  private checkTypeScriptFiles() {
    console.log('📝 检查TypeScript文件...')
    
    const tsFiles = this.findFiles('src', '.ts')
    
    for (const file of tsFiles) {
      this.checkTypeScriptFile(file)
    }
  }

  /**
   * 检查单个TypeScript文件
   */
  private checkTypeScriptFile(filePath: string) {
    try {
      const content = readFileSync(filePath, 'utf-8')
      const lines = content.split('\n')
      
      // 检查文件头注释
      if (!content.startsWith('/**') && !content.startsWith('//')) {
        this.addResult(filePath, 'file-header', 'info', '建议添加文件头注释说明文件用途')
      }
      
      // 检查函数注释
      const functionRegex = /^\s*(export\s+)?(async\s+)?function\s+\w+|^\s*(static\s+)?(async\s+)?\w+\s*\(/gm
      let match
      while ((match = functionRegex.exec(content)) !== null) {
        const lineNumber = content.substring(0, match.index).split('\n').length
        const prevLines = lines.slice(Math.max(0, lineNumber - 3), lineNumber - 1)
        const hasComment = prevLines.some(line => line.trim().startsWith('/**') || line.trim().startsWith('//'))
        
        if (!hasComment) {
          this.addResult(filePath, 'function-comments', 'info', '公共函数建议添加注释', lineNumber)
        }
      }
      
      // 检查错误处理
      if (content.includes('await ') && !content.includes('try {') && !content.includes('catch')) {
        this.addResult(filePath, 'error-handling', 'warning', '异步操作应包含错误处理')
      }
      
    } catch (error) {
      this.addResult(filePath, 'file-read', 'error', `无法读取文件: ${error}`)
    }
  }

  /**
   * 检查服务层文件
   */
  private checkServiceFiles() {
    console.log('🔧 检查服务层文件...')
    
    const serviceFiles = this.findFiles('src/services', '.ts')
    
    for (const file of serviceFiles) {
      this.checkServiceFile(file)
    }
  }

  /**
   * 检查单个服务文件
   */
  private checkServiceFile(filePath: string) {
    try {
      const content = readFileSync(filePath, 'utf-8')
      
      // 检查是否使用了类型定义
      if (!content.includes('import type')) {
        this.addResult(filePath, 'service-types', 'warning', '服务层应导入并使用TypeScript类型定义')
      }
      
      // 检查是否有错误处理
      if (content.includes('supabase.from') && !content.includes('if (error)')) {
        this.addResult(filePath, 'database-error-handling', 'error', '数据库操作必须包含错误处理')
      }
      
      // 检查是否使用了静态方法
      if (content.includes('class ') && !content.includes('static ')) {
        this.addResult(filePath, 'service-static-methods', 'info', '服务类建议使用静态方法')
      }
      
      // 检查命名规范
      const fileName = basename(filePath, '.ts')
      if (!fileName.endsWith('-service')) {
        this.addResult(filePath, 'service-naming', 'warning', '服务文件应以-service结尾')
      }
      
    } catch (error) {
      this.addResult(filePath, 'file-read', 'error', `无法读取文件: ${error}`)
    }
  }

  /**
   * 检查配置文件
   */
  private checkConfigFiles() {
    console.log('⚙️ 检查配置文件...')
    
    const configFiles = this.findFiles('src/config', '.ts')
    
    for (const file of configFiles) {
      this.checkConfigFile(file)
    }
  }

  /**
   * 检查单个配置文件
   */
  private checkConfigFile(filePath: string) {
    try {
      const content = readFileSync(filePath, 'utf-8')
      
      // 检查是否使用了常量导出
      if (!content.includes('export const')) {
        this.addResult(filePath, 'config-constants', 'warning', '配置文件应导出常量')
      }
      
      // 检查是否有类型定义
      if (!content.includes('as const') && !content.includes(': ')) {
        this.addResult(filePath, 'config-types', 'info', '配置对象建议添加类型定义')
      }
      
    } catch (error) {
      this.addResult(filePath, 'file-read', 'error', `无法读取文件: ${error}`)
    }
  }

  /**
   * 检查文档文件
   */
  private checkDocumentationFiles() {
    console.log('📚 检查文档文件...')
    
    const docFiles = this.findFiles('docs', '.md')
    
    // 检查必需文档
    const requiredDocs = [
      'docs/RULES_SYSTEM.md',
      'docs/AUGMENT_WORK_RULES.md',
      'docs/AUGMENT_QUICK_REFERENCE.md'
    ]
    
    for (const doc of requiredDocs) {
      const fullPath = join(this.projectRoot, doc)
      try {
        statSync(fullPath)
      } catch (error) {
        this.addResult(doc, 'required-docs', 'error', `必需文档文件不存在: ${doc}`)
      }
    }
    
    // 检查文档内容
    for (const file of docFiles) {
      this.checkDocumentationFile(file)
    }
  }

  /**
   * 检查单个文档文件
   */
  private checkDocumentationFile(filePath: string) {
    try {
      const content = readFileSync(filePath, 'utf-8')
      
      // 检查是否有标题
      if (!content.startsWith('#')) {
        this.addResult(filePath, 'doc-title', 'warning', '文档应以标题开始')
      }
      
      // 检查是否有更新日期
      if (!content.includes('更新日期') && !content.includes('最后更新')) {
        this.addResult(filePath, 'doc-date', 'info', '建议在文档中包含更新日期')
      }
      
    } catch (error) {
      this.addResult(filePath, 'file-read', 'error', `无法读取文件: ${error}`)
    }
  }

  /**
   * 查找指定扩展名的文件
   */
  private findFiles(dir: string, extension: string): string[] {
    const files: string[] = []
    const fullDir = join(this.projectRoot, dir)
    
    try {
      const items = readdirSync(fullDir)
      
      for (const item of items) {
        const fullPath = join(fullDir, item)
        const stat = statSync(fullPath)
        
        if (stat.isDirectory()) {
          // 递归查找子目录
          const subFiles = this.findFiles(join(dir, item), extension)
          files.push(...subFiles)
        } else if (extname(item) === extension) {
          files.push(fullPath)
        }
      }
    } catch (error) {
      // 目录不存在或无法访问
    }
    
    return files
  }

  /**
   * 生成检查报告
   */
  generateReport(): string {
    const errors = this.results.filter(r => r.level === 'error')
    const warnings = this.results.filter(r => r.level === 'warning')
    const infos = this.results.filter(r => r.level === 'info')
    
    let report = '\n📊 Augment工作规则检查报告\n'
    report += '='.repeat(50) + '\n\n'
    
    report += `📈 统计信息:\n`
    report += `  • 错误: ${errors.length} 个\n`
    report += `  • 警告: ${warnings.length} 个\n`
    report += `  • 建议: ${infos.length} 个\n`
    report += `  • 总计: ${this.results.length} 个问题\n\n`
    
    if (errors.length > 0) {
      report += '❌ 错误 (必须修复):\n'
      for (const error of errors) {
        report += `  • ${error.file}: ${error.message}\n`
      }
      report += '\n'
    }
    
    if (warnings.length > 0) {
      report += '⚠️  警告 (建议修复):\n'
      for (const warning of warnings) {
        report += `  • ${warning.file}: ${warning.message}\n`
      }
      report += '\n'
    }
    
    if (infos.length > 0) {
      report += '💡 建议 (可选优化):\n'
      for (const info of infos) {
        report += `  • ${info.file}: ${info.message}\n`
      }
      report += '\n'
    }
    
    // 质量评分
    const totalChecks = this.results.length || 1
    const score = Math.max(0, 100 - (errors.length * 10 + warnings.length * 5 + infos.length * 1))
    
    report += `🎯 代码质量评分: ${score}/100\n`
    
    if (score >= 90) {
      report += '✅ 优秀！代码质量很高，符合Augment工作规则。\n'
    } else if (score >= 70) {
      report += '👍 良好！代码质量不错，建议修复警告项。\n'
    } else if (score >= 50) {
      report += '⚠️  一般！需要修复错误和警告项。\n'
    } else {
      report += '❌ 需要改进！存在较多问题，请认真修复。\n'
    }
    
    return report
  }
}

/**
 * 主函数
 */
async function main() {
  const projectRoot = process.cwd()
  const checker = new WorkRulesChecker(projectRoot)
  
  try {
    await checker.checkAll()
    const report = checker.generateReport()
    console.log(report)
    
    // 如果有错误，退出码为1
    const errors = checker.results.filter(r => r.level === 'error')
    if (errors.length > 0) {
      process.exit(1)
    }
    
  } catch (error) {
    console.error('❌ 检查过程中发生错误:', error)
    process.exit(1)
  }
}

// 如果直接运行此脚本
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}

export { WorkRulesChecker }
