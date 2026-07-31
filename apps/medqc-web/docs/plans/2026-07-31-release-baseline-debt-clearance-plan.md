# 发布基线清账实施计划

> **执行要求：** 实施本计划时使用 `executing-plans` 工作流，按任务逐项执行、聚焦验证、提交；不得将未分类改动整批提交。

**目标：** 将当前开发工作区收敛为一个源码可追溯、数据库可迁移、交付包可复验、客户环境可回滚的发布基线，同时把不阻塞发布的大型架构债转入后续技术债台账。

**架构原则：** 本轮不重写业务架构，只守住已经确认的最小直通链：`Bundle / Snapshot（仅输入） → Native 规则 → CanonicalQcResultEnvelope → 数据库原样保存 → 单一结果 API 原样返回 → 前端只渲染`。任何会让聚合器、API 或前端再次解释质控状态的改动均不进入发布基线。

**技术栈：** Vue 3、Vite、TypeScript、Python、FastAPI、PostgreSQL、Alembic、pytest、Vitest、PowerShell。

---

## 1. 当前证据与根因判断

截至 2026-07-31 的只读检查结果：

- 工作区存在约 179 个已跟踪文件改动、159 个未跟踪项，不能直接用当前目录作为可发布源码基线。
- `scripts/package-customer-release.ps1` 已能以 customer mode 构建，并扫描前端产物中的 `api.medqc.com`。
- 当前打包流程尚未强制要求干净 Git 状态，也没有把 Git SHA、Alembic head、前后端版本、规则运行时清单和文件哈希绑定到同一份发布清单。
- 当前最新迁移包括：
  - `backend/alembic/versions/20260729_000023_add_luxian_0609_record_result_envelopes.py`
  - `backend/alembic/versions/20260731_000024_add_sample_sync_cursors.py`
- 已有发布冒烟基础：`backend/tests/integration/test_release_gate_smoke.py`。
- 已有 LX0609 运行时清单和黄金闸门能力，但它解决的是规则运行时可追溯性，不能替代整个客户交付包的发布清单。
- 目前同时存在发布功能改动、试验文件、临时输出、本地配置和长期技术债；没有先分类就打包，是版本不一致、遗漏迁移、客户机行为与本机不同的主要风险。

根因不是“还缺一次编译”，而是尚未形成以下完整闭环：

```text
需求范围冻结
  → 改动逐项归属
  → 逻辑提交
  → 干净工作树
  → 质量门禁
  → 绑定版本与迁移的交付包
  → 解包复验
  → 客户等价环境演练
  → 发布与回滚证据归档
```

## 2. 范围

### 本阶段必须完成

1. 盘点并分类全部工作区改动，做到零“来源不明”和零“归属不明”。
2. 建立可恢复快照，确保清账过程不丢失用户现有工作。
3. 把准备发布的改动拆为可审查的逻辑提交。
4. 建立全局发布清单，绑定源码、前端产物、后端、迁移、规则运行时和交付包哈希。
5. 强化打包门禁，拒绝脏工作树、过期产物、敏感配置、外部 API 地址和缺失迁移。
6. 在干净工作树完成构建、测试、打包、解包复验和客户等价环境演练。
7. 形成部署、升级、回滚和验收记录。

### 本阶段不做

- 不拆分 `CustomerSampleValidationView.vue`、`SemanticRulesBatchResultDrawer.vue` 等超大组件。
- 不拆分 `custom_qc_sample_pool_service.py`、`custom_qc_workspace_service.py` 等超大服务。
- 不为“代码更漂亮”重构已稳定的 Bundle、Native 规则或 Canonical Envelope 链。
- 不在缺少客户定义时擅自完善 pending 规则口径。
- 不把历史截图、日志、临时数据库、构建产物或本地密钥纳入 Git。
- 不直接在客户生产数据库上做迁移试验或回滚试验。

## 3. 清账分类标准

每一个改动路径必须进入且只能进入以下一个类别：

| 类别            | 含义                                 | 处理方式                             |
| --------------- | ------------------------------------ | ------------------------------------ |
| A 发布功能      | 本次客户版必须包含的功能或修复       | 审查后进入逻辑提交                   |
| B 发布保障      | 测试、迁移、打包、部署与文档         | 审查后进入逻辑提交                   |
| C 后续技术债    | 不阻塞本次发布的重构或优化           | 记录到台账，本轮不改                 |
| D 本地产物      | 日志、截图、缓存、临时文件、构建输出 | 加入忽略规则或保留在外部快照，不提交 |
| E 敏感/环境配置 | `.env`、口令、客户连接、机器路径     | 不提交；仅保留安全模板和部署说明     |
| F 待确认        | 无法证明来源或发布必要性             | 阻塞基线，确认后重新分类             |

