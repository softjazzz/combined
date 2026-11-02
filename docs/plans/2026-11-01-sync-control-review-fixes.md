# 独立同步服务复审问题修复实施计划

**Goal:** 在独立适配分支修复绑定身份、持久重试及时间精度，保留MQ和同步迁移两条历史。

**Architecture:** 从业务线d2a94df3b整合固定来源fd9e9a186，只在该新工作树修复。控制仓储为任务身份和重试意图唯一owner；Pipeline提供不可逆摘要身份，发布/抽取算法仍复用原服务。精确时间字段拒绝仅日期值，raw原文不丢弃。

**Tech Stack:** Python3.10，现有PostgreSQL状态机，SQLAlchemy/Alembic离线图和内存SQLite测试。

## 执行顺序

1. 整合来源；保留双方TODO及目标C01/双模型代码，不读取原同步工作树WIP。
2. 先加失败反例：跨目标重试、退避重启、纯日期精确时间；再实现最小修复。
3. 首次执行前仓储CAS冻结数据面及合同摘要；缺身份但已有完成单元的旧任务进入恢复，绑定变化不得复用旧完成单元。
4. 自动退避和预算在控制库持久化；领取时原子恢复到期任务，取消/人工重试清理意图，未知提交保持恢复闸门。
5. 精确datetime/timestamptz只接受明确时刻，date字段仍允许日期，保留时区转换；不以签名/提交补记录时间。
6. 新增control002向前迁移，不改001；新增应用20261102_000060_sync_mq_heads汇合来源058和MQ057，并验证已声明字段/表的实际合同。
7. 严格网络/环境隔离测试控制、发布及日期回归；应用迁移图、独立PACS与最新检查专项保护。相关Ruff/mypy/编码；前端未改，记录未执行范围。
8. 本地中文提交，不push、不合并正式PR、不部署。

## 验收边界

禁止连接任何现有PG/ODBC/客户机/模型或写业务库，不启动数据库、不运行病历质控。仅固定应答/合成材料、临时文件及内存SQLite。真实PG并发、DDL升级、现场接管和Bundle读链未执行，不冒充验收通过。来源独立PACS语义是继承范围，不在本批改变医学口径。原账单/病理059WIP完全排除。

## 完成结果（2026-11-01）

开发基线为business `d2a94df3b30182a7431e4d1a00a2d06c8c8a32e1`，来源固定`fd9e9a18688748afba2345d4f6290e3855ecc369`。唯一文本冲突PROJECT_ROLLING_TODO保留双方条目。Native检查执行器自动合并后，用C01和独立PACS保护复核；前端源码无差异。

- 绑定：Pipeline在附加job/unit/attempt UUID前生成稳定SHA256身份；仓储CAS先绑定再执行或跳过成功单元。source namespace、ingest/CDM或合同变化进入恢复，仅秘密文件轮换不改变身份；历史成功单元缺身份失败关闭。
- 重试：finish_job与到期意图同事务持久化，覆盖child提交failed后Supervisor尚未观察就退出的窗口。新进程按UTC到期及冻结预算原子领取；取消、手工retry、未知提交合同保留，最多两次额外重试。
- 精度：纯日期投影精确timestamp时显式publish_contract失败，raw保留；不补零点或签名时间。date字段及显式午夜正常。
- 控制迁移：001原文不改；002新增typed owner列、索引和约束。未升级时ready、提交、领取统一503。新空库自动001+002；旧库停服务、备份后显式--upgrade-reliability。源码包和wheel均包含002；acceptance调用同一初始化owner。升级函数不经过新版运行时repo连接前置，不会自阻塞。
- 应用迁移060：汇合来源058和MQ057，验证CDM新增字段类型/可空/默认、传染病字段/主键及MQ必要表/列/主键，不覆盖历史或MQ表。本候选单head只证明本分支；另一首页候选061共同整合时仍须新的联合汇合与schema验收，不能宣称二者已共同单head。

## 隔离验证命令与结果

