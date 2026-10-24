# visit_index 同步字段向前修复与本机升级

## 根因与迁移归属

三个字段的原始 owner 是 `20261006_000047_visit_index_sync_fields.py`：

| 字段 | 合同 |
| --- | --- |
| latest_mirror_success_time | 无时区 timestamp、可空、无默认值 |
| mirror_delay_base_minutes | integer、非空、默认 30 |
| sync_interval_minutes | integer、非空、默认 30 |

旧版 047 在 split 模式固定向 qc 模式加列。本机同时存在 public.visit_index 和 qc.visit_index，前者 1 行、后者 21 行。qc 已有三列，public 缺失三列；应用 `DB_SEARCH_PATH=public,qc,sys,cdm,legacy` 实际解析 public 表，因此严格启动门禁仍失败。当前 047 虽已按实际搜索路径定位，但本机迁移版本已到 052，不会重新执行 047。

## 本次修复

独立工作树 `C:/medqc-qc-source-fixes`，分支 `codex/qc-source-completion-20261023`，代码提交 `168bcf2cf`。

新增 `20261023_000053_visit_index_resolved_sync_fields.py`，前序为 052。按应用搜索路径解析目标表，先检查所有已存在目标列的类型、空约束和默认值，再仅添加缺列；不兼容时整体拒绝，不覆盖现有值，不搬迁两张同名表的数据，不猜测历史镜像成功时间。禁止自动降级删除证据列。保留原 047 文件。

## 备份与实际升级

已获得用户明确授权，目标仅本机 localhost:5432/medqc。

- 升级前全量 custom 格式备份：`.tmp/0910-full-audit/visit-index-20261024T024717206922Z-private/medqc-before-053-private.dump`。
- 大小：196599867 字节；SHA256：`115e65b7d057a8d802b55661a7ccc20babf1f43aa3280c9c1a80646d1906dc6d`。
- 已检查归档目录，并完整解压到空设备校验；校验过程未连接目标库。
- 实际执行 052 → 053，未回退版本、未改写 stamp。
- public 三列已补齐；原 1 行其他字段不变，镜像成功时间为空，两个间隔默认 30。qc 21 行及列定义全部保持不变。
- 在 PostgreSQL 只读事务内重入真实 053 函数通过，证明已补齐时不重复发 DDL。
- 启动完整结构门禁通过，包含所需表、父任务列和索引、实际 visit_index 的三坐标主键与有效的 scene/updated 索引。
- 1603 条任务的身份/状态/更新时间摘要、1294 条结果 envelope 的完整内容摘要前后不变。

## 启动与运行验证

已停止上轮临时的 lifespan=off 后端，恢复 Uvicorn 完整启动生命周期 `lifespan=on`。后端 PID 34620，实际导入本独立工作树的 app/main.py；前端 PID 27820，继续从同一独立工作树运行 Vite dev，3000 端口代理 8001。

为遵守“不调用模型、不重跑质控”，使用已有 `MEDQC_STARTUP_MODE=acceptance`，通过真实只读结构门禁后启动，不执行初始化 DDL、后台预热或旧任务自动恢复。没有关闭 schema gate，没有猴子补丁跳过 startup handler；这不是 `MEDQC_STARTUP_MODE=normal` 的后台恢复模式。生产环境不支持该验收模式。

启动日志确认 Application startup complete；运行源清单确认分支、代码提交、PID、lifespan 和启动门禁均匹配。开发源码运行没有伪造客户发布包 build_id。

运行中 9 次真实认证 GET（含前端 3000 代理）全部通过；5 份死亡文书 20 个独立字段、7 例共 11137 条医嘱的 14424 个非空时间值与数据库一致，C17/C22 已保存病程 Bundle 共 401 条医嘱同样一致。验收请求共执行 1055 条只读 SQL，写操作尝试为 0；未认证请求仍为 401。历史 1022 结果摘要保持一致。

运行中只读 API 验收证据以 `.tmp/0910-full-audit/runtime-source-current-private.txt` 指向的目录为准。验收请求沿真实认证、路由和读取链，增加仅针对验收 header 的 PG 只读事务及禁止外发 HTTP 保护；不降低账号认证或角色校验。继续核对既有 1022 死亡字段和医嘱时间，避免结构升级破坏前一步补数。

## 测试和保护范围

- 定向 pytest：迁移合同、acceptance startup、visit_index service 共 159 项通过。
- Ruff、暂存编码检查、diff whitespace 检查通过。
- 增加同名表并存、仅补实际 public 表、已有列完全/部分具备、幂等、不兼容时不发 DDL、053 唯一 head 与 052 的升级路径保护。
- 未跑全量前后端测试，未调用模型、未重跑任何病例、未覆盖历史质控结果、未访问或写入医院源库，未打包或推送合并。
- 业务集成工作树的 HEAD、分支、工作区状态与本轮开始相同；未暂存生成的 index.prebuilt.css。

## 接续

如后续部署本独立分支，数据库须包含 053，不能只替换旧 047 文件期待自动修复已升级数据库。客户机本轮未升级。正常后台恢复模式、打包和发布另按用户授权执行；不得为验证本次结构修复而重跑整批质控。

## 客户机 051/052 → 053 升级工具

已准备 `medqc-pg-upgrade-053-20261023.zip`，包含 052/053 原始迁移、SHA256 清单、Python 升级器及 PowerShell 入口。只读取用户指定 backend/.env，限制 localhost 的 medqc/split 数据库；校验 PostgreSQL 备份工具版本，完整 pg_dump 后用 pg_restore 解压校验，失败即停止。之后仅新增缺失的迁移文件，已有不同内容拒绝覆盖，升级目标固定为 053。完成后核对既有索引/死亡记录行和字段不变，并在只读事务重入 053 校验列合同。

仅补数据库结构，不部署新应用、不补历史临床数据、不刷新 Bundle、不启动前后端、模型或质控。用户仍需将包复制至客户机执行，本机本轮未再迁移；客户机执行结果未验证。8 项离线保护测试通过，Ruff、PowerShell 解析、包内迁移校验及 ZIP 完整性检查通过。没有重新执行全量测试。包 SHA256：`9ac85907f640740a502b0c89792ab94729705455f866be2826698001d2c37af5`。
