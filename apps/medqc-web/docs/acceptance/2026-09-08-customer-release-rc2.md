# 客户部署包 RC2 包内验收记录（2026-09-08）

## 当前结论

发布源码已收口、干净工作树正式构建和 ZIP 内容校验通过；**包内业务验收未完成，不能视为已验收交付**。
病历列表在只读验收连接下被运行时自动 DDL 阻断，因此本轮未完成包内病历结果和诊断预览/下载闭环。

## 构建来源与产物

- 发布源码：`9c82190df1642fcdf465a52c53093ac9b8a45d6c`。
- 构建目录：`D:/LLM/LX888/apps/medqc-web/.release-packages/20260908-rc2/source`，构建前后 Git 状态均干净。
- 命令：`scripts/package-customer-release.ps1`，指定本轮 inventory 与发行私钥路径；未使用 AllowDirty、SkipBuild。
- 发布包：`medqc-web-customer-20260908-155224.zip`，10,272,291 字节，1192 个归档条目。
- 路径：`D:/LLM/LX888/apps/medqc-web/.release-packages/20260908-rc2/artifacts/medqc-web-customer-20260908-155224.zip`。
- SHA256：`14833865457766845e54e749a1e811ba622b3ed3614a6fd8a31cd70f215f83ec`。
- 包内 `runtime_build.json` 的提交号、build_id 与源码及包名一致。
- 此包为前端静态资源 + 后端源码部署 ZIP；不包含 Python 运行环境、数据库、客户配置或 ICD 向量索引。

## 本轮收口的发布阻断

1. Vite 非零退出码和缺少 dist/index.html 必须阻断打包，避免复制旧产物。
2. 离线授权显式参数齐全时不读取服务器 Settings，干净环境无需 JWT_SECRET 即可签发。
3. 5 个旧页面/服务的 6 处公网 API 分支复用已有 resolveApiBaseUrl；源码和产物门禁覆盖旧公网 IP。
4. 首页移除搜索输入后保留 URL 关键词可见/可清除入口，清除时保持当前科室并避免重复请求。

## 已通过检查

- 前端完整 type-check 通过；最终全量单测 111 文件 / 891 项通过（52.84 秒）。
- 全量只读 ESLint 0 errors / 668 既有 warnings；最终改动定向 ESLint 与提交钩子通过。
- check:encoding 通过，但工具本次报告扫描 0；收口阶段另行核对变更文本 UTF-8 无 BOM。
- 后端规则/Canonical/诊断包聚焦回归 505 项通过；授权 16 项通过。
- 源码门禁 7 项、打包/预检合同 14 项通过，包含真实 PowerShell 产物门禁执行。
- ZIP CRC、必需运行文件、无私钥、无 .env/本地数据库/临时日志/字体、无已知公网 API 地址检查通过。
- 客户包默认试用授权有效，required=true，edition=trial，到期时间 `2026-12-08T07:54:37Z`。

## 从 ZIP 解压目录运行的验收

解压至 `.release-packages/20260908-rc2/acceptance/medqc-web-customer-20260908-155224`。
使用本机已有 Python 依赖；环境仅由原 backend/.env 读入进程，不写入 ZIP；授权状态使用独立文件。
前端 `http://127.0.0.1:3001` 代理到后端 `http://127.0.0.1:8002`。
PostgreSQL 连接额外强制 `default_transaction_read_only=on`，未执行 Alembic upgrade。

| 检查                              | 结果                                    |
| --------------------------------- | --------------------------------------- |
| 深层页面静态路由及浏览器登录      | HTTP 200，进入终末病历页面              |
| /api/v1/health                    | HTTP 200                                |
| OpenAPI 与历史诊断路由            | HTTP 200，prepare/download/discard 存在 |
| /api/v1/product-activation/status | HTTP 200，active                        |
| 通知、样本池列表                  | HTTP 200                                |
| 病历列表                          | HTTP 500，只读连接阻断自动 ALTER TABLE  |

失败证据：`ALTER TABLE qc.custom_qc_batch_jobs ADD COLUMN IF NOT EXISTS job_kind VARCHAR(20) DEFAULT 'leaf'`。
调用位置：`backend/app/services/custom_qc_workspace_service.py::_sync_batch_job_parent_columns`。
启动时既有 CREATE VIEW/CREATE SCHEMA 同样被只读连接阻断，故不能将健康检查成功等同完整启动成功。
未通过修改包源码、绕过初始化或模拟结果让业务验收变绿。

## 剩余事项与权限边界

- 需按 AGENTS.md“数据库写操作需要确认”取得授权，才能对本机测试库正常初始化并完成列表、已保存病例结果及诊断导出验收。
- 包内只读预检通过核心表/列；本机 Alembic current=`20260903_000042`，代码 head=`20260903_000043`，不能忽略版本差异。043 涉及非药医嘱 planned_start/end_datetime；未执行升级。
- 先前开发环境的真实病历规则保存和诊断预览已验证；此次包内闭环尚未验证，不能替代。
- 先前 IAB 下载事件 canceled，不能宣称诊断 Markdown 已成功落盘；最终仍需普通浏览器验证实际下载。
- 尚未在全新客户机安装 Python 依赖并验收，不等于可直接运行的 EXE 安装包。
- 非阻断提示：构建大分块、既有组件命名冲突、Browserslist 数据较旧；favicon 文件缺失、登录装饰图片依赖外网。

完整脱敏检查结果和本地日志在 `.release-packages/20260908-rc2/`，生成产物不提交 Git。
