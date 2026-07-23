# 客户样本验证 E2E 验收器

## 目标

`backend/scripts/run_customer_sample_validation_e2e.py` 用固定隔离样本验证以下正式链路：

```text
服务/规则预检
  → 固定 fixture 身份校验
  → 匹配/同步/bundle 就绪校验
  → 精确 LX0609 规则范围创建与轮询
  → 复核、HTML/CSV/XLSX 导出可用性与安全台账检查
```

它不是数据准备工具。脚本不会自动导入、重匹配或重同步样本，避免远端匹配逻辑破坏已经 seed 的合成病历。

## 固定 fixture

当前只登记一个命令行别名：

| 命令行别名      | 样本池 ID                  | 来源标识                                     | 病历前缀      |
| --------------- | -------------------------- | -------------------------------------------- | ------------- |
| `lx0609-e2e-v1` | `luxian-0609-synthetic-v1` | `synthetic://luxian_0609_synthetic_cases_v1` | `LX0609_SYN_` |

脚本同时校验样本池 ID、显示名、来源标识和全部病历前缀。仅名称相同、来源不明的样本池不能用于 E2E。

fixture 的准备入口是 `scripts/qc/build_luxian_0609_synthetic_pg_cases.py`。该脚本的写入模式具有独立副作用，不能由 E2E 验收器隐式调用。

## 安全模式

### 只读预检

```powershell
cd backend
python scripts/run_customer_sample_validation_e2e.py `
  --dry-run `
  --fixture-pool lx0609-e2e-v1 `
  --selected-rule-ids LX0609-001,LX0609-017,LX0609-029 `
  --output ..\tmp-safe-e2e-dry-run.json
```

`--dry-run` 只发起 GET 请求，检查：

- API 健康；
- `luxian_0609_qc_v1` 规则集存在；
- 版本化验收工件与当前运行版本一致（`artifact_freshness=fresh`）；
- 指定规则均在 LX0609 目录；
- fixture 身份唯一且正确；
- 全部病历为 `matched + synced/synthetic_seeded + bundle ready`。

不会创建任务、执行匹配、执行同步、复核或导出。

### 受控本地写入

只有在隔离本地环境、fixture 已准备完成且明确允许本地任务写入时运行：

```powershell
cd backend
python scripts/run_customer_sample_validation_e2e.py `
  --fixture-pool lx0609-e2e-v1 `
  --selected-rule-ids LX0609-001,LX0609-017,LX0609-029 `
  --allow-local-writes `
  --output ..\tmp-safe-e2e.json
```

该模式允许：

- 创建客户样本验证任务；
- 轮询正式工作区任务；
- 写入 LX0609 复核报告；
- 读取 HTML、CSV、XLSX 导出进行可用性检查。

即使开启写权限，也不会导入、重匹配或重同步 fixture。

## 五阶段状态

安全 ledger 固定输出五个阶段：

1. `preflight`
2. `fixture_import`
3. `match_sync`
4. `run_poll`
5. `review_export_privacy`

阶段状态仅为：

- `passed`
- `failed`
- `skipped`

任一阶段失败后，后续阶段统一 `skipped / upstream_failed`，不会继续制造任务或复核写入。dry-run 的最后两段为 `skipped / dry_run`。

## 输出边界

ledger 只包含：

- schema、运行模式和 fixture/job 哈希引用；
- 显式选择的 LX0609 规则 ID；
- 阶段状态、受控 reason code 和耗时；
- 病历数量、结果状态计数；
- LLM 调用数和输入/输出/总 token；
- 复核数量和导出格式通过数；
- 后端生成的安全 `operation_ref`、`execution_scope_hash`。

禁止输出：

- 患者、机构、就诊、住院号等坐标；
- 姓名、电话、证件；
- 病历正文、文书内容、原始时间；
- SQL、prompt、raw response；
- 原始 API 错误正文。

任务创建返回的 `operation_ref` 必须符合 `sample-op-` 加 24 位小写十六进制，
`execution_scope_hash` 必须是 64 位小写十六进制；异常值会立即中止。任务结果
状态也必须属于受控枚举。三种导出除状态码和非空内容外，还分别校验 HTML、
CSV、XLSX 的 MIME 类型。

输出文件采用同目录临时文件加原子替换写入。`tmp-safe-e2e*.json` 仅供本地验收，不得提交。

## 验收命令

```powershell
cd backend
python -m pytest tests/unit/test_customer_sample_validation_e2e.py -q --confcutdir=tests/unit
python -m py_compile scripts/run_customer_sample_validation_e2e.py
python scripts/run_customer_sample_validation_e2e.py --help
```

单测覆盖：

- dry-run 全程 GET-only；
- 无 `--allow-local-writes` 在任何网络请求前拒绝写模式；
- fixture 未就绪时停止下游任务；
- 精确规则范围、轮询、复核和三种导出；
- ledger 禁止字段和私有值泄漏。
