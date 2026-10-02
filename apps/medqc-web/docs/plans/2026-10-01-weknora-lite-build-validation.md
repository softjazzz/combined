# WeKnora Lite 独立构建与接口验证

日期：2026-10-01。用户授权：独立构建 Lite，再做启动和接口验证。

## 交付结论

官方 v0.8.2 源码在本机 Windows 原生构建成功，独立服务已启动于 `http://127.0.0.1:18083`，浏览器显示正常登录页。使用独立 SQLite、本地存储和内存队列，无需 Docker 或 WSL。重启后账号、知识库、文档、API Key 均保留，接口复验通过。

已验证合成文档的入库、检索结果关联同一文档、原文读取，以及只读 Key 的范围与写入拒绝。通用搜索和入库的嵌入接口使用本地固定向量测试桩；真实 Embedding、真实规范与语义质量尚未验收。未调用真实模型，未消耗既有业务助手 10/10 之外的真实聊天预算。

## 独立目录和运行

- 根目录：`D:/LLM/WeKnora-Lite-evaluation`。
- 源码：`WeKnora-0.8.2/`；对照下载归档逐一校验 4355 个普通文件，改动为 0。
- 运行包：`runtime/WeKnora-lite.exe`、`runtime/web/`、`runtime/config/`、`runtime/migrations/sqlite/`。
- 数据：`runtime/data/weknora.db`、`runtime/data/files/`。
- 配置和测试凭据：`runtime/backend/.env`。登录邮箱与密码对应 `LITE_TEST_EMAIL`、`LITE_TEST_PASSWORD`，只读 Key 对应 `WEKNORA_API_KEY`。这些是独立测试身份，不是 MedQC 的 admin 账号；不在聊天或仓库公开密钥。
- 构建脚本：`build-lite.ps1`；启动：`pwsh -NoProfile -File D:/LLM/WeKnora-Lite-evaluation/run-lite.ps1`。当前已作为隐藏后台进程运行，未安装系统服务或开机自启。
- 日志：`runtime-stdout.log`、`runtime-stderr.log`；验证证据：`build-verification.json`、`api-verification.json`、`dsh-verification.json`。
- 复验：`python D:/LLM/WeKnora-Lite-evaluation/verify-lite.py`，会临时启动仅监听本机 18084 的固定向量测试桩，并调用本工作树已安装的 DSH 客户端。执行结束后测试桩关闭。不能用该脚本评估模型质量。

主 MedQC 服务、共享数据库和任务队列、旧 `D:/LLM/WeKnora` 未更改；未把测试 Key 写入 MedQC 配置，也未修改 MedQC 或 WeKnora 产品源码。

## 可复现的构建条件

工具均下载到上述独立目录，不全局安装、不修改系统 PATH：

| 项目          | 已验证条件                                                                                       |
| ------------- | ------------------------------------------------------------------------------------------------ |
| Go            | 1.26.8 windows/amd64，`GOTOOLCHAIN=local`                                                        |
| C/C++         | WinLibs GCC 16.2.0，MinGW-w64 14.0.0 UCRT/POSIX/SEH                                              |
| CGO           | `CGO_ENABLED=1`，tag `sqlite_fts5`                                                               |
| SQLite 头文件 | 来自锁定依赖 `go-sqlite3@v1.14.24` 的 `sqlite3-binding.h` 与 `sqlite3ext.h`，仅增加 include 路径 |
| 前端          | Node 24，`npm ci --no-audit --no-fund`、`npm run build` 成功；有体积提示，无构建错误             |
| 二进制        | 267592192 字节，SHA256 `871CF5F82E88990B5A5B798229D8B6157DB6059037F48CFF6CE77D0AC1FE0510`        |

失败尝试保留：LLVM 首次缺 SQLite 头文件，补齐后仍与 DuckDB 的 GCC C++ ABI 不匹配；w64devkit 的运行库组合仍缺 UCRT/线程符号。最终 UCRT/POSIX 工具链完成链接。PE 导入表仅列 Windows 系统 DLL，重启时已移除运行脚本对编译器 PATH 的依赖。

