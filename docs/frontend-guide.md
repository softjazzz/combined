# 前端界面与交互指南（Yibao Web）

> 介绍规则列表页面的功能、交互、视觉与实现要点，记录主要优化。

## 目录
- 页面概览
- 功能清单
- 交互细节与视觉规范
- 组件与关键代码
- 性能与可用性优化
- 常见问题与最佳实践

## 页面概览
- 路由：/rules
- 核心文件：apps/yibao-web/src/views/RulesList.vue
- 主要区域：
  1) 页面头（标题、快捷操作）
  2) 筛选区（搜索与条件）
  3) 快速筛选与查询/重置（同一行）
  4) 批量操作提示区
  5) 规则列表表格
  6) 规则详情抽屉 + 版本历史

## 功能清单
- 搜索：按名称/编码/描述模糊搜索
- 筛选：启用状态、严重级别、规则类型、分类
- 快速筛选：常用标签（全部类型/性别/年龄/儿童专用/保险类型/拦截规则/已启用）
- 查询/重置按钮：与快速筛选标签同行，靠右对齐
- 表格列：规则编号/规则信息/类型/严重级别/状态/版本/更新时间/操作
- 切换启停：行内 Switch
- 详情抽屉：基本信息、统计摘要、触发事件、条件配置、动作配置
- 版本历史模态：时间线展示，支持比较与回滚（入口已就绪）
- 导出对话框：支持 JSON/CSV，字段可选

## 交互细节与视觉规范
- 规则编号列：仅展示完整原始编号（如 DRUG_INSURANCE_TYPE_001），使用等宽字体和彩色徽章风格
- 规则信息列：仅展示纯名称（去掉“ - 类型限制”尾注）；描述两行截断
- 类型列：中文标签，按类型着色（性别-粉、年龄-橙、儿童-绿、保险-蓝...）
- 严重级别列：信息/警告/阻断，对应蓝/橙/红，并带图标
- 状态列：小尺寸 Switch，可直接切换
- 查询/重置：位于快速筛选栏最右侧（ml-auto），小屏可自动换行
- 空态与加载：使用 antd 的 empty 与 spin，表格最小高度保证稳定布局

## 组件与关键代码
- ApiService（apps/yibao-web/src/services/apiService.ts）
  - 请求拦截器自动注入 Authorization
  - 401 时自动尝试 refresh；失败后清 token 并跳登录
  - 403 时在页面层面提示“没有权限访问该资源”

- 列定义（RulesList.vue）
```ts
// 规则编号（仅完整编号）
{ title: '规则编号', key: 'code', width: 200, fixed: 'left',
  customRender: ({ record }) => h('div',{class:'flex justify-center'},[
    h('div',{class:'rule-code-badge font-mono text-xs'}, record.code)
  ])
}
```

- 规则类型中文化（颜色+文案）
```ts
const getRuleTypeLabel = (type: string) => ({
  drug_gender:'性别限制', drug_age:'年龄限制', drug_children_only:'儿童专用',
  drug_children_limit:'儿童限制', drug_payment_course:'支付疗程限制',
  drug_insurance_type:'保险类型限制', drug_diagnosis:'诊断限制',
  drug_dosage_form:'剂型限制', drug_route:'给药途径', drug_indication:'适应症限制',
  visit_type:'就诊方式限制', hospital_level:'机构级别限制', duration:'疗程限制',
  surgery_pricing:'手术折价'
}[type] || type || '未分类')
```

- 快速筛选与按钮同行（靠右）
```vue
<div class="quick-filters mb-4">
  <div class="flex items-center gap-3 flex-wrap">
    <!-- 左侧若干标签 -->
    <div class="ml-auto flex items-center gap-2 flex-shrink-0">
      <a-button type="primary" @click="load">查询</a-button>
      <a-button @click="clearFilters">重置</a-button>
    </div>
  </div>
</div>
```

## 性能与可用性优化
- 后端分页：page/page_size，合并筛选参数，避免前端全量加载
- 组件懒渲染：抽屉/模态按需打开
- 视觉性能：表格 hover/阴影/渐变适度使用，确保流畅
- 错误处理：
  - 401：弹出“登录已过期”，清理并跳登录
  - 403：提示“没有权限访问该资源”
  - 其他：提示“加载规则失败，请检查网络连接”

## 常见问题与最佳实践
- 规则名称带“ - 类型限制”尾注：在展示时 split(' - ')[0] 去尾注，避免与类型列重复
- 类型映射缺失：后端新增类型时请同步维护 label/color
- Token 过期：确保 refresh_token 有效；若后端不支持 refresh，请在前端关闭自动刷新或调整逻辑
- 表格横向滚动：当列较多时设置 :scroll="{ x: 1450 }"，移动端自动横向滚动

