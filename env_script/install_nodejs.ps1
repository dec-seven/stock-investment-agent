# ============================================
# Node.js 环境检测与自动安装脚本 (Windows PowerShell)
# ============================================
# 使用方法: 右键点击 -> 使用 PowerShell 运行
# 或者: powershell -ExecutionPolicy Bypass -File install_nodejs.ps1
# ============================================

# 设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Node.js 环境检测与安装工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 步骤 1: 检测 Node.js
Write-Host "[步骤 1/3] 正在检测 Node.js 安装状态..." -ForegroundColor Yellow

try {
    $nodeVersion = node -v 2>$null
    $npmVersion = npm -v 2>$null

    if ($nodeVersion) {
        Write-Host "[√] Node.js 已安装" -ForegroundColor Green
        Write-Host "    版本: $nodeVersion" -ForegroundColor White

        if ($npmVersion) {
            Write-Host "    npm 版本: $npmVersion" -ForegroundColor White
        }

        Write-Host ""
        Write-Host "[完成] Node.js 环境已就绪，无需安装。" -ForegroundColor Green
        Write-Host ""
        Read-Host "按 Enter 键退出"
        exit 0
    }
} catch {
    # Node.js 未安装
}

Write-Host "[×] 未检测到 Node.js" -ForegroundColor Red
Write-Host ""

# 步骤 2: 获取系统信息
Write-Host "[步骤 2/3] 准备下载并安装 Node.js..." -ForegroundColor Yellow
Write-Host ""

$arch = if ([Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
Write-Host "    系统架构: $arch" -ForegroundColor White

# Node.js LTS 版本
$nodeVersion = "20.15.0"
$nodeMsi = "node-v$nodeVersion-$arch.msi"
$nodeUrl = "https://nodejs.org/dist/v$nodeVersion/$nodeMsi"
$downloadPath = Join-Path $env:TEMP $nodeMsi

Write-Host "    目标版本: v$nodeVersion (LTS)" -ForegroundColor White
Write-Host "    下载地址: $nodeUrl" -ForegroundColor White
Write-Host ""

# 步骤 3: 下载 Node.js
Write-Host "[步骤 3/3] 正在下载 Node.js 安装包..." -ForegroundColor Yellow
Write-Host "    保存位置: $downloadPath" -ForegroundColor White
Write-Host ""

try {
    # 使用 WebClient 下载 (带进度显示)
    $webClient = New-Object System.Net.WebClient

    # 注册进度事件
    Register-ObjectEvent -InputObject $webClient -EventName DownloadProgressChanged -SourceIdentifier DownloadProgress -Action {
        $Global:DownloadProgress = $EventArgs.ProgressPercentage
        Write-Progress -Activity "下载 Node.js 安装包" -Status "$($EventArgs.ProgressPercentage)% 完成" -PercentComplete $EventArgs.ProgressPercentage
    } | Out-Null

    $webClient.DownloadFileAsync($nodeUrl, $downloadPath)

    # 等待下载完成
    while ($webClient.IsBusy) {
        Start-Sleep -Milliseconds 100
    }

    Unregister-Event -SourceIdentifier DownloadProgress -ErrorAction SilentlyContinue
    $webClient.Dispose()

    if (-not (Test-Path $downloadPath)) {
        throw "下载文件不存在"
    }

    Write-Host ""
    Write-Host "[√] 下载完成" -ForegroundColor Green
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "[错误] 下载失败: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "请检查网络连接或手动下载:" -ForegroundColor Yellow
    Write-Host "  $nodeUrl" -ForegroundColor White
    Write-Host ""
    Read-Host "按 Enter 键退出"
    exit 1
}

# 安装 Node.js
Write-Host "正在启动 Node.js 安装程序..." -ForegroundColor Yellow
Write-Host ""
Write-Host "[提示] 请在安装向导中完成安装步骤" -ForegroundColor Cyan
Write-Host "       建议保持默认设置，安装完成后会自动配置环境变量" -ForegroundColor Cyan
Write-Host ""

try {
    # 使用 MSI 安装 (静默安装)
    $installProcess = Start-Process msiexec.exe -ArgumentList "/i `"$downloadPath`" /passive /norestart" -Wait -PassThru

    if ($installProcess.ExitCode -ne 0) {
        Write-Host "[警告] 安装程序返回非零退出码: $($installProcess.ExitCode)" -ForegroundColor Yellow
    }

} catch {
    Write-Host "[错误] 安装失败: $($_.Exception.Message)" -ForegroundColor Red
}

# 清理安装包
Write-Host ""
Write-Host "正在清理临时文件..." -ForegroundColor Yellow
Remove-Item -Path $downloadPath -Force -ErrorAction SilentlyContinue

# 刷新环境变量
Write-Host "正在刷新环境变量..." -ForegroundColor Yellow
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# 添加 Node.js 默认安装路径
$nodePath = "${env:ProgramFiles}\nodejs"
if (Test-Path $nodePath) {
    $env:Path = "$nodePath;$($env:Path)"
}

# 验证安装结果
Write-Host ""
Write-Host "验证安装结果..." -ForegroundColor Yellow

try {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

    $newNodeVersion = node -v 2>$null
    $newNpmVersion = npm -v 2>$null

    if ($newNodeVersion) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "[√] Node.js 安装成功！" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "    Node.js 版本: $newNodeVersion" -ForegroundColor White

        if ($newNpmVersion) {
            Write-Host "    npm 版本: $newNpmVersion" -ForegroundColor White
        }

        Write-Host ""
        Write-Host "[提示] 如果命令行无法识别 node 命令，" -ForegroundColor Cyan
        Write-Host "       请关闭当前窗口并重新打开一个新的命令行窗口" -ForegroundColor Cyan
        Write-Host ""

    } else {
        throw "Node.js 未正确安装"
    }

} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "[!] 安装可能未完全成功" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "请尝试以下操作:" -ForegroundColor White
    Write-Host "  1. 关闭当前 PowerShell 窗口" -ForegroundColor White
    Write-Host "  2. 重新打开一个新的 PowerShell 窗口" -ForegroundColor White
    Write-Host "  3. 运行 node -v 检查是否安装成功" -ForegroundColor White
    Write-Host ""
    Write-Host "或者手动下载安装:" -ForegroundColor White
    Write-Host "  $nodeUrl" -ForegroundColor White
    Write-Host ""
}

Read-Host "按 Enter 键退出"
exit 0
