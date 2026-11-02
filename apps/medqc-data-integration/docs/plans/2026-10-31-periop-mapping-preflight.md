# Perioperative Mapping Preflight Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用第二批17接口的已验收快照生成明确映射合同及只读投影预检，保护原13接口和全部原始数据。

**Architecture:** 合同绑定客户回传ZIP的字段顺序、16个schema哈希和441列离线ORM目录。
纯标准库转换器验证原始有序数组哈希、构造风险评估技术文档键并检查更粗目标主键碰撞。
CLI仅以运行身份、只读事务读取第二批库；不调用Caché、不创建CDM、不改正式注册表。

**Tech Stack:** Python3.10标准库；客户已有psycopg2；unittest；JSON/CSV非PHI合同。

## Task 1: Evidence and contract

- Create `contracts/periop-acceptance-contracts.json`：显式逐字段映射、raw-only、缺失目标字段、来源状态。
- 原ZIP SHA256为`738d5ccdbc44e69ebb7a8ff8e16dfa010f996894f642f4ce888e83b18aae1843`。
- `documentid`等别名逐项列出，不对任意字段运行模糊匹配。
- 风险评估document_id使用`cache-risk-v1:`和病例三键/application_id的稳定技术哈希，保留来源说明。
- 手术记录无源结构则阻断；三个零行来源只提供结构合同，不宣称已验证正文。

## Task 2: Pure conversion and regression

- Create `tools/periop_transform.py` and `tests/test_periop_transform.py`。
- 先验证伪造快照哈希、字段长度、时间、同手术号不同文档/同输血号不同血袋碰撞的失败用例。
- 使用`major_document_transform.py`的既有上海时区转换，不以提交时间补事件或签署时间。
- 同源内容变更不改变技术主键；标识保留前导零和原始字符。

## Task 3: Read-only preflight

- Create `tools/preflight_periop_projection.py` and fake orchestration tests。
- 连接仅限`medqc_periop_acceptance_20261031104123`、本机端口和medqc_sync，使用libpq passfile。
- 读取第一轮成功快照，核对全局候选键与目标键、schema/row_hash和目标长度/类型；不使用临时extractor的current表作为真值。
- 报告95个批次和102条审计的事件口径；只读重比两轮完整行多重集。
- 日期观察不推断筛选字段；13接口注册表保持原样。

## Task 4: Verify and deliver

- `PYTHONPATH=src python -m unittest discover -s tests -p test_periop_transform.py -v`。
- ruff、mypy和项目现有测试；Windows独立解包后复测，不依赖开发机文件布局。
- 新ZIP仅含合同、纯转换器、只读预检、测试和说明，不含原始payload/凭据。
- 客户仅查询第二批库，回传非PHI预检结果后才进入实际CDM建库/投影；本轮不发明业务列或改迁移。
