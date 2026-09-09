# 终末质控冻结出院时间贯通

## 根因与证据

任务创建的 RecordEvaluationHorizon 已保存出院时间及评价截止日；worker 又把快照放入 package_bundle.evaluation_horizon_snapshot。但是 running/final 服务到 prepare 的调用没有传递该快照，Provider 的 authoritative_discharge 分支重新读取执行时数据库值。

主协调使用真实 Provider 加只读内存 row_reader 复现：任务冻结 2026-06-10，实时来源改为 2026-07-20，最终 horizon_date 错误变为 2026-07-20。断言冻结值不变失败。这是已明确的冻结合同缺失，不需要猜测医院各时间字段的权威优先级。

## 最小方案与范围

复用已有快照，沿 bundle_service → prepare → Provider 传递；prepare 的带材料和 snapshot-only 两条内部路径都覆盖。不改 worker、任务创建 API、数据库、规则判定与场景识别。Provider 仅在 authoritative_discharge 且提供快照时消费冻结入/出院时间；旧任务未提供快照保持原有兼容路径，在院及禁用策略保持原口径。

冻结快照须属于当前病例，完整三坐标及可选 record_key 一致；旧 record_id-only 快照仅在其等于当前 visit_id 时接受。缺字段或非法时间关闭终点，逆序/截止日不一致/元数据或病例身份冲突关闭终点；任何已提供但无效的快照不能被当作缺失而回退实时数据库值。

原始资料行不被改写。derived evaluation_context.horizon 保存实际采用的冻结终点，已有诊断输入捕获包含该材料及完整 Fact。session_restore 直接恢复材料与 Fact，不重新执行 Provider，因此无需新建第二份捕获合同；用真实 roundtrip 验证这一点。

新增校验集中于现有 evaluation_horizon 模块，较长的入口/Provider 只增加参数及原分支接入；不新增 Resolver、状态机、缓存或资料来源。

## 验收标准及剩余风险

- 冻结 A + 实时 B/空/查询错误，均保持 A；反复执行不漂移，保留时分秒。
- 日期缺失、非法、逆序、快照归属错误，明确关闭，不回退 B。
- 真正服务入口经 prepare/Provider 使用 A；旧 None、running、disabled行为不回归。
- 排障输入冻结/恢复后仍 A，原始源 B仍保留B；不借诊断恢复重新解释终点。
- 不新增 LLM 调用、不访问源库、不修改保存任务或发布包。

原排障病例被任务冻结为 running，登记/首页缺出院值而出院记录有时间；本轮不改变其场景，也不擅自把出院记录字段提升为全局权威。场景入口混用 update_time、跨来源优先级仍需独立处理，不能宣称此修复已解决原病例全部截止问题。

## 完成验证

主协调独立回放原始红测：冻结 2026-06-10，实时 2026-07-20，修复后实际 horizon_date=2026-06-10。Provider/现有资料快照/输入捕获/离线恢复回归 156 项通过（1.21 秒）；真实服务入口新增 4 项通过（1.53 秒），既有场景不变性 3 项通过（1.25 秒）。

真实服务入口测试使用生产 SichuanQCService 与 Provider，仅将资料库读接缝替换为合成 row_reader；它证明快照真正贯穿入口，而不是只断言参数。冻结 6 月 10 日 09:30 被保留，实时 7 月 20 日仍作为原始材料保留。freeze_execution_inputs → restore_execution_session 原样恢复同一终点及原始材料，未改捕获schema或增加另一份资料链。

无 LLM 调用、无源库/数据库操作，未更新实际保存任务或正式发布包。前端没有修改，未重复前端全量类型/单测；无自动修复 ESLint 通过，既有编码脚本扫描 0 文件，另独立验证本轮文件 UTF-8 无 BOM/LF。此为合成变更源反例和生产入口回归，不冒充原 running 病例已改为 final。

最终补充真实 resolver 产出的空 basis 冲突快照反例：仍保留 authoritative_time_conflict；新增 19 项及既有 Provider 103 项，共 122 项再次通过（0.74 秒）。
