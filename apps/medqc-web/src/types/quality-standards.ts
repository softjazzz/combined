/**
 * 住院质量评定标准类型定义
 * 自动生成于 2025-07-16T08:39:50.262Z
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
    totalGroups: 6,
    totalItems: 6,
    totalContents: 234,
    generatedAt: "2025-07-16T08:39:50.251Z"
  },
  groups: [] // 实际数据从 quality-standards.json 加载
};
