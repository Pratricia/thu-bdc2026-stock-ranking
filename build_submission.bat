@echo off
REM ============================================
REM THU-BDC2026 比赛提交打包脚本 (Windows版本)
REM ============================================

setlocal enabledelayedexpansion

if "%~1"=="" (
    echo 用法: build_submission.bat ^<团队名称^>
    echo 示例: build_submission.bat THU-BDC-Team
    exit /b 1
)

set TEAM_NAME=%~1
set IMAGE_NAME=bdc2026
set TAR_FILE=%TEAM_NAME%.tar

echo ========================================
echo   THU-BDC2026 打包提交镜像
echo ========================================
echo.
echo 团队名称: %TEAM_NAME%
echo 镜像名称: %IMAGE_NAME%:latest
echo 输出文件: %TAR_FILE%
echo.

REM 检查Docker是否可用
echo [1/5] 检查Docker环境...
docker --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Docker，请先安装Docker Desktop
    exit /b 1
)
echo   Docker已安装 ✓
echo.

REM 构建镜像
echo [2/5] 构建Docker镜像...
echo   这可能需要10-30分钟，请耐心等待...
echo.
docker build -t %IMAGE_NAME%:latest .
if errorlevel 1 (
    echo 错误: 镜像构建失败
    exit /b 1
)
echo   镜像构建成功 ✓
echo.

REM 验证镜像
echo [3/5] 验证镜像...
docker image inspect %IMAGE_NAME%:latest >nul 2>&1
if errorlevel 1 (
    echo 错误: 镜像不存在
    exit /b 1
)
for /f "tokens=*" %%i in ('docker image inspect %IMAGE_NAME%:latest --format "{{.Size}}"') do set IMAGE_SIZE=%%i
echo   镜像大小: %IMAGE_SIZE%
echo   镜像验证通过 ✓
echo.

REM 导出镜像
echo [4/5] 导出镜像为tar文件...
docker save -o %TAR_FILE% %IMAGE_NAME%:latest
if errorlevel 1 (
    echo 错误: 镜像导出失败
    exit /b 1
)
echo   镜像导出成功 ✓
echo.

REM 计算MD5和文件大小
echo [5/5] 计算文件信息...
for %%A in ("%TAR_FILE%") do set FILE_SIZE=%%~zA
echo   文件: %TAR_FILE%
echo   大小: %FILE_SIZE% 字节
echo.
echo   MD5值:
certutil -hashfile "%TAR_FILE%" MD5 | findstr /v "MD5" | findstr /v "CertUtil"
echo.

echo ========================================
echo   打包完成!
echo ========================================
echo.
echo 提交文件: %TAR_FILE%
echo.
echo 下一步:
echo   1. 发送邮件报备到 data@tsinghua.edu.cn
echo   2. 主题: %TEAM_NAME% + 模型数据报备
echo   3. 上传 %TAR_FILE% 到比赛指定位置
echo.
