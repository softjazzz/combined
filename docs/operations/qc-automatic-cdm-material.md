# 单病历自动一致性取材交付说明

分析/开发基线：2907213e1；独立分支 `codex/qc-material-preflight-20261113`。仅本地修复，未部署。

## 用户操作与实际行为

正常新任务无需人工填写取材窗口。准备病历时，业务用现有临床只读连接，在一次 `REPEATABLE READ`、`READ ONLY` 事务中读取材料和可访问的发布回执；退出源事务后保存本轮材料，再运行规则。模型运行不占用源事务。

- 来源缺表、非身份必需列缺失、空查询分别保存为来源状态，不因一个领域缺失拒绝整例。
- 可独立证明的结果保留。主诉超长、明确会诊内容不足、复制病历、CT医嘱与病程明确冲突、可靠给药差异、鉴别诊断明确不相关、终末主诊断明确冲突等分支由原判定代码声明其正面证据，并验证真实材料引用。
- 来源范围按实际消费的文书、受控事实和来源观察确定，不按所有可选来源一刀切。通用正文列为空不代表结构化字段不可用，必要正文由原规则校验。
- “没查到”不能证明上游临床未书写。发布覆盖未知时，依赖缺失推断的结论转资料不足/待核，旧缺陷文案不会残留。此策略可能使部分此前直接判缺陷的结果转待核；不宣称所有领域供给已完成。
- 身份缺失/冲突、权限不足或账号非只读、连接错误、捕获超时/容量限制、保存失败及回执版本矛盾仍属技术问题。沿用任务级错误处理，不把准备失败显示为76条已执行。

## 发布证据合同及现场边界

依据同步侧 `edea5cc42448669f65a9e9d066a5727fc2ced94b` 的40接口主键合同，新增 `cdm_publication_keys.json`。新手术接口不在该清单内，不擅自认定已获生产发布授权。

同一 CDM 连接只读以下 `sync_delivery` 对象：

| 对象 | 使用列 |
| --- | --- |
| identity | epoch |
| contract | interface_name, source_epoch, mapping_hash, activation, bootstrap_required |
| receipt | source_epoch, interface_name, source_key_hash, generation, mapping_hash, activation, target_key_hash |
| operation | operation_id, source_epoch, interface_name, mapping_hash, queue_hash, scope_hash, commit_order |
| operation_item | operation_id, source_key_hash, generation |

目标键使用完整目标主键及原始类型的规范 JSON 计算，不用 document_id 冒充源键。通过 receipt 获取源键，精确关联 generation、接口、源 epoch、映射和 activation 对应的 queue hash；不以全库最大 commit_order 证明本例已发布。

现有回执不能证明源端全住院期完整，也没有正文哈希可供验证。材料自有指纹只证明本轮所保存的内容。没有元数据表或没有读取权限时，显式保存 `metadata_unavailable` / `metadata_permission_unconfirmed`，不切换账号、不申请写权限、不阻断正常临床读取。已读到相互矛盾的回执则保护性失败。

**现场尚未验证**：这些元数据对象的只读授权、真实接口字段供给及真实模型质量。此交付不创建权限、不修改同步服务、不自动启用日常病程补充。后续如需授权，只申请上述对象/列的 SELECT 和 schema USAGE；本轮未执行。

## 历史、冻结及补跑

- 新自动材料范围协议为 `cdm-auto-v1`；来源可用性及发布证据进入材料指纹，避免同正文但不同供给状态错误复用冻结。
- 原材料快照优先读取；旧快照没有新增自动范围时沿用原合同。不修改旧冻结文件或历史结果。
- 补跑必须使用原任务已保存材料；缺少原材料不能读取当前 CDM 冒充旧轮次。
- 1026 专用来源入口不变。新字段 `positive_document_refs` 为空时不进入安全序列化，保持旧默认决策合同。

## 必要隔离验证

所有后端验证使用 `scripts/run_pr8_offline_tests.py`（禁外网/真实模型、隔离合成数据）。未运行全量质量门、真实质控或27份。

- 新自动取材测试21项通过：窗口不再必需；缺表/权限区分；指纹变化；相关规则隔离；技术错误保留；正文空但结构化字段可用；正面缺陷经真实 Binding/Finalizer 和合成 SQLite 保存读回；受控事实实际来源。
- 既有直接相关文件：准入、快照、Binding/Reducer、日常病程、CT、化疗、终末诊断，共456项通过。
- 病程执行器仅选 typed_017 / typed_018 / 077：28项通过。未放宽原医学断言；018新增引用仅用于新自动范围，兼容旧调用合同。
- 一次性原生PG18合成集群：5项通过，覆盖并发更新时材料/回执同版本、版本冲突拒绝、回执无schema权限、缺表和非身份缺列仍保留其他材料。使用已有运行器 `run_pr8_disposable_pg_tests.py`；各次结束均停止集群，未连接现有库。
- PG18不是现场PG16；未宣称完成PG16验证。PG用例中只为合成手术表注入测试主键合同，不修改生产40接口映射。捕获链测试隔离了既有账号权限预检，未把造数管理员冒充业务只读账号。
- UTF-8无BOM、LF及 `git diff --check` 通过；本轮源码/新增测试Ruff通过。既有 `test_daily_material_projection.py` 有17项存量lint问题，与HEAD逐项对比无新增，未扩展整改。
- 独立静态复审提出的正面缺陷被牵连、017早退位置、受控fact来源遗漏均已修正并复核。此结论不等于全体医学规则穷尽验证。

最小复跑入口（backend目录）：

```powershell
python scripts/run_pr8_offline_tests.py tests/unit/test_automatic_case_material.py
python scripts/run_pr8_disposable_pg_tests.py --pg-bin 'D:/Program Files/PostgreSQL/18/bin' --port 55873 tests/unit/test_automatic_case_material_pg.py
```

不合并、不推送、不部署、不连接业务库、不调用模型、不重跑27份。无需手工SHA核对或侧车文件。
