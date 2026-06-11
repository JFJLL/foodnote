param(
  [string]$InstallDir = "tools/external/yt-dlp",
  [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$TargetDir = Join-Path $ProjectRoot $InstallDir
$Target = Join-Path $TargetDir "yt-dlp.exe"
$EnvPath = Join-Path $ProjectRoot $EnvFile

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null

$Url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
Invoke-WebRequest -Uri $Url -OutFile $Target

if (-not (Test-Path -LiteralPath $EnvPath)) {
  Copy-Item -LiteralPath (Join-Path $ProjectRoot ".env.example") -Destination $EnvPath
}

$lines = Get-Content -LiteralPath $EnvPath -Encoding UTF8
$command = "YTDLP_COMMAND=$Target"
$found = $false
$updated = foreach ($line in $lines) {
  if ($line -match "^YTDLP_COMMAND=") {
    $found = $true
    $command
  } else {
    $line
  }
}
if (-not $found) {
  $updated += $command
}

Set-Content -LiteralPath $EnvPath -Value $updated -Encoding UTF8
Write-Output "Installed yt-dlp to $Target"
Write-Output "Updated $EnvPath with YTDLP_COMMAND"