Go 压缩包官方 SHA256：`b92c3b2adae85a11ba71fe7216daf0d84e82af4c8ab6c5625807f28622043a59`；最终 WinLibs ZIP 的 GitHub asset digest：`d5dbafc4a170e762ca6143151ec918fb9e2c72736fb14cd704abebc6bdd5276a`，下载均校验一致。二进制哈希是本机构建产物标识，不是官方发布签名。

## 实测接口和边界

只使用标题为“Lite独立验证说明（合成测试）”的手工 Markdown，内含 `LITEPROBE20261001` 标记与“不是医疗规范、不含患者资料”的说明。另建空的越界反例库。所有数据仅在新建 SQLite 内。

| 检查                                 | 实际结果                                                                                                  |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `/health`、首页、登录                | HTTP 200；初始注册 201；浏览器显示登录表单                                                                |
| 无 Key、无效 Key 读取知识库          | HTTP 401                                                                                                  |
| 文档发布和解析                       | 经本地嵌入测试桩后 `completed`，保存 1 个正文块                                                           |
| 限定库只读 Key 列表                  | HTTP 200，仅返回允许的 1 个库                                                                             |
| `/knowledge-search`                  | HTTP 200，命中测试标记；该入口仍请求嵌入测试桩                                                            |
| `/knowledge-bases/:id/hybrid-search` | `disable_vector_match=true`，关键词命中 1 条，无嵌入请求                                                  |
| 关键词负例                           | 测试桩停止后，不存在的标记返回 HTTP 200、0 命中                                                           |
| 文档详情及 `/chunks/:id`             | HTTP 200，正文包含原始标记                                                                                |
| 只读 Key 访问另一个真实存在的测试库  | HTTP 403                                                                                                  |
| 只读 Key 创建知识库                  | HTTP 403，未创建                                                                                          |
| DSH `@wxg-prc-cpg/dsh-weknora@0.1.0` | 实际执行列表、名称查找、详情、分块、搜索共 5 个方法，全部通过；搜索结果 `knowledge_id` 与读取文档 ID 相同 |
| 重启持久化                           | 重启前后完整接口和 DSH 复验通过                                                                           |

最终一次复验的本地嵌入测试桩请求为 2 次（直接通用搜索、DSH 搜索各一次），真实模型请求为 0。该计数仅指最后一次复验，不是所有调试运行的累计值。数据量只有 1 份合成文档，不代表生产性能或检索质量。

## 已发现的兼容限制

1. 知识库配置 `vector_enabled=false, keyword_enabled=true`，入库仍会按实例默认引擎走向量路径：`knowledge_process.go` 调用 `CreateRetrieveEngineForKB`，未绑定存储时后者使用 `tenant.GetEffectiveEngines()`；SQLite 默认映射含关键词与向量。第一次本地拒绝式测试桩收到 5 次尝试，文档正确记为 failed。之后用固定向量桩验证基础设施，未改源码来掩盖该事实。
2. `/knowledge-search` 仍需要嵌入服务；显式关闭向量的 KB hybrid-search 可以纯关键词读取。因此“Lite 无 Docker”不等于“DSH 通用搜索不需要模型”。测试桩已关闭，当前通用搜索不能作为真实可用检索交付；列表、详情、原文和显式关键词读取不依赖测试桩。
3. 测试占位模型无真实凭据，地址仅指向本机 18084。正式接入前需更换为获授权的真实 Embedding 配置，并重新索引测试资料；不能沿用固定向量索引评估排序或回答。
4. 默认构建未包含 anydoc；扫描 PDF、复杂 DOCX、真实规范引用页码、模型回答质量和 MedQC 助手完整端到端尚未验收。
5. 本次未扩展 SQLBot、写业务工具或更换聊天模型；未将管理员联调表述为生产医院医生/科室权限验收。

## 下一步

使用获授权的真实 Embedding 配置和少量带条款号、出处的规范重建索引，验证检索→引用→原文，再接入 MedQC 工作树的限定库配置。真实聊天质量仍需明确新的调用预算。独立构建、启动与接口合同验证已完成，不能据此宣布业务助手全部完成。

本次仓库仅增加/更新交接文档；运行产物、日志、测试脚本、SQLite 与凭据均留在独立目录，不提交。提交前暂存区编码检查（3 文件）与完整 Lint 通过；MedQC 产品源码未变，不重复运行此前已通过的类型检查及上海时区 1173 项单测。
