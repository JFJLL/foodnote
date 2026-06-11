param(
  [string]$TargetDir = "tools/external",
  [int]$XhsPort = 5556,
  [int]$DouyinPort = 5557,
  [switch]$Install
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectPath([string]$Path) {
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $Path
  }
  return Join-Path (Split-Path -Parent $PSScriptRoot) $Path
}

function Set-EnvValue([string]$Name, [string]$Value) {
  $envPath = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
  $lines = @()
  if (Test-Path -LiteralPath $envPath) {
    $lines = Get-Content -LiteralPath $envPath -Encoding UTF8
  }
  $updated = $false
  $next = foreach ($line in $lines) {
    if ($line -match "^$([Regex]::Escape($Name))=") {
      "$Name=$Value"
      $updated = $true
    } else {
      $line
    }
  }
  if (-not $updated) {
    $next += "$Name=$Value"
  }
  Set-Content -LiteralPath $envPath -Value $next -Encoding UTF8
}

function Get-EnvValue([string]$Name) {
  $envPath = Join-Path (Split-Path -Parent $PSScriptRoot) ".env"
  if (-not (Test-Path -LiteralPath $envPath)) {
    return ""
  }
  foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
    if ($line -match "^\s*$([Regex]::Escape($Name))=(.*)$") {
      return $Matches[1].Trim().Trim('"').Trim("'")
    }
  }
  return ""
}

function Get-LogTail([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    return ""
  }
  $lines = Get-Content -LiteralPath $Path -Tail 80 -Encoding UTF8
  return ($lines -join [Environment]::NewLine)
}

function Test-HttpReachable([string]$Url) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2 -SkipHttpErrorCheck
    return [int]$response.StatusCode -lt 500
  } catch {
    return $false
  }
}

function Join-ProcessArguments([string[]]$Arguments) {
  return ($Arguments | ForEach-Object {
    $escaped = $_ -replace '"', '\"'
    if ($escaped -match "[\s;]") {
      '"' + $escaped + '"'
    } else {
      $escaped
    }
  }) -join " "
}

function Start-HiddenProcess(
  [string]$Name,
  [string]$FilePath,
  [string[]]$Arguments,
  [string]$WorkingDirectory,
  [string]$HealthUrl,
  [string]$LogSlug
) {
  if (Test-HttpReachable $HealthUrl) {
    Write-Host "$Name already reachable: $HealthUrl"
    return
  }

  $logDir = Join-Path $root "storage\logs\collectors"
  New-Item -ItemType Directory -Force -Path $logDir | Out-Null
  $stdoutPath = Join-Path $logDir "$LogSlug.out.log"
  $stderrPath = Join-Path $logDir "$LogSlug.err.log"
  "" | Set-Content -LiteralPath $stdoutPath -Encoding UTF8
  "" | Set-Content -LiteralPath $stderrPath -Encoding UTF8

  $process = Start-Process `
    -FilePath $FilePath `
    -ArgumentList (Join-ProcessArguments $Arguments) `
    -WorkingDirectory $WorkingDirectory `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

  Write-Host "$Name starting: PID $($process.Id)"
  for ($i = 0; $i -lt 40; $i += 1) {
    Start-Sleep -Milliseconds 500
    $process.Refresh()
    if ($process.HasExited) {
      $stderrTail = Get-LogTail $stderrPath
      $stdoutTail = Get-LogTail $stdoutPath
      throw "$Name exited before it became reachable. See $stderrPath. stderr: $stderrTail stdout: $stdoutTail"
    }
    if (Test-HttpReachable $HealthUrl) {
      Write-Host "$Name reachable: $HealthUrl"
      Write-Host "  stdout: $stdoutPath"
      Write-Host "  stderr: $stderrPath"
      return
    }
  }

  $stderrTail = Get-LogTail $stderrPath
  $stdoutTail = Get-LogTail $stdoutPath
  throw "$Name did not become reachable at $HealthUrl. See $stderrPath. stderr: $stderrTail stdout: $stdoutTail"
}

