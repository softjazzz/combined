# 2026-10-08 化疗 TP-D01 空病程返回合同修复

限定规则 `LX0609-05-02-01`，工作树 `F:/MedQC-worktrees/qc-fix-chemo-v2-20261008`，基线 `6930540f27e9c279241d35ac05d1c1c6e9134f82`。

空病程行、空正文及纯空白正文原先返回四项，正式执行入口按五项解包并抛出 ValueError。仅在该分支补上空事实 `None`，与声明及其他资料不足分支保持一致；正式执行、绑定和 Finalizer 输出 data_gap/source_unavailable，未生成匹配事实或“继续保持”建议。

专属测试 `backend/tests/unit/test_luxian_0609_chemo_closure.py`：修复前 3 failed/1 passed；修复后 4 passed。正常完整化疗记录仍 compliant，四字段 matched，证据精确绑定合成医嘱和病程两文书。

运行器继承审计隔离机制：拒绝 `.env*` 读取、真实数据库会话、DNS/外部连接和模型；Windows asyncio 仅允许内部 self-pipe。模型、客户PG、网络及环境文件读取均为 0。没有测试真实患者、正式API或浏览器。

提交门禁：暂存编码检查扫描 3 个文本文件通过。fresh 工作树最初因缺 eslint 无法运行 Lint；获授权后只读复用 F 集成树依赖并恢复标准 Husky 启动器，Lint 使用 `--no-fix` 通过（0 errors、1214 warnings），未修改 D 盘依赖。类型和前端全量单元未运行；不把后端四例通过称完整发布验收。

TP-D02/03 及 N13 留待独立问题提交，N01/N07 既有关闭状态保持，未重写剂量匹配算法。
