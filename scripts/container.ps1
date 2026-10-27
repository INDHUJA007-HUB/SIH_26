param([ValidateSet('up','check','stop')][string]$Action='up')
$ErrorActionPreference='Stop'
$repoRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dockerCommand=Get-Command docker -ErrorAction SilentlyContinue
$dockerExecutable=if($dockerCommand){$dockerCommand.Source}else{Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'}
if(-not(Test-Path -LiteralPath $dockerExecutable)){throw 'Docker Desktop/Engine with Compose is required.'}
$env:PATH=(Split-Path -Parent $dockerExecutable)+';'+$env:PATH
$runtimeImage=if($env:SIH_RUNTIME_IMAGE){$env:SIH_RUNTIME_IMAGE}else{'ghcr.io/indhuja007-hub/sih_26:latest'}
$parserImage=if($env:SIH_PARSER_IMAGE){$env:SIH_PARSER_IMAGE}else{'ghcr.io/indhuja007-hub/sih_26-parser:latest'}
$composeArgs=@('compose','--env-file','.env','-f','infra/compose/compose.yaml','-f','infra/compose/compose.distribution.yaml')
Push-Location $repoRoot
try {
    if($Action -eq 'up') {
        foreach($image in @($runtimeImage,$parserImage)) {
            & $dockerExecutable pull $image
            if($LASTEXITCODE -ne 0){throw "Unable to pull $image. Confirm the GHCR package is public or sign in with docker login ghcr.io."}
        }
        & $dockerExecutable run --rm --mount "type=bind,source=$repoRoot,target=/workspace" -e WB_PROJECT_ROOT=/workspace -w /workspace $runtimeImage python -m workbench.tools bootstrap
        if($LASTEXITCODE -ne 0){throw 'Container-only bootstrap failed'}
        & $dockerExecutable @composeArgs up -d --wait
        if($LASTEXITCODE -ne 0){throw 'Container startup failed'}
        Write-Output 'Workbench backend ready: API http://127.0.0.1:8000/docs'
    } elseif($Action -eq 'check') {
        & $dockerExecutable @composeArgs ps
        if($LASTEXITCODE -ne 0){throw 'Unable to inspect the stack'}
        $response=Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:8000/health/ready -TimeoutSec 10
        if($response.StatusCode -ne 200){throw 'API readiness check failed'}
        Write-Output 'Container stack is ready.'
    } else {
        & $dockerExecutable @composeArgs down
        if($LASTEXITCODE -ne 0){throw 'Container stop failed'}
    }
} finally { Pop-Location }