function Update-DouyinCookie([string]$ApiBase) {
  $cookie = Get-EnvValue "DOUYIN_COOKIE"
  if ([string]::IsNullOrWhiteSpace($cookie)) {
    return
  }
  $body = @{ service = "douyin"; cookie = $cookie } | ConvertTo-Json
  try {
    Invoke-RestMethod -Method Post -Uri "$($ApiBase.TrimEnd('/'))/api/hybrid/update_cookie" -ContentType "application/json" -Body $body | Out-Null
    Write-Host "Douyin collector cookie updated from local .env DOUYIN_COOKIE."
  } catch {
    throw "Failed to update Douyin collector cookie from DOUYIN_COOKIE: $($_.Exception.Message)"
  }
}

function Install-PythonRequirements([string]$Path, [string]$PythonVersion) {
  $venvPath = Join-Path $Path ".venv"
  $cfgPath = Join-Path $venvPath "pyvenv.cfg"
  $needsVenv = -not (Test-Path -LiteralPath $venvPath)
  if (-not $needsVenv -and (Test-Path -LiteralPath $cfgPath)) {
    $cfg = Get-Content -LiteralPath $cfgPath -Raw -Encoding UTF8
    if ($cfg -notmatch "version\s*=\s*$([Regex]::Escape($PythonVersion))\.") {
      Remove-Item -LiteralPath $venvPath -Recurse -Force
      $needsVenv = $true
    }
  }
  if ($needsVenv) {
    uv venv --python $PythonVersion $venvPath
    if ($LASTEXITCODE -ne 0) {
      throw "Failed to create virtual environment for $Path with Python $PythonVersion"
    }
  }
  $python = Join-Path $Path ".venv\Scripts\python.exe"
  uv pip install --python $python -r (Join-Path $Path "requirements.txt")
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to install requirements for $Path"
  }
}

$root = Split-Path -Parent $PSScriptRoot
$externalRoot = Resolve-ProjectPath $TargetDir
$xhsPath = Join-Path $externalRoot "XHS-Downloader"
$douyinPath = Join-Path $externalRoot "Douyin_TikTok_Download_API"

if (-not (Test-Path -LiteralPath $xhsPath) -or -not (Test-Path -LiteralPath $douyinPath)) {
  throw "Collectors are missing. Run scripts\install_collectors.ps1 first."
}

if ($Install) {
  Write-Host "Installing XHS-Downloader dependencies..."
  Install-PythonRequirements $xhsPath "3.12"
  Write-Host "Installing Douyin_TikTok_Download_API dependencies..."
  Install-PythonRequirements $douyinPath "3.12"
}

$douyinConfig = Join-Path $douyinPath "config.yaml"
if (Test-Path -LiteralPath $douyinConfig) {
  $content = Get-Content -LiteralPath $douyinConfig -Raw -Encoding UTF8
  $content = $content -replace "Host_IP:\s*.*", "Host_IP: 127.0.0.1    # default IP | 默认IP"
  $content = $content -replace "Host_Port:\s*\d+.*", "Host_Port: $DouyinPort    # local Foodnote port"
  Set-Content -LiteralPath $douyinConfig -Value $content -Encoding UTF8
}

$xhsPython = Join-Path $xhsPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $xhsPython)) {
  $xhsPython = "python"
}
$douyinPython = Join-Path $douyinPath ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $douyinPython)) {
  $douyinPython = "python"
}

$xhsStartCode = "import asyncio; from main import api_server; asyncio.run(api_server(host='127.0.0.1', port=$XhsPort))"
Start-HiddenProcess "XHS-Downloader API" $xhsPython @("-c", $xhsStartCode) $xhsPath "http://127.0.0.1:$XhsPort" "xhs"
Start-HiddenProcess "Douyin_TikTok_Download_API" $douyinPython @("start.py") $douyinPath "http://127.0.0.1:$DouyinPort" "douyin"
Update-DouyinCookie "http://127.0.0.1:$DouyinPort"

Set-EnvValue "XHS_COLLECTOR_API_BASE" "http://127.0.0.1:$XhsPort"
Set-EnvValue "DOUYIN_COLLECTOR_API_BASE" "http://127.0.0.1:$DouyinPort"

Write-Host ""
Write-Host "Foodnote .env updated:"
Write-Host "  XHS_COLLECTOR_API_BASE=http://127.0.0.1:$XhsPort"
Write-Host "  DOUYIN_COLLECTOR_API_BASE=http://127.0.0.1:$DouyinPort"
Write-Host ""
Write-Host "Restart the Foodnote backend after changing .env."
