# P9-D实施记录

基线：最新业务线d063761e5，独立工作树C:/medqc-strata-p9d-20261103，分支codex/strata-p9d-counter-20261103。PR31尚未合入，明确cherry-pick abe9eba0f为ce79c401a。

## 外部交付已定位

用户补充实际目录后找到Downloads/ab-2026-10-30/provider-handoff完整14文件。此前D:/Sync_medqc路径不存在和旧handoff不完整的判断只适用于当时目录，不再构成打包阻塞。已人工检查纯标准库Counter、全部合同、资源和原向量，固定SHA256，原始verify.py离线17/17通过。

## 已实施

1. 复用原P9-B/P5-B，目标Qwen3.6强制完整Greedy、Thinking OFF、身份及预算；保留旧Qwen3.8和百炼路径。
2. CounterInstaller验证资源、模型/模板/计量身份、原向量、不修改输入和生命周期；只加载已审查DSH模块，不实现第二套分词器。
3. Direct/Gateway注册真实Counter；真实HTTP前核对/models和/health合同。开发机HTTP只使用Mock，不猜/props，不以回显model代替身份。
4. 缺组件、未验证形态、strict json_schema、超限、身份失败均拒绝目标请求，不阻止系统/百炼启动。恢复重新准入，必要输出上限保留。
5. 虚构病例验收入口只注入固定材料reader，复用正式执行、绑定、聚合和Canonical；不连接PG。技术结果留在审计，不冒充临床成功；成功结果逐项保存读取。
6. Windows包按已提交源码和交付白名单构建，含隔离Runtime、新编译前端、版本/资源哈希、固定虚构材料、操作指南；不含真实病例、密钥或开发配置。

## 验收分层

- Mock、真实离线计量向量、真实API三者分开记录。
- 包内Runtime必须重新验证实际Counter和原向量，阻断网络。
- DSH另行执行SSH、真实身份GET、固定探针和虚构病例业务链；开发机不执行。
- 不把13次服务器比对或旧口头20项说明当成开发机实际跑出的17项序列化向量。
- 本轮不新增迁移；普通可选产品UI需要既有062及全新p9d_*测试PG，开发机不执行迁移或账号创建。

详见[DSH操作、回滚及16K限制](2026-11-03-strata-p9d-delivery.md)。不推送、不合并、不部署、不改集成分支或业务库，不重跑患者质控。
