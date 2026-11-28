# MedQC 架构边界治理清单（2026-11）

- **固定审查基线**：`0a8b3aa86`（`codex/business-agent-integration`，树指纹 `8aab2dfa35afa1908b62ea3447a9dd9cdc2d7771`）
- **总体原则**：保留现有模块化单体，按“权限判定 → 底层去重与仓库清理 → 取材/冻结边界 → 0609 规则族拆分（排在 PR #90 合入之后）”分批推进；每批迁移完成同批删除旧副本并补 AST/回归门禁。

---

## 权威口径决策（已确认）

1. **全局质控规则修改权限**（用户 2026-11-27 拍板）：
   - **绑定了具体院区（`institute_id` 非空）的 `admin` 与 `super_admin` 均不允许修改全局质控规则**；仅 `sync_admin` 或未绑定院区的 `admin`/`super_admin` 放行。
   - 持久账号复核发生意外数据库异常时，**统一 fail-closed 返回 HTTP 503**，禁止回退到令牌声明放行（仅离线 SQLite 单测未建 `sys_users` 表时允许受控回退）。
   - 统一入口：`app/core/security.py::require_global_qc_rule_admin`；持久化角色解析归位 `app/core/roles.py::effective_persistent_roles`。

---

## 批次执行台账

| 批次 | 范围 | 状态 | 改动/删除摘要与验证证据 |
| :--- | :--- | :--- | :--- |
| **批次 1（PR #91）** | ① 5 个规则管理路由全局管理员权限归一 + 503 fail-closed<br>② 5 个路由 `_table_columns` 去重<br>③ `_effective_persistent_roles` 归位 `core/roles.py`<br>④ 核查 `qc_sichuan.py:538` 旧结果读取调用点 | **已合入**（`4c9464a40`） | - **权限归一**：`semantic_rules` / `scoring_rules` / `rule_validation` / `custom_qc` / `qc_sichuan` 全部删除各自 `_is_global_admin_sync`（共消除 5 处 fail-open `except Exception: pass`），统一委托 `app.core.security.require_global_qc_rule_admin`，保留各自错误文案。<br>- **表结构探测去重**：新增 `app/database/schema_introspection.py::get_table_columns`，迁移 `appeals` / `defects` / `qc` / `remediation` / `reports` 并删除 5 份副本。<br>- **AST 门禁与单测**：`tests/unit/test_arch_gov_batch1_auth_and_schema.py`（停用账号、绑定院区 `admin`/`super_admin`、全局账号、DB 异常 503、PG/SQLite schema 顺序、防副本回流 AST 检查）。 |
| **批次 2（PR #92）** | ① 核实医保前端 `evaluateRulesByDbContext` / `ruleEngine.ts` 无外部消费者后删除<br>② 迁完 `Yibao/` 下 6 个硬编码 `pdf_converter_venv` 路径的脚本，清理工具改为清单+SHA-256 校验安全删除，并通过普通提交 `git rm` 移除跟踪的 12,059 个虚拟环境文件 | **已合入**（`a7230625a`） | 已移除死代码 `ruleEngine.ts` 及未使用入口；`Yibao/` 脚本解耦并通过正常菜单/预览-修改-确认验收；`pdf_converter_venv/` 退跟踪。 |
| **批次 3（PR #93）** | ① `case_material_capture.py` 改经读取模块显式合同获取来源与字段，移除对 `assembly._*` / `reader._*` 私有属性及 `walk_tb` 函数名推断阶段依赖<br>② 统一 4 个冻结模块底层锁/原子替换/范围键机制<br>③ `department_qc_rules.py:_resolve_qc_manager_scope` 收口为 fail-closed 503 | **已合入**（`938e33997`） | 显式阶段标记与公开契约落地；4 个冻结模块复用 `freeze_storage.py`（`-520` 重复行）；科室权限移除 `anonymous` 特例与缺表/缺列文本宽放行，5/5 CI 全绿。 |
| **批次 4 · Pilot #1（PR #94）** | 从 `native_extended_document_execution.py` 拆出首个规则族 **危急值族（`LX0609-06-04-01` / `LX0609-06-04-02`）**，沉淀扩展文书规则族公共运行时契约 `extended_document/family_runtime.py` 与组内 `SourceRowsCache` | **已合入**（`bb02a3ab0`） | - 新增 `extended_document/family_runtime.py` 与 `extended_document/critical_value_family.py`。<br>- `native_extended_document_execution.py` 净删 `1,278` 行（`8,129 → 6,854`）；引入 `SourceRowsCache` 保证检验主表/明细组内单次读取；5/5 PR CI 与 2/2 主干 CI 全绿。 |
| **批次 4 · Family #2（本 PR）** | 从 `native_extended_document_execution.py` 拆出 **抗菌药规则族（`LX0609-05-01-02..06` / `05-03-01`）**，连同 `order_reason_cache`、特殊级专家审批、疗效评估与用量统计一并迁出 | **进行中** | - 新增 `extended_document/antimicrobial_family.py`；将共用的医院时间解析、出院时间与评价终点读取沉淀至 `family_runtime.py`。<br>- `native_extended_document_execution.py` 净删 `1,435` 行（`6,854 → 5,419`）；纯抗菌药组直通快速路径不再读取死亡/出院/转出/输血等 15 张无关来源，混合顺序组通过 `SourceRowsCache` 保证共享来源单次读取。<br>- 新增 `tests/unit/test_arch_gov_batch4_antimicrobial_family.py` 验证基线 `bb02a3ab0` 判定/原因码/证据引用、共享抽取次数、冻结回读、单次取材与 AST 边界。 |

---

## 批次 1 专项核查记录

- **`qc_sichuan.py:538`（`_can_read_all_saved_qc_results` / `_can_read_saved_qc_result`）**：
  - 仅用于旧文件型历史结果目录 `storage/qc_results/*.json` 的 3 个只读端点：`GET /api/v1/qc/sichuan/results`（`L4060`）、`GET /api/v1/qc/sichuan/results/latest`（`L4163`）、`GET /api/v1/qc/sichuan/results/{result_id}`（`L4187`）。
  - 现行测试 `tests/unit/test_sync_admin_business_read.py:77` 断言 `sync_admin` 返回 `True`；暂未发现现场跨院读取证据，后续在批次 3 评估是否与持久化账号/院区作用域收口对齐。
- **`department_qc_rules.py:78-154`（`_resolve_qc_manager_scope`）**：
  - 复核时发现其同样存在 `except Exception: pass` 回退到令牌声明的科室作用域查询，已登记至批次 3 同步收口为 fail-closed 503。
