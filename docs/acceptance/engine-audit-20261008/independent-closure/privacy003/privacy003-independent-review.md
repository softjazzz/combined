# PRIV003 独立复核：限定发送边界

固定提交：`511bd12dbd96d3f65927963c956bc8a132444c0f`。工作树：`F:/MedQC-worktrees/qc-fix-privacy-v2-20261008`。仅 0609，本次未审 0916。

**结论：支持此提交的三脚本发送边界与可信 collector 的限定集成，本次范围无阻断缺陷。PRIV003 不记全关闭。** ordinary-shadow、semantic20 的真实 CLI 没有合法身份来源接入，仍拒发；本轮没有恢复真实外发。实际模块导入/配置边界只作静态证据修正，没有执行 CLI、读取 `.env`、PG、患者或模型。

## 独立冻结与执行

预期及原始合成反例先冻结于 `frozen-counterexamples.json`，源码的 Git blob 与工作树字节完整 SHA256 先冻结于 `source-manifest.json`。本次独立编写断言，复用修复者 `offline_support.py` 的 AST 装载和内存计数接缝，没有调用修复者的测试函数。当前 `_perform_observed_attempt` 源码经 AST 提取；观察、capture、transport 为内存替身；业务执行、配置构造、材料解析为替身。

第一次执行在 Windows asyncio 初始化的 stdlib socketpair/self-pipe 处被网络守卫拒绝，**0 个冻结用例运行、无生产结论**，记录保留于 `first-attempt-infrastructure.json`。唯一探针修正为单个 asyncio.run 初始化完成后在 main 内禁止 socket connect；fixture、预期、生产代码均未改。获 root 再次唯一槽授权后只重跑一次：退出码 0，**7 组全部通过，0 失败**。测试完成即释放唯一槽。

| 冻结项 | 验证与结果 |
|---|---|
| F01 | ordinary 缺 collector 在 source/config/attempt 前拒绝；semantic 两分支缺 collector 不读 source、返回 privacy_boundary_error、call_count=0。通过。 |
| F02/F06 PHONE | 输入回调先断言原始 `PHONE_13800138000_BEARER_SECRET` 与 `13800138000` 确实存在，并收集原始电话；两个 semantic 分支送达内存 transport 时标记/数字/姓名均已去除，`130mg`、`1.5h`、`头孢呋辛` 保留。ordinary 有标签姓名也脱敏。通过。 |
| F03/F04 | closed、masked name、只有三个坐标、dict、callable、同 patient/visit 错 institute 均拒发；semantic source row 的显式 CaseRef 错例也拒发，观察/capture/transport 无事件。通过。 |
| F06 residual | 无标签已知原始姓名残留，ordinary 拒发且内存出口事件为零。通过。 |
| F05 | provider 预检通过、wrapper 已创建后 close，既有 wrapper 仍拒发且无事件；另一次模拟 attempt1 合法，close 后 attempt2 拒绝，仅第一轮 transport/观察存在。通过。 |
| F07 | 与原 Scenario 相等但不同对象的同标签 clone 被拒；替换 SCENARIOS tuple 被拒；原十个对象在替身流程均允许经过发送边界。通过。十个业务期望由替身映射，不能当作医疗 Golden 判据通过。 |
| F08 | 异常/取消后 scope 恢复；借入 collector 不被脚本误关；作用域外延迟子任务拒发，出口无事件。通过。 |
| F09 | 静态证据：AST main 不能证明实际 CLI 导入时不读配置。实际 CLI 未执行。 |
| F10 | 七个 PRIV002 公共模块逐一 Git blob 对比父提交，全部不变。静态通过。 |

上述实际执行结果见 `independent-probe-result.json`，探针见 `independent_probe.py`。实际网络模型/PG调用为 0，`.env` 文件读取为 0；只读取固定源码与 helper，并使用合成 source rows。

## Spec 轴：发送边界与身份来源

三脚本的 `_source_identity_provider` 均限定 `_Luxian0609IdentityCollector`，以 `CaseRef(institute_id, patient_id, visit_id)` 精确取 provider；`_bind_script_identity` 合并 source 与材料 provider，source provider 每次调用重新检查，并未缓存原始值快照。collector 的 `provider_for_case` 每次检查 active、invalid、精确 holder、原始姓名；`close` 清空持有值。wrapper 和最终 attempt 再检查生命周期，不能依赖首次预检永久授权。

- ordinary：`_run` 先拒缺失/伪造 collector，再由既有 source selector 取得坐标，以 exact source provider 预检，进入 case scope、构造 evidence session、合并 provider、再预检，随后才构造未注入 client 并包装 native 执行。合法类型但已关闭/错例 collector 可能先经过既有 source selector；承诺是模型出口拒发，不是所有输入读取都先拒绝。
- semantic：每个 case 先取可信 source provider，失效则 privacy_boundary_error 并跳过 row_loader；copy 与 consultation 分支在 scope 内合并材料 provider，`protect_current_payload` 在 guarded.generate 前完成检查，失败不计 call_count。显式材料坐标错例不能继承本 case 身份。
- 028：`_FIXED_SCENARIOS = SCENARIOS` 保存原对象 tuple；`_session_for` 同时检查 tuple 身份与成员对象 `is`，`_run` 拒绝替换 tuple。标签、相等 dataclass、新对象不能取得权限。每个原场景由内部固定合成身份 collector 进入 scope，finally close；本次没有执行实际模型或医疗判据。