硬规则：清单中只要还有 F 类，禁止生成正式客户交付包。

## 4. 发布验收总指标

- 干净验证工作树执行 `git status --porcelain` 输出为空。
- 改动清单中未分类数量为 0。
- Git 中不包含密钥、客户连接串、临时数据库、日志、截图和 `dist/`。
- Alembic 只有一个 head，且交付包包含截至 `20260731_000024` 的迁移链。
- 发布清单中的 Git SHA、迁移 head、前端哈希、后端哈希、规则运行时哈希与包内实际内容一致。
- customer mode 前端产物不存在 `api.medqc.com` 等外部生产域名硬编码。
- 解压到全新临时目录后，后端可导入、前端静态资源可启动、核心接口冒烟通过。
- 在院病历即使没有 `medical_record_frontpage`，只要主记录和住院登记已同步，也能进入样本池并启动质控。
- 已完成任务能通过单一结果 API 打开对应病历的 Canonical Envelope，不回退到其他病历或旧结果链。
- 部署和回滚步骤均在隔离环境演练成功，并保留证据。

---

## 5. 实施任务

### Task 0：冻结发布目标并建立可恢复快照

**Files:**

- Create: `docs/releases/<RELEASE_ID>/scope.md`
- Create: `docs/releases/<RELEASE_ID>/change-inventory.json`
- Create: `docs/releases/<RELEASE_ID>/change-inventory.md`
- Create: `scripts/release_baseline_inventory.py`
- Test: `backend/tests/unit/test_release_baseline_inventory.py`

**Step 1：先写失败测试**

覆盖以下行为：

- 能解析 `git status --porcelain=v1 -z`，正确处理中文、空格和重命名路径。
- 每个路径必须具有 `category`、`owner`、`release_required`、`reason`。
- 存在 F 类或未分类路径时返回非零退出码。
- 清单不得记录文件内容和密钥，只记录路径、状态、大小和 SHA-256。

运行：

```powershell
Set-Location backend
python -m pytest tests/unit/test_release_baseline_inventory.py -q
```

预期：测试因脚本尚未实现而失败。

**Step 2：实现只读盘点脚本**

`scripts/release_baseline_inventory.py` 只允许读取 Git 状态和文件元数据，不允许删除、移动、恢复或暂存文件。输出应包含：

```json
{
  "schema_version": 1,
  "generated_at": "ISO-8601",
  "git_head": "40-char SHA",
  "entries": [
    {
      "path": "relative/path",
      "git_status": "M",
      "sha256": "...",
      "size": 123,
      "category": "F",
      "owner": "",
      "release_required": null,
      "reason": ""
    }
  ],
  "summary": {
    "tracked_changes": 0,
    "untracked_entries": 0,
    "unclassified": 0
  }
}
```

**Step 3：创建外部可恢复快照**

在仓库外的受控目录保存：

- `git diff --binary`
- 未跟踪文件路径清单及 SHA-256
- 当前 Git HEAD
- 当前分支

不得使用 `git reset --hard`、`git clean` 或删除命令。未跟踪的大文件只做路径和哈希登记；需要复制时逐项确认目标目录。

**Step 4：人工完成 A-F 分类**

重点逐项审查：

- `backend/alembic/versions/`
- Bundle 构建和文书归并
- Native 规则和 Canonical Envelope
- 样本池同步与在院病例支持
- 结果 API 与前端结果抽屉
- 打包、部署和测试
- `.env*`、截图、日志、临时脚本、SQLite/导出文件

**Step 5：验证**

```powershell
Set-Location backend
python -m pytest tests/unit/test_release_baseline_inventory.py -q
Set-Location ..
python scripts/release_baseline_inventory.py --check docs/releases/<RELEASE_ID>/change-inventory.json
```

预期：未分类数量为 0，否则停止。

**Step 6：提交**

```powershell
git add scripts/release_baseline_inventory.py backend/tests/unit/test_release_baseline_inventory.py docs/releases/<RELEASE_ID>/scope.md docs/releases/<RELEASE_ID>/change-inventory.json docs/releases/<RELEASE_ID>/change-inventory.md
git commit -m "构建发布基线改动清账清单"
```

