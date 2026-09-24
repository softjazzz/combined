# 原始 LX0609-004：隔离 SQLite 到 V5 页面的真实 HTTP 技术回读

基线：`2f34e32ae`。日期：2026-09-25。全部身份和结论均为合成数据，不含患者原文，也不使用客户 PostgreSQL。

## 验证范围

`backend/scripts/acceptance/lx0609_live_http_fixture.py` 在独立进程内建立内存 SQLite，将一条原始 `LX0609-09-01-01` 的合成合规结果通过 `CanonicalResultStore.replace_for_job` 保存。测试 FastAPI 服务挂载生产 `qc_sichuan.router`；`latest-result` 经 `CustomQCWorkspaceService.build_latest_single_record_result_dto` 查询 SQLite Envelope，批量详情经 `CanonicalResultStore.load_root_job_items` 查询同一结果。任务表中的旧 `items` 故意放入另一条不合规规则，以检查详情不会绕过 Canonical。

服务只对鉴权、病历列表和无关 API 返回合成桩数据。正式质控读取路由与保存/读取服务未被浏览器拦截。V5 前端由独立 Vite 进程运行，浏览器 `page.route` 未启用；浏览器和脚本请求均经 Vite 代理到测试 FastAPI 服务。

复现步骤（先确认本机 8001、3001 端口空闲）：

1. 在 `backend/` 运行 `py -3.10 -m uvicorn scripts.acceptance.lx0609_live_http_fixture:app --host 127.0.0.1 --port 8001`。
2. 在项目目录运行 `npx vite --config vite.config.mjs --port 3001 --host 127.0.0.1`。
3. 在项目目录运行 `node scripts/acceptance/lx0609-browser-live-http.mjs`。

本轮实测：两个正式质控 HTTP 接口均为 200；latest 的 `data_origin=canonical_result_envelope`，与详情的规则号、状态、原因码、结论、建议、公开事实逐字段一致。页面显示“合规”、同一结论和建议；浏览器只请求一次 latest，附带正确机构及患者标识。脚本输出 `ok=true` 与 `synthetic_sqlite_to_real_http_to_v5_without_browser_interception`。Python Ruff 与 Node 语法检查通过。验收结束后已停止两个临时服务。

## 证据界限

这补齐了此前“后端 TestClient 结果 + 浏览器 API 拦截”之间的真实网络桥接，但测试后端仍是只挂载质控路由的合成服务，不是完整生产应用启动；认证、病历列表使用桩数据。内存 SQLite 不能证明 PostgreSQL 多进程竞争或安装包重启；合成 004 不能证明独立临床判读或全部原始规则等价。因此阶段 A 的技术页面回读增强，A 的全部退出条件、B/D 外部验收均未据此关闭。
