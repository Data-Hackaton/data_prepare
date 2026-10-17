$ErrorActionPreference = 'Stop'
$workspaceDir = Split-Path -Parent $PSScriptRoot
& docker compose -p hackalem-cvat -f (Join-Path $workspaceDir 'cvat_local/docker-compose.yml') -f (Join-Path $PSScriptRoot 'compose.local.yml') up -d
if ($LASTEXITCODE -ne 0) { throw 'CVAT startup failed' }
