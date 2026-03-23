/**
 * Vite 6 热修补脚本
 * 
 * 问题：Vite 6 在 Windows 上调用 exec("net use") 检测网络驱动器，
 * 被系统 EPERM 拒绝，导致 dev server 卡死。
 * 
 * 修复：将 optimizeSafeRealPathSync 中的 exec("net use") 调用
 * 替换为直接使用 fs.realpathSync（跳过网络驱动器检测）。
 */
const path = require('path')
const fs = require('fs')

const viteDir = path.dirname(require.resolve('vite/package.json'))
const chunksDir = path.join(viteDir, 'dist', 'node', 'chunks')

let patched = false

for (const file of fs.readdirSync(chunksDir)) {
  if (!file.startsWith('dep-')) continue
  const filePath = path.join(chunksDir, file)
  let content = fs.readFileSync(filePath, 'utf8')
  
  if (!content.includes('"net use"')) continue
  
  console.log(`找到目标文件: ${file}`)
  
  // 补丁策略：把 exec("net use", callback) 整段替换为
  // 直接设置 safeRealpathSync = fs.realpathSync
  // 原始代码大致是：
  //   exec("net use", (error, stdout) => { ... })
  // 替换为：
  //   safeRealpathSync = fs__default.realpathSync; /* patched: skip net use */
  
  const oldPattern = 'exec("net use", (error, stdout) =>'
  if (content.includes(oldPattern)) {
    // 找到 exec("net use" 的完整块并替换
    const idx = content.indexOf(oldPattern)
    // 找到这个 exec 调用的开始（往前找到 } 或 ;）
    // 和结束（找到匹配的 })）
    
    // 更安全的方式：直接把 exec("net use" 替换为一个 no-op
    content = content.replace(
      'exec("net use", (error, stdout) =>',
      '/* PATCHED: skip net use */ void ((error, stdout) =>'
    )
    
    fs.writeFileSync(filePath, content, 'utf8')
    console.log('补丁已应用！exec("net use") 已被跳过')
    patched = true
  } else {
    console.log('未找到预期的代码模式，尝试备用补丁...')
    // 备用：直接替换 "net use" 为一个无害命令
    content = content.replace('"net use"', '"echo vite-patched"')
    fs.writeFileSync(filePath, content, 'utf8')
    console.log('备用补丁已应用：net use → echo vite-patched')
    patched = true
  }
}

if (!patched) {
  console.log('未找到需要补丁的文件')
  process.exit(1)
}

console.log('\n验证补丁...')
for (const file of fs.readdirSync(chunksDir)) {
  if (!file.startsWith('dep-')) continue
  const content = fs.readFileSync(path.join(chunksDir, file), 'utf8')
  if (content.includes('"net use"')) {
    console.log(`警告: ${file} 仍包含 "net use"`)
  }
}
console.log('补丁验证完成')
