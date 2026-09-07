# 工作台 UI 正式打包前核对

- 基础提交：5723ab72f（统计接口合同常量导入修复）。本次新增范围见同目录 change-inventory.json。
- 当前本地 UI 修改经静态审核：侧栏公共样式、运行/终末结果列表、复核预览、头像、分页器、结果分析与进度条；未改变质控判定合同。
- 部分大 diff 仅来自格式化；独立模板编译比较未发现行为变化。
- 新增 patient-avatar.ts 与两个引用组件一起提交，不依赖未跟踪模块。
- 结果分析接口补齐共享筛选函数参数；没有数据库结构变更。

## 已执行验证

- npm run test:unit：109 个测试文件、870 项通过，80.65 秒。
- npm run lint：通过。
- npm run type-check：通过（修复首页测试断言后完整复跑）。
- 首页测试类型断言由 get().exists() 改为 find().exists() 后，单独复跑 18 项通过。
- 后端：python -m pytest tests/unit/test_luxian_0609_result_analysis_service.py tests/unit/test_workstation_result_analysis_router.py -q --tb=short，9 项通过。
- 浏览器：本机实际后端、1440×1000，qc-overview、worklist、records/running、records/final 无 pageerror 或横向溢出；没有发起质控或数据库写操作。
- 包内编译产物冒烟结果记录在交付时核对，不以本文件代替客户环境验收。

## 打包边界

从本次提交的独立干净工作树调用 scripts/package-customer-release.ps1，不使用 AllowDirty，不复制当前工作区临时病例、调试数据、原型和本地 .env。脚本按默认规则移除 frontend/dist/fonts，另在 ZIP 中核对字体文件数量。构建产物、ZIP、日志不提交 Git。
