---
description: 检查并修复前端 UI 问题
---

# UI 检查与修复

## 步骤

1. 确保前端服务正在运行
   - 如果未运行，执行 `/start-dev`

2. 使用浏览器工具导航到目标页面
   - 仪表板: http://localhost:3000/dashboard
   - 质控工作站: http://localhost:3000/workstation
   - 任务管理: http://localhost:3000/dashboard/tasks/all
   - 评分标准: http://localhost:3000/dashboard/scoring-rules
   - 质控员排名: http://localhost:3000/dashboard/staff-ranking
   - 通知与整改: http://localhost:3000/dashboard/notifications

3. 截图并分析当前 UI 状态
   - 检查布局、颜色、字体
   - 确认组件渲染是否正常
   - 验证数据是否加载
   - 检查控制台是否有错误

4. 根据分析结果进行修复
   - 样式文件: `apps/medqc-web/src/styles/`
   - 组件文件: `apps/medqc-web/src/components/`
   - 视图文件: `apps/medqc-web/src/views/`

5. 提交修复
```bash
git add apps/medqc-web/src/
git commit -m "style: <修复描述>"
git push
```

## 项目配色变量

```less
@primary-color: #1890ff;
@success-color: #52c41a;
@warning-color: #faad14;
@error-color: #ff4d4f;
```
