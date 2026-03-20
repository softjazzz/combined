/**
 * 提取 CN-DRG 2023 绩效监测版引擎
 * 参照 sichuan2024Grouper.js 的提取模式
 */
const fs = require('fs');
const path = require('path');

const inputPath = path.join(__dirname, 'OpenDRG/opendrg.github.io/7377.js');
const outputPath = path.join(__dirname, 'apps/medqc-web/src/views/drg-grouper/cnDrg2023Grouper.js');

console.log('读取源文件:', inputPath);
const raw = fs.readFileSync(inputPath, 'utf8');
console.log('源文件大小:', (raw.length / 1024).toFixed(1), 'KB');

// webpack chunk 格式:
// (self.webpackChunkdrg_group=...||[]).push([[7377],{7377:function(x){var S;S=()=>(()=>{...return S})(),x.exports=S}}])
// 需要提取 S=()=>(...) 这个 IIFE

// 方案：找到 S=()=> 后面的 IIFE 部分
const factoryStart = raw.indexOf('S=()=>');
if (factoryStart === -1) {
  console.error('找不到工厂函数入口');
  process.exit(1);
}

// 从 S=()=> 开始，找到最外层的 IIFE
const iifeStart = raw.indexOf('(()=>{', factoryStart);
if (iifeStart === -1) {
  console.error('找不到 IIFE 入口');
  process.exit(1);
}

// 找到匹配的闭合括号 - 向后搜索 "return S})()" 
const returnPattern = 'return S})()';
const returnIdx = raw.lastIndexOf(returnPattern);
if (returnIdx === -1) {
  console.error('找不到 return S})() 模式');
  process.exit(1);
}

// 提取 IIFE 体：从 (()=>{ 到 return S})()
const iifeBody = raw.substring(iifeStart, returnIdx + returnPattern.length);
console.log('IIFE 体大小:', (iifeBody.length / 1024).toFixed(1), 'KB');

// 构造输出
const output = `/*
 * CN-DRG 2023 绩效监测版 - 从 OpenDRG 提取
 * 源文件: OpenDRG/opendrg.github.io/7377.js
 * 提取时间: ${new Date().toISOString()}
 */
const __chunkExports = ${iifeBody};

export const CC = __chunkExports.CC;
export const CCE = __chunkExports.CCE;
export const MCC = __chunkExports.MCC;
export const SS_VALID = __chunkExports.SS_VALID;
export const group_record = __chunkExports.group_record;
export const group_record_str = __chunkExports.group_record_str;
`;

fs.writeFileSync(outputPath, output, 'utf8');
console.log('输出文件:', outputPath);
console.log('输出大小:', (output.length / 1024).toFixed(1), 'KB');
console.log('✅ 提取完成');
