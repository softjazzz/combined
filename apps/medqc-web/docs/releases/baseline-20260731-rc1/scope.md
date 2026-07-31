# baseline-20260731-rc1 发布范围

## 状态

- 类型：发布基线清账候选，不是正式客户版本号
- 当前阶段：工作区盘点与分类
- 正式发布条件：`change-inventory.json` 未分类数量归零，且后续发布门禁全部通过

## 本次候选必须包含

1. 客户样本池的在院/已出院病历同步与展示。
2. 无 `medical_record_frontpage` 的在院病历可进入样本池并启动质控。
3. Bundle 文书归并、文书身份、签名、关键时间及检查检验报告归并。
4. LX0609 Native 规则及明确范围内的规则修复。
5. `CanonicalQcResultEnvelope` 原样保存、单一结果 API 原样读取、前端只渲染。
6. 样本同步游标迁移 `20260731_000024`。
7. 客户模式前端构建、数据库升级、交付包校验和部署文档。

## 本次候选不包含

1. 与客户样本验证无关的工作台、DRG、首页或旧页面视觉改造。
2. 超大 Vue 组件和超大 Python 服务的架构拆分。
3. 缺少客户定义的 pending 规则口径。
4. `.release-packages/`、`.codegraph/`、`tmp-*`、截图、日志和本地数据库。
5. `.env.production`、客户连接串、密钥、输入法文件和机器级配置。
6. 自动生成的 `src/components.d.ts` 变更。

## 结果链约束

```text
Bundle / Snapshot（仅输入）
  → Native 规则
  → CanonicalQcResultEnvelope
  → 数据库原样保存
  → 单一结果 API 原样返回
  → 前端只渲染
```

聚合器、API 和前端不得重新解释、覆盖或推导质控状态。

## 可恢复快照

快照位于仓库外：

`C:\tmp\medqc-release-baseline\baseline-20260731-rc1`

包含：

- `tracked-working-tree.diff`
  - SHA-256：`E192B5479F0474AEAB5B53FADBA995FBC24B37EB3EA10D8D0EA25A235E4CC515`
- `full-working-tree-inventory.json`
  - SHA-256：`B86A0116BE317387FD22219E2A4026E3AF8B7496D6E07D919886A71E4EBFB761`
- `git-head.txt`
- `git-branch.txt`

快照生成时统计：

- 已跟踪改动：179
- 未跟踪文件：8836
- 总路径：9015

清账期间禁止使用 `git reset --hard`、`git clean` 或批量删除恢复工作区。

## 分类出口

| 类别            | 本轮处理                           |
| --------------- | ---------------------------------- |
| A 发布功能      | 逐项 diff 审查后进入逻辑提交       |
| B 发布保障      | 测试、迁移、脚本和文档进入独立提交 |
| C 后续技术债    | 本轮不改，进入技术债台账           |
| D 本地产物      | 不提交，后续由忽略规则隔离         |
| E 敏感/环境配置 | 不提交，只保留安全模板             |
| F 待确认        | 阻塞正式打包                       |
