param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop", "restart", "health", "free-vram")]
    [string]$Action,

    [Parameter(Mandatory=$false)]
    [ValidateSet("unlimited-ocr", "comfyui")]
    [string]$Service = "unlimited-ocr",

    [string]$HostName = $env:AEGIS_SERVER_HOST,
    [string]$User = "mk"
)

$ErrorActionPreference = "Stop"

if (-not $HostName) {
    $HostName = python -c "from aegis.config.services import get_server_host; print(get_server_host())"
    if ($LASTEXITCODE -ne 0 -or -not $HostName) {
        throw "Unable to resolve the AEGIS server host."
    }
    $HostName = $HostName.Trim()
}

function Invoke-Remote {
    param([string]$Command)
    ssh "$User@$HostName" $Command
}

$commands = @{
    "unlimited-ocr" = @{
        start = "cd ~/AEGIS/compose/unlimited-ocr && docker compose up -d unlimited-ocr"
        stop = "cd ~/AEGIS/compose/unlimited-ocr && docker compose stop unlimited-ocr || true"
        restart = "cd ~/AEGIS/compose/unlimited-ocr && docker compose up -d --force-recreate unlimited-ocr"
        health = "curl -fsS http://127.0.0.1:8190/health >/dev/null"
    }
    "comfyui" = @{
        start = "docker start comfyui || systemctl --user start comfyui || true"
        stop = "docker stop comfyui || systemctl --user stop comfyui || true"
        restart = "docker restart comfyui || systemctl --user restart comfyui || true"
        health = "curl -fsS http://127.0.0.1:8188/system_stats >/dev/null"
    }
}

if ($Action -eq "free-vram") {
    Invoke-Remote "nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -n 1"
    exit $LASTEXITCODE
}

Invoke-Remote $commands[$Service][$Action]
