# 第二批17接口实际投影验收

## 证据与当前结论

客户只读预检包SHA256：b8c7566b25a456cd660bc17473c66c13de516bad9ee016b30826fb819e2d5577。
五个产物已逐项复核；实际为11个candidate_ready、2个partial、3个零样本、1个厂商阻断，
不是报告中写的12个candidate_ready。首轮9365行，源键/目标主键碰撞均0。
源95批次、88结果集、16schema、18730快照；102审计为95 started+7 failed的事件历史。

## 正式字段补齐

000057在9张第二批表上增加22列，可空、无默认、不回填、不改主键。
保留护理/麻醉签署原值及带时区签署时间；保留申请/评估/记录/手术/麻醉/入出室时间，
医院事件时间用timestamp without time zone，签署时间显式按Asia/Shanghai解释。
风险评估保留application_id；技术document_id只由机构/患者/就诊/源申请号派生。
输血申请transfution_datetime不作为实际执行证据。

正式实际catalog还纠正离线合同三处时区描述：surgery_record的surgery_begin_time/
surgery_end_time、postsurg_firstcourse_record.physician_sign_datetime均为timestamptz。
源617字段及有序hash不变，目标441→463列，映射343→365；其余字段仍在原raw保留。

## 一次运行的边界

固定源medqc_periop_acceptance_20261031104123，以运行账号只读。
创建独立CDM/恢复库，以正式bootstrap和57条迁移从空库初始化，部署授权不进Alembic。
核实际catalog后对13个有数据接口做两轮投影、字段相等、源保护、目标备份恢复。
源失败/零样本独立保留；不重抽、不访问原13接口或业务库、不部署服务、不启用任务。
本次不执行bundle/LX0609/完整质控，不能称已验证临床判定。

## 开发机验证

独立合成PostgreSQL18.3集群（新端口、新目录，非现有实例），无真实病历或凭据：
- 正式初始化器空库到000057、实际17表463列与权限校验通过。
- 9365条虚构源数据两轮投影；首轮9365变化，次轮0，365映射字段逐项相等。
- 源8表及序列不变；目标自定义备份恢复全表/序列指纹相同。
- 超过一块写入后注入故障：目标数据完整回滚，失败审计独立保留。
- 运行账号改表被拒；旧形状迁移增加22列、初值NULL、重复迁移不变、错误类型拒绝。
- 初始化器原有6项专属PG测试通过。
- 服务完整pytest132通过，2项真实PG测试默认跳过，已另在专属PG执行2/2通过；Ruff、mypy通过。
- PowerShell AST解析通过。客户机PG16与真实数据投影尚待执行，不将本机PG18称为PG16实测。

前端无改动。check:encoding已通过；eslint/vue-tsc/vitest缺依赖，相关命令受阻，未安装。

## 交付

使用tools/build_periop_projection_package.py生成独立校验包；DSH指令见DSH_PERIOP_PROJECTION.txt。
成功出口明确带源限制，服务0.3.2注册表仍为原13接口；本包只用于隔离验收。