---

### Task 1：补齐本地产物与敏感配置门禁

**Files:**

- Modify: `.gitignore`
- Modify: `scripts/package-customer-release.ps1`
- Create: `scripts/verify_release_source.py`
- Test: `backend/tests/unit/test_verify_release_source.py`

**Step 1：写失败测试**

验证以下内容会阻塞正式打包：

- 工作树不干净。
- 存在未分类改动。
- `.env`、私钥、口令或客户数据库连接进入候选文件集。
- `.codegraph/`、`.release-packages/`、`dist/`、coverage、日志、截图、临时数据库或 `tmp-*` 进入候选文件集。
- 前端环境配置包含外部生产 API 域名。

同时验证 `.env.example` 等无密钥模板允许进入包。

**Step 2：更新忽略规则**

只添加经清单确认属于 D/E 类的模式。不得用宽泛规则掩盖真实源码，例如不得整体忽略 `scripts/`、`docs/` 或 `backend/data/`。

**Step 3：实现源码预检**

正式模式默认要求：

```text
clean_git_tree = true
unclassified_changes = 0
secret_scan_hits = 0
forbidden_source_paths = 0
```

如确需开发期试包，可提供显式 `-AllowDirty`，但该模式必须在 README 和 manifest 标记 `non_releasable=true`，并禁止命名为正式客户包。

**Step 4：聚焦验证**

```powershell
Set-Location backend
python -m pytest tests/unit/test_verify_release_source.py -q
```

**Step 5：提交**

```powershell
git add .gitignore scripts/verify_release_source.py scripts/package-customer-release.ps1 backend/tests/unit/test_verify_release_source.py
git commit -m "增加发布源码与敏感配置门禁"
```

---

### Task 2：把当前功能改动拆成可审查的逻辑提交

**Files:**

- Modify: 仅限 `change-inventory.json` 中 A/B 类路径
- Create: `docs/releases/<RELEASE_ID>/commit-ledger.md`

**Step 1：建立提交顺序**

建议按依赖顺序拆分，不按“前端一包、后端一包”粗暴归类：

1. 数据库迁移与模型。
2. 数据同步、Bundle 与文书字段。
3. Native 规则与 Canonical Envelope。
4. Envelope 保存和单一结果 API。
5. 样本池与在院/出院状态。
6. 前端纯渲染与交互。
7. 发布脚本、测试和文档。

**Step 2：逐文件审查 diff**

每个提交前检查：

```powershell
git diff -- <path>
git diff --check -- <path>
```

禁止：

- `git add .`
- 为通过类型检查而引入共享类型的宽泛 `any`
- 提交自动生成的 `src/components.d.ts`
- 把旧聚合状态解释逻辑重新接回结果链
- 把互不相关的临时修复塞入同一提交

**Step 3：每个逻辑提交做聚焦验证**

按改动选择最小相关测试。示例：

```powershell
Set-Location backend
python -m pytest tests/unit/test_sample_sync_cursor_repository.py tests/unit/test_sample_sync_incremental_capability_audit.py -q
python -m pytest tests/unit/test_custom_qc_sample_pool_service.py tests/unit/test_qc_sample_pools_router.py -q
python -m pytest tests/unit/test_custom_qc_workspace_service_records.py tests/unit/test_records_qc_detail_doc_preference.py -q
```

前端结果链改动运行：

```powershell
npm run test:unit:release
npm run type-check:release
```

完整检查只在功能闭环结束和正式打包前运行，不在每个微小补丁后重复执行。

**Step 4：记录提交台账**

`commit-ledger.md` 每项记录：

- commit SHA
- 业务目标
- 涉及路径
- 聚焦测试
- 已知风险
- 回滚方式

**Step 5：停止条件**

以下任一情况出现时停止合并该改动，转入 C/F 类：

- 不能用真实业务目标解释改动。
- 必须同时大改多个旧链才能“看起来能用”。
- 缺少数据或客户口径，无法确定状态语义。
- 聚焦测试通过但真实结果链仍需前端或聚合器二次解释。

---

### Task 3：清除发布阻塞型重复实现，不做大规模重构

**Files:**

- Inspect/Modify if proven safe: `backend/app/services/custom_qc_workspace_service.py`
- Test: `backend/tests/unit/test_custom_qc_workspace_service_records.py`
- Create: `docs/releases/<RELEASE_ID>/deferred-tech-debt.md`

