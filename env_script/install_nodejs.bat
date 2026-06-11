@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================
:: Node.js 环境检测与自动安装脚本 (Windows)
:: ============================================

echo.
echo ========================================
echo    Node.js 环境检测与安装工具
echo ========================================
echo.

:: 检测 Node.js 是否已安装
echo [步骤 1/3] 正在检测 Node.js 安装状态...
where node >nul 2>&1
if %errorlevel% equ 0 (
    echo [√] Node.js 已安装
    for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
    echo     版本: !NODE_VERSION!

    :: 检测 npm
    where npm >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=*" %%i in ('npm -v') do set NPM_VERSION=%%i
        echo     npm 版本: !NPM_VERSION!
    )

    echo.
    echo [完成] Node.js 环境已就绪，无需安装。
    goto :end
)

echo [×] 未检测到 Node.js
echo.

:: 进入安装流程
echo [步骤 2/3] 准备下载并安装 Node.js...
echo.

:: 获取系统架构
set "ARCH=x64"
if "%PROCESSOR_ARCHITECTURE%"=="x86" (
    if not defined PROCESSOR_ARCHITEW6432 (
        set "ARCH=x86"
    )
)
echo     系统架构: %ARCH%

:: 设置 Node.js 版本 (LTS 版本)
set "NODE_VERSION=20.15.0"
set "NODE_MSI=node-v%NODE_VERSION%-%ARCH%.msi"
set "NODE_URL=https://nodejs.org/dist/v%NODE_VERSION%/%NODE_MSI%"
set "DOWNLOAD_PATH=%TEMP%\%NODE_MSI%"

echo     目标版本: v%NODE_VERSION% (LTS)
echo     下载地址: %NODE_URL%
echo.

:: 检测下载工具 (优先使用 curl，Windows 10+ 自带)
where curl >nul 2>&1
if %errorlevel% equ 0 (
    echo [步骤 3/3] 正在使用 curl 下载 Node.js 安装包...
    echo     保存位置: %DOWNLOAD_PATH%
    echo.

    curl -L -o "%DOWNLOAD_PATH%" "%NODE_URL%"
    if %errorlevel% neq 0 (
        echo [错误] 下载失败，请检查网络连接
        goto :error
    )
) else (
    :: 使用 PowerShell 作为备选
    echo [步骤 3/3] 正在使用 PowerShell 下载 Node.js 安装包...
    echo     保存位置: %DOWNLOAD_PATH%
    echo.

    powershell -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%DOWNLOAD_PATH%' -UseBasicParsing"
    if %errorlevel% neq 0 (
        echo [错误] 下载失败，请检查网络连接
        goto :error
    )
)

echo.
echo [√] 下载完成
echo.

:: 验证文件是否下载成功
if not exist "%DOWNLOAD_PATH%" (
    echo [错误] 安装包文件未找到
    goto :error
)

:: 安装 Node.js
echo 正在启动 Node.js 安装程序...
echo.
echo [提示] 请在安装向导中完成安装步骤
echo        建议保持默认设置，安装完成后会自动配置环境变量
echo.

:: 以管理员权限运行 MSI 安装程序
msiexec /i "%DOWNLOAD_PATH%" /passive /norestart

echo.
echo 等待安装完成...

:: 等待安装进程结束 (最多等待 5 分钟)
set /a COUNT=0
:wait_install
timeout /t 5 /nobreak >nul
set /a COUNT+=5
tasklist /fi "imagename eq msiexec.exe" 2>nul | find "msiexec.exe" >nul
if %errorlevel% equ 0 (
    if !COUNT! lss 300 (
        goto :wait_install
    )
)

:: 清理安装包
echo.
echo 正在清理临时文件...
del /f /q "%DOWNLOAD_PATH%" 2>nul

:: 刷新环境变量
echo 正在刷新环境变量...
call :refresh_env

:: 再次检测安装结果
echo.
echo 验证安装结果...
where node >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo [√] Node.js 安装成功！
    echo ========================================
    for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
    echo     Node.js 版本: !NODE_VERSION!

    where npm >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=*" %%i in ('npm -v') do set NPM_VERSION=%%i
        echo     npm 版本: !NPM_VERSION!
    )
    echo.
    echo [提示] 如果命令行无法识别 node 命令，
    echo        请关闭当前窗口并重新打开一个新的命令行窗口
    echo.
    goto :end
) else (
    echo.
    echo ========================================
    echo [!] 安装可能未完全成功
    echo ========================================
    echo.
    echo 请尝试以下操作:
    echo   1. 关闭当前命令行窗口
    echo   2. 重新打开一个新的命令行窗口
    echo   3. 运行 node -v 检查是否安装成功
    echo.
    echo 或者手动下载安装:
    echo   %NODE_URL%
    echo.
    goto :end
)

:: ============================================
:: 函数: 刷新环境变量
:: ============================================
:refresh_env
:: 从注册表重新读取用户环境变量
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%b"

:: 从注册表重新读取系统环境变量
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYSTEM_PATH=%%b"

:: 合并环境变量
set "PATH=%USER_PATH%;%SYSTEM_PATH%"

:: 添加 Node.js 默认安装路径 (如果存在)
if exist "C:\Program Files\nodejs" (
    set "PATH=%PATH%;C:\Program Files\nodejs"
)
goto :eof

:: ============================================
:: 错误处理
:: ============================================
:error
echo.
echo ========================================
echo [×] 安装过程中出现错误
echo ========================================
echo.
echo 请尝试手动安装 Node.js:
echo   访问: https://nodejs.org/
echo   下载: LTS 版本 (推荐)
echo.
pause
exit /b 1

:: ============================================
:: 结束
:: ============================================
:end
echo.
pause
exit /b 0
