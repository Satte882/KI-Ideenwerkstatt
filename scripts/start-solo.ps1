param([switch]$Prepare)
$ErrorActionPreference = 'Stop'
$soloRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $soloRoot
$env:DJANGO_SETTINGS_MODULE = 'config.settings.solo'
$soloPassword = Join-Path $soloRoot 'secrets/solo-master-password.txt'
if ($Prepare) {
    if (-not (Test-Path -LiteralPath $soloPassword)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $soloPassword) | Out-Null
        $soloBytes = [byte[]]::new(24)
        $soloRandom = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try { $soloRandom.GetBytes($soloBytes) } finally { $soloRandom.Dispose() }
        [Convert]::ToBase64String($soloBytes) | Set-Content -LiteralPath $soloPassword -Encoding utf8
    }
    uv run python manage.py prepare_solo_test --create-database --password-file $soloPassword
    if ($LASTEXITCODE -ne 0) { throw 'Solo preparation failed.' }
}
uv run python manage.py migrate --check
if ($LASTEXITCODE -ne 0) { throw 'Prepare solo database first: scripts/start-solo.ps1 -Prepare' }
$soloRuntime = Join-Path $soloRoot 'var/solo'
New-Item -ItemType Directory -Force -Path $soloRuntime | Out-Null
$soloDb = if ($env:SOLO_DATABASE_NAME) { $env:SOLO_DATABASE_NAME } else { 'ki_radar_solo' }
if ($soloDb -notmatch '^ki_radar_solo[A-Za-z0-9_]*$') { throw 'Invalid solo database name.' }
$soloPidFile = Join-Path $soloRuntime "$soloDb-worker.pid"
$soloWorker = $null
if (Test-Path -LiteralPath $soloPidFile) {
    $soloPid = 0
    if ([int]::TryParse((Get-Content -LiteralPath $soloPidFile -Raw).Trim(), [ref]$soloPid)) {
        $soloWorker = Get-CimInstance Win32_Process -Filter "ProcessId=$soloPid" -ErrorAction SilentlyContinue
        if ($soloWorker -and $soloWorker.CommandLine -notmatch 'run_investigation_worker.*--settings=config.settings.solo') {
            $soloWorker = $null
        }
    }
}
if (-not $soloWorker) {
    $soloWorker = Start-Process -FilePath (Get-Command uv).Source -WorkingDirectory $soloRoot -WindowStyle Hidden -ArgumentList @('run','python','manage.py','run_investigation_worker','--settings=config.settings.solo') -RedirectStandardOutput (Join-Path $soloRuntime "$soloDb-worker.out.log") -RedirectStandardError (Join-Path $soloRuntime "$soloDb-worker.err.log") -PassThru
    $soloWorker.Id | Set-Content -LiteralPath $soloPidFile -Encoding ascii
}
Write-Output 'Local solo practice: http://127.0.0.1:8000/solo/ ; login solo_master'
Write-Output 'Password: secrets/solo-master-password.txt (local only). Stop with Ctrl+C.'
Write-Output 'Configured live models and regular investigation worker are enabled; model calls can incur costs.'
uv run python manage.py runserver 127.0.0.1:8000 --noreload
if ($LASTEXITCODE -ne 0) { throw 'Solo server stopped with an error.' }
