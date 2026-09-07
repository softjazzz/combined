# 诊断包首批：开发侧安全导入与匿名文案回放

## 交付边界

本批是开发侧基础闭环，不是已可安装使用的客户诊断功能。只接受人工匿名回归输入，支持 LX0609-032 不适用文案、LX0609-066 合规计数文案。它能比较已知文案变化，不能重新判断临床事实。

**尚未交付：** 客户侧采集、原始身份脱敏、引用重映射/等价验证、加密存储、权限与下载界面、执行器或录制模型回放、百炼核查、编译安装包验收。不能把真实病历改一个 synthetic 标签就作为可外发诊断包。

## 文件与调用

- `backend/app/services/qc_diagnostics/contracts.py`：严格六文件合同；拒绝额外字段、未知版本/规则/能力及不匹配状态。
- `package.py`：仅内存读取 ZIP，绝不解压或执行。限制 ZIP 8 MiB、单文件 1 MiB、总内容 4 MiB、压缩比 100、JSON 深度 20/节点 20000；拒绝穿越、重复、特殊文件、加密、非标准压缩、CRC/校验和错误、重复 JSON 键和非有限数值。
- `replay.py`：仅调用当前本地既有文案函数，源观察文本只比较不回显。包内意见不作为指令或判定金标准。
- `backend/scripts/qc_diagnostic.py`：开发机只读 CLI。inspect 不要求 Git；replay 读取本地版本并检查后端工作区干净。
- `backend/tests/fixtures/qc_diagnostics/render-wording-v1.json`：人工匿名输入集合，不是可直接导入 ZIP。集成测试按原始 JSON 字节生成文件清单校验和和 ZIP。

在项目根目录：

```powershell
python backend/scripts/qc_diagnostic.py inspect C:/diagnostics/anonymous.zip
python backend/scripts/qc_diagnostic.py replay C:/diagnostics/anonymous.zip
# 跨版本必须明确选择比较；不能据此宣称原版本复现。
python backend/scripts/qc_diagnostic.py replay C:/diagnostics/anonymous.zip --compare-current
```

成功返回 JSON/退出码 0；拒绝返回固定安全错误码/退出码 2。文案有差异仍返回 0，调用方检查 `findings_equal`，不要把退出码当作医学正确性结果。`privacy_verified`、`evidence_verified`、`clinical_correctness_verified` 恒为 false，明确本批能力限制。

Checksum 只能检测清单与字节不匹配，**不验证来源身份**。观察文案、源版本及 synthetic 声明都是不可信包数据。`status_unchanged`/`reason_unchanged` 表示合同一致，不是重新执行规则得到的结果。

## 真实缺陷对应的匿名回归

| 规则 | 已知旧文案问题                         | 本地文案函数回放                                   |
| ---- | -------------------------------------- | -------------------------------------------------- |
| 032  | 把未触发正式手术记录条件说成未实施手术 | 保持不适用状态，文案明确缺少核查所需的正式手术记录 |
| 066  | 用记录数量宣称逐台关联符合要求         | 保持输入状态，只陈述手术台数和记录份数             |

计数为人工构造，不能把该验证表述为重跑客户病例。066 调用 `customer_finding_from_controlled_facts`，032 调用 `not_applicable_customer_message`；报告带 projection，不声称整条 Finalizer/保存/API 链路回放。

## 安全接缝及验证

实际新进程验证发现 032 完整 renderer 会经目录加载资料组件与 SQLAlchemy。新增 7 行纯文案查询，并将原 renderer 分支改为复用它，生产净增 6 行，没有迁移业务职责、重判状态或改变映射。所有既有不适用映射和默认文案均保持一致，公开 API 仅新增此查询入口。

聚焦测试使用 `--noconftest`，避免项目全局测试启动时初始化 demo SQLite；独立新进程阻止数据库/模型/HTTP 客户端导入以及 socket、SQLite 操作，再执行两条回放。首次该测试失败，修复调用接缝后通过。

```powershell
$env:PYTHONPATH=(Resolve-Path backend).Path
python -m pytest --noconftest -o addopts='' backend/tests/unit/test_qc_diagnostic_contracts.py backend/tests/unit/test_qc_diagnostic_import_safety.py backend/tests/integration/test_qc_diagnostic_replay.py backend/tests/unit/test_luxian_0609_032_applicability_copy.py backend/tests/unit/test_luxian_0609_066_count_finding.py backend/tests/unit/test_luxian_0609_customer_renderer.py -q
```

上述回归加 `backend/tests/unit/test_qc_diagnostic_cli.py`：最终 **499 passed，10.28 秒**（含 96 项诊断专项测试），1 条既有 Pydantic 弃用警告。CLI 门禁含跨版本拒绝/显式比较、脏后端拒绝、Git 失败及错误信息不泄露。

提交前检查：`npm run lint -- --no-fix` 通过（0 errors、652 条既有 UI warnings），未自动格式化用户 UI 改动；`npm run check:encoding` 通过但扫描 0 文件，另对本批 13 个文件逐字节验证 UTF-8、无 BOM、LF；`git diff --check` 通过。本批未改前端或共享 TS/API 类型，未重复运行全量前端类型检查/单测。

注意：子代理最初按普通 pytest 启动，全局 conftest 曾初始化现有 demo SQLite；不是诊断模块访问病历或运行模型。之后切换到隔离测试方式。未触碰客户生产数据、未启动模型或改变正在运行的后端服务。

## 下一检查点

T2 必须验证结构化身份映射、自由文本隐私拦截、病例内日期变换一致性、事实引用重映射和脱敏前后等价；任何不确定泄漏或等价失败都拒绝导出。在该阶段完成前，本批不提供客户导出按钮，也不声称诊断包能直接修复任意质控点。
