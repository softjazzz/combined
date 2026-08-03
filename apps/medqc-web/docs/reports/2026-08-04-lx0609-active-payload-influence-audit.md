# LX0609 active 规则旧 payload 影响审计

日期：2026-08-04

## 结论

当前 75 条 active 规则的 Typed 主线以 `EvidenceSnapshot/MaterialStore` 为唯一权威资料源。没有发现旧 Scene `evidence_payload` 能改变 active 规则最终状态的路径，本 Task 无需修改生产代码。

旧 payload 参数仍保留在 7 个 executor 中，用于 Typed 关闭后的回滚或混合兼容模式；它们不是当前主线的第二证据来源，暂不删除。

## 逐族核对

| Executor | active Typed 主线 | 旧 payload 当前作用 | 聚焦证据 |
|---|---|---|---|
| `basic_timeliness` | 从同一请求的 Snapshot/MaterialStore 构造决定 | 仅处理未被 Typed 接管的兼容规则 | Typed 规则会从 legacy 结果循环中排除 |
| `exam_lab` | 使用 Snapshot trigger、MaterialStore 和受控投影 | 混合回滚时仅服务 legacy 子集 | 冲突输入隔离测试通过 |
| `tumor_pathology` | 使用独立 Typed source | 仅兼容回滚 | 019 不读取陈旧 payload 的测试通过 |
| `course_quality` | 使用请求内 MaterialStore | 仅兼容回滚 | 016/018 同一材料会话测试通过 |
| `surgery_gate` | Typed 决定完成后从 `selected` 中移除 | 仅剩余 legacy 规则才解析 payload 文书 | 全量 Typed 时在读取 payload 前返回 |
| `surgery_document` | Typed 使用 MaterialStore | timeline/payload 只服务 `legacy_selected` | Typed 手术文书族不读旧 payload 测试通过 |
| `transfusion` | Typed 规则使用 `typed_material_by_rule` | legacy 文书仅服务兼容分支 | 045 冲突 payload 测试通过 |

`consultation_quality`、`surgery_mdt`、`extended_document` 不读取外部兼容 payload。`surgery_presence` 使用从同一 MaterialStore 派生的内部 payload，不属于旧 Scene payload。

## 验证

七族聚焦冲突/隔离测试共 11 项通过：

- basic timeliness：Typed 接管后排除 legacy 结果；
- exam/lab：混合回滚资料隔离；
- tumor/pathology：陈旧 payload 不影响 019；
- course quality：016/018 使用同一材料会话；
- surgery gate：Typed 门控 fail-closed；
- surgery document：Typed 文书规则不读取旧 payload；
- transfusion：045 使用 Snapshot 材料而非冲突 payload。

## 保留风险

- 兼容入口名称和参数仍容易误导维护者，但删除它们需要单独验证回滚能力，不应在本轮顺手清理。
- `extended_document` 的 executor 级预取范围较宽，属于性能和截断传播问题，不是旧 payload 影响。
