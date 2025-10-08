#!/usr/bin/env node

/**
 * 修复自动替换造成的语法错误
 */

const fs = require('fs');
const path = require('path');

// 修复规则
const FIXES = [
  // 修复 data?[] -> data?: unknown[]
  {
    pattern: /data\?\[\]/g,
    replacement: 'data?: unknown[]',
    description: 'data?[] -> data?: unknown[]'
  },
  
  // 修复 (data || : unknown[]) -> ((data || []) as unknown[])
  {
    pattern: /\((\w+) \|\| : unknown\[\]\)/g,
    replacement: '(($1 || []) as unknown[])',
    description: '(data || : unknown[]) -> ((data || []) as unknown[])'
  },
  
  // 修复 }> { try { -> }> {\n  try {
  {
    pattern: /\}> \{ try \{/g,
    replacement: '}> {\n  try {',
    description: '}> { try { -> }> {\\n  try {'
  },
  
  // 修复 []: unknown[] -> []: unknown[]
  {
    pattern: /\[\]: unknown\[\]/g,
    replacement: '[]: unknown[]',
    description: '[]: unknown[] (no change needed)'
  },
  
  // 修复 Record<string, unknown>[] -> Record<string, unknown>[]
  {
    pattern: /Record<string, unknown>\[\]/g,
    replacement: 'Record<string, unknown>[]',
    description: 'Record<string, unknown>[] (no change needed)'
  },
];

function fixFile(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let modified = false;
    let changeCount = 0;
    
    FIXES.forEach(({ pattern, replacement }) => {
      const before = content;
      content = content.replace(pattern, replacement);
      if (content !== before) {
        modified = true;
        changeCount++;
      }
    });
    
    if (modified) {
      fs.writeFileSync(filePath, content, 'utf8');
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
        if (file !== 'node_modules' && file !== '.git' && file !== 'dist') {
          results = results.concat(findFiles(filePath, extensions));
        }
      } else {
        const ext = path.extname(file);
        if (extensions.includes(ext) && !file.endsWith('.d.ts') && !file.endsWith('.vue.ts')) {
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
  
  console.log('🔧 修复语法错误...\n');
  
  const files = findFiles(srcDir);
  let totalModified = 0;
  let totalChanges = 0;
  const modifiedFiles = [];
  
  files.forEach((file) => {
    const result = fixFile(file);
    
    if (result.modified) {
      totalModified++;
      totalChanges += result.changeCount;
      const relativePath = path.relative(srcDir, file);
      modifiedFiles.push({ path: relativePath, changes: result.changeCount });
      console.log(`✅ ${relativePath} (${result.changeCount} 处修复)`);
    } else if (result.error) {
      const relativePath = path.relative(srcDir, file);
      console.log(`❌ ${relativePath} - 错误: ${result.error}`);
    }
  });
  
  console.log('\n' + '='.repeat(80));
  console.log('📊 修复统计\n');
  console.log(`修改文件数: ${totalModified}`);
  console.log(`总修复次数: ${totalChanges}`);
  console.log('='.repeat(80) + '\n');
  
  if (modifiedFiles.length > 0) {
    console.log('📝 修改的文件:\n');
    modifiedFiles.forEach(({ path, changes }) => {
      console.log(`  ${path} (${changes} 处)`);
    });
  }
  
  console.log('\n✅ 完成！\n');
}

if (require.main === module) {
  main();
}

module.exports = { fixFile };

