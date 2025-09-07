#!/usr/bin/env tsx

/**
 * Vue组件重命名脚本
 * 
 * 此脚本用于批量重命名Vue组件文件，使其符合命名规范
 * 规范：组件名应以View或Component结尾
 */

import { readFileSync, writeFileSync, renameSync, readdirSync, statSync } from 'fs'
import { join, dirname, basename, extname } from 'path'

interface RenameMapping {
  oldPath: string
  newPath: string
  oldName: string
  newName: string
}

class VueComponentRenamer {
  private projectRoot: string
  private renameMappings: RenameMapping[] = []

  constructor(projectRoot: string) {
    this.projectRoot = projectRoot
  }

  /**
   * 执行重命名操作
   */
  async renameComponents(): Promise<void> {
    console.log('🔄 开始Vue组件重命名...\n')
    
    // 1. 扫描所有Vue文件并生成重命名映射
    this.scanVueFiles()
    
    // 2. 显示重命名计划
    this.showRenameplan()
    
    // 3. 执行文件重命名
    this.executeFileRenames()
    
    // 4. 更新所有引用
    this.updateReferences()
    
    console.log('\n✅ Vue组件重命名完成！')
  }

  /**
   * 扫描Vue文件
   */
  private scanVueFiles(): void {
    const vueFiles = this.findVueFiles('src')
    
    for (const filePath of vueFiles) {
      const fileName = basename(filePath, '.vue')
      const dir = dirname(filePath)
      
      // 跳过已经符合规范的文件
      if (this.isValidComponentName(fileName)) {
        continue
      }
      
      const newName = this.generateNewName(fileName, dir)
      const newPath = join(dir, `${newName}.vue`)
      
      this.renameMappings.push({
        oldPath: filePath,
        newPath,
        oldName: fileName,
        newName
      })
    }
  }

  /**
   * 检查组件名是否符合规范
   */
  private isValidComponentName(name: string): boolean {
    return /^[A-Z][a-zA-Z]*(?:View|Component)$/.test(name)
  }

  /**
   * 生成新的组件名
   */
  private generateNewName(oldName: string, dir: string): string {
    // 根据目录位置决定后缀
    if (dir.includes('/views/')) {
      return oldName.endsWith('View') ? oldName : `${oldName}View`
    } else if (dir.includes('/components/')) {
      return oldName.endsWith('Component') ? oldName : `${oldName}Component`
    } else {
      // 默认使用Component后缀
      return oldName.endsWith('Component') ? oldName : `${oldName}Component`
    }
  }

  /**
   * 显示重命名计划
   */
  private showRenameplan(): void {
    if (this.renameMappings.length === 0) {
      console.log('✅ 所有Vue组件名称已符合规范！')
      return
    }

    console.log(`📋 重命名计划 (${this.renameMappings.length} 个文件):\n`)
    
    for (const mapping of this.renameMappings) {
      const relativePath = mapping.oldPath.replace(this.projectRoot + '/', '')
      console.log(`  ${mapping.oldName} → ${mapping.newName}`)
      console.log(`    ${relativePath}`)
    }
    console.log()
  }

  /**
   * 执行文件重命名
   */
  private executeFileRenames(): void {
    console.log('📁 重命名文件...')
    
    for (const mapping of this.renameMappings) {
      try {
        renameSync(mapping.oldPath, mapping.newPath)
        console.log(`  ✅ ${mapping.oldName} → ${mapping.newName}`)
      } catch (error) {
        console.error(`  ❌ 重命名失败: ${mapping.oldName} - ${error}`)
      }
    }
  }

  /**
   * 更新所有引用
   */
  private updateReferences(): void {
    console.log('\n🔗 更新组件引用...')
    
    // 需要更新引用的文件类型
    const fileExtensions = ['.vue', '.ts', '.js']
    
    for (const ext of fileExtensions) {
      const files = this.findFiles('src', ext)
      
      for (const file of files) {
        this.updateFileReferences(file)
      }
    }
  }

  /**
   * 更新单个文件中的引用
   */
  private updateFileReferences(filePath: string): void {
    try {
      let content = readFileSync(filePath, 'utf-8')
      let hasChanges = false

      for (const mapping of this.renameMappings) {
        // 更新import语句
        const importRegex = new RegExp(
          `(import\\s+\\w+\\s+from\\s+['"].*/)${mapping.oldName}(['"])`,
          'g'
        )
        if (importRegex.test(content)) {
          content = content.replace(importRegex, `$1${mapping.newName}$2`)
          hasChanges = true
        }

        // 更新组件注册
        const componentRegex = new RegExp(`\\b${mapping.oldName}\\b`, 'g')
        if (componentRegex.test(content)) {
          content = content.replace(componentRegex, mapping.newName)
          hasChanges = true
        }
      }

      if (hasChanges) {
        writeFileSync(filePath, content, 'utf-8')
        const relativePath = filePath.replace(this.projectRoot + '/', '')
        console.log(`  ✅ 更新引用: ${relativePath}`)
      }
    } catch (error) {
      console.error(`  ❌ 更新引用失败: ${filePath} - ${error}`)
    }
  }

  /**
   * 查找Vue文件
   */
  private findVueFiles(dir: string): string[] {
    return this.findFiles(dir, '.vue')
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
}

/**
 * 主函数
 */
async function main() {
  const projectRoot = process.cwd()
  const renamer = new VueComponentRenamer(projectRoot)
  
  try {
    await renamer.renameComponents()
  } catch (error) {
    console.error('❌ 重命名过程中发生错误:', error)
    process.exit(1)
  }
}

// 如果直接运行此脚本
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}

export { VueComponentRenamer }
