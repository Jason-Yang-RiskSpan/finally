# FinAlly - start the production container (Windows PowerShell).
#
# Usage:
#   .\scripts\start_windows.ps1            # start (build only if image missing)
#   .\scripts\start_windows.ps1 -Build     # force a rebuild before starting
#   .\scripts\start_windows.ps1 -Open      # also open the browser
#
# Idempotent: safe to run multiple times.

[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Open
)

$ErrorActionPreference = 'Stop'

$ImageName     = 'finally:latest'
$ContainerName = 'finally-app'
$VolumeName    = 'finally-data'
$HostPort      = if ($env:FINALLY_HOST_PORT) { $env:FINALLY_HOST_PORT } else { '8000' }

# Resolve project root (one level up from this script).
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $ProjectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error 'docker is not installed or not on PATH.'
    exit 1
}

try {
    docker info *> $null
} catch {
    Write-Error 'Docker daemon is not running. Start Docker Desktop and retry.'
    exit 1
}

# Ensure .env exists.
if (-not (Test-Path '.env')) {
    if (Test-Path '.env.example') {
        Write-Host 'No .env found - creating one from .env.example.'
        Copy-Item '.env.example' '.env'
    } else {
        Write-Warning 'No .env or .env.example present; container will run without env file.'
    }
}

# Build image if missing or forced.
$ImageExists = $false
try {
    docker image inspect $ImageName *> $null
    if ($LASTEXITCODE -eq 0) { $ImageExists = $true }
} catch {
    $ImageExists = $false
}

if ($Build -or -not $ImageExists) {
    Write-Host "Building image $ImageName..."
    docker build -t $ImageName .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Ensure volume exists.
docker volume inspect $VolumeName *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating volume $VolumeName..."
    docker volume create $VolumeName | Out-Null
}

$Url = "http://localhost:$HostPort"

# Inspect container state.
$AllNames     = (docker ps -a --format '{{.Names}}') -split "`n"
$RunningNames = (docker ps    --format '{{.Names}}') -split "`n"

if ($AllNames -contains $ContainerName) {
    if ($RunningNames -contains $ContainerName) {
        Write-Host "FinAlly is already running at $Url"
    } else {
        Write-Host "Removing stopped container $ContainerName..."
        docker rm $ContainerName | Out-Null

        Write-Host 'Starting FinAlly...'
        $envFlag = @()
        if (Test-Path '.env') { $envFlag = @('--env-file', '.env') }
        docker run -d `
            --name $ContainerName `
            @envFlag `
            -p ("{0}:8000" -f $HostPort) `
            -v ("{0}:/app/data" -f $VolumeName) `
            --restart unless-stopped `
            $ImageName | Out-Null
        Write-Host "FinAlly is starting at $Url"
    }
} else {
    Write-Host 'Starting FinAlly...'
    $envFlag = @()
    if (Test-Path '.env') { $envFlag = @('--env-file', '.env') }
    docker run -d `
        --name $ContainerName `
        @envFlag `
        -p "$HostPort`:8000" `
        -v "$VolumeName`:/app/data" `
        --restart unless-stopped `
        $ImageName | Out-Null
    Write-Host "FinAlly is starting at $Url"
}

if ($Open) {
    Start-Process $Url
}

Write-Host "Tail logs with: docker logs -f $ContainerName"
Write-Host 'Stop with:      .\scripts\stop_windows.ps1'
