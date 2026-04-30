<#
.SYNOPSIS
  将本机 MODstore_deploy 目录（含未提交修改）整体同步到 Linux 服务器：打 tar 包 -> scp -> 解压
  并保留下线 .env，在服务器上 pip、npm build、mvn、systemctl 重启 modstore / modstore-payment。

.PARAMETER SshTarget
  例如 root@119.27.178.147

.PARAMETER RemoteBase
  服务器上**仓库根**（即 MODstore_deploy 的**父目录**），必须与 modstore / modstore-payment 的 systemd 中 JAR/WorkingDirectory 所在树为**同一套目录**（否则 mvn 改了一处、java 仍跑另一处旧 JAR，表现为「支付 Java 不可用」）。
  未设置时默认 /root/modstore-git（全 ASCII，避免 PS5.1/SSH 对中文路径解析不一致）。在服务器上需保证该路径指向真实代码树：执行一次 scripts/ensure_modstore_symlink.sh 或手建 ln -s 到实际目录。
  或设置环境变量 DEPLOY_REMOTE_BASE 为**完整部署根路径**（含中文时务必与磁盘上实际目录名完全一致，可用 UTF-8 无 BOM 文本手算 Base64 写入脚本测试解码）。
  服务器上若 FastAPI 非 9999：在 systemd 或 profile 中 export MODSTORE_API_HEALTH_PORTS="8765"（空格分隔多端口探测顺序）。

.EXAMPLE
  .\scripts\sync-modstore-to-server.ps1
#>
param(
  [string] $SshTarget = $env:DEPLOY_SSH,
  [string] $RemoteBase = $env:DEPLOY_REMOTE_BASE
)

$ErrorActionPreference = "Stop"
if (-not $SshTarget) { $SshTarget = "root@119.27.178.147" }
# 默认只用 ASCII 路径，避免与服务器上《真实目录名》有细微差（Unicode 同形/编码）时部署错树、Java 与 Python 不同步
if (-not $RemoteBase) {
  $defB64 = "L3Jvb3QvbW9kc3RvcmUtZ2l0"
  $RemoteBase = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($defB64))
}

# 脚本在 MODstore_deploy\scripts\… → 上两级 = MODstore_deploy 根目录
$ModstoreDeploy = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$CompanyRoot = Split-Path -Parent $ModstoreDeploy
$TarName = "modstore_deploy_sync.tgz"
$LocalTar = Join-Path $env:TEMP $TarName

Write-Host "[sync] local MODstore: $ModstoreDeploy"
Write-Host "[sync] target: $SshTarget  REMOTE_BASE=$RemoteBase"
Write-Host "[sync] 1/4 creating tar (excludes venv, node_modules, dist, target)..."

# Windows 自带 tar=bsdtar: -C 父目录 后列 MODstore_deploy，排除为相对该目录的路径
# 在 CompanyRoot 下执行: tar ... MODstore_deploy
$excludes = @(
  "MODstore_deploy/.venv"
  "MODstore_deploy/market/node_modules"
  "MODstore_deploy/market/dist"
  "MODstore_deploy/java_payment_service/target"
  "MODstore_deploy/modstore_server/payment_orders"
  "MODstore_deploy/modstore_server/__pycache__"
  "MODstore_deploy/tests/__pycache__"
)
# Windows tar：--exclude 无 ** 时更稳
Push-Location $CompanyRoot
try {
  if (Test-Path $LocalTar) { Remove-Item -Force $LocalTar }
  $argsT = @(
    "-czf", $LocalTar
  )
  foreach ($e in $excludes) { $argsT += "--exclude=$e" }
  $argsT += "MODstore_deploy"
  $p = Start-Process -FilePath "tar" -ArgumentList $argsT -NoNewWindow -PassThru -Wait
  if ($p.ExitCode -ne 0) { throw "tar failed exit=$($p.ExitCode)" }
} finally {
  Pop-Location
}

