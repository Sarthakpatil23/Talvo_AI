$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$py = 'C:/TALVO/voiceenv311/Scripts/python.exe'

if (-not (Test-Path $py)) {
    Write-Error "Python 3.11 speech environment not found at $py"
}

$env:PHONEMIZER_ESPEAK_LIBRARY = 'C:/Program Files/eSpeak NG/libespeak-ng.dll'
$env:ESPEAK_DATA_PATH = 'C:/Program Files/eSpeak NG/espeak-ng-data'
$env:Path = "C:/Program Files/eSpeak NG;" + $env:Path
$env:WHISPER_MODEL_SIZE = if ($env:WHISPER_MODEL_SIZE) { $env:WHISPER_MODEL_SIZE } else { 'base' }
$env:COQUI_TTS_MODEL = if ($env:COQUI_TTS_MODEL) { $env:COQUI_TTS_MODEL } else { 'tts_models/en/ljspeech/vits' }
$env:TTS_USE_GPU = if ($env:TTS_USE_GPU) { $env:TTS_USE_GPU } else { '0' }

Set-Location $root
& $py -m uvicorn speech_worker.app:app --host 127.0.0.1 --port 8001
