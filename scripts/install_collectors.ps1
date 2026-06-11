param(
  [string]$TargetDir = "tools/external",
  [switch]$SkipClone
)

$ErrorActionPreference = "Stop"

function Ensure-Directory([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Clone-Or-Update([string]$Name, [string]$Url) {
  $repoPath = Join-Path $TargetDir $Name
  if (Test-Path -LiteralPath $repoPath) {
    git -C $repoPath pull --ff-only
  } else {
    git clone $Url $repoPath
  }
}

Ensure-Directory $TargetDir

if (-not $SkipClone) {
  Clone-Or-Update "XHS-Downloader" "https://github.com/JoeanAmier/XHS-Downloader.git"
  Clone-Or-Update "Douyin_TikTok_Download_API" "https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git"
}

Write-Host ""
Write-Host "Collectors are placed under $TargetDir."
Write-Host "Next, install each collector with its own README, then expose either:"
Write-Host "  XHS_DOWNLOADER_COMMAND / DOUYIN_DOWNLOADER_COMMAND"
Write-Host "or:"
Write-Host "  XHS_COLLECTOR_API_BASE / DOUYIN_COLLECTOR_API_BASE"
Write-Host ""
Write-Host "Foodnote expects a JSON object with fields such as:"
Write-Host "  title, author, text, image_paths, video_path, kind, metadata"
Write-Host ""
Write-Host "The script only installs source code. It does not bypass platform login, cookies, rate limits, or risk controls."
