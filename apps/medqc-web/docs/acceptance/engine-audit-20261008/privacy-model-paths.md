# 0609 隐私发送边界旧成果归档（2026-10-08）

本次只归档既有证据和限定后续修复边界，不新增审查、测试或生产修改。原审计版本 `7b894dc84491b7b72eb096de58fe61f772cc0080`。0916、其他引擎与智能助手已标 `scope_excluded_by_user`，不计本次分母、阻断项或完成率。缺少真实验证与未经审查分别记录，不相互替代。本报告不授权恢复任何真实模型外发。

## 已完成的已知身份保护

`2f7ff8091` / `7aa4737fe` 已有成果以 [已知身份发送边界验收](../2026-10-08-known-identity-send-boundary.md) 为索引，文档记载10个聚焦文件171项通过。本轮未重跑，也不重新宣称独立核验这些提交或171项。

- 0609正式running/final与orchestrated入口建立病例ContextVar作用域，异常、取消及嵌套退出恢复。
- execution从当前材料及三坐标建立identity provider；prompt/kwargs包装保留脱敏并拒绝已知身份残留。
- `SichuanQCLLMClient._perform_observed_attempt` 在每次HTTP尝试、包括length重试时，对最终payload检查，先于观测、诊断捕获及transport。
- 身份集合/provider不进入repr；身份上下文和残留异常使用固定提示。

这些属于已完成的“上下文实际已知身份”保护，不能因未验真实模型而改标未审，也不能扩大为全部患者身份完整覆盖。

关键文件索引：

| 文件 | 既有职责 |
|---|---|
| `backend/app/services/luxian_0609/privacy_request_scope.py` | 入口scope、绑定provider、每次最终payload守卫 |
| `backend/app/services/luxian_0609/privacy_identity_context.py` | 读取当前已知材料身份并核验归属 |
| `backend/app/services/luxian_0609/llm_prompt_privacy.py` | prompt脱敏、已知身份检测、wrapper |
| `backend/app/services/luxian_0609/execution.py:367` | 构造/绑定provider并包装客户端 |
| `backend/app/services/qc_llm_client.py:348` | 每次attempt在观测/capture/HTTP之前调用守卫 |
| `backend/app/services/sichuan_qc/running_final_bundle_service.py:39` | 正式bundle入口scope |
| `backend/app/services/sichuan_qc_service.py:1167` | 正式orchestrated入口scope |

## 已知但未闭的上游身份覆盖缺口

`bundles/assembly.py:2348` 把既有PG读取的 `patient_profile` 交给builder；`bundles/factory.py:49` 只保留masked姓名/手机/证件。正文仍可能含无标签原名，而多数0609源字段投影也不带原名。当前provider只有三坐标时可满足非空，但无法识别已被上游丢弃的原名；这是一项**已审查、已合成复现、未修复**的覆盖缺口（PRIV-002），并非已完成gate失效。

此前限定纯函数合成证据位于 `.tmp/engine-audit-20261008/privacy-model-paths/offline_repro.py` 和 `offline-repro.json`：实际factory输出不保留原名身份字段，provider只知3坐标，scope守卫后正文合成无标签姓名仍保留。使用已知原名的同一attempt方法两次均在观测/capture/transport之前拒绝；没有scope时两次进入内存capture/transport替身。本归档轮不再次运行它们。复现移除了应用相对导入并使用内存替身，不等于正式应用E2E，也没有网络、PG、`.env`或真实病例读取。

后续真实0609外发前应先闭合原始身份来源，不以检测未命中、零Token、聚合调用量或旧171项推导原名完整覆盖。

## 最小request-scoped内存provider接入建议

1. **scope早于身份丢弃点。** 在一个由主协调选定的0609构包调用方、既有bundle获取/装配之前建立病例scope。仅给evaluate入口加scope过晚，不能恢复已丢的patient_profile。
2. **只捕获已经合法读取的身份。** `bundles/assembly.py` 既有 `_fetch_patient_profile` 之后及builder调用处，将本次patient_profile的身份值交给非序列化callback或request/case ContextVar。不得追加PG查询，不得修改返回bundle、可保存metadata、结果或日志字段。
3. **execution显式消费同一provider。** `privacy_identity_context.py` 把上游内存值与既有材料/三坐标核验结合，缺失、读取失败或归属不一致拒发；`execution.py:367–373` 在同一病例scope内绑定并包装。保持现有最终payload每次attempt守卫，finally恢复，不跨病例缓存原值。
4. **缓存bundle是明确失败场景。** 如果只拿到masked缓存bundle且本次合法上下文没有原身份，不能从星号逆推，也不能为补覆盖临时查PG；应阻断该真实外发，或使用调用方本来已持有且经归属校验的身份内存上下文。

建议生产写入白名单仅为 `privacy_identity_context.py`、`privacy_request_scope.py`、`execution.py`、`bundles/assembly.py` 中0609可选内存采集接缝，以及主协调确定的**一个**构包调用方。若必须传递私有provider参数，再限定 `running_final_bundle_service.py` 或 `sichuan_qc_service.py` 中实际需要的一个入口。`qc_llm_client.py` 与 `llm_prompt_privacy.py` 已验guard可保持现有实现，无需扩大公共客户端重构。

排除写入：0916、其他引擎、bundle序列化合同/factory/持久化schema、数据库迁移、生产配置、业务判据及未经分配的共享测试。本建议只提供范围，尚未授权或实施生产修改。

## 其余既有0609路径观察

- PRIV-003：直接native golden、ordinary shadow与semantic20辅助脚本没有建立已知身份scope/wrapper；脚本命名、结果repr检查不能验收含真实病例的发送。纯合成脚本也可能实际联网。
- PRIV-004：准生产runner共用execution的prompt/kwargs包装，但入口未建scope，不能据此签收最终payload每次attempt保护；属于已审的部分覆盖。
- PRIV-005：客户端上游错误summary只遮API key，既有合成姓名仍保留；`execution.py:362` 固定消息的 `logger.exception` 仍会附异常正文和traceback。诊断是受限内存原文载体，不能直接导出。日志/发布链仍有待闭合面，不据此声称真实患者已泄露。

详细findings、已完成保护、范围外归档、生产写入建议与此前合成计数见同名JSON。当前可继续仅合成且明确禁用网络/PG的离线工作；本轮无新增执行。
