# 病历池 Clinical 手术记录补充读取

病历池的「查看病历」请求通过 `include_clinical_surgery=true` 补充手术目录。服务端沿用现有病历访问和 `independent_cdm` 连接，并在同一只读 RR 事务核对绑定、版本、正文和有效回执。目录只返回文书标识、版本和长度。点击时 `render` 按原三键、文书号和目录版本再次核对，版本失效返回 409 和刷新提示。存在唯一、已核实的对应关系且基础记录可读时，目录只保留基础记录。

## 正式 CDM 所需的只读证据

当前投影和投递回执能核对已发布的版本。对于已经投递、尚无选材清单的住院，现有资料缺少可供业务读取的正式住院绑定和逐文书**当前有效性**，尤其无法证明入库后是否出现了删除、HOLD 或替代版本。请同步侧在 `medqc_sync_cdm` 提供只读关系 `sync_material.clinical_surgery_browse_v1`，按获准浏览的范围约束以下列。

| 列 | 合同 |
| --- | --- |
| `institute_id`、`patient_id`、`visit_id` | 业务 CDM 住院三键。业务与 Clinical 原生住院三键按核实的一对一绑定提供。 |
| `clinical_institute_id`、`clinical_patient_id`、`clinical_visit_id`、`document_id` | 手术投影四键。保留原字符串与前导零。 |
| `lifecycle_state` | `USABLE` 表示该版本当前可展示，已核对生命周期、删除状态及发布生效。HOLD、删除、已替代、未知或待核的版本不得返回 `USABLE`。若新版本尚未通过校验且旧投影仍在，旧版也不得返回 `USABLE`。 |
| `source_epoch`、`source_key_hash`、`target_key_hash`、`generation`、`mapping_hash`、`activation` | 对应已读回版本的发布证据。业务同当前回执及有效投递合同精确比对。 |
| `surgery_process_sha256` | 经同步侧核实的同版目标正文 UTF-8 SHA-256 小写十六进制，包含原有空格与换行。 |
| `cache_document_id` | 可空。仅在两侧同一住院的两份文书有已核实的对应关系时填写，不按同号推测。 |

业务 CDM 只读角色所需权限如下。

- `sync_material` 与 `sync_delivery` schema 的 `USAGE`。
- `clinical_surgery_browse_v1` 上表所列列的 `SELECT`。
- `clinical_surgery_record_current` 的 `institute_id`、`patient_id`、`visit_id`、`document_id`、`document_title`、`record_time`、`submit_time`、`surgery_process` 的 `SELECT`。
- `sync_delivery.receipt` 的 `interface_name`、`source_epoch`、`source_key_hash`、`target_key_hash`、`generation`、`mapping_hash`、`activation`，以及 `sync_delivery.contract` 的 `interface_name`、`source_epoch`、`mapping_hash`、`activation` 的 `SELECT`。

正式启用沿用独立 CDM 配置，由同步侧发布上述只读关系及证据。入口不依赖四类选材开关。隔离测试中验证了角色缺权限时基础目录仍返回，补充状态为 `permission_unavailable`。接口尚未发布时为 `contract_unavailable`。正式账号的实际权限与真实就诊 `2725811` 的点击验收仍待获准范围内的证据就绪。验收比对目录版本、发布代际 `861733` 和正文长度 `494`，仅记录匹配结论。

## 开发副本验证

- PostgreSQL 16.15 合成库以独立只读角色读取合成发布证据，目录及正文版本一致，原样比对通过，正文 494 字符。HOLD、激活代际失效、正文摘要不符时保留基础目录。发布代际变化后旧版本不能继续读取。
- Chrome 点击真实病历池预览组件的「查看病历」，目录和正文 API 使用合成响应。正文请求携带目录版本，HTTP 409 显示刷新提示。另一份无 Clinical 补充的合成病历能查看日常病程、术前小结和术后首次病程。
- 后端 29 项定向离线测试、前端 64 项定向测试与一项隔离 PostgreSQL 测试通过。