$len = (Get-Item $LocalTar).Length / 1MB
$mb = [math]::Round($len, 2)
Write-Host "[sync] tgz: $mb MB  path: $LocalTar"
Write-Host "[sync] 2/4 scp tgz and remote_sync_extract.sh..."
$enc = [System.Text.UTF8Encoding]::new($false)
$extPath = Join-Path $ModstoreDeploy "scripts/remote_sync_extract.sh"
# 将 sh 转 LF
$extContent = (Get-Content -Raw -Path $extPath -ErrorAction SilentlyContinue)
if ($extContent) {
  $extContent = $extContent -replace "`r`n", "`n" -replace "`r", "`n"
  $tmpSh = Join-Path $env:TEMP "remote_sync_extract_$(Get-Date -Format 'yyyyMMddHHmmss').sh"
  [System.IO.File]::WriteAllText($tmpSh, $extContent, $enc)
} else { throw "script not found: $extPath" }

$null = & scp -o BatchMode=yes -q $LocalTar ($SshTarget + ":/tmp/") 2>&1
if ($LASTEXITCODE -ne 0) { throw "scp tgz failed exit=$LASTEXITCODE" }
$null = & scp -o BatchMode=yes -q $tmpSh ($SshTarget + ":/tmp/remote_sync_extract.sh") 2>&1
if ($LASTEXITCODE -ne 0) { throw "scp script failed" }
Remove-Item -Force $tmpSh -ErrorAction SilentlyContinue

# 路径经 UTF-8 -> base64 写入小文件（纯 ASCII 一行）；远端 base64 -d 还原。避免 JSON/直写 UTF-8 在部分 locale 下乱码
$b64 = [Convert]::ToBase64String($enc.GetBytes($RemoteBase))
$tmpBase = Join-Path $env:TEMP "remote_sync_remote_base.txt"
try {
  [System.IO.File]::WriteAllText($tmpBase, $b64, $enc)
} catch { throw "write remote base temp failed: $_" }
$null = & scp -o BatchMode=yes -q $tmpBase ($SshTarget + ":/tmp/remote_sync_remote_base") 2>&1
if ($LASTEXITCODE -ne 0) { Remove-Item -Force $tmpBase -ErrorAction SilentlyContinue; throw "scp remote base path failed exit=$LASTEXITCODE" }
Remove-Item -Force $tmpBase -ErrorAction SilentlyContinue

$boot = Join-Path $ModstoreDeploy "scripts/remote_sync_bootstrap.sh"
$bootTmp = Join-Path $env:TEMP "remote_sync_bootstrap_$(Get-Date -Format 'yyyyMMddHHmmss').sh"
$bootContent = (Get-Content -Raw -Path $boot -ErrorAction Stop)
$bootContent = $bootContent -replace "`r`n", "`n" -replace "`r", "`n"
[System.IO.File]::WriteAllText($bootTmp, $bootContent, $enc)
$null = & scp -o BatchMode=yes -q $bootTmp ($SshTarget + ":/tmp/remote_sync_bootstrap.sh") 2>&1
Remove-Item -Force $bootTmp -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) { throw "scp bootstrap failed exit=$LASTEXITCODE" }

Write-Host "[sync] 3/4 on server: extract, pip, npm, mvn, systemctl..."
$remote = "chmod +x /tmp/remote_sync_bootstrap.sh; bash /tmp/remote_sync_bootstrap.sh; ec=`$?; rm -f /tmp/remote_sync_bootstrap.sh; exit `$ec"
ssh -o BatchMode=yes $SshTarget $remote
$exit = $LASTEXITCODE

Write-Host "[sync] 4/4 local tgz still at: $LocalTar (delete if not needed)"
# Remove-Item -Force $LocalTar -ErrorAction SilentlyContinue

if ($exit -ne 0) { exit $exit }
Write-Host "[sync] done."