**Step 1：验证重复定义**

当前只读分析发现 `CustomQCWorkspaceService` 中存在同名方法重复定义风险：

- `_build_records_query`
- `_serialize_record_row`

先用 AST 和 CodeGraph 确认实际生效定义、调用者和两份实现差异。

**Step 2：建立行为测试**

测试至少覆盖：

- 在院病历无 `medical_record_frontpage` 时仍可返回主记录。
- 已出院病历正常返回。
- 科室、日期、住院状态筛选不互相误伤。
- 序列化字段兼容现有前端 DTO。

**Step 3：最小处理**

只有当两份实现语义等价且测试能证明时，删除被覆盖的死定义；如果语义不等价或影响范围不明，不在本轮删除，记录到 `deferred-tech-debt.md`。

**Step 4：验证**

```powershell
Set-Location backend
python -m pytest tests/unit/test_custom_qc_workspace_service_records.py tests/unit/test_medical_records_service.py -q
```

**Step 5：提交**

仅在确有安全修改时：

```powershell
git add backend/app/services/custom_qc_workspace_service.py backend/tests/unit/test_custom_qc_workspace_service_records.py docs/releases/<RELEASE_ID>/deferred-tech-debt.md
git commit -m "清除发布阻塞的病例查询重复实现"
```

否则只提交技术债台账。

---

### Task 4：建立全局发布清单

**Files:**

- Create: `scripts/generate_release_manifest.py`
- Create: `scripts/verify_release_manifest.py`
- Test: `backend/tests/unit/test_release_manifest.py`
- Modify: `scripts/package-customer-release.ps1`

**Step 1：定义 manifest 契约**

包根目录生成 `release-manifest.json`，至少包含：

```json
{
  "schema_version": 1,
  "release_id": "<RELEASE_ID>",
  "generated_at": "ISO-8601",
  "source": {
    "git_head": "40-char SHA",
    "git_dirty": false
  },
  "frontend": {
    "package_version": "1.0.0",
    "build_mode": "customer",
    "dist_sha256": "..."
  },
  "backend": {
    "source_sha256": "...",
    "python_version": "..."
  },
  "database": {
    "alembic_heads": ["20260731_000024"],
    "required_upgrade_from": "20260729_000023"
  },
  "qc_runtime": {
    "manifest_sha256": "...",
    "rule_set_id": "...",
    "bundle_schema_version": "..."
  },
  "package": {
    "file_count": 0,
    "content_sha256": "..."
  }
}
```

全局 manifest 引用现有 LX0609 runtime manifest 的哈希，不复制或改写其规则语义。

**Step 2：写失败测试**

覆盖：

- 脏树不能生成正式 manifest。
- Git SHA 不匹配时校验失败。
- 迁移出现多 head 时失败。
- 任一文件被修改、遗漏或额外注入时哈希校验失败。
- manifest 不得包含密钥或绝对客户路径。

**Step 3：实现生成与校验**

文件树哈希必须使用排序后的相对路径和单文件 SHA-256，避免时间戳或 ZIP 顺序导致不可复验。

**Step 4：验证**

```powershell
Set-Location backend
python -m pytest tests/unit/test_release_manifest.py -q
```

**Step 5：提交**

```powershell
git add scripts/generate_release_manifest.py scripts/verify_release_manifest.py scripts/package-customer-release.ps1 backend/tests/unit/test_release_manifest.py
git commit -m "绑定发布包源码迁移与运行时清单"
```

---

### Task 5：建立数据库迁移发布门禁

**Files:**

- Create: `scripts/verify_alembic_release.py`
- Test: `backend/tests/unit/test_verify_alembic_release.py`
- Modify: `docs/deployment/客户机交付包编译打包指南.md`
- Create: `docs/releases/<RELEASE_ID>/database-upgrade.md`
- Create: `docs/releases/<RELEASE_ID>/database-rollback.md`

**Step 1：写迁移图测试**

验证：

- `python -m alembic heads` 只有一个 head。
- 最新 head 为发布清单声明的版本。
- `000023 → 000024` 路径连续。
- 打包后的 `backend/alembic/versions` 包含所需迁移。
- 升级前版本不在支持范围时阻塞并给出客户可读提示。

**Step 2：实现只读预检**

