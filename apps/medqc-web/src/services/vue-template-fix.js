#!/usr/bin/env node

/**
 * Vue模板语法修复脚本
 * 修复Vue模板中的语法错误
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PROJECT_ROOT = path.resolve(__dirname, '../..')

console.log('🔧 开始Vue模板语法修复...')

// Vue模板语法修复规则
const VUE_TEMPLATE_FIXES = [
  // 修复v-model语法错误
  {
    pattern: /v-model:\s+value=/g,
    replacement: 'v-model:value='
  },
  
  // 修复v-bind语法错误
  {
    pattern: /:\s+([a-zA-Z-]+)=/g,
    replacement: ':$1='
  },
  
  // 修复v-on语法错误
  {
    pattern: /@\s+([a-zA-Z-]+)=/g,
    replacement: '@$1='
  },
  
  // 修复slot语法错误
  {
    pattern: /#\s+([a-zA-Z-]+)=/g,
    replacement: '#$1='
  },
  
  // 修复其他指令语法错误
  {
    pattern: /v-([a-zA-Z-]+):\s+([a-zA-Z-]+)=/g,
    replacement: 'v-$1:$2='
  }
]

function fixVueTemplates(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf-8')
    let modified = false
    
    // 应用Vue模板修复
    VUE_TEMPLATE_FIXES.forEach(fix => {
      const originalContent = content
      content = content.replace(fix.pattern, fix.replacement)
      if (content !== originalContent) {
        modified = true
      }
    })
    
    if (modified) {
      fs.writeFileSync(filePath, content, 'utf-8')
      const relativePath = path.relative(PROJECT_ROOT, filePath)
      console.log(`✅ 修复Vue模板语法: ${relativePath}`)
      return true
    }
    
    return false
  } catch (error) {
    console.error(`❌ 修复文件失败 ${filePath}:`, error.message)
    return false
  }
}

// 扫描并修复Vue文件
function scanAndFixVueFiles(dir) {
  const files = fs.readdirSync(dir)
  let fixedCount = 0
  
  for (const file of files) {
    const fullPath = path.join(dir, file)
    const stat = fs.statSync(fullPath)
    
    if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
      fixedCount += scanAndFixVueFiles(fullPath)
    } else if (file.endsWith('.vue')) {
      if (fixVueTemplates(fullPath)) {
        fixedCount++
      }
    }
  }
  
  return fixedCount
}

// 主执行函数
async function main() {
  console.log('🚀 开始Vue模板语法修复流程')
  
  try {
    // 修复Vue模板语法错误
    console.log('\n📝 修复Vue模板语法错误')
    const fixedCount = scanAndFixVueFiles(path.join(PROJECT_ROOT, 'src'))
    console.log(`✅ 修复了 ${fixedCount} 个Vue文件的模板语法错误`)
    
    console.log('\n🎉 Vue模板语法修复完成!')
    console.log('\n📋 修复总结:')
    console.log(`- ✅ 修复了 ${fixedCount} 个Vue文件`)
    console.log('\n🎯 下一步建议:')
    console.log('1. 运行 npm run build 验证编译')
    console.log('2. 运行 npm run dev 验证开发服务器')
    
  } catch (error) {
    console.error('❌ Vue模板语法修复过程中出现错误:', error)
    process.exit(1)
  }
}

// 执行主函数
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
