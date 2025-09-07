#!/usr/bin/env node

/**
 * 最终语法错误修复脚本
 * 修复剩余的语法错误
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PROJECT_ROOT = path.resolve(__dirname, '../..')

console.log('🔧 开始最终语法错误修复...')

// 最终语法修复规则
const FINAL_FIXES = [
  // 修复数组类型注解
  {
    pattern: /records\[\]/g,
    replacement: 'records: any[]'
  },
  
  // 修复数组参数
  {
    pattern: /\(([^)]*)\[\]\)/g,
    replacement: '($1: any[])'
  },
  
  // 修复泛型数组
  {
    pattern: /\.\.\.\s*args\[\]/g,
    replacement: '...args: any[]'
  },
  
  // 修复对象类型注解中的数组
  {
    pattern: /{\s*([^}]*)\[\],/g,
    replacement: '{ $1: any[],'
  },
  
  // 修复变量声明中的数组
  {
    pattern: /const\s+([^=]*)\[\]\s*=/g,
    replacement: 'const $1: any[] ='
  },
  
  // 修复let声明中的数组
  {
    pattern: /let\s+([^=]*)\[\]\s*=/g,
    replacement: 'let $1: any[] ='
  },
  
  // 修复函数参数中的类型注解
  {
    pattern: /([^:]*): any,([^)]*): any\)/g,
    replacement: '$1: any, $2: any)'
  },
  
  // 修复watch参数
  {
    pattern: /watch\(([^,]*): any,/g,
    replacement: 'watch($1,'
  },
  
  // 修复addEventListener参数
  {
    pattern: /addEventListener\('([^']*)': any,/g,
    replacement: "addEventListener('$1',"
  },
  
  // 修复removeEventListener参数
  {
    pattern: /removeEventListener\('([^']*)': any,/g,
    replacement: "removeEventListener('$1',"
  },
  
  // 修复on方法参数
  {
    pattern: /\.on\('([^']*)': any,/g,
    replacement: ".on('$1',"
  },
  
  // 修复set方法参数
  {
    pattern: /\.set\('([^']*)': any,/g,
    replacement: ".set('$1',"
  },
  
  // 修复forEach参数
  {
    pattern: /\.forEach\(\(\[([^:]*): any,([^\]]*)\]\)/g,
    replacement: '.forEach(([$1, $2])'
  },
  
  // 修复defineStore参数
  {
    pattern: /defineStore\('([^']*)': any,/g,
    replacement: "defineStore('$1',"
  },
  
  // 修复describe和it参数
  {
    pattern: /(describe|it)\('([^']*)': any,/g,
    replacement: "$1('$2',"
  },
  
  // 修复函数参数默认值
  {
    pattern: /([^=]*) = ([^:]*): any\)/g,
    replacement: '$1 = $2)'
  },
  
  // 修复Omit类型
  {
    pattern: /Omit<([^>]*)>: any\)/g,
    replacement: 'Omit<$1>)'
  },
  
  // 修复Record类型
  {
    pattern: /Record<([^>]*)>: any\)/g,
    replacement: 'Record<$1>)'
  },
  
  // 修复错误的数组访问
  {
    pattern: /\?\.\[0\]s/g,
    replacement: '?.[0]'
  }
]

function applyFinalFixes(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf-8')
    let modified = false
    
    // 应用最终修复
    FINAL_FIXES.forEach(fix => {
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
      if (applyFinalFixes(fullPath)) {
        fixedCount++
      }
    }
  }
  
  return fixedCount
}

// 主执行函数
async function main() {
  console.log('🚀 开始最终语法错误修复流程')
  
  try {
    // 修复语法错误
    console.log('\n📝 修复剩余语法错误')
    const fixedCount = scanAndFixFiles(path.join(PROJECT_ROOT, 'src'))
    console.log(`✅ 修复了 ${fixedCount} 个文件的语法错误`)
    
    console.log('\n🎉 最终语法错误修复完成!')
    console.log('\n📋 修复总结:')
    console.log(`- ✅ 修复了 ${fixedCount} 个文件`)
    console.log('\n🎯 下一步建议:')
    console.log('1. 运行 npm run build 验证编译')
    console.log('2. 运行 npm run dev 验证开发服务器')
    
  } catch (error) {
    console.error('❌ 最终语法修复过程中出现错误:', error)
    process.exit(1)
  }
}

// 执行主函数
if (import.meta.url === `file://${process.argv[1]}`) {
  main()
}
