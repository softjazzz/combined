# WorkstationV4View 拆分实施计划（可施工版）

## 1. 目标
- 将 `src/views/workstation-v2/WorkstationV4View.vue` 从超大单文件拆为 composable + 子组件。
- 优先降低脚本复杂度，保证功能不回归。
- 采用分批灰度方式，每批可独立回滚。

当前基线：
- 文件：`src/views/workstation-v2/WorkstationV4View.vue`
- 行数：约 1811 行

## 2. 拆分原则
- 先拆 `script`，后拆 `template`。
- 先拆“低耦合、纯数据/状态”模块，再拆“高耦合 UI 片段”。
- 先做字段归一层，再做功能迁移，避免 `status/auditStatus` 等混用导致回归。

## 3. 预处理（必须先做）
新增一层记录归一函数（建议放在 composable 内或 `utils`）：
- `normalizeRecord(raw)`：统一输出 `record_id/patient_name/department/status/auditStatus` 等核心字段。
- `normalizeDefect(raw)`：统一输出 `id/record_id/status/severity/rule_name` 等核心字段。

要求：
- 页面内所有渲染和动作逻辑都只消费归一后的字段。
- 禁止在模板里继续直接写多套字段兜底（如 `a || b || c`）。

## 4. 分批实施

### Batch 1（低风险，先落地）
目标：先减脚本复杂度，不动大块模板结构。

新增：
- `src/views/workstation-v2/composables/usePatientRecords.ts`
- `src/views/workstation-v2/composables/useNotifications.ts`

迁移内容：
- 病历列表加载、筛选、分页、统计、科室切换、刷新。
- 消息通知拉取、已读/全部已读、点击通知处理、相对时间格式化。

验收：
- 列表加载、筛选、分页行为与拆分前一致。
- 通知红点数量、已读状态、点击跳转一致。

### Batch 2（中风险）
目标：拆模板主体区块，降低主文件模板体积。

新增组件：
- `src/views/workstation-v2/components/PatientCardGrid.vue`
- `src/views/workstation-v2/components/DetailHeader.vue`
- `src/views/workstation-v2/components/DetailSidebar.vue`

约束：
- 子组件仅通过 `props + emits` 通信，不直接访问全局页面状态。
- 抽离后保持现有交互顺序：选中病历 -> 详情刷新 -> 文书树/标签联动。

验收：
- 卡片点击、上一例/下一例、详情区顶部操作全部可用。
- 文书树、病历详情、页面滚动行为不变。

### Batch 3（可选，按业务优先级执行）
仅在结算清单仍是当前版本核心路径时执行。

新增：
- `src/views/workstation-v2/composables/useSettlement.ts`
- `src/views/workstation-v2/components/SettlementTabContent.vue`

说明：
- 如果短期不做结算清单强化，可延期该批次，避免投入到低优先级模块。

## 5. 代码组织建议
- `composables/`：只放状态与业务方法，不含 UI 逻辑。
- `components/`：只放视图渲染与局部交互。
- `types/`（可选）：沉淀 `RecordVM/DefectVM/NotificationVM` 视图模型类型。

## 6. 回归检查清单
- 页面入口：`/workstation-v4`
- 检查项：
1. 列表：搜索、科室筛选、状态筛选、分页。
2. 详情：患者头部信息、翻页、ICD 查询按钮、AI 首页生成按钮。
3. 标签：病历详情 / 病案首页 / 结算清单切换。
4. 通知：未读数、单条已读、全部已读。
5. 性能：首次进入、切换病历、切换标签无明显退化。

## 7. 命令验证
在 `apps/medqc-web` 下执行：

```powershell
npx vue-tsc --noEmit
npm run build
```

如项目内已有单测/冒烟脚本，按现有命令补跑。

## 8. 风险与回滚
- 风险 1：字段口径不一致导致显示错位。
  - 缓解：先做 `normalizeRecord/normalizeDefect`，再迁移。
- 风险 2：子组件拆分后事件链断裂。
  - 缓解：每批拆分后立即走“列表->详情->操作”全链路手工验证。
- 回滚策略：
  - 每个 Batch 独立提交；
  - 发现问题可按批次回滚，不跨批次混改。

## 9. 交付定义
- Batch 1 完成即视为“脚本可维护性达标”。
- Batch 2 完成视为“页面结构可维护性达标”。
- Batch 3 按业务优先级排期，不作为当前必需项。
