[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceConfig = "F:\AI_WORKSPACE\config"
$servicesFile = Join-Path $workspaceConfig "services.yaml"
$oldAddress = "192.168.1.7"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required for this migration."
}

$dirty = git -C $projectRoot status --porcelain
if ($dirty) {
    Write-Warning "The AEGIS worktree has uncommitted changes. They will not be removed."
}

New-Item -ItemType Directory -Path $workspaceConfig -Force | Out-Null
if ((Test-Path -LiteralPath $servicesFile) -and -not $Force) {
    Write-Host "Existing services.yaml preserved. Use -Force to replace it."
} else {
    if (Test-Path -LiteralPath $servicesFile) {
        $backup = "$servicesFile.$(Get-Date -Format 'yyyyMMdd-HHmmss').bak"
        Copy-Item -LiteralPath $servicesFile -Destination $backup
        Write-Host "Backup created: $backup"
    }
    @"
schema_version: 1
server:
  host: "192.168.1.12"
  scheme: "http"
services:
  ollama: {port: 11434, base_url: null}
  unlimited_ocr: {port: 8190, base_url: null}
  comfyui: {port: 8188, base_url: null}
paths:
  comfyui_models: "\\\\192.168.1.12\\aegis\\comfyui\\models"
"@ | Set-Content -LiteralPath $servicesFile -Encoding utf8
}

$scanRoots = @((Join-Path $projectRoot "aegis"), (Join-Path $projectRoot "config"))
$remaining = Get-ChildItem -LiteralPath $scanRoots -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\.git\\|\\.venv\\|site-packages|__pycache__' } |
    Select-String -SimpleMatch $oldAddress
if ($remaining) {
    Write-Warning "Remaining production occurrences of ${oldAddress}:"
    $remaining | ForEach-Object { Write-Host "$($_.Path):$($_.LineNumber):$($_.Line.Trim())" }
} else {
    Write-Host "No production occurrences of $oldAddress remain."
}
