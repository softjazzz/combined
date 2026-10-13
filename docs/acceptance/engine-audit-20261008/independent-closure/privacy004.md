# PRIV004 固定提交独立复审

审阅固定提交 `6b8fa3e583d22979c305f4959db8ee8953c80e68`，父提交 `041b3be67a9e34df7c0d72ce83e0c53c0d89687a`。所有生产源码来自固定 `git show` 副本，只审 0609；未编辑生产/共享测试，未混读后续工作树修改。

结论：本次限定的0609病例作用域、provider合并与租约失效边界未发现可确认新增缺陷。静态复核与执行前冻结的13项独立反例全部通过；完成层级为固定源码/实际方法体消费边界，不能宣称全工程或部署通过。PRIV002原身份来源仍开放。

首次标准库探针失败于 runner 合规 DTO 断言，静态定位为计划替身未提供 `package_plan.selected_rule_ids`；已仅补齐探针，首轮失败记录保留 `harness-first-failure.txt`。根任务重新授予独占槽后，命令 `python -B F:/MedQC-worktrees/review-artifacts/privacy004/probe.py` 返回13 passed / 0 failed，进程约0.44秒。修复的是探针替身，不是生产源码。

## 作用域与实际消费边界

`privacy_request_scope.py` 为 scope 增加共享租约、病例三坐标和 provider 合并标识。完整三坐标一致、外层租约有效时，准生产入口继承外层 provider 并共享租约；否则建立独立、初始未绑定的 scope。绑定新 provider 时，同病例内层组合旧与新 provider，每次发送重读双方，任一失败在闸门处固定拒发。内层退出恢复外层 provider，拥有租约的边界退出置 `active=False`，阻止继承 ContextVar 的延迟任务继续发送。provider 和坐标不进入 dataclass repr。

`preproduction_runner.py` 实际 `run_luxian_0609_preproduction` 添加显式病例 scope 装饰器。取消仍经 `finally` 恢复上下文；`CancelledError` 不被 runner 的 `except Exception` 转为客户 DTO。正式0609入口退出也失效其租约。非0609无 scope 时仍按原样返回 payload。

独立 `probe.py` 加载完整纯隐私模块、完整客户端类的 `generate` 与最终 attempt 方法、完整准生产 runner 函数和完整 prepare 函数。prepare 执行到实际身份 provider 构建/绑定/客户端包装完成后的首个规则 loader，用专用 sentinel 停止；随后在同一 runner scope 内消费真实客户端方法体。runner 业务校验/聚合、adapter、计划、配置、transport、观测均为明确内存替身。不是完整工程，也没有执行下游规则或正式 worker/API 链。

冻结反例覆盖当前身份拒发、同病例旧/新身份并集、旧 provider 故障不可替换、跨病例/缺坐标/布尔坐标不可继承、安全请求保留 transport、第二次调用重读失效 provider、外层退出后的延迟子任务、同病例内层退出后的外层租约、取消恢复与子租约失效、并发病例隔离和无 scope 兼容。

逐项结果见 `results.json`。拒发均断言发生在 observation/capture/transport 替身副作用之前；safe 请求仍经过这三个接收端。第二次调用使用同一真实客户端 `generate` 方法验证闸门再次消费provider，不等同于本次已观测客户端长度重试路径。取消验证真实runner传播取消、外层provider恢复及异病例子任务租约失效；父边界退出也验证延迟子任务拒发。并发验证各自已知身份集合独立、repr不含身份/病例坐标。

冻结 `expectations.json` SHA256：`0d9bcd6a34abe629c39196bfeadf8c1f19ab0a3202382dcc08ff6fd4afd52098`。首轮和复验没有改变反例期望。

## 覆盖限制与门禁

owner 的 20 项离线测试包含既有005与004用例，004用例接入真实 runner 函数/装饰器、3条执行绑定语句及最终 attempt 方法，业务合同/聚合为替身；它们支持隐私接缝证据，不是全工程验收。本报告独立补充完整 prepare 至绑定边界和完整 client 消费方法，仍不替代最终集成 SHA 工程测试及客户正式链。

PRIV002 原身份来源仍开放，本修复不能证明已知身份集合完整。004真实 Husky 通过为 root/owner 给出的独立提交证据，本审计未重跑钩子；005历史缺本地 `.husky/_` 事实不因004而改变。最终正式链、真实观测日志、安装/权限/模型/部署门禁另行记录。

产物：`expectations.json`（执行前冻结）、`probe.py`、`results.json`、固定 `*.fixed.py` 副本、`harness-first-failure.txt`。未使用pytest、真实模型、PG、`.env`、服务或浏览器，未编辑生产源码。可确认findings/defects为空；上述工程/客户链缺口为门禁限制。