开发阶段默认只读取迁移图和数据库当前版本；任何数据库写操作必须在隔离测试库中进行。

**Step 3：隔离数据库升级验证**

在可丢弃数据库或生产库副本运行：

```powershell
Set-Location backend
python -m alembic current
python -m alembic heads
python -m alembic upgrade head
python -m alembic current
```

预期最终版本：

```text
20260731_000024 (head)
```

**Step 4：回滚演练**

在同一隔离数据库验证回滚到升级前版本，再重新升级。若迁移因数据写入不可逆，文档必须明确采用“数据库备份恢复”而不是伪造 downgrade。

**Step 5：提交**

```powershell
git add scripts/verify_alembic_release.py backend/tests/unit/test_verify_alembic_release.py docs/deployment/客户机交付包编译打包指南.md docs/releases/<RELEASE_ID>/database-upgrade.md docs/releases/<RELEASE_ID>/database-rollback.md
git commit -m "完善客户版数据库升级与回滚门禁"
```

---

### Task 6：把打包脚本升级为失败即停止的正式流水线

**Files:**

- Modify: `scripts/package-customer-release.ps1`
- Create: `scripts/verify_release_package.py`
- Test: `backend/tests/unit/test_verify_release_package.py`
- Modify: `docs/deployment/客户机交付包编译打包指南.md`

**Step 1：明确流水线顺序**

`package-customer-release.ps1` 正式模式按以下顺序执行：

1. 源码预检。
2. Alembic 单 head 与迁移包含性检查。
3. customer mode 前端构建。
4. 复制后端、前端、工具和必要文档。
5. 生成发布 manifest。
6. 扫描敏感内容和外部 API 域名。
7. 校验包内文件哈希。
8. 压缩 ZIP。
9. 解压 ZIP 到新临时目录并再次校验。
10. 输出 release ID、Git SHA、迁移 head、ZIP SHA-256。

**Step 2：补齐禁止项**

除现有规则外，还需阻塞：

- `.git/`、`.codegraph/`、`.codex/`
- `.env*` 中非模板文件
- 私钥、证书私钥、token 形态的敏感值
- 测试数据库和客户数据导出
- 旧 `dist` 与当前 Git SHA 不一致
- 缺失 `release-manifest.json`

**Step 3：保留现有关键检查**

继续保留并测试：

```text
frontend/dist 中不得出现 api.medqc.com
backend/.env 不得进入包
tests、cache、日志和本地向量数据不得进入包
```

**Step 4：聚焦验证**

```powershell
Set-Location backend
python -m pytest tests/unit/test_verify_release_package.py -q
```

**Step 5：提交**

```powershell
git add scripts/package-customer-release.ps1 scripts/verify_release_package.py backend/tests/unit/test_verify_release_package.py docs/deployment/客户机交付包编译打包指南.md
git commit -m "强化客户交付包构建与解包复验"
```

---

### Task 7：在干净工作树执行发布质量门禁

**Files:**

- Create: `docs/releases/<RELEASE_ID>/quality-gate.md`
- Modify only if a real defect is found: corresponding source/test file

**Step 1：创建发布分支**

完成当前工作区的分类和逻辑提交后，创建或切换：

```powershell
git switch -c codex/release-baseline-20260731
```

如果分支已存在，使用现有分支，不覆盖。

**Step 2：创建干净验证 worktree**

从已提交的发布分支创建新的验证目录。新的 worktree 只用于验证和打包，不承接原目录未提交文件。

**Step 3：前端完整门禁**

在 `apps/medqc-web` 运行：

```powershell
npm run check:encoding
npm run lint
npm run type-check
npm run test:unit
npm run type-check:release
npm run test:unit:release
```

记录命令、耗时、通过数和失败原因。不得通过关闭规则或跳过文件强行变绿。

**Step 4：后端发布相关门禁**

```powershell
Set-Location backend
python -m pytest `
  tests/unit/test_sample_sync_cursor_repository.py `
  tests/unit/test_sample_sync_incremental_capability_audit.py `
  tests/unit/test_custom_qc_sample_pool_service.py `
  tests/unit/test_qc_sample_pools_router.py `
  tests/unit/test_custom_qc_workspace_service_records.py `
  tests/unit/test_records_qc_detail_doc_preference.py `
  tests/unit/test_luxian_0609_runtime_manifest.py `
  -q

python -m pytest tests/integration/test_release_gate_smoke.py -q
```

