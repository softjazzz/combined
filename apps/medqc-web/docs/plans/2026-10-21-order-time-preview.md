# C17/C22 医嘱时间只读预览

## 范围

仅预览两例各一条已核实的药品医嘱，以机构、患者、就诊、医嘱四个坐标精确查询。
客户机病历坐标存放在私有 scope 文件中，不提交；脚本可以脱离最新项目代码单独运行，
仅依赖客户机原后端已有的 Python 包和 get_remote_db_url 配置读取函数。

## 用法

把 preview-medqc-order-times.ps1、preview_order_time_fill.py 和
order-time-scope-private.json 放在客户机同一目录。执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File 'D:\medqc\order-time-preview\preview-medqc-order-times.ps1' `
    -BackendPath 'D:\medqc\medqc-web-customer-R26.4\backend'
```

两侧连接均使用数据库强制只读、REPEATABLE READ 事务；查询有超时；结束回滚并关闭连接。
不更改配置、开关、安装代码、表结构、Bundle、原任务或质控结果；不调用模型。
此版本没有 Apply 参数，确认预览后再实现补数步骤。

## 输出

- 每例先核对药品名是否一致、双方有值的开立/计划开始时间是否一致；只输出核对状态。
- 四个字段显示源时间、本地时间及动作：fill_candidate、equal、conflict、both_empty、
  source_empty_keep_local、source_column_missing、local_column_missing。
- 本地缺列时仍能预览，不执行升级；源空不会被当成待清空本地值。
- 状态差异只显示，不修改；计划结束时间不冒充实际停嘱时间。
- done 事件的 preview_ready=false 表示有缺列、身份问题或非空冲突，需要先处理再补。
- 输出不包含姓名、药名、病历正文、凭据；只包含样本别名、目标字段、时间、状态和受控错误码。

## 验证

16 项独立单测通过，覆盖空值保留、非空冲突、缺列、北京时间比较、医嘱身份、只读事务。
Python Ruff 通过；PowerShell AST 解析与参数检查在打包前执行。
真实源库仅客户机可达，当前没有执行真实预览，也没有任何数据库写入。
后端独立脚本不改前端；隔离树没有 node_modules，不安装共享依赖或运行全前端测试。

## 客户源端实测后的身份校正

C17 源端通用名与本地 generic_name 不同，但源端商品名与本地 generic_name
完全一致且药品编码一致；这是治理字段语义差异。预览改为在编码非空一致且
通用名/商品名存在确切交叉匹配时放行；单凭同编码、模糊名称或无编码商品名
相似仍不放行。两侧非空编码不同也拦截。不会修改任何药名或状态。
实测仍发现客户机四个目标列全部缺失，补列和补数需要后续明确确认。
