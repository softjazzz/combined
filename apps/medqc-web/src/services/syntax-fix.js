#!/usr/bin/env node

/**
 * 语法错误修复脚本
 * 修复类型修复脚本引入的语法错误
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PROJECT_ROOT = path.resolve(__dirname, '../..')

console.log('🔧 开始修复语法错误...')

// 语法修复规则
const SYNTAX_FIXES = [
  // 修复错误的函数参数类型注解
  {
    pattern: /\(: any\)/g,
    replacement: '()'
  },
  
  // 修复错误的箭头函数参数
  {
    pattern: /async \(: any\) =>/g,
    replacement: 'async () =>'
  },
  
  // 修复错误的computed参数
  {
    pattern: /computed\(\(: any\) =>/g,
    replacement: 'computed(() =>'
  },
  
  // 修复错误的watch参数
  {
    pattern: /watch\(\[([^]]*): any,([^]]*)\]: any, \(: any\) =>/g,
    replacement: 'watch([$1,$2], () =>'
  },
  
  // 修复错误的watch单参数
  {
    pattern: /watch\(([^,]*): any, \(: any\) =>/g,
    replacement: 'watch($1, () =>'
  },
  
  // 修复错误的setTimeout参数
  {
    pattern: /setTimeout\(\(: any\) =>/g,
    replacement: 'setTimeout(() =>'
  },
  
  // 修复错误的setInterval参数
  {
    pattern: /setInterval\(\(: any\) =>/g,
    replacement: 'setInterval(() =>'
  },
  
  // 修复错误的catch参数
  {
    pattern: /\.catch\(\(: any\) =>/g,
    replacement: '.catch(() =>'
  },
  
  // 修复错误的函数参数默认值
  {
    pattern: /\(([^=]*) = ([^:]*): any/g,
    replacement: '($1 = $2'
  },
  
  // 修复错误的对象解构
  {
    pattern: /\{\s*([^}]+)\s*\}: any/g,
    replacement: '{ $1 }'
  },
  
  // 修复错误的数组解构
  {
    pattern: /\[([^\]]*)\]: any/g,
    replacement: '[$1]'
  },
  
  // 修复错误的onMounted参数
  {
    pattern: /onMounted\(async \(\) =>/g,
    replacement: 'onMounted(async () =>'
  },
  
  // 修复错误的onUnmounted参数
  {
    pattern: /onUnmounted\(\(\) =>/g,
    replacement: 'onUnmounted(() =>'
  }
]

function fixSyntaxErrors(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf-8')
    let modified = false
    
    // 应用语法修复
    SYNTAX_FIXES.forEach(fix => {
      const originalContent = content
      content = content.replace(fix.pattern, fix.replacement)
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
      if (fixSyntaxErrors(fullPath)) {
        fixedCount++
      }
    }
  }
  
  return fixedCount
}

// 主执行函数
async function main() {
  console.log('🚀 开始语法错误修复流程')
  
  try {
    // 修复语法错误
    console.log('\n📝 修复语法错误')
    const fixedCount = scanAndFixFiles(path.join(PROJECT_ROOT, 'src'))
    console.log(`✅ 修复了 ${fixedCount} 个文件的语法错误`)
    
    console.log('\n🎉 语法错误修复完成!')
    console.log('\n📋 修复总结:')
    console.log(`- ✅ 修复了 ${fixedCount} 个文件`)
    console.log('\n🎯 下一步建议:')
    console.log('1. 运行 npm run build 验证编译')
    console.log('2. 运行 npm run dev 验证开发服务器')
    
  } catch (error) {
    console.error('❌ 语法修复过程中出现错误:', error)
    process.exit(1)
  }
}

// 执行主函数
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
