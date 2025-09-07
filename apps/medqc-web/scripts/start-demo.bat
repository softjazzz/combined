@echo off
chcp 65001 >nul

REM 医生工作站演示启动脚本
REM 作者：医疗质控系统开发团队
REM 版本：1.0.0

echo 🏥 医疗质控系统 - 医生工作站演示
echo ==================================
echo.

REM 检查Node.js环境
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未找到Node.js，请先安装Node.js
    pause
    exit /b 1
)

REM 检查npm环境
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误：未找到npm，请先安装npm
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i

echo ✅ Node.js版本：%NODE_VERSION%
echo ✅ npm版本：%NPM_VERSION%
echo.

REM 检查项目依赖
if not exist "node_modules" (
    echo 📦 正在安装项目依赖...
    npm install
    if %errorlevel% neq 0 (
        echo ❌ 依赖安装失败，请检查网络连接或npm配置
        pause
        exit /b 1
    )
    echo ✅ 依赖安装完成
    echo.
)

REM 启动开发服务器
echo 🚀 正在启动开发服务器...
echo.
echo 📋 演示访问地址：
echo    - 主演示页面：http://localhost:5173/demo
echo    - 医生工作站：http://localhost:5173/dashboard/doctor-workstation
echo.
echo 💡 演示提示：
echo    1. 选择不同的演示场景体验质控效果
echo    2. 在编辑器中修改病历内容观察实时分析
echo    3. 查看右侧质控面板的详细分析结果
echo    4. 点击改进建议按钮应用智能建议
echo.
echo ⌨️  快捷键：
echo    - Ctrl+C：停止服务器
echo    - Ctrl+S：保存病历（在编辑器中）
echo.

REM 启动服务器
npm run dev
