# Strata P1与最小P2实施边界

开发基线：`467af4e78`。工作树 `C:/medqc-strata-case-cache-20261030`，分支
`codex/strata-case-cache-20261030`。本轮只实现Gateway可选缓存和检查结果核验的显式适配，
不实现亲和调度，不改变医学判断、事件范围、候选裁剪、原有补核与保存合同。

## 1. 分工与公共合同

- Gateway owner：缓存配置、短期状态、单次Prime/规则调度、协议模型及错误trace。
- Adapter owner：最终隐私处理后的描述符、检查结果核验作用域、Worker客户端和Settings。
- Observation/verification owner：Prime实际成本、固定应答正式链、隔离反例。
- 主协调：关键diff复核、统一隔离验证、交付文档和本地提交；不移动业务集成分支。

线上新增可选 `case_prefix`，仅提供匿名病例键、证据摘要、上下文版本、单user文本内
的证据起始偏移和明确的剩余请求预算。不重复携带正文，不接受任意端点或凭据覆盖。
off/observe仍使用原有请求字段；prefix只支持明确Strata Gateway，直接路径不能绕过容量。

Gateway同时绑定真实resource/profile/model、显式部署版本及本次运行代次。缓存只保留
有限期、有限数量的checkpoint元数据，不跨重启持久化L0，不持久化KV或患者正文。

## 2. 输入与保守启用

Worker保留原始单user payload，只在明确生产者作用域内，在最终隐私处理后生成偏移。
Gateway只有实际Prime或复用已有checkpoint时才按完整证据与完整指令拆为两条user消息。
所有字符逐字保留，不加入system权限，不增加证据，不改输出schema。

没有可用checkpoint且剩余同组请求预算小于2时，不Prime，发送原始冷payload。
“原请求最多可能补核一次”不是两次已知请求：正常生产者默认预算1，不能为了演示命中
把潜在重试、选中规则数或批次大小伪装成明确的同前缀调用计划。

显式计划可在确定有多个同组调用时传入预算，用于最小闭环和后续真实接入。该预算只
决定是否值得尝试，不证明所有输入都净提速。真实Token边界、净成本和医学等价仍需
客户环境另行验收；本轮不连接现场。

## 3. 生命周期与失败

Prime和规则均经原Gateway准入、lease、生命周期和同一绝对deadline。等待single-flight
不占模型槽位；等待者仍服从自身预算。保留Strata资源2槽及FIFO，不增加病例锁。

Prime取max_tokens=1、非流式与关闭思考，移除规则输出schema/stop等后缀约束；只有
合法usage.prompt_tokens才可存L0。实际规则保持原max_tokens和输出合同。

已知Prime拒绝/无效元数据允许在剩余预算内走原冷请求。发送后超时/断连导致远端未知
仍触发原有quarantine，不能假定GPU停止后继续发。缓存miss而规则成功时保留该次应答，
不重复医学判断；失效只影响后续请求是否重新建立前缀。

## 4. 成本与证据

`_strata_cache`为Gateway保留的安全trace，只含策略、实际Prime/规则发送次数、Prime的
nullable Token/耗时和固定错误码，不含choices、Prompt或原始异常。错误响应也应保留
已经发生的Prime成本。Provider同名字段不能伪造Gateway成本。

规则原有 `_gateway_timing` 与Prime阶段分开；P0事件增加独立purpose=prime观测，不能
把一次逻辑判断的Prime算成临床结果、重复attempt或免费调用。未知成本不补零。

验证只用合成输入、MockTransport、进程内ASGI与必要的合成内存SQLite；通过既有
offline runner禁真实网络、dotenv、业务数据库及普通子进程。测试可证明请求、协议、
取消、失败和保存合同，不可证明真实Strata缓存命中、实际GPU性能或医学准确率。

## 5. 当前状态

本文件记录实施边界；最终实现、实际命令/结果及剩余限制将在交付记录补齐。没有对
客户机、Strata、业务数据库、运行服务或集成分支进行操作，也没有执行真实模型。