**Step 5：质控运行时闸门**

使用现有脚本和与当前 Git HEAD 匹配的 runtime manifest 运行 LX0609 release gate。若黄金样本闸门尚未满足，不得将“单测通过”写成“规则已正式验收”；应在发布说明中明确规则覆盖状态和 pending 口径。

**Step 6：验收**

`quality-gate.md` 必须包含：

- Git SHA
- Node/Python 版本
- 每条命令及结果
- 失败修复对应 commit
- 未执行项及原因
- 最终结论：PASS / BLOCKED

**Step 7：提交证据**

```powershell
git add docs/releases/<RELEASE_ID>/quality-gate.md
git commit -m "归档发布基线质量门禁证据"
```

---

### Task 8：生成并复验正式交付包

**Files:**

- Generated outside Git: `<OUTPUT_ROOT>/medqc-web-customer-<RELEASE_ID>.zip`
- Create: `docs/releases/<RELEASE_ID>/package-verification.md`

**Step 1：从干净验证 worktree 打包**

```powershell
.\scripts\package-customer-release.ps1 -OutputRoot '<OUTPUT_ROOT>'
```

正式包禁止使用 `-AllowDirty` 或 `-SkipBuild`。

**Step 2：校验 ZIP**

```powershell
python scripts/verify_release_package.py '<ZIP_PATH>'
```

预期：

```text
source_clean: PASS
manifest: PASS
hashes: PASS
alembic_head: 20260731_000024
external_api_scan: PASS
secret_scan: PASS
```

**Step 3：解包启动冒烟**

在全新临时目录：

- 后端执行模块导入或 `compileall`。
- 读取 Alembic 配置和 migration graph。
- 前端静态服务启动后，验证登录页资源均为 200。
- 验证 API base URL 指向客户部署配置，而不是公网域名。
- 验证健康检查、鉴权拒绝和授权接口行为。

**Step 4：记录**

`package-verification.md` 记录 ZIP SHA-256、大小、文件数、manifest 摘要、解包目录和冒烟结果。ZIP 本身不提交 Git。

---

### Task 9：客户等价环境业务演练

**Files:**

- Create: `docs/releases/<RELEASE_ID>/customer-rehearsal.md`
- Create: `docs/releases/<RELEASE_ID>/acceptance-checklist.md`

**Step 1：准备隔离环境**

使用客户环境配置的副本和脱敏/授权样本，不连接客户生产写库。记录旧版本、旧迁移版本、服务启动方式和备份位置。

**Step 2：执行升级**

按包内文档完成：

1. 停止旧后端。
2. 备份数据库和旧程序目录。
3. 替换程序文件。
4. 执行 Alembic upgrade。
5. 启动后端和前端。
6. 验证 manifest 与实际运行版本一致。

**Step 3：业务验收矩阵**

至少验收：

| 场景                   | 预期                                                     |
| ---------------------- | -------------------------------------------------------- |
| `/workstation-v4` 登录 | 正常登录，无公网 API 请求                                |
| 样本池列表             | 在院、已出院状态明确且均可显示                           |
| 无首页在院病历         | 可进入样本池，不因缺 `medical_record_frontpage` 被拒绝   |
| 第一阶段同步           | 主记录、住院登记、入院记录就绪后病例立即可见             |
| 第二阶段同步           | 文书、医嘱、检查检验后台补齐，页面显示“文书整理中”       |
| 质控启动               | 数据验证不误报“未同步到当前 PG”                          |
| 结果读取               | 单一结果 API 返回对应病历的 Canonical Envelope           |
| 前端结果               | 只渲染 Envelope，不重新解释状态                          |
| Bundle 文书            | 检验按报告归并，签名、关键时间、手术/麻醉/输血文书不丢失 |
| 迁移版本               | `20260731_000024 (head)`                                 |

优先使用已经持续验证的病例 `208790`、`359787`，同时补一个无 `medical_record_frontpage` 的在院病例和一个已出院病例。

**Step 4：性能记录**

记录：

- 病例进入样本池耗时。
- 文书整理完成耗时。
- 单病历质控耗时。
- 当前并发数和每条规则调用次数。
- 结果 API 响应时间。

若比既有基线明显退化，发布状态标记 BLOCKED，先定位真实瓶颈，不通过增加无界并发掩盖问题。

**Step 5：回滚演练**

验证：

