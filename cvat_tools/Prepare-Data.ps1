$ErrorActionPreference = 'Stop'
$workspaceDir = Split-Path -Parent $PSScriptRoot
$repoDir = Join-Path $workspaceDir 'data_prepare'
$dataDir = Join-Path $workspaceDir 'data'
$archivePath = Join-Path $workspaceDir 'open.zip'
New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
& docker build -t hackalem-data-prepare:local $repoDir
if ($LASTEXITCODE -ne 0) { throw 'Container build failed' }
& docker run --rm --mount "type=bind,source=$archivePath,target=/input/open.zip,readonly" --mount "type=bind,source=$dataDir,target=/data" hackalem-data-prepare:local prepare /input/open.zip
if ($LASTEXITCODE -ne 0) { throw 'Source preparation failed' }
& docker run --rm --mount "type=bind,source=$dataDir,target=/data" --mount "type=bind,source=$PSScriptRoot,target=/tools,readonly" hackalem-data-prepare:local python /tools/probe_videos.py
if ($LASTEXITCODE -ne 0) { throw 'Frame count inspection failed' }
