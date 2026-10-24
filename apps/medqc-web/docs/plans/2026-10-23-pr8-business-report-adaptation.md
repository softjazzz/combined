# PR8 业务集成线定向适配：第一阶段

## 基线与硬边界

- 独立工作树：`C:/medqc-pr8-adapt`；独立分支：`codex/pr8-business-report-adapt-20261023`。
- 起点：本机业务线已提交 `754fa2f7af23e9d60209f3cbbcf96e3d59d9813f`。它包含远端 `codex/business-agent-integration=8c005ee08d7caf43df53cbe1821016736836de8e` 后的 7 个提交，不能把远端当成本机完整产品基线。
- 七个提交为 `bd3b0440e`、`ce22fd69f`、`99e876e40`、`9344af329`、`cb319f042`、`0b1c43fd2`、`754fa2f7a`，包含客户批量结果/质控记录视图及医生“智能分析面板”原弹窗恢复。
- 只读核对过 `C:/medqc-agent-merge`；其脏文件仍为两份 AGENTS、`qc_sichuan.py`、`custom_qc_workspace_service.py`、`taskHistoryPresentation.ts`，及未跟踪 `.claude/`、意见冻结目录。这些内容不在本次起点中，未搬运、未覆盖。未修改该工作树、`C:/medqc-safe-source-sync` 或 D 盘主工作树，未操作其服务。
- 没有移动/推送业务集成分支，没有 merge/rebase/reset/clean/强推。PR8 固定 base 仍是 `8c56466e906cad9c2926464ad9c8ff5d3cfbf635`；本适配代码不进入 PR8。

## 已落地的定向代码

1. 只在目标线 `workstationNav.ts` 追加四个分析入口，原19个入口和权限解析不变；在目标线 router 追加四个 V5 子路由，`admin/qc_manager`，直接懒加载页面，不重定向 Dashboard。
2. 从 PR8 `88e8f864b` 移入原本不存在的四报表页面、其直接面板/样式、六个 API 客户端和相关测试。没有移入27项指标页面，没有改27项计算。`auth.ts` 仅补可选 `institute_id` 类型，不改变登录行为或把 HTTP 声明当服务端授权。
3. `reportPage.css` 的收缩修复限于报表根容器 `min-width:0/grid-template-columns:minmax(0,1fr)`；不改全局字距、外壳、MQ Token 或主题。
4. 目标线已有 Canonical 摘要读取器新增默认关闭的 `include_rule_set_context`。仅在原选择器已判 `ready` 时附加所选行的 `root_job_id/envelope_id/rule_set_key/rule_set_version`；原调用输出、结果条目、状态、选择器、排除名单和客户视图不变。没有移入 gap 分支的多规则版本选择逻辑，没有任意旧轮回查，也没有新增质控执行或写入。
5. 应用 `.gitignore` 原有 `reports/` 会吞掉新增源码目录；仅例外放行 `/src/views/qc/reports/`，没有放行生成报表或私有证据。

**本阶段不是后端接通或可合并交付。** 目标线尚无以下报表 owner/API/持久模型，不能把页面的合成 API 验证称为真实报表可用。未在 `main.py` 注册一个依赖不完整的 router，也未用旧 payload 或零值兜底。当前直接运行这些页面会如实显示 API 不可用；应在后端与迁移适配完成前保持在独立开发分支。

## V7.1 保护证据

`workstation-report-protection.spec.ts` 固定 `754fa2f7a` 的 Git blob，比对18个文件的规范化内容：Layout、MqIcon/MqIconTile/mqIcons、main、tokens、全局 mq-components、workstationTheme、GlobalAssistantHost、确认框/controller、医生面板和本地新客户视图。全部保持相同，包含目标图标 `failed/pending`。

导航测试保留原19个 key 的顺序、手术目录/规则验收、DRG五个页内地址、选中项和面包屑，四报表按原 `meta.permission` 隐藏；没有用 gap 的 AntMenu 替换目标配置式 RouterLink 外壳。这证明固定保护集在**本适配差异**中没有覆盖，不保证尚未纳入的脏改动，也不等同全站视觉回归。

## 后端真实调用链与未解决依赖

