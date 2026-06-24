#!/usr/bin/env node

/**
 * 批量替换 TypeScript any 类型
 * 
 * 策略：
 * 1. 函数参数 any → unknown
 * 2. 返回值 any → unknown  
 * 3. 对象属性 any → unknown
 * 4. 数组 any[] → unknown[]
 * 5. Record<string, any> → Record<string, unknown>
 * 6. 保留必要的 any（如第三方库类型）
 */

const fs = require('fs');
const path = require('path');

// 需要保留 any 的模式（第三方库、特殊情况）
const KEEP_ANY_PATTERNS = [
  /\/\/ @ts-ignore/,
  /\/\/ eslint-disable/,
  /import.*from/,
  /export.*from/,
  /@ts-expect-error/,
];

// 替换规则
const REPLACEMENTS = [
  // Record<string, any> → Record<string, unknown>
  {
    pattern: /Record<string,\s*any>/g,
    replacement: 'Record<string, unknown>',
    description: 'Record<string, any> → Record<string, unknown>'
  },
  
  // : any[] → : unknown[]
  {
    pattern: /:\s*any\[\]/g,
    replacement: ': unknown[]',
    description: ': any[] → : unknown[]'
  },
  
  // : any) → : unknown)
  {
    pattern: /:\s*any\)/g,
    replacement: ': unknown)',
    description: ': any) → : unknown)'
  },
  
  // : any, → : unknown,
  {
    pattern: /:\s*any,/g,
    replacement: ': unknown,',
    description: ': any, → : unknown,'
  },
  
  // : any; → : unknown;
  {
    pattern: /:\s*any;/g,
    replacement: ': unknown;',
    description: ': any; → : unknown;'
  },
  
  // : any = → : unknown =
  {
    pattern: /:\s*any\s*=/g,
    replacement: ': unknown =',
    description: ': any = → : unknown ='
  },
  
  // <any> → <unknown>
  {
    pattern: /<any>/g,
    replacement: '<unknown>',
    description: '<any> → <unknown>'
  },
  
  // Array<any> → Array<unknown>
  {
    pattern: /Array<any>/g,
    replacement: 'Array<unknown>',
    description: 'Array<any> → Array<unknown>'
  },
];

function shouldKeepAny(line) {
  return KEEP_ANY_PATTERNS.some(pattern => pattern.test(line));
}

function processFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    let modified = false;
    let changeCount = 0;
    
    const newLines = lines.map((line, index) => {
      // 跳过需要保留 any 的行
      if (shouldKeepAny(line)) {
        return line;
      }
      
      let newLine = line;
      REPLACEMENTS.forEach(({ pattern, replacement }) => {
        const before = newLine;
        newLine = newLine.replace(pattern, replacement);
        if (newLine !== before) {
          modified = true;
          changeCount++;
        }
      });
      
      return newLine;
    });
    
    if (modified) {
      fs.writeFileSync(filePath, newLines.join('\n'), 'utf8');
      return { modified: true, changeCount };
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
        // 跳过 node_modules 和 .git
        if (file !== 'node_modules' && file !== '.git' && file !== 'dist') {
          results = results.concat(findFiles(filePath, extensions));
        }
      } else {
        const ext = path.extname(file);
        // 排除 .d.ts 文件
        if (extensions.includes(ext) && !file.endsWith('.d.ts')) {
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
  
  console.log('🔍 查找需要处理的文件...\n');
  const files = findFiles(srcDir);
  console.log(`找到 ${files.length} 个文件\n`);
  
  console.log('🔄 开始替换 any 类型...\n');
  
  let totalModified = 0;
  let totalChanges = 0;
  const modifiedFiles = [];
  
  files.forEach((file, index) => {
    const result = processFile(file);
    
    if (result.modified) {
      totalModified++;
      totalChanges += result.changeCount;
      modifiedFiles.push({
        path: path.relative(srcDir, file),
        changes: result.changeCount
      });
      console.log(`✅ [${index + 1}/${files.length}] ${path.relative(srcDir, file)} (${result.changeCount} 处修改)`);
    } else if (result.error) {
      console.log(`❌ [${index + 1}/${files.length}] ${path.relative(srcDir, file)} - 错误: ${result.error}`);
    }
  });
  
  console.log('\n' + '='.repeat(80));
  console.log('📊 替换统计\n');
  console.log(`总文件数: ${files.length}`);
  console.log(`修改文件数: ${totalModified}`);
  console.log(`总替换次数: ${totalChanges}`);
  console.log('='.repeat(80) + '\n');
  
  if (modifiedFiles.length > 0) {
    console.log('📝 修改的文件列表:\n');
    modifiedFiles.slice(0, 20).forEach(({ path, changes }) => {
      console.log(`  ${path} (${changes} 处)`);
    });
    
    if (modifiedFiles.length > 20) {
      console.log(`  ... 还有 ${modifiedFiles.length - 20} 个文件\n`);
    }
  }
  
  console.log('\n✅ 完成！\n');
  console.log('⚠️  注意: 请运行以下命令检查类型错误:');
  console.log('   pnpm exec tsc --noEmit\n');
}

if (require.main === module) {
  main();
}

module.exports = { processFile, findFiles };

