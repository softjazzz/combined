/**
 * 路由 meta.permission 使用的角色集合。
 *
 * 后端是数据安全边界：前端集合只能等于或窄于页面核心接口的后端角色，不得更宽。
 * 修改前先核对注释中的后端依赖；后端未变时不要为了让页面可用而放宽这里。
 */

/**
 * DRG/DIP 模块：后端 `routers/drg.py`（/api/v1/drg/*，含 analysis/config/operations 子路由）
 * 与 `routers/settlement.py` 路由级 `require_roles("admin", "qc_manager", "doctor", "reviewer")`。
 * 后端不含 coder。
 */
export const DRG_ROLES = ['admin', 'qc_manager', 'doctor', 'reviewer']

/**
 * DRG 事后分析（全院绩效统计）：后端 /api/v1/drg/analysis 属 DRG_ROLES，
 * 前端沿用旧版 /dashboard/drg/analysis 的更窄口径。
 */
export const DRG_ANALYSIS_ROLES = ['admin', 'qc_manager']

/**
 * 质控规则管理：后端规则写接口 `routers/custom_qc.py` 路由级
 * `require_roles("admin", "qc_manager")`，`department_qc_rules` 写操作同口径；
 * 与旧版 /dashboard/rules 一致。
 */
export const RULE_ADMIN_ROLES = ['admin', 'qc_manager']

/**
 * 全院质控统计：后端 /api/v1/workstation/analytics/luxian-0609 目前仅校验登录（待定是否收紧），
 * 前端与同类全院页面（运行/已出院病历、问题集中点）保持质控科口径。
 */
export const QC_ANALYTICS_ROLES = ['admin', 'qc_manager']
