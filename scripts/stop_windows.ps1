# FinAlly - stop the production container (Windows PowerShell).
#
# Stops and removes the running container. The named volume 'finally-data'
# is intentionally preserved so portfolio state survives restarts.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ContainerName = 'finally-app'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error 'docker is not installed or not on PATH.'
    exit 1
}

try {
    docker info *> $null
} catch {
    Write-Error 'Docker daemon is not running.'
    exit 1
}

$AllNames     = (docker ps -a --format '{{.Names}}') -split "`n"
$RunningNames = (docker ps    --format '{{.Names}}') -split "`n"

if ($AllNames -notcontains $ContainerName) {
    Write-Host 'FinAlly is not running. Nothing to stop.'
    exit 0
}

if ($RunningNames -contains $ContainerName) {
    Write-Host "Stopping $ContainerName..."
    docker stop $ContainerName | Out-Null
}

Write-Host "Removing $ContainerName..."
docker rm $ContainerName | Out-Null

Write-Host "FinAlly stopped. (Volume 'finally-data' preserved - your portfolio is safe.)"