- 服务可停。
- 旧程序目录可恢复。
- 数据库按已验证策略恢复。
- 旧版本可重新启动。
- 回滚后核心查询正常。

**Step 6：形成签字清单**

`acceptance-checklist.md` 每一项标记：验证人、时间、证据、PASS/BLOCKED、遗留风险。

---

### Task 10：发布封板与技术债转账

**Files:**

- Modify: `docs/releases/<RELEASE_ID>/deferred-tech-debt.md`
- Create: `docs/releases/<RELEASE_ID>/release-notes.md`
- Create: `docs/releases/<RELEASE_ID>/known-issues.md`
- Create: `docs/releases/<RELEASE_ID>/final-signoff.md`

**Step 1：技术债分级**

至少记录以下候选债务：

- 超大 Vue 页面和结果抽屉拆分。
- 超大样本池/工作区服务拆分。
- 重复方法和被覆盖死代码。
- Bundle schema 的单一所有者和版本升级策略。
- 老聚合器与前端状态二次解释链的彻底下线。
- 规则定义、字典和客户 pending 口径的配置化治理。
- 数据同步的增量游标、失败重试、幂等性和可观测性。

每条债务必须写清：

- 客户影响
- 当前规避方式
- 是否阻塞发布
- 根因
- 建议边界
- 验收指标
- 依赖和优先级

**Step 2：封板判断**

只有以下全部满足才可标记 READY：

- 清账分类完成。
- 所有发布 commit 已审查。
- 干净工作树质量门禁通过。
- manifest 和 ZIP 哈希通过。
- 迁移与回滚演练通过。
- 客户等价业务矩阵通过。
- 已知问题均有客户影响说明和回退策略。

**Step 3：最终标签与归档**

发布负责人确认版本号后再创建 Git tag。不得用日期临时包冒充已签字正式版本。最终归档：

- Git SHA / tag
- ZIP SHA-256
- release-manifest
- 数据库 head
- quality gate
- customer rehearsal
- rollback result
- known issues

---

## 6. 建议执行节奏

| 阶段      | 内容                             | 预计耗时 |
| --------- | -------------------------------- | -------: |
| 第 1 阶段 | 快照、全量分类、范围冻结         | 0.5–1 天 |
| 第 2 阶段 | 逻辑提交、发布阻塞缺陷处理       |   1–2 天 |
| 第 3 阶段 | manifest、迁移和打包门禁         |     1 天 |
| 第 4 阶段 | 干净构建、解包复验、客户等价演练 |     1 天 |
| 第 5 阶段 | 封板、发布说明、技术债转账       |   0.5 天 |

预计总计 4–5.5 个工作日。若第一阶段发现大量 F 类改动，时间应优先用于澄清归属，不应压缩验证环节。

## 7. 关键风险和控制

| 风险                   | 控制措施                                                         |
| ---------------------- | ---------------------------------------------------------------- |
| 清账时丢失未提交工作   | 先做外部二进制 diff、未跟踪清单与哈希快照；禁止 reset/clean      |
| 本机能用、客户机不能用 | 绑定 Git SHA、迁移 head、构建模式和包哈希；做解包与客户等价演练  |
| 迁移遗漏               | manifest 声明 head，包内迁移图校验，隔离库 upgrade/rollback 演练 |
| 旧前端指向公网 API     | customer mode 构建、静态扫描、运行时网络请求冒烟三重检查         |
| 测试通过但结果链错误   | 用真实病例验证 Envelope 保存/API 原样返回/前端只渲染             |
| 技术债扩散发布范围     | 仅处理明确阻塞项，其余进入 deferred ledger                       |
| 自动生成文件反复污染   | `components.d.ts` 保持开发默认不生成，生成物不得进入提交         |
| 客户口径尚未确认       | 标记 pending，发布说明明确，不伪装为已完整覆盖                   |

## 8. Definition of Done

发布基线清账完成，不等于“代码能编译”，而是以下事实均成立：

1. 当前要发布的代码已经被完整识别和逐项提交。
2. 任意交付包都能反查到唯一 Git SHA、迁移 head 和规则运行时清单。
3. 同一个 ZIP 在新目录解压后可独立通过校验和启动冒烟。
4. 客户等价环境完成升级、业务验证和回滚演练。
5. 在院/出院病例、样本同步和质控结果直通链均有真实病例证据。
6. 未完成的架构债和规则口径已从发布范围中剥离，并进入有优先级的技术债台账。
