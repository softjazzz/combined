/**
 * 质控标准数据加载器
 * 提供便捷的API来访问和使用质控标准数据
 */

import type { QualityStandards, QualityStandardGroup, QualityStandardItem, QualityStandardContent } from '../types/quality-standards';

// 懒加载质控标准数据
let qualityStandardsData: QualityStandards | null = null;

/**
 * 加载质控标准数据
 * @returns Promise<QualityStandards> 质控标准数据
 */
export async function loadQualityStandards(): Promise<QualityStandards> {
  if (qualityStandardsData) {
    return qualityStandardsData;
  }
  
  try {
    // 动态导入JSON数据
    const response = await fetch('/src/data/quality-standards.json');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    qualityStandardsData = await response.json() as QualityStandards;
    return qualityStandardsData;
  } catch (error) {
    console.error('加载质控标准数据失败:', error);
    throw new Error('无法加载质控标准数据');
  }
}

/**
 * 获取所有评分项目组
 * @returns Promise<QualityStandardGroup[]> 评分项目组列表
 */
export async function getAllGroups(): Promise<QualityStandardGroup[]> {
  const data = await loadQualityStandards();
  return data.groups;
}

/**
 * 根据名称获取评分项目组
 * @param groupName 项目组名称
 * @returns Promise<QualityStandardGroup | null> 找到的项目组
 */
export async function getGroupByName(groupName: string): Promise<QualityStandardGroup | null> {
  const data = await loadQualityStandards();
  return data.groups.find(group => group.name === groupName) || null;
}

/**
 * 获取所有评分项目
 * @returns Promise<QualityStandardItem[]> 所有评分项目列表
 */
export async function getAllItems(): Promise<QualityStandardItem[]> {
  const data = await loadQualityStandards();
  return data.groups.flatMap(group => group.items);
}

/**
 * 根据名称获取评分项目
 * @param itemName 项目名称
 * @returns Promise<QualityStandardItem | null> 找到的项目
 */
export async function getItemByName(itemName: string): Promise<QualityStandardItem | null> {
  const items = await getAllItems();
  return items.find(item => item.name === itemName) || null;
}

/**
 * 获取所有评分内容
 * @returns Promise<QualityStandardContent[]> 所有评分内容列表
 */
export async function getAllContents(): Promise<QualityStandardContent[]> {
  const data = await loadQualityStandards();
  return data.groups.flatMap(group => 
    group.items.flatMap(item => item.contents)
  );
}

/**
 * 根据质控点ID获取评分内容
 * @param qualityPointId 质控点ID
 * @returns Promise<QualityStandardContent | null> 找到的评分内容
 */
export async function getContentByQualityPointId(qualityPointId: string): Promise<QualityStandardContent | null> {
  const contents = await getAllContents();
  return contents.find(content => content.qualityPointId === qualityPointId) || null;
}

/**
 * 根据科室获取相关的评分内容
 * @param department 科室名称
 * @returns Promise<QualityStandardContent[]> 相关的评分内容列表
 */
export async function getContentsByDepartment(department: string): Promise<QualityStandardContent[]> {
  const contents = await getAllContents();
  return contents.filter(content => 
    content.departments.some(dept => dept.includes(department))
  );
}

/**
 * 根据提醒等级获取评分内容
 * @param alertLevel 提醒等级
 * @returns Promise<QualityStandardContent[]> 相关的评分内容列表
 */
export async function getContentsByAlertLevel(alertLevel: string): Promise<QualityStandardContent[]> {
  const contents = await getAllContents();
  return contents.filter(content => content.alertLevel === alertLevel);
}

/**
 * 获取启用的评分内容
 * @returns Promise<QualityStandardContent[]> 启用的评分内容列表
 */
export async function getEnabledContents(): Promise<QualityStandardContent[]> {
  const contents = await getAllContents();
  return contents.filter(content => content.isEnabled);
}

/**
 * 获取生效到医生端的评分内容
 * @returns Promise<QualityStandardContent[]> 生效到医生端的评分内容列表
 */
export async function getDoctorEffectiveContents(): Promise<QualityStandardContent[]> {
  const contents = await getAllContents();
  return contents.filter(content => content.isEffectiveToDoctor);
}

/**
 * 搜索评分内容
 * @param keyword 搜索关键词
 * @returns Promise<QualityStandardContent[]> 匹配的评分内容列表
 */
export async function searchContents(keyword: string): Promise<QualityStandardContent[]> {
  const contents = await getAllContents();
  const lowerKeyword = keyword.toLowerCase();
  
  return contents.filter(content => 
    content.content.toLowerCase().includes(lowerKeyword) ||
    content.rule.toLowerCase().includes(lowerKeyword) ||
    content.qualityPointName.toLowerCase().includes(lowerKeyword)
  );
}

/**
 * 获取统计信息
 * @returns Promise<Object> 统计信息
 */
export async function getStatistics() {
  const data = await loadQualityStandards();
  const contents = await getAllContents();
  
  return {
    metadata: data.metadata,
    totalGroups: data.groups.length,
    totalItems: data.groups.reduce((sum, group) => sum + group.items.length, 0),
    totalContents: contents.length,
    enabledContents: contents.filter(c => c.isEnabled).length,
    doctorEffectiveContents: contents.filter(c => c.isEffectiveToDoctor).length,
    alertLevels: [...new Set(contents.map(c => c.alertLevel))],
    departments: [...new Set(contents.flatMap(c => c.departments))],
    totalScore: data.groups.reduce((sum, group) => sum + group.totalScore, 0)
  };
}

/**
 * 质控标准缓存管理
 */
export const QualityStandardsCache = {
  /**
   * 清除缓存
   */
  clear() {
    qualityStandardsData = null;
  },
  
  /**
   * 预加载数据
   */
  async preload() {
    await loadQualityStandards();
  },
  
  /**
   * 检查是否已缓存
   */
  isCached() {
    return qualityStandardsData !== null;
  }
}; 