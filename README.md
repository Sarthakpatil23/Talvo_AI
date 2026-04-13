<div align="center">
  <img src="assets/readme-hero.svg" alt="Talvo AI Hero" width="100%" />
</div>

<div align="center">
  <img src="assets/talvo-logo.svg" alt="Talvo Logo" width="80" style="margin-top: 20px; margin-bottom: 20px;" />
</div>

<h1 align="center">🚀 Talvo AI</h1>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Inter&weight=600&size=20&pause=1000&color=2E8B57&center=true&vCenter=true&width=600&lines=Interview+simulation+that+feels+real.;Responds+fluently+in+voice.;Coaches+you+with+precision.;Conquer+your+next+tech+interview." alt="Typing effect description" />
</p>

<p align="center">
  <a href="#-the-vibe"><strong>✨ Features</strong></a> ·
  <a href="#-system-architecture"><strong>🏗️ Architecture</strong></a> ·
  <a href="#-quick-start"><strong>⚡ Quick Start</strong></a> ·
  <a href="#%EF%B8%8F-environment-variables"><strong>⚙️ Config</strong></a> ·
  <a href="#-troubleshooting"><strong>🩺 Troubleshooting</strong></a>
</p>

<div align="center">

  <img alt="Django" src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=green" />
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB" />
  <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black" />
  <br/>
  <img alt="STT" src="https://img.shields.io/badge/STT-faster--whisper-1d4ed8?style=for-the-badge" />
  <img alt="LLM" src="https://img.shields.io/badge/LLM-Groq%20Llama-6d28d9?style=for-the-badge" />
  <img alt="TTS" src="https://img.shields.io/badge/TTS-Coqui-f97316?style=for-the-badge" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" />

</div>

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## ✨ The Vibe

Talvo is built for candidates who want high-quality repetition under realistic interview pressure. It’s not just about practicing questions; it's about conversing with an AI that actively listens and coaches you.

<details>
<summary><b>🎯 Dynamic Follow-Ups</b></summary>
<br/>
No generic scripts. The AI actively adapts to your answers, generating context-aware follow-up questions tailored specifically to what you just said.
</details>

<details>
<summary><b>🎙️ Push-to-Talk Voice Loop</b></summary>
<br/>
Designed for natural speaking and precise input. Just like a walkie-talkie, providing you full control over when the AI listens.
</details>

<details>
<summary><b>🔄 Replay-Ready Sessions</b></summary>
<br/>
Review stored interview sessions and turn-by-turn interactions anytime. Track your growth through detailed transcripts.
</details>

<details>
<summary><b>💡 Instant Coaching</b></summary>
<br/>
Get real-time nudges and actionable feedback on the fly, empowering you to adjust and improve your next answer instantly.
</details>

<details>
<summary><b>🧩 Aptitude & Technical Matches</b></summary>
<br/>
Not just behavioral! Specialized rounds including technical algorithms, system design, and rigorous aptitude quizzes.
</details>

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🏗️ System Architecture

Talvo utilizes a dual-worker setup to handle realtime voice processing efficiently alongside typical web routing.

`mermaid
graph TD
    User([Candidate]) -->|Push-to-Talk Voice| Browser
    Browser -->|Audio Blob| STT
    
    subgraph "Python 3.13 - Django App"
        WEB[Web Server]
        Auth[OAuth & Session]
        Orch[Interview Orchestration]
        RAG[RAG + Prompt Eng]
    end
    
    subgraph "Python 3.11 - Speech Worker"
        STT[STT: faster-whisper]
        TTS[TTS: Coqui]
    end
    
    Browser <-->|HTTP / WebSocket| WEB
    WEB <--> Auth
    WEB <--> Orch
    Orch <--> RAG
    
    RAG <-->|Fetch context| Groq[Groq Llama LLM]
    STT -->|Transcribed Text| WEB
    Orch -->|Response Text| TTS
    TTS -->|Synthesized Audio| Browser
`

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🧠 Intelligence Stack (Prompt Engineering & RAG)

Talvo runs a state-of-the-art **two-layer interviewer intelligence stack**:

1. **Prompt Engineering Layer:** Modular guidance by company, role, difficulty, and interview type.
2. **RAG (Retrieval-Augmented Generation) Layer:** Retrieves relevant interview examples from a local dataset and injects them into the LLM context.

### 🔍 How It Works

1. **Context Capture:** User context is captured from the interview setup form.
2. **Retrieval:** The retriever selects top-*k* relevant examples based on metadata + semantic context overlap.
3. **Prompt Assembly:** The builder constructs layered system rules combining standard guidelines and retrieved examples.
4. **Generation:** The Groq model generates a deeply grounded interviewer question plus concise coaching feedback.