工作树根目录PowerShell先设置`PYTHONIOENCODING=utf-8`、`PYTHONDONTWRITEBYTECODE=1`、`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`。下面Python通过`py -3.10 -B -`执行：

```python
import sys, os
from pathlib import Path
root = Path.cwd()
backend = root / 'apps/medqc-web/backend'
app = root / 'apps/medqc-data-integration'
sys.path.insert(0, str(backend))
from tests.scheduler_support import OfflineIsolation
with OfflineIsolation():
    sys.path.insert(0, str(app / 'src'))
    sys.path.insert(0, str(app / 'tests'))
    os.chdir(app)
    import pytest
    names = ['control_review_fixes', 'job_admission', 'job_repository',
             'job_runner', 'worker_recovery', 'sync_scheduler', 'control_pipeline',
             'domain', 'service', 'major_document_contracts', 'orders_lab_exam_service',
             'remaining_contracts', 'control_api', 'control_runtime', 'control_profiles',
             'control_prepare', 'control_deployment', 'control_bootstrap', 'control_cli']
    raise SystemExit(pytest.main([
        '-q', '--capture=sys', '--tb=short', '-p', 'no:cacheprovider', '-o', 'addopts=',
        '--confcutdir=' + str(app / 'tests'), '-k',
        'not clean_cli_bootstrap_import_does_not_read_secrets_or_change_environment',
        *[str(app / 'tests' / ('test_' + n + '.py')) for n in names]]))
```

结果：**379 passed、1 deselected**，另有1项Starlette弃用警告；主代理独立同命令复跑379通过。排除项为test_control_runtime.py::test_clean_cli_bootstrap_import_does_not_read_secrets_or_change_environment，它需要创建子进程，严格guard禁止，本轮未放宽。合成打包夹具固定Git版本来源，不调用子进程。先前一次旧退避测试仅推进monotonic未推进UTC，夹具已同步推进两者，生产状态机未放宽。

业务保护：同环境变量和工作目录，执行以下Python：

```python
import sys, os
from pathlib import Path
backend = Path.cwd() / 'apps/medqc-web/backend'
sys.path.insert(0, str(backend))
sys.path.insert(0, str(backend / 'tests/unit'))
from tests.scheduler_support import OfflineIsolation
with OfflineIsolation():
    os.chdir(backend)
    import pytest
    names = ['test_exam_result_pair_recovery.py', 'test_exam_poc_acceptance.py',
             'test_luxian_0609_exam_result_record_check.py',
             'test_luxian_0609_exam_finding_full_coverage.py',
             'test_luxian_0609_independent_pacs_reports.py']
    raise SystemExit(pytest.main([
        '-q', '--capture=sys', '--tb=short', '-p', 'pytest_asyncio.plugin',
        '-p', 'no:cacheprovider', '-o', 'addopts=',
        '--confcutdir=' + str(backend / 'tests/unit'),
        *[str(backend / 'tests/unit' / n) for n in names]]))
```

结果：**78 passed、1 skipped**，另有1项Pydantic弃用警告。跳过项为需要显式私有原报告路径的POC回放，本轮未读取患者材料。C01局部正负引用、严格跨报告定位、不完整不冻结、长文覆盖和正式保存链固定保护保留。

静态：app目录`py -3.10 -m mypy --config-file pyproject.toml src/medqc_ingest`，41源文件通过；相关control/domain、新测试、初始化CLI及060 Ruff通过；diff --check、UTF8/BOM检查通过。

## 仍未验收

未运行真实PG DDL、角色授权、并发原子领取、跨进程断电恢复和索引性能。控制SQL仅完成假连接事务合同、迁移图和Inspector反例，不代表实际PG已升级。未建立PG实例、未启动服务、未执行ODBC现场、正式接管或真实Bundle读链。继承的独立PACS语义有固定保护，但不是现场医学验收。前端未改，未重跑前端类型/浏览器或全量应用回归。未纳入原同步工作树账单/病理WIP059。未来正式集成须与首页061候选联合迁移验证。
