# 1022出院签署时间与JSON规则读取接通

## 范围

用户授权补齐规则白名单，使用1022六例定向验证；签署时间不作为记录/提交时间，不调用模型、不重跑质控。修改位于集成工作树C:/medqc-agent-merge/apps/medqc-web、分支codex/business-agent-integration；没有合并独立同步分支其他改造。

## 修复

在source_evidence_reader的discharge_record原生批准字段中增加chief_physician_sign_datetime和v2_schema；快照白名单由同一字段元组派生，因此两条读取链同时接通。字段缺失的旧客户库仍按实际列交集读取，不新增schema要求，不在此处做DDL或补数。

AUTHORITATIVE_DOCUMENT_TIME_FIELDS保持record_time、record_datetime、submit_time、submit_datetime不变。签署时间不参与文书选时，也不把JSON中的签署时间转成记录或提交时间。没有修改业务执行器判定、原因、阈值或历史结果。整个JSON只进入服务端材料；既有普通正文模型投影没有自动拼接JSON。

## 1022真实只读验证

C03、C04、C16、C17、C18、C22逐份核对本机PG、原生SQL、快照SQL、EvidenceReadSession材料及执行器\_source_rows入口。六个签署时间全部同值保留；C03/C04/C17/C22四份JSON逐字及SHA256一致，字符数分别为67772、593、86477、87814。C16/C18字段可读取但原值为NULL，未造JSON。

六份文书的统一记录/提交时间选择器和出院记录完成时间函数仍返回空，普通出院内容仍可读取。验证在只读事务内执行；数据库写入0、模型调用0、质控任务创建0，未刷新Bundle或改历史任务。完整输入不输出，前后报告及脚本保存在未提交的.tmp/0910-full-audit/1022-rule-read-fields-private/。

## 定向回归与运行状态

新增5项回归，覆盖原生/快照SQL真正投影新字段、旧库缺列兼容、长JSON完整保留、普通提示词不增加原始JSON、签署时间不变成文书时间。四个相关测试文件203项通过，修改文件Ruff与diff检查通过；未运行全项目检查。

本机8001后端当前未监听，未擅自启动。这里验证的是当前集成代码的真实数据库读取与执行器材料入口，不冒充运行进程内验收或整条质控重跑；后端下次启动加载本提交。
