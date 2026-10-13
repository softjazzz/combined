# N12 既有测试调用合同适配

本次仅适配 LX0609-04-04-02（037）的测试客户端和调用量断言。生产固定于 `08aed59db3ed9bf08316fc792a757a3ee65d992b`，公共文案支持父提交为 `1b973859d1f95c099745c8af7500c3e937c05772`；不修改生产、原医学输入、状态、缺项、正常值、证据引用或参数化装饰器。

## 变更与保护

- 三个原边界文件的 25 个自由文本用例改用纯标准库人工原子事实客户端。每个用例的 present/absent 与原文片段预先逐项固定；不从生产结果或通用关键词推导答案。
- native、freeze、precise-fact-refs 三个既有 037 用例使用各自明确人工答案。仅 freeze/precise 原文的“呼吸循环稳定”片段人工明确同时支持呼吸、循环两项，不推广为通用文本判定。
- 权限测试仅将 037 移出 program_only，明确检查 v3、program_then_optional_llm、上限 1 和 Prompt 版本。其他规则的客户端与零调用断言保持。
- 客户端核对逻辑调用恰好一次、禁止 length retry、completion 预算不超过 4096、PRE/POST 文书边界和原片段坐标。固定合成 Token 为 10/5/15，不代表真实模型消耗或 HTTP 请求数。
- AST 静态对照证明七个既有文件的原医学断言与参数化输入保留；生产目录无 diff。新 helper 不导入生产或其他测试，避免循环依赖。

## 实际门禁

| 门禁                                                                             | 结果                                                   |
| -------------------------------------------------------------------------------- | ------------------------------------------------------ |
| 新受控抽取 36 + 分组 7                                                           | 43 通过                                                |
| 原 037 边界保护                                                                  | 28 通过                                                |
| native / freeze / precise refs / rule contracts / binding / reducer 六个完整文件 | 275 通过、2 既有失败                                   |
| 同一进程组合、无六文件过滤                                                       | 收集 348；346 通过、2 失败、1 warning；6.38 秒，退出 1 |
| Python Ruff、git diff --check                                                    | 通过                                                   |

两个失败为 freeze 的 029 reason `association_failed` 与原 `requirement_satisfied` 不一致，以及族规则集合多出 031/032；断言原样保留。父 `1b973859d1f95c099745c8af7500c3e937c05772` 相同六文件实际 275 通过、2 同 ID/原因失败（2.78 秒）。适配前固定 core08 六文件 271 通过、6 失败，新增的四项调用合同影响本次已解决。原三文件的 25 项先前停在零调用断言，未曾冒称医学断言通过；本次实际进入并通过原医学断言。

原父版本第一次隔离运行因缺静态配置 collection 失败，日志保留；按固定 git blob 配置闭包补齐后重跑，无 env/runtime/userdata/dependencies 复制。本次静态准备曾发现 freeze 客户端类名笔误，测试启动前修正，未混为生产红测。

合成离线 runner 阻止 env、DNS/外部连接；无真实模型、PG、病例或用户数据。真实模型语义验收仍未完成，限定工程证据不宣布临床语义关闭。

## 提交门禁与资源披露

本次为八个测试路径及本文档。按根协调授权使用真实 Husky pre-commit（lint-staged + staged 编码），不绕过。前端源码/package/config 与既有验收相同；复用 `.tmp/iml01/lint-revision.txt` 的 0 errors、1214 既有 warnings，SHA256 `478FF8AC56E06A91572145C3BCD79A34B586BAF0DAF256E840865B34584A12B6`。本轮受独占资源调度限制未重复前端 lint/type-check/test:unit；不声称本轮全量前端通过。

## 可复核产物

工作树 `.tmp/n12/test-adapted-348.txt`、`.exit.txt`、`test-adaptation-preservation.json`、`six-file-comparison.json`，及 `baseline-1b-manifest.json` 保留结果与父 blob 清单。外部独审目录 `F:/MedQC-worktrees/review-artifacts/n12-closure/` 的核心复核不由本次测试适配替代。