| 入口/能力                                  | 源头依赖，目标当前缺失或合同不同                                                                                                                             | 本阶段状态                                                                                                            |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| 病历质量 summary/records/CSV               | `quality_reports` router → `record_quality_report_service` →可信持久账号 scope、病历池/登记补充的机构 SQL → Canonical 摘要 →评分/审核/人工缺陷批量 owner     | 仅桥接目标 Canonical 可选锚点；owner/router 未移入                                                                    |
| 病案首页统计                               | 同 router → `frontpage_quality_report_service` → `modern_case_qc_result_service` 的 source+三坐标排名SQL →池维度                                             | modern owner、现代 QCResult/Defect 身份列均缺，不可回退旧 result_id/record_id                                         |
| 特殊病历报表                               | `special_record_reports` → source/config、完整出院队列 `case_scope_service`、基础报表、`special_report_scoring_service`、冻结规则分类                        | 分类配置/评分绑定/完整队列合同未接，不拿当前池冒充出院分母                                                            |
| 质控员工作分析                             | `staff_work_analysis_service` → QCRecordReview、QCAppealReview、任务/人工历史、现代整改事件、时间窗、缺陷冻结快照、批量显示名                                | 事件模型及来源归属未接，不能用任务完成量冒充审核量                                                                    |
| 直接面板：18项核心制度、人工质控、整改分析 | 各自 router/service、制度目录/冻结版本、现代整改与申诉目标、人工审核 owner、事件时间线                                                                       | 前端依赖已带入，后端未接，不宣称新功能完成                                                                            |
| 授权                                       | `report_institute_scope` → `_person` → `user_scope_owner`；活动 SysUser +持久机构                                                                            | 目标 SysUser **没有 institute_id**；必须先核实并适配目标认证 owner，不可仅加HTTP字段                                  |
| 评分与审核                                 | `scoring_service/scoring_standard_service/rule_set_version_service/record_review_service/manual_defect_review_service/record_review_defect_snapshot_service` | 目标缺这些模块及模型。共享 query_service 也没有 `build_review_anchors/load_scoring_departments`，不能只复制首次五提交 |

源 report 的默认 Canonical 调用是 `build_luxian_0609_completed_record_result_summaries(include_items=True, include_rule_set_context=True)`。目标已有同名读取器，但只支持当前固定规则版本；本次只加返回锚点，不擅自扩大候选。目标 `custom_qc_workspace_service` 已有 `readonly=True` 构造模式，后续报表适配必须使用它，不能触发旧构造器的兼容建表/补列。

## 迁移衔接设计，未执行

共同祖先为 `20260915_000044`。源码检查确认 snapshot head 为 `20261003_000084`，目标 head 为 `20261020_000050`；这是两个不同分支，不以末尾序号排序。`76` 的真实 parent 是 `72`，不能编造73–75迁移。

### 目标必须保留的六个 DDL

| 完整 revision     | 对象与关键合同                                                                                                                 |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `20261002_000045` | `qc_business_feedback`，split=qc，否则默认 schema；创建者/request和创建者/session/reference两套唯一约束；不改变 Canonical 结果 |
| `20261003_000046` | `qc_business_actions`，同 schema 策略；owner/session索引，预览/确认/幂等及关联 job                                             |
| `20261006_000047` | 按实际 search_path 解析 `visit_index` owner；补无时区镜像成功时间、两个非空默认30的同步间隔，已有列先核合同；拒绝自动降级      |
| `20261016_000048` | cdm/public 已有病理 `eye_findings` 扩 Text，不截断降级                                                                         |
| `20261016_000049` | cdm/public 医嘱执行/撤销时间、药物计划结束 timestamptz、检验 `report_status`；保留证据，不自动降级                             |
| `20261020_000050` | split仅cdm，否则public；日常/上级/术后首次病程签署文本与 timestamptz；必需表缺失先拒绝，不自动降级                             |

### Snapshot DDL 的对象组和前置条件

| 实际 revision（日期以前述迁移源码为准） | 对象/约束及适配判断                                                                                                                                                                                                                                              |
| --------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 45–51                                   | qc/public任务scene、病例三坐标/refs、规则集/版本、task_qc_runs及run_scope；旧单record_id不能自动补齐身份                                                                                                                                                         |
| 52–56                                   | qc/public缺陷origin CHECK；result/defect/notification现代来源+三坐标 CHECK/索引；queue现代/旧身份分区索引；任务完成轮次；人工独立审核态与创建人。56对qc.status历史Text可空默认open、public.status VARCHAR(20)非空无默认有**不同精确基线**，不能按ORM猜实际库兼容 |
| 57–58、67、82                           | qc/public `qc_record_reviews`：结果/请求幂等唯一、阶段/决定/非空身份/理由/轮次 CHECK，后加上下文及scene、JSONB缺陷快照；必须绑定保存结果，不代替任务完成                                                                                                         |
| 59、63–66                               | 过滤模板扩展、任务模板、配置版本与周期调度；属于间接owner依赖，不为四报表盲搬整条任务写链                                                                                                                                                                        |
| 60、81                                  | 任务病例department、JSONB分类冻结，历史NULL未知，不反填当前科室/分类                                                                                                                                                                                             |
| 61–62、69、83–84                        | qc/public冻结规则版本与唯一发布约束；评分标准/分组/项目、默认绑定与范围CHECK；科室范围；特殊报表purpose+scene评分绑定和版本；首页场景CHECK扩展。不能拿当前规则配置替代历史冻结版本                                                                               |
| 70–71                                   | 文书定义与QR登录；71基于sys/public账号owner的FK与会话CHECK。不是四报表必需，暂不移入，不重做目标登录                                                                                                                                                             |
| 72、76                                  | 现代申诉目标来源约束/开放目标唯一索引；实际可信sys_users owner新增VARCHAR(128)机构与机构/科室索引，非全库同名表一起写                                                                                                                                            |
| 77–80                                   | qc/public现代整改表/事件、事件version/CAS/request/目标唯一与提醒撤回关联唯一、派发/提交文书快照、病例沟通记录；不得替代目标 business_feedback/actions 的独立事实                                                                                                 |

