$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @(
    'C:/TALVO/voiceenv311/Scripts/python.exe',
    (Join-Path (Split-Path -Parent $root) '.venv/Scripts/python.exe'),
    (Join-Path $root '.venv/Scripts/python.exe')
)

$py = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) {
    Write-Error "No Python environment found for Django app. Checked: $($pythonCandidates -join ', ')"
}

$workerScript = Join-Path $PSScriptRoot 'start_speech_worker.ps1'
if (-not (Test-Path $workerScript)) {
    Write-Error "Speech worker startup script not found: $workerScript"
}

Write-Host 'Starting speech worker on http://127.0.0.1:8001 ...'
Start-Process -FilePath 'powershell' -ArgumentList @(
    '-NoExit',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $workerScript
) -WorkingDirectory $root | Out-Null

Start-Sleep -Seconds 2
Write-Host 'Starting Django on http://127.0.0.1:8000 ...'
Set-Location $root
& $py manage.py runserver 127.0.0.1:8000