Spec 独立静态复核没有可行动的新增违反，7 组探针支持以上限定判断。没有把 masked bundle 视为能恢复原始姓名，也未将坐标-only provider 视为完整身份来源。

## Standards 轴：无硬性违反，一项非阻断判断

独立 Standards 复核硬性违反 0。P3 判断项：三脚本完全重复 `_source_identity_provider` 与 `_bind_script_identity`，未来修改容易漂移；本次按限定修复范围保留，不建议为此修改 PRIV002 公共模块。此轴与 Spec 分列，不合并成安全阻断。

## 真实 CLI 与证据限制

ordinary `main` 不注入 collector，会进入固定 refusal 分支；semantic `main` 仅解析参数并输出 fixed trusted-source refusal，return 1。两者目前**拒发未恢复**，需要另外接通合法的 request-scoped 原始身份来源才可讨论功能恢复。本次没有做该接入。

实际 ordinary 在模块顶层导入 `app.database.connection`（脚本第 18 行），该模块第 16 行调用 `load_dotenv(_env_path)`。semantic 顶层 native execution/reader 导入可到 database/settings；Settings 的 Config 第 348 行声明 `.env`。因此所有 AST 装载下的 main/源读取拒绝断言，均不能证明真实 CLI 导入前没有配置读取。该事实只用于纠正证据表述；本轮未实际读取 `.env` 或执行应用启动。修复者名为 real_cli 的 AST 测试也不能作为真实 import/config 证据。

本轮没有覆盖真实配置构造、HTTP provider、持久化日志/观测后端、真实原材料解析/ORM读取、完整 CLI argv 启动或医疗业务判据。内存 observation/capture 的先后顺序证据支持阻断发生于最终 attempt 出口之前，不能推导所有日志系统均已安全，也不能推导未审出口安全。

## 源码索引与固定范围

执行后再次核对，11 个预冻结源码的工作树字节 SHA256 全部未漂移。AST helper 另加载 CaseRef 文件 `apps/medqc-web/backend/app/services/case_identity.py`，其完整 Git blob/工作树 SHA256 在 manifest 补充记录；该项在执行后测量，与固定提交字节一致，未声称测试前已冻结。

所有以下相对路径均以 `F:/MedQC-worktrees/qc-fix-privacy-v2-20261008/` 为根。完整文件 SHA256（同时记录 Git blob 与工作树字节）在 `source-manifest.json`，也嵌入 JSON 主报告。

| 文件 | 关键行 |
|---|---|
| apps/medqc-web/backend/scripts/run_luxian_0609_consultation_ordinary_shadow_validation.py | 18 顶层DB导入；217/227 provider；240 _run；307 main |
| apps/medqc-web/backend/scripts/review_luxian_0609_semantic20.py | 15/16 顶层native导入；448/458 provider；471 build；531/580 最终预检；704 main |
| apps/medqc-web/backend/scripts/run_luxian_0609_028_synthetic_golden.py | 76 固定tuple；79/89 provider；102 原对象检查；143 _run |
| apps/medqc-web/backend/app/services/luxian_0609/privacy_identity_context.py | 63 collector；106 capture；124 live provider；136 close |
| apps/medqc-web/backend/app/services/luxian_0609/privacy_request_scope.py | 118 强制 collected identity；166 protect_current_payload |
| apps/medqc-web/backend/app/services/luxian_0609/llm_prompt_privacy.py | 409 wrapper.generate |
| apps/medqc-web/backend/app/services/qc_llm_client.py | 348 _perform_observed_attempt |
| apps/medqc-web/backend/tests/privacy_closure_20261008/offline_support.py | 50 内存计数attempt；214 AST脚本装载 |
| apps/medqc-web/backend/app/database/connection.py | 16 load_dotenv |
| apps/medqc-web/backend/app/core/settings.py | 348 env_file |

固定提交只改三脚本、相关测试及验收文档，七个 PRIV002 公共模块相对父提交的 Git blob 无变化（具体路径/blob 在 manifest）。本轮不改任何生产/测试源码、不提交、不回退其他工作。

后续可安全离线继续：收集固定提交证据、用合成输入复核身份provider契约。恢复真实 ordinary/semantic CLI 前的开放前置：已有合法读取所得原始身份必须进入 request-scoped 内存 collector，并贯穿准确 CaseRef 与活跃scope；不能额外读 PG、全局缓存/持久化原始值，不能从 masked bundle 假造恢复。该前置未接通，真实外发继续拒绝。
