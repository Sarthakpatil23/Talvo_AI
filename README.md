<p align="center">
  <img src="assets/readme-hero.svg" alt="Talvo AI Hero" width="100%" />
</p>

<p align="center">
  <img src="assets/talvo-logo.svg" alt="Talvo Website Logo" width="56" />
</p>

<h1 align="center">Talvo AI</h1>

<p align="center">
  <strong>Interview simulation that feels real, responds in voice, and coaches with precision.</strong>
</p>

<p align="center">
  <img alt="Django" src="https://img.shields.io/badge/Django-6-0f172a?style=flat-square" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13%20%2B%203.11-0f766e?style=flat-square" />
  <img alt="STT" src="https://img.shields.io/badge/STT-faster--whisper-1d4ed8?style=flat-square" />
  <img alt="LLM" src="https://img.shields.io/badge/LLM-Groq%20Llama-6d28d9?style=flat-square" />
  <img alt="TTS" src="https://img.shields.io/badge/TTS-Coqui-f97316?style=flat-square" />
</p>

---

## The Vibe

Talvo is built for candidates who want high-quality repetition under realistic interview pressure.

- Dynamic follow-up questions, not generic scripts
- Push-to-talk voice loop designed for natural speaking
- Replay-ready stored interview sessions and turns
- Instant coaching nudges you can use in the next answer

## Live Flow

1. AI asks the interview question.
2. User holds the dock button to speak and releases to submit.
3. Local Whisper transcribes voice.
4. Groq Llama generates next interviewer response.
5. Local Coqui synthesizes AI voice playback.
6. Loop continues until the interview ends.

If Talvo cannot detect a response, it prompts the user to answer again.

## System Design

```text
Browser (push-to-talk)
   |
   v
Django App (Python 3.13)
  - auth, APIs, session persistence
  - interview orchestration + Groq prompt logic
   |
   v
Speech Worker (Python 3.11)
  - /stt -> faster-whisper
  - /tts -> Coqui TTS
```

## Prompt Engineering + RAG

Talvo now uses a two-layer interviewer intelligence stack:

- Prompt engineering layer: modular guidance by company, role, difficulty, and interview type
- RAG layer: retrieves relevant interview examples from a local dataset and injects them into the LLM context

Current implementation files:

- talvo1/prompt_engineering.py
- talvo1/rag_retriever.py
- talvo1/data/interview_question_bank.json

How it works:

1. User context is captured from interview setup.
2. Retriever selects top-k relevant examples by metadata + context overlap.
3. Prompt builder assembles layered system rules and retrieved examples.
4. Groq model generates one grounded interviewer question plus concise coaching feedback.

Phase-2 upgrades:

- Candidate pool retrieval + MMR-style reranking for diversity
- Configurable metadata and semantic weighting
- Diversity control to avoid near-duplicate question retrieval
- Scenario evaluator script for retrieval quality checks

Evaluator command:

```powershell
Set-Location c:/TALVO/talvo
c:/TALVO/.venv/Scripts/python.exe scripts/evaluate_rag_phase2.py
```

## Quick Start

### 1. Install Django-side dependencies

```powershell
Set-Location c:/TALVO/talvo
c:/TALVO/.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### 2. Install speech worker dependencies

```powershell
Set-Location c:/TALVO/talvo
c:/TALVO/voiceenv311/Scripts/python.exe -m pip install -r speech_worker/requirements.txt
```

### 3. Apply migrations

```powershell
Set-Location c:/TALVO/talvo
c:/TALVO/.venv/Scripts/python.exe manage.py migrate
```

### 4. Start speech worker (Terminal A)

```powershell
Set-Location c:/TALVO/talvo
powershell -ExecutionPolicy Bypass -File scripts/start_speech_worker.ps1
```

### 5. Start Django server (Terminal B)

```powershell
Set-Location c:/TALVO/talvo
c:/TALVO/.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
```

### 6. Validate health

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8001/health | Select-Object -ExpandProperty Content
```

## Environment

Use `.env` from `.env.example`.

Required:

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GROQ_API_KEY`
- `GROQ_MODEL_NAME`
- `SPEECH_WORKER_URL` (default `http://127.0.0.1:8001`)

Common tuning:

- `WHISPER_MODEL_SIZE=base`
- `COQUI_TTS_MODEL=tts_models/en/ljspeech/vits`
- `TTS_USE_GPU=0` (recommended on most Windows setups)
- `INTERVIEW_RAG_DATA_PATH=talvo1/data/interview_question_bank.json`
- `INTERVIEW_RAG_TOP_K=4`
- `INTERVIEW_RAG_CANDIDATE_POOL=12`
- `INTERVIEW_RAG_ENABLE_RERANK=1`
- `INTERVIEW_RAG_DIVERSITY_LAMBDA=0.20`
- `INTERVIEW_RAG_METADATA_WEIGHT=1.0`
- `INTERVIEW_RAG_SEMANTIC_WEIGHT=1.1`

## OAuth Redirects

Configure both in Google Cloud Console:

- `http://127.0.0.1:8000/accounts/google/login/callback/`
- `http://localhost:8000/accounts/google/login/callback/`

## Core Routes

- `GET /live-interview/`
- `POST /api/live-interview/start/`
- `POST /api/live-interview/turn/`
- `GET /auth/login/`

## Troubleshooting

### Connection refused on STT (WinError 10061)

1. Ensure speech worker starts before Django interview turn requests.
2. Confirm `/health` responds on port `8001`.
3. Confirm `SPEECH_WORKER_URL` in `.env` points to the same host and port.

### Voice not captured

- Keep the Hold to Speak button pressed while speaking.
- Release only after finishing the sentence.
- Confirm browser mic permission and OS mic level are enabled.

### Coqui GPU issues

- Keep `TTS_USE_GPU=0` first.
- Enable GPU only after CUDA/cuDNN compatibility is verified.

## License

Licensed under the terms in [LICENSE](LICENSE).
