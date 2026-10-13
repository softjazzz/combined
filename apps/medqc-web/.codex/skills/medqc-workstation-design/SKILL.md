---
name: medqc-workstation-design
description: 设计、审查或实现 MedQC 工作台页面、弹窗和抽屉时使用，遵循仓库 v7.1 规范。
---

# MedQC 工作台设计

唯一规范为 `docs/0418/UI/WorkstationV4-医疗浅色-DESIGN.md`（v7.1），适用于 `/workstation-v5/*`。先阅读该文档及对应模板，再实施。旧版 24px 标题、8px 按钮、Lucide 专用要求已被取代，不再重复定义参数。

- 使用 `src/styles/tokens-v2.css` 的 `--mq-*` 变量和 `src/styles/mq-components.css` 公共类；页标题32px、控件12px、卡片24px、按钮胶囊形。
- 使用 MqIcon / MqIconTile；不增加装饰色或面板悬浮位移。
- 页面内弹窗使用 `mq-modal`。工作台确认操作使用 `useWorkstationConfirmation`，其 Layout 宿主继承工作台主题；旧入口兼容仅留在旧路径。
- 保留业务布局、接口、状态、事件、文案原意与 data-testid。纯展示不修改后端合同。
- 私有 CSS 只管理页面布局；不要复制公共材质。分离样式不等于业务组件已完成拆分。
- 运行编码、Lint、类型检查及相关单测，浏览器核对真实计算样式和响应式，不能把外壳接入算成页面内部迁移完成。
