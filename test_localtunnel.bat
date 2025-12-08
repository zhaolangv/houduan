@echo off
chcp 65001 >nul
echo ========================================
echo 测试 localtunnel 连接
echo ========================================
echo.

echo 检查 Node.js 和 npm 版本...
node --version
npm --version
npx --version
echo.

echo 尝试启动 localtunnel...
echo 注意：如果看到 "your url is: https://xxx.loca.lt"，说明成功！
echo.

npx localtunnel --port 5000

pause