<details>
<summary><b>🛠️ Click to see Phase-2 Upgrades</b></summary>
<br/>

- **MMR-Style Reranking:** Enhanced diversity for candidate pool retrieval.
- **Configurable Weights:** Tune metadata and semantic weighting dynamically.
- **Diversity Control:** Avoid near-duplicate question retrieval in the same session.
- **Scenario Evaluator:** Built-in script for retrieval quality checks.

*Run the Evaluator:*
`powershell
Set-Location c:/TALVO/talvo
../.venv/Scripts/python.exe scripts/evaluate_rag_phase2.py
`
</details>

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## ⚡ Quick Start

### 1. Prerequisites
- **Python 3.13** (for the Django web app)
- **Python 3.11** (for the Speech Worker)
- **Node.js** (for frontend UI components / Tailwind)

### 2. Setup Django App (Terminal A)

`powershell
Set-Location c:/TALVO/talvo
# Create and activate your 3.13 virtual environment if you haven't yet
c:/TALVO/.venv/Scripts/python.exe -m pip install -r requirements.txt
c:/TALVO/.venv/Scripts/python.exe manage.py migrate
c:/TALVO/.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
`

### 3. Setup Speech Worker (Terminal B)

`powershell
Set-Location c:/TALVO/talvo
# Activate your 3.11 virtual environment (voiceenv311)
c:/TALVO/voiceenv311/Scripts/python.exe -m pip install -r speech_worker/requirements.txt
powershell -ExecutionPolicy Bypass -File scripts/start_speech_worker.ps1
`

### 4. Verify Services
Check if the speech worker is healthy:
`powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8001/health | Select-Object -ExpandProperty Content
`

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## ⚙️ Environment Variables

Copy .env.example to .env and fill in the required keys:

### 🔐 Required
`ini
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL_NAME=llama3-70b-8192
SPEECH_WORKER_URL=http://127.0.0.1:8001
`

<details>
<summary><b>🎛️ Tuning Options (Optional)</b></summary>
<br/>

`ini
WHISPER_MODEL_SIZE=base
COQUI_TTS_MODEL=tts_models/en/ljspeech/vits
TTS_USE_GPU=0  # Recommended to keep 0 on most Windows setups unless CUDA is configured

# RAG Configuration
INTERVIEW_RAG_DATA_PATH=talvo1/data/interview_question_bank.json
INTERVIEW_RAG_TOP_K=4
INTERVIEW_RAG_CANDIDATE_POOL=12
INTERVIEW_RAG_ENABLE_RERANK=1
INTERVIEW_RAG_DIVERSITY_LAMBDA=0.20
INTERVIEW_RAG_METADATA_WEIGHT=1.0
INTERVIEW_RAG_SEMANTIC_WEIGHT=1.1
`
</details>

> **Note on OAuth Redirects:**
> Make sure to configure http://127.0.0.1:8000/accounts/google/login/callback/ and http://localhost:8000/accounts/google/login/callback/ in your Google Cloud Console.

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🧭 Core Routes

### Web
- 🏠 **Landing:** GET /
- 🎯 **Dashboard:** GET /dashboard/
- 🎙️ **Live Interview:** GET /live-interview/
- 📊 **Feedback & Analytics:** GET /post-interview-feedback/

### API
- 🏁 **Start Interview:** POST /api/live-interview/start/
- 🔄 **Interview Turn:** POST /api/live-interview/turn/

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🩺 Troubleshooting

<details>
<summary><b>🔴 Connection refused on STT (WinError 10061)</b></summary>
<br/>

1. Ensure the Speech Worker is running before starting an interview turn.
2. Confirm the /health endpoint responds on port 8001.
3. Verify that SPEECH_WORKER_URL in your .env points to the correct host/port.

</details>

<details>
<summary><b>🎤 Voice not captured</b></summary>
<br/>

- Keep the **Hold to Speak** button pressed actively while speaking.
- Release it **only after** you've finished your sentence.
- Check browser microphone permissions and OS input levels.

</details>

<details>
<summary><b>🐌 Slow TTS / Coqui GPU issues</b></summary>
<br/>

- Leave TTS_USE_GPU=0 by default.
- Only enable GPU if you are certain your CUDA/cuDNN toolkit precisely matches PyTorch requirements in the oiceenv311 environment.

</details>

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 📜 License

Talvo is distributed under the terms in the [LICENSE](LICENSE) file.

<br/>
<div align="center">
<p><i>Made with <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Red%20Heart.png" alt="Heart" width="20" height="20" style="vertical-align:bottom" /> for better interviewing.</i></p>
</div>