以上是**迁移源码合同**清单，不是实际数据库列/约束实测，也不是完整DDL兼容证明。本阶段没有复制迁移、建立新merge head、stamp、删迁移或连接PG。

### 明确的下一阶段衔接门禁

1. 先固定目标已提交基线，单独对未提交的认证/Canonical调用链差异做归属复核。按实际持久owner设计报表只读适配和最小模型，不覆盖目标认证、主执行器或业务动作。
2. 创建全新、完全合成的 PG 测试库，构造 qc/public/sys/cdm 的两套**已知基线**。缺一套预期表、默认值、约束或可信owner就失败；不得用本机客户/业务库推断后试升级。
3. 对表定义做三路比较：共同44 → snapshot84、共同44 →目标50、目标50 →报表所需增量。命名相似不表示同表；现代整改与业务动作保持独立。只为已评审对象编写目标基线上的兼容增量；不直接运行整条gap迁移。
4. 若最终保留两条原迁移历史，先在隔离库证明“目标50补snapshot对象”和“snapshot84补目标对象”两条路径得到相同列/约束/索引且原业务数据不变，再用新兼容revision和显式双parent merge revision记录汇合。若选择只移植功能DDL，则新revision从目标50线性追加，不能假装原84已经执行。两种迁移图策略不能混用；本阶段未批准/实现任一种上线脚本。
5. 验证升级前后保护集、拒绝漂移/多owner、历史NULL未知、结果锚点、事务/CAS及角色机构边界；两条路径未执行前均标记**未验证、不可合并/部署**。

## 已执行验证

最终定向结果：前端 **18文件198项通过**；后端 **23通过/104未选中**；应用全量类型检查、只读 `eslint src`、三个相关Python文件Ruff通过。所有测试均非生产、非真实质控；未跑全仓全部测试。

- 目标 Canonical 定向：23 passed / 104 deselected，禁dotenv/网络/非SQLite runner；覆盖原有投影、跨机构同号、歧义/重复/坏Envelope不带锚点，选中结果只读、原输出与输入不变。没有运行真实规则/模型。
- 前端首轮17文件171项通过；补充竞态与保护集后独立两文件43项通过。完整合并后的计数以最终提交记录为准，不能把两次数字直接相加。首次新增路由测试类型错误已修正；首次补充测试错误使用loading禁用的刷新按钮、保护路径写错，修正测试后通过，未放宽业务断言。
- 浏览器3032独立临时服务/标签，只用合成账号/API；后端代理指向不可用端口。四报表入口及目标RouterLink外壳可见，病历/首页汇总和各一份合成病例下钻渲染。两个当前CSV正例实际下载；持有各一个有效请求，先改筛选，再成功fulfill 200 CSV，`Page.downloadWillBegin` 计数分别 **1→1、2→2**，按钮恢复可用。不是把请求超时当作拦截成功。
- 显式CDP CSS viewport=390×844，稳定后两抽屉 rect 均 x=0、width/right约390.4，document scrollWidth=390；这是亚像素边界，不依据截图像素推断。截图和去敏事件摘要在 `.tmp/0910-full-audit/pr8-adapt-*-private.*`，不提交。早期取消导航的失效interception、一次错误的dialog role查询、首次合成首页字段拼写不符均未计入证据；修正后检查了真实字段与有效响应。
- 临时标签已关闭、视口覆盖清除；用户原3011标签未动。3032进程32716与监听结束时已不存在，没有停止别人的服务。两个合成CSV留在Downloads自动带 `(1)` 后缀，没有删除既有文件。
- 不包含实际PG、真实账号/病例、目标API联调、完整迁移图升级、全仓测试或全站视觉验收。80项完成台账不调整，27指标/门急诊/引擎均不扩大。
