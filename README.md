# Talvo_AI

## Google Authentication Setup

This project now uses `django-allauth` for Google sign-in and first-time registration onboarding.

### 1. Set environment variables

Use the values from `.env.example`:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GROQ_API_KEY`
- `GROQ_MODEL_NAME`
- `WHISPER_MODEL_SIZE`
- `COQUI_TTS_MODEL`

On Windows PowerShell:

```powershell
$env:GOOGLE_OAUTH_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
$env:GOOGLE_OAUTH_CLIENT_SECRET="your-google-client-secret"
$env:GROQ_API_KEY="your-groq-api-key"
$env:GROQ_MODEL_NAME="llama-3.1-8b-instant"
$env:WHISPER_MODEL_SIZE="base"
$env:COQUI_TTS_MODEL="tts_models/en/ljspeech/vits"
```

The project also auto-loads a local `.env` file from the repository root, so you can keep these values in `.env` instead of exporting every terminal session.

### 2. Live Interview Voice Pipeline

Live interview now runs this sequence per turn:

1. Browser records ~7 second audio chunk.
2. Backend transcribes with local `faster-whisper`.
3. Transcript + history go to Llama 3 via Groq.
4. AI response is synthesized with local Coqui TTS.
5. Frontend plays AI audio and continues the loop.

Install dependencies:

```powershell
c:/TALVO/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Create DB tables for session/turn storage:

```powershell
c:/TALVO/.venv/Scripts/python.exe manage.py migrate
```

Notes:

- Keep `WHISPER_MODEL_SIZE=base` or `small` for laptop performance.
- Ensure FFmpeg is available on PATH (required by Whisper for webm/audio decoding).
- Generated interview audio files are stored under `media/interviews/`.

### 2.1 Local Speech Worker (Whisper + Coqui)

Run speech models in Python 3.11 sidecar process and keep Django in its existing environment.

Install speech worker dependencies:

```powershell
c:/TALVO/voiceenv311/Scripts/python.exe -m pip install -r speech_worker/requirements.txt
```

Start speech worker:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_speech_worker.ps1
```

Health check:

```powershell
Invoke-WebRequest http://127.0.0.1:8001/health | Select-Object -ExpandProperty Content
```

Then run Django as usual in your app environment. The app will call `SPEECH_WORKER_URL` for STT/TTS.

Optional tuning:

- `TTS_USE_GPU=0` is safest on Windows if CUDA/cuDNN mismatch appears.
- Set `TTS_USE_GPU=1` only after confirming your CUDA runtime supports Coqui model inference.

### 3. Google Cloud Console OAuth redirect URI

Configure this redirect URI in your Google OAuth app:

`http://127.0.0.1:8000/accounts/google/login/callback/`

If you use `localhost`, also add:

`http://localhost:8000/accounts/google/login/callback/`

### 4. Run the app

```powershell
c:/TALVO/.venv/Scripts/python.exe manage.py runserver
```

### 5. Auth flow

1. Go to `/auth/login/` and sign in with Google.
2. First-time users are redirected to `/auth/registration/`.
3. Onboarding requires:
	- Target Role
	- Experience Level
	- Target Company
4. Optional onboarding fields:
	- Interview Focus
	- Confidence Level