# 日常病程补充业务适配实施计划

> 执行方式：subagent-driven-development，单一实现者修改此工作树，独立审阅者只读。

Goal：按已批准daily-material-r2-v3合同，将补充材料贯通同事务捕获、实际Provider、目录与不可变任务快照。
Architecture：固定d7dc窄只读读取模块随业务交付；公共projection owner仅搬运判定和选择，不重新reconcile。复用既有RR连接和case-material-v1全文对象/引用。新增独立供给scope，不把查询完整性当上游完整性。
Tech：Python/SQLAlchemy/PostgreSQL；Vue已有文书定位。
Spec：用户本轮详细授权、Downloads/medqc-cache-clinical-supplement-strategy-20261112-r2、固定d7dc交接及独立复审。

Baseline：06c2fd4fa（含未合入PR57反馈安全补修）；此工作树全新干净。sync d7dc包已自动验证97清单/98文件和五模块完全一致。

Constraints：默认关闭；仅独立CDM；无外部工作树运行时路径；不改同步算法/反馈安全补丁；不部署推送合并现场连接真实模型/规则服务/OCR；只合成离线及必要一次性隔离PG，不读.env患者材料，不重跑27份/1026。

## Tasks
- [x] 1. 先用合成失败测试锁定窄只读manifest读取与SQLAlchemy同连接适配。随业务交付固定源身份、只读代码闭包/固定投影，不带connect/publish/reconcile权限；异常失败关闭；默认关闭。
- [x] 2. 建daily material projection统一owner：目录保留全部版本，正式事实仅selected/rule_usable，完整scope/field_availability及confirmation_basis保持。daily来源身份由namespace/object/native key/version组成。接capture与同事务current view。
- [x] 3. 接snapshot/native/course Provider和程序事实，scope与查询完整性分开；在实际缺失推断消费者加供给前提，不在renderer/保存层重判。独立可靠缺陷保留。相关执行器仅按真实调用点最小修改。
- [x] 4. 现有不可变快照携带manifest/basis并保持旧文件兼容；准备引用先于执行，重试原快照。目录全文/证据定位/导出携带版本身份，修type::id碰撞。
- [x] 5. 必要合成整链：真实业务取材/Provider输入/文件历史回放；等价新旧任务、冲突覆盖、M01/M03、同RR中途发布、对象与引用故障/并发、损坏拒绝、默认关闭。固定fixture/真实PG边界明确，不执行临床规则服务。
- [ ] 6. 固定本地提交；独立Spec及Standards复审，P1/P2补修；交付完成矩阵、权限精确草案、现场只读联验说明。禁止把开发通过写成现场上线。

## Review focus
多来源同号定位；scope未知不能生成缺失缺陷；同RR不能再开连接；fresh=false旧可靠材料不等最新全集；旧任务/1026原绑定不变；confirmation_basis/完整proof同时保存；并发首次引用及跨资源失败恢复。

## Rulings
用户已明确批准设计和实施，不重复询问方案。native worktree工具长期无响应且未创建树，改用git worktree add成功；D:/MedQC-worktrees/daily-material-business-v3-20261112 / codex/daily-material-business-v3-20261112。所有实现写入仅一位Agent，其他Agent只读或在外部临时目录验证，遵守单树单写者。