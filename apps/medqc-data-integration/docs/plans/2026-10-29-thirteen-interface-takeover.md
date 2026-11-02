# 13 接口接管与部署验收 Implementation Plan

**Goal:** 固定 13 个接口，将客户已有 raw/版本/批次保留后迁入独立正式 ingest 验收库，并以正式发布器完成克隆 CDM 的幂等、回滚和恢复验收，交付单次执行入口。

**Architecture:** 原验收库只读；ingest 接管库全新初始化；CDM 使用另外的新克隆。原始历史按原表逐行归档，规范化记录与来源映射另存，不改写原库。验收工具复用正式 ExtractService/PublishService，调度只允许固定 13 来源。

**Tech Stack:** Python 3.10、PostgreSQL 16、ODBC35、PowerShell 5.1；显式选择psycopg3或客户已有psycopg2，不自动换身份或安装依赖。

## Task 1：接管合同与原历史保存

Files: `src/medqc_ingest/takeover.py`、`migrations/005_takeover_audit.sql`、`tests/test_takeover.py`。

先写源/目标库身份、源原始哈希、文书键、日期窗口及历史多版本反例。再实现：源只读一致快照；新目标空库闸门；原记录及原列合同归档；批次 ID 映射；规范化 schema/当前 raw/历史版本；迁移依据与汇总。目标单事务，失败整体回滚；迁移不创建业务增量断点。历史空哈希只允许经本次范围和逐行校验的迁移转换，正式发布默认门禁保持不变。

Run: `py -3.10 -m pytest tests/test_takeover.py`。预期：错误库名、错误哈希、跨接口键、缺字段、历史丢失均失败；重跑已完成接管只验证，不覆盖数据。

## Task 2：正式服务运行验收

Files: `tools/accept_takeover.py`、`tests/test_deployment_acceptance.py`。

复用正式发布器跑 13 来源两轮，输出逐来源选择/变化计数；以单独回滚事务验证分块失败后当前 raw、版本、schema、断点均不变，失败审计保留；恢复后重新执行同一工作成功。验证包只输出计数和受控原因码。具备本机隔离 PostgreSQL 环境则执行真实 SQL 回归，否则明确保留客户机真实验收，不能用 fake 结果冒充。

Run: `py -3.10 -m pytest tests/test_deployment_acceptance.py`，再执行指定独立测试库的验收命令。

## Task 3：运行、备份恢复与冻结交付

Files: `deploy/windows/run-daily.ps1`、`docs/DSH_START-takeover.txt`、`tools/run_takeover.py`。

固定 13 个接口顺序、排除当天、逐命令检查退出码；支持明确起止日期与失败后重跑；定时任务默认不启用，完成验收后再按部署步骤注册。交付当前解释器/依赖核验、库初始化、归档迁入、发布与恢复检查的同一组命令。源或正式业务库禁止成为写入目标，不删除测试库。

验收退出条件：13 来源逐项计数/字段一致，第二轮零业务变化；故障回滚与恢复通过；备份恢复计数/摘要一致；新目标库可运行一次完整日任务；交付固定版本与运维说明。其余接口、在院能力和全规则引擎不纳入本版本。
