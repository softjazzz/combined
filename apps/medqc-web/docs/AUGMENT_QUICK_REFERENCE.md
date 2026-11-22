# MedQC 开发快速参考

最后更新：2026-11-22。

| 任务 | 命令或入口 |
| --- | --- |
| 配置开发库、安装依赖并启动 FastAPI | [MedQC 本地启动](../README.md#本地启动) |
| 启动前端 | 在仓库根目录执行 `pnpm --dir apps/medqc-web dev` |
| 确认开发服务地址和代理 | [端口分配](../../../DEVELOPMENT_PORTS.md) |
| 检查暂存文件编码 | 在应用目录执行 `npm run check:encoding` |
| 检查项目工作规则 | 在应用目录执行 `npm run check-work-rules` |
| 执行定向验证 | 按[仓库指令](../../../AGENTS.md)选择受影响的用例 |
| 定位规则目录、发布手册和历史文档 | [活文档索引](../../../docs/INDEX.md) |
