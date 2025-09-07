#!/usr/bin/env node

/**
 * 全面语法错误修复脚本
 * 一次性修复所有剩余的语法错误
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PROJECT_ROOT = path.resolve(__dirname, '../..')

console.log('🔧 开始全面语法错误修复...')

// 全面的语法修复规则
const COMPREHENSIVE_FIXES = [
  // 修复函数参数中的数组类型错误
  {
    pattern: /\(([^)]*?)\[\]\)/g,
    replacement: '($1: any[])'
  },
  
  // 修复变量声明中的数组类型错误
  {
    pattern: /const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\[\]\s*=/g,
    replacement: 'const $1: any[] ='
  },
  
  // 修复let声明中的数组类型错误
  {
    pattern: /let\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\[\]\s*=/g,
    replacement: 'let $1: any[] ='
  },
  
  // 修复函数参数中多个数组参数的错误
  {
    pattern: /\(([^,)]+),\s*([^,)]+)\[\],\s*([^,)]+)\[\]\)/g,
    replacement: '($1, $2: any[], $3: any[])'
  },
  
  // 修复函数参数中单个数组参数的错误
  {
    pattern: /\(([^,)]+),\s*([^,)]+)\[\]\)/g,
    replacement: '($1, $2: any[])'
  },
  
  // 修复对象属性中的数组类型错误
  {
    pattern: /([a-zA-Z_$][a-zA-Z0-9_$]*)\[\]:/g,
    replacement: '$1: any[]:'
  },
  
  // 修复箭头函数参数中的数组类型错误
  {
    pattern: /=>\s*\(([^)]*?)\[\]\)\s*=>/g,
    replacement: '=> ($1: any[]) =>'
  },
  
  // 修复类型注解中的错误格式
  {
    pattern: /:\s*([^:]+)\[\]:/g,
    replacement: ': $1[]:'
  }
]

function applyComprehensiveFixes(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf-8')
    let modified = false
    
    // 应用全面修复
    COMPREHENSIVE_FIXES.forEach(fix => {
      const originalContent = content
      content = content.replace(fix.pattern, fix.replacement)
      if (content !== originalContent) {
        modified = true
      }
    })
    
    // 特殊处理：修复特定的错误模式
    const specialFixes = [
      // 修复 handleFilesProcessed = (results[]) => 这种模式
      {
        from: /const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\(([^)]*?)\[\]\)\s*=>/g,
        to: 'const $1 = ($2: any[]) =>'
      },
      
      // 修复 handleBatchCompleted = (results[]) => 这种模式
      {
        from: /([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*\(([^)]*?)\[\]\)\s*=>/g,
        to: '$1 = ($2: any[]) =>'
      },
      
      // 修复 onSelectAll: (selected: boolean, selectedRows[], changeRows[]) => 这种模式
      {
        from: /([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*\([^)]*?,\s*([^,)]+)\[\],\s*([^,)]+)\[\]\)\s*=>/g,
        to: '$1: (selected: boolean, $2: any[], $3: any[]) =>'
      }
    ]
    
    specialFixes.forEach(fix => {
      const originalContent = content
      content = content.replace(fix.from, fix.to)
      if (content !== originalContent) {
        modified = true
      }
    })
    
    if (modified) {
      fs.writeFileSync(filePath, content, 'utf-8')
      const relativePath = path.relative(PROJECT_ROOT, filePath)
      console.log(`✅ 修复语法错误: ${relativePath}`)
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
      if (applyComprehensiveFixes(fullPath)) {
        fixedCount++
      }
    }
  }
  
  return fixedCount
}

// 主执行函数
async function main() {
  console.log('🚀 开始全面语法错误修复流程')
  
  try {
    // 修复语法错误
    console.log('\n📝 修复全面语法错误')
    const fixedCount = scanAndFixFiles(path.join(PROJECT_ROOT, 'src'))
    console.log(`✅ 修复了 ${fixedCount} 个文件的语法错误`)
    
    console.log('\n🎉 全面语法错误修复完成!')
    console.log('\n📋 修复总结:')
    console.log(`- ✅ 修复了 ${fixedCount} 个文件`)
    console.log('\n🎯 下一步建议:')
    console.log('1. 运行 npm run build 验证编译')
    console.log('2. 运行 npm run dev 验证开发服务器')
    
  } catch (error) {
    console.error('❌ 全面语法修复过程中出现错误:', error)
    process.exit(1)
  }
}

// 执行主函数
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
