#!/usr/bin/env node

/**
 * ref语法错误修复脚本
 * 修复所有ref中的语法错误
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PROJECT_ROOT = path.resolve(__dirname, '../..')

console.log('🔧 开始ref语法错误修复...')

// ref语法修复规则
const REF_FIXES = [
  // 修复ref中的错误语法 ref<Type>(: any[]) -> ref<Type>([])
  {
    pattern: /ref<([^>]+)>\(:\s*any\[\]\)/g,
    replacement: 'ref<$1>([])'
  },
  
  // 修复ref中的错误语法 ref(: any[]) -> ref([])
  {
    pattern: /ref\(:\s*any\[\]\)/g,
    replacement: 'ref([])'
  },
  
  // 修复ref中的错误语法 ref<Type>(: any) -> ref<Type>(null)
  {
    pattern: /ref<([^>]+)>\(:\s*any\)/g,
    replacement: 'ref<$1>(null)'
  },
  
  // 修复ref中的错误语法 ref(: any) -> ref(null)
  {
    pattern: /ref\(:\s*any\)/g,
    replacement: 'ref(null)'
  }
]

function fixRefSyntax(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf-8')
    let modified = false
    
    // 应用ref语法修复
    REF_FIXES.forEach(fix => {
      const originalContent = content
      content = content.replace(fix.pattern, fix.replacement)
      if (content !== originalContent) {
        modified = true
      }
    })
    
    if (modified) {
      fs.writeFileSync(filePath, content, 'utf-8')
      const relativePath = path.relative(PROJECT_ROOT, filePath)
      console.log(`✅ 修复ref语法: ${relativePath}`)
      return true
    }
    
    return false
  } catch (error) {
    console.error(`❌ 修复文件失败 ${filePath}:`, error.message)
    return false
  }
}

// 扫描并修复文件
function scanAndFixFiles(dir) {
  const files = fs.readdirSync(dir)
  let fixedCount = 0
  
  for (const file of files) {
    const fullPath = path.join(dir, file)
    const stat = fs.statSync(fullPath)
    
    if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
      fixedCount += scanAndFixFiles(fullPath)
    } else if (file.endsWith('.vue') || file.endsWith('.ts')) {
      if (fixRefSyntax(fullPath)) {
        fixedCount++
      }
    }
  }
  
  return fixedCount
}

// 主执行函数
async function main() {
  console.log('🚀 开始ref语法错误修复流程')
  
  try {
    // 修复ref语法错误
    console.log('\n📝 修复ref语法错误')
    const fixedCount = scanAndFixFiles(path.join(PROJECT_ROOT, 'src'))
    console.log(`✅ 修复了 ${fixedCount} 个文件的ref语法错误`)
    
    console.log('\n🎉 ref语法错误修复完成!')
    console.log('\n📋 修复总结:')
    console.log(`- ✅ 修复了 ${fixedCount} 个文件`)
    console.log('\n🎯 下一步建议:')
    console.log('1. 运行 npm run build 验证编译')
    console.log('2. 运行 npm run dev 验证开发服务器')
    
  } catch (error) {
    console.error('❌ ref语法修复过程中出现错误:', error)
    process.exit(1)
  }
}

// 执行主函数
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
