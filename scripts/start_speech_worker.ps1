$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @(
    'C:/TALVO/voiceenv311/Scripts/python.exe',
    (Join-Path (Split-Path -Parent $root) '.venv/Scripts/python.exe'),
    (Join-Path $root '.venv/Scripts/python.exe')
)

$py = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $py) {
    Write-Error "No Python environment found for speech worker. Checked: $($pythonCandidates -join ', ')"
}

$envFile = Join-Path $root '.env'
if (Test-Path $envFile) {
    $allowedKeys = @(
        'WHISPER_MODEL_SIZE',
        'COQUI_TTS_MODEL',
        'TTS_USE_GPU',
        'STT_LANGUAGE',
        'STT_NO_SPEECH_THRESHOLD',
        'STT_LOG_PROB_THRESHOLD',
        'STT_COMPRESSION_RATIO_THRESHOLD',
        'STT_BEAM_PRIMARY',
        'STT_BEAM_BACKUP',
        'STT_INITIAL_PROMPT',
        'RHUBARB_BINARY',
        'RHUBARB_TIMEOUT_SECONDS'
    )

    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#') -or -not $line.Contains('=')) {
            return
        }

        $parts = $line -split '=', 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($allowedKeys -contains $key -and $value) {
            [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
        }
    }
}

$env:PHONEMIZER_ESPEAK_LIBRARY = 'C:/Program Files/eSpeak NG/libespeak-ng.dll'
$env:ESPEAK_DATA_PATH = 'C:/Program Files/eSpeak NG/espeak-ng-data'
$env:Path = "C:/Program Files/eSpeak NG;" + $env:Path
$env:WHISPER_MODEL_SIZE = if ($env:WHISPER_MODEL_SIZE) { $env:WHISPER_MODEL_SIZE } else { 'medium.en' }
$env:COQUI_TTS_MODEL = if ($env:COQUI_TTS_MODEL) { $env:COQUI_TTS_MODEL } else { 'tts_models/en/ljspeech/vits' }
$env:TTS_USE_GPU = if ($env:TTS_USE_GPU) { $env:TTS_USE_GPU } else { '0' }
$env:STT_LANGUAGE = if ($env:STT_LANGUAGE) { $env:STT_LANGUAGE } else { 'en' }
$env:STT_NO_SPEECH_THRESHOLD = if ($env:STT_NO_SPEECH_THRESHOLD) { $env:STT_NO_SPEECH_THRESHOLD } else { '0.85' }
$env:STT_LOG_PROB_THRESHOLD = if ($env:STT_LOG_PROB_THRESHOLD) { $env:STT_LOG_PROB_THRESHOLD } else { '-2.0' }
$env:STT_COMPRESSION_RATIO_THRESHOLD = if ($env:STT_COMPRESSION_RATIO_THRESHOLD) { $env:STT_COMPRESSION_RATIO_THRESHOLD } else { '2.8' }
$env:STT_BEAM_PRIMARY = if ($env:STT_BEAM_PRIMARY) { $env:STT_BEAM_PRIMARY } else { '8' }
$env:STT_BEAM_BACKUP = if ($env:STT_BEAM_BACKUP) { $env:STT_BEAM_BACKUP } else { '12' }

Set-Location $root
& $py -m uvicorn speech_worker.app:app --host 127.0.0.1 --port 8001
