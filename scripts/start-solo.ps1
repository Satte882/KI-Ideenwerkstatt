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
        [System.Security.Cryptography.RandomNumberGenerator]::Fill($soloBytes)
        [Convert]::ToBase64String($soloBytes) | Set-Content -LiteralPath $soloPassword -Encoding utf8
    }
    uv run python manage.py prepare_solo_test --create-database --password-file $soloPassword
    if ($LASTEXITCODE -ne 0) { throw 'Solo preparation failed.' }
}
uv run python manage.py migrate --check
if ($LASTEXITCODE -ne 0) { throw 'Prepare solo database first: scripts/start-solo.ps1 -Prepare' }
Write-Output 'Local solo practice: http://127.0.0.1:8000/solo/ ; login solo_master'
Write-Output 'Password: secrets/solo-master-password.txt (local only). Stop with Ctrl+C.'
uv run python manage.py runserver 127.0.0.1:8000 --noreload
if ($LASTEXITCODE -ne 0) { throw 'Solo server stopped with an error.' }
