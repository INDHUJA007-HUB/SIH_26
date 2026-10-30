param([ValidateSet('native','up','check','stop','doctor')][string]$Action='native')
$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectUv=Join-Path $repoRoot '.tools\uv\bin\uv.exe'
$uvExecutable=if(Test-Path -LiteralPath $projectUv){$projectUv}else{(Get-Command uv -ErrorAction Stop).Source}
Push-Location $repoRoot
try {
    & $uvExecutable sync --project backend --frozen --group dev --group spikes
    if($LASTEXITCODE -ne 0){throw 'Dependency sync failed'}
    & $uvExecutable run --project backend python -m workbench.tools bootstrap
    if($LASTEXITCODE -ne 0){throw 'Bootstrap failed'}
    if($Action -eq 'native') {
        & $uvExecutable run --project backend uvicorn workbench.api.main:app --host 127.0.0.1 --port 8000 --no-access-log
    } elseif($Action -eq 'doctor') {
        & $uvExecutable run --project backend python -m workbench.tools doctor
    } else {
        $dockerCommand=Get-Command docker -ErrorAction SilentlyContinue
        $dockerExecutable=if($dockerCommand){$dockerCommand.Source}else{Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'}
        if(-not(Test-Path -LiteralPath $dockerExecutable)){throw 'Docker Desktop/Engine is required for the container stack. Native mode remains available.'}
        $env:PATH=(Split-Path -Parent $dockerExecutable)+';'+$env:PATH
        $composeArgs=@('compose','--env-file','.env','-f','infra/compose/compose.yaml')
        if($Action -eq 'up') {
            if($env:WB_BUILD_NETWORK -eq 'host') {
                foreach($target in @('runtime','parser','media')) {
                    $tag=if($target -eq 'runtime'){'foundation'}else{$target}
                    & $dockerExecutable buildx build --allow=network.host --network=host --load --target $target -t "sih-workbench:$tag" -f Dockerfile .
                    if($LASTEXITCODE -ne 0){throw 'Container build failed'}
                }
            } else {
                & $dockerExecutable @composeArgs build migrate parser media-worker
                if($LASTEXITCODE -ne 0){throw 'Container build failed'}
            }
            & $dockerExecutable @composeArgs up -d --wait
            if($LASTEXITCODE -ne 0){throw 'Container startup failed'}
            & $uvExecutable run --project backend python -m workbench.tools seed-db
            if($LASTEXITCODE -ne 0){throw 'Database seed failed'}
            & $uvExecutable run --project backend python -m workbench.tools seed-buckets
            if($LASTEXITCODE -ne 0){throw 'Bucket seed failed'}
        } elseif($Action -eq 'check') {
            & $uvExecutable run --project backend python backend/tools/platform_smoke.py
            if($LASTEXITCODE -ne 0){throw 'Platform smoke failed'}
            & $uvExecutable run --project backend python backend/tools/check_oidc.py
            if($LASTEXITCODE -ne 0){throw 'OIDC smoke failed'}
        } elseif($Action -eq 'stop') {
            & $dockerExecutable @composeArgs down
            if($LASTEXITCODE -ne 0){throw 'Container stop failed'}
        }
    }
} finally { Pop-Location }
