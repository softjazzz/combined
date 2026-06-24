#!/usr/bin/env node

/**
 * CSV转JSON转换器
 * 将住院质量评定标准CSV文件转换为结构化的JSON格式
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// 获取当前文件的目录
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 输入和输出文件路径
const inputFile = '（运行病历）住院质量评定标准_433377418703_2024-04-03_09-59-13.csv';
const outputFile = 'src/data/quality-standards.json';

/**
 * 解析CSV行
 * @param {string} line CSV行
 * @returns {Array} 解析后的字段数组
 */
function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;
  
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  
  result.push(current.trim());
  return result;
}

/**
 * 转换CSV数据为结构化JSON
 * @param {string} csvContent CSV文件内容
 * @returns {Object} 结构化的JSON对象
 */
function convertToJSON(csvContent) {
  const lines = csvContent.split('\n').filter(line => line.trim());
  
  if (lines.length === 0) {
    throw new Error('CSV文件为空');
  }
  
  // 解析表头
  const headers = parseCSVLine(lines[0]);
  console.log('CSV表头:', headers);
  
  // 解析数据行
  const rawData = [];
  for (let i = 1; i < lines.length; i++) {
    const fields = parseCSVLine(lines[i]);
    if (fields.length === headers.length) {
      const row = {};
      headers.forEach((header, index) => {
        row[header] = fields[index];
      });
      rawData.push(row);
    }
  }
  
  // 按评分项目组分组
  const groupedData = {};
  rawData.forEach(row => {
    const groupName = row['评分项目组'];
    if (!groupedData[groupName]) {
      groupedData[groupName] = {
        name: groupName,
        totalScore: parseInt(row['项目组总分值']) || 0,
        items: []
      };
    }
    
    // 查找或创建评分项目
    let item = groupedData[groupName].items.find(item => item.name === row['评分项目']);
    if (!item) {
      item = {
        name: row['评分项目'],
        totalScore: parseInt(row['项目总分值']) || 0,
        contents: []
      };
      groupedData[groupName].items.push(item);
    }
    
    // 添加评分内容
    item.contents.push({
      content: row['评分内容'],
      rule: row['评分规则'],
      deductionScore: parseInt(row['扣分分值']) || 0,
      qualityPointId: row['质控点ID'],
      qualityPointName: row['质控点名称'],
      document: row['质控文书'],
      departments: row['生效科室'] ? row['生效科室'].split(',') : [],
      alertLevel: row['提醒等级'],
      isEnabled: row['是否启用'] === '是',
      isEffectiveToDoctor: row['是否生效到医生端'] === '是'
    });
  });
  
  // 转换为数组格式
  const result = {
    metadata: {
      title: '住院质量评定标准',
      version: '2024-04-03',
      totalGroups: Object.keys(groupedData).length,
      totalItems: Object.values(groupedData).reduce((sum, group) => sum + group.items.length, 0),
      totalContents: rawData.length,
      generatedAt: new Date().toISOString()
    },
    groups: Object.values(groupedData)
  };
  
  return result;
}

/**
 * 生成TypeScript类型定义
 * @param {Object} jsonData JSON数据
 */
function generateTypeDefinitions(jsonData) {
  const typeDefinitions = `/**
 * 住院质量评定标准类型定义
 * 自动生成于 ${new Date().toISOString()}
 */

export interface QualityStandardContent {
  /** 评分内容 */
  content: string;
  /** 评分规则 */
  rule: string;
  /** 扣分分值 */
  deductionScore: number;
  /** 质控点ID */
  qualityPointId: string;
  /** 质控点名称 */
  qualityPointName: string;
  /** 质控文书 */
  document: string;
  /** 生效科室 */
  departments: string[];
  /** 提醒等级 */
  alertLevel: string;
  /** 是否启用 */
  isEnabled: boolean;
  /** 是否生效到医生端 */
  isEffectiveToDoctor: boolean;
}

export interface QualityStandardItem {
  /** 评分项目名称 */
  name: string;
  /** 项目总分值 */
  totalScore: number;
  /** 评分内容列表 */
  contents: QualityStandardContent[];
}

export interface QualityStandardGroup {
  /** 评分项目组名称 */
  name: string;
  /** 项目组总分值 */
  totalScore: number;
  /** 评分项目列表 */
  items: QualityStandardItem[];
}

export interface QualityStandardMetadata {
  /** 标题 */
  title: string;
  /** 版本 */
  version: string;
  /** 总项目组数 */
  totalGroups: number;
  /** 总项目数 */
  totalItems: number;
  /** 总内容数 */
  totalContents: number;
  /** 生成时间 */
  generatedAt: string;
}

export interface QualityStandards {
  /** 元数据 */
  metadata: QualityStandardMetadata;
  /** 评分项目组列表 */
  groups: QualityStandardGroup[];
}

// 导出示例数据结构
export const QUALITY_STANDARDS_EXAMPLE: QualityStandards = {
  metadata: {
    title: "住院质量评定标准",
    version: "2024-04-03",
    totalGroups: ${jsonData.metadata.totalGroups},
    totalItems: ${jsonData.metadata.totalItems},
    totalContents: ${jsonData.metadata.totalContents},
    generatedAt: "${jsonData.metadata.generatedAt}"
  },
  groups: [] // 实际数据从 quality-standards.json 加载
};
`;

  const typeFile = 'src/types/quality-standards.ts';
  const typeDir = path.dirname(typeFile);
  
  if (!fs.existsSync(typeDir)) {
    fs.mkdirSync(typeDir, { recursive: true });
  }
  
  fs.writeFileSync(typeFile, typeDefinitions, 'utf-8');
  console.log(`📝 TypeScript类型定义已生成: ${typeFile}`);
}

/**
 * 主函数
 */
async function main() {
  try {
    console.log('🔄 开始转换CSV文件...');
    
    // 检查输入文件是否存在
    if (!fs.existsSync(inputFile)) {
      throw new Error(`输入文件不存在: ${inputFile}`);
    }
    
    // 读取CSV文件
    console.log('📖 读取CSV文件...');
    const csvContent = fs.readFileSync(inputFile, 'utf-8');
    
    // 转换为JSON
    console.log('🔄 转换为JSON格式...');
    const jsonData = convertToJSON(csvContent);
    
    // 确保输出目录存在
    const outputDir = path.dirname(outputFile);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    
    // 写入JSON文件
    console.log('💾 保存JSON文件...');
    fs.writeFileSync(outputFile, JSON.stringify(jsonData, null, 2), 'utf-8');
    
    // 输出统计信息
    console.log('✅ 转换完成！');
    console.log(`📊 统计信息:`);
    console.log(`   - 评分项目组: ${jsonData.metadata.totalGroups}个`);
    console.log(`   - 评分项目: ${jsonData.metadata.totalItems}个`);
    console.log(`   - 评分内容: ${jsonData.metadata.totalContents}个`);
    console.log(`   - 输出文件: ${outputFile}`);
    
    // 生成TypeScript类型定义
    generateTypeDefinitions(jsonData);
    
  } catch (error) {
    console.error('❌ 转换失败:', error.message);
    process.exit(1);
  }
}

// 执行主函数
main();

export { convertToJSON, parseCSVLine }; 