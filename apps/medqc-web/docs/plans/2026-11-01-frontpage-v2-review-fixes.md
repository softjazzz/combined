# 首页质控V2复审修复与独立适配计划

**Goal:** 修复已确认授权、评分、取消、导出及最新结果问题，在独立分支适配迁移并保护V7.1。

**Architecture:** 基于业务线d2a94df3b，在本工作树整合来源354e7dd18。持久账号owner提供院范围，Store再次实施SQL谓词和任务归属；评分只在原引擎内按主次项装配。任务以CAS领取，最新结果按任务创建顺序排序并由PG病例锁及唯一索引保护。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Vue3、Vitest、隔离pytest。

## 实施步骤

1. 整合来源：保留目标Layout/main/Token/主题/图标，解决TODO与导航测试冲突，导航仅增首页入口。
2. 授权：新增frontpage权限owner复用持久_person；绑定Store SQL范围，列表/统计/详情/任务/导出/复核一致，未知/坏角色/无机构失败关闭。校验注入来源不返回异院。
3. 引擎：L06/L07按具体item_index绑定主次评分项，分别验证次诊1分和次手术编码0.5分及封顶/混合情形。
4. 任务：CAS queued且未取消领取，每份开始前检查取消；结果保存病例锁、唯一latest及新旧快慢任务创建时间选轮。
5. 导出：未质控不导出结果；请求开始固定参数和身份，切换筛选/账号/权限/卸载后令旧响应失效，包含Blob下载前和finally。
6. 迁移：保留目标既有050签名及MQ056/057；保留来源048三表迁移，移除来源未正式集成的同号伪050，仅本新适配树内处理。用独立20261102_000061向前汇合MQ057与首页048，校验三表列并添加latest唯一索引。不得占用同步分支060/来源WIP059。
7. 隔离验证：固定合成材料/内存或临时SQLite，网络/.env/业务PG/真实模型阻断。覆盖持久A/B账号、同号跨院、次项评分、取消、最新轮及导出竞态；PG锁仅静态或显式专用跳过测试，不能称实际PG并发已验收。
8. 完成类型/只读lint/编码/Ruff及必要回归，本地中文提交，不push/部署/合并业务线。

## 迁移兼容边界

本方案面向已明确沿业务线050签名链升级的目标，或空/旧业务线可验证起点。历史PR4测试库若stamp了同号050，不能只看版本号判断含签名字段还是伪merge；上线前必须核对原版本来源及表结构。身份不明必须停止升级，不得stamp冒充修复。没有连接任何PG验证本次迁移，现场备份/实际schema验收仍需另行授权。


## 本轮完成与范围修正

本独立适配分支基于业务线 `d2a94df3b30182a7431e4d1a00a2d06c8c8a32e1`，整合来源 `354e7dd183f25815caf0b8affa0c56bbf9503b0a`。来源不仅包含规则引擎，还包含批量任务、复核、统计、导出、前端结果与分析；本轮按这些实际调用链修复，不沿用原PR早期“仅后端”的范围说明。

| 已确认问题 | 本轮实现与验证 |
| --- | --- |
| 可信机构与对象授权 | 首页专属 owner 通过持久 SysUser SQL 复用有效账号与角色解析；HTTP 角色、客户端 all/home/机构及显式三坐标均不能扩权。Store 对结果、任务、复核再次实施范围。真实内存账号 A/B 同患者/同就诊反例、伪造 HTTP admin、合法持久 admin/sync_admin、coder、停用/损坏/缺机构均有保护。共享旧报表权限未放宽。 |
| 次诊断/次手术误扣主项分数 | L-06/L-07 保留原规则与 item_index，在评分 owner 按主次项分组；次诊1分、次手术0.5分，混合主次与多项封顶以及正式保存读取都有验证。规则集版本升至2026.11.01，旧结果显示陈旧。 |
| 排队取消及末尾竞态 | queued且未取消 CAS 领取；取消的排队任务不读CDM/不出结果，每份安全边界检查。终态不复活，完成提交以当时 cancel_requested 决定，保留此前成功数。 |
| 未质控导出与列表范围矛盾 | “未质控”筛选禁用结果导出，不再静默清空筛选；结果导出仍只导出已有结果。 |
| 导出异步竞态 | 请求参数和文件名开始时固定；账号/机构/角色/筛选变化及卸载使旧成功、错误、finally失效。当前下载成功与旧finally不影响新loading都有延迟Promise对照。 |
| 迁移重复050 | 正式050签名历史保持原文件、原编号和父版本。仅本适配树移除来源伪050，保留来源048；唯一061汇合源048与目标MQ057。PG升级前核对正式050实际签名结构，不明stamp报ambiguous_050_history并停止。 |
| 并发 latest 与旧慢任务抢轮 | PG事务级病例 advisory lock覆盖首次无行窗口，部分唯一索引防多latest；选轮按任务创建时间/ID，旧慢任务仅存历史。迁移去除旧重复latest且保留历史结果。内存验证唯一约束、两种快慢完成顺序和原分数/证据。 |

## 可重复隔离验证

在 `apps/medqc-web/backend`：

```powershell
py -3.10 -B scripts/run_frontpage_v2_tests.py
py -3.10 -m ruff check app/services/frontpage_qc_v2 app/routers/frontpage_qc_v2.py tests/unit/test_frontpage_qc_v2_*.py scripts/run_frontpage_v2_tests.py alembic/versions/20261102_000061_frontpage_v2_business_heads.py
```

后端 **439 passed**，3条既有Pydantic/Starlette弃用警告。入口使用 OfflineIsolation，禁止真实网络、.env、PG及模型；仅允许内存SQLite及入口自身创建的临时SQLite。包含原规则/负例、loader、API、正式内存保存读取、迁移图、迁移DDL去重以及新反例，不是只mock授权函数。

在 `apps/medqc-web`（将路径按实际工作树展开）：

```powershell
$env:NODE_OPTIONS='--require=' + ((Resolve-Path scripts/frontpage-v2-no-network.cjs).Path -replace '\\','/')
node node_modules/vitest/vitest.mjs run src/views/workstation-v4/frontpage-qc/__tests__ src/components/layout/__tests__/workstationNav.spec.ts
npm run type-check
node node_modules/eslint/bin/eslint.js src --ext .vue,.js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts --quiet
npm run check:encoding
```

前端4文件 **54 passed**（页面13、服务6、任务轮询7、目标导航28），传输层TCP/TLS/fetch阻断。完整类型检查、相关及完整src只读ESLint、相关Ruff、暂存区61个文本编码检查均通过。无依赖下载/升级，无服务启动或患者任务。主代理已独立复跑后端439及前端54并复核关键代码。

## V7.1与迁移交付边界

- 目标 WorkstationLayout、main.ts、Token、主题、图标无差异；保留配置式导航、既有全部入口、反馈工单/消息等成果。导航仅新增首页入口，router仅增加新页面，backend/main仅注册新路由。
- 原两个显式冲突只在本适配树解决：TODO同时保留双方历史，导航测试保留全部目标入口及新增首页入口。未对另一工作树执行改动。
- 来源PR4的伪050历史库不能依赖 alembic current 唯一判断身份；必须先备份并确认迁移来源和050签名字段。此处未替历史库自动补stamp或修改已部署历史。061提供失败关闭保护，而不是宣称所有来源历史库均可直接升级。
- 同步服务独立适配线另有060，之后若同时整合需独立复核迁移图并新增唯一汇合版本；本分支不预先合入另一代理的迁移，也不占用其编号。

## 未执行及仍需验收

1. 未连接任何真实或一次性PG，未执行PG upgrade、回退或真实并发事务压测。PG advisory锁/部分唯一索引代码已实现，SQLite只证明SQL持久合同、去重和唯一约束；不能替代PG并发验收。
2. 未做浏览器真实后端验收、患者首页质量验收、全站全部前后端回归、生产部署或正式PR合并。固定合成材料通过不能推导医学规则全量准确。
3. 本轮仅本地提交，不推送、不改业务集成分支，不写业务库、不调用模型、不重跑患者质控。页面已接入目标V7.1外壳，但不声称全站V7.1迁移完成。
