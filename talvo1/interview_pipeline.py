import json
import importlib
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import requests
from django.conf import settings


class PipelineUnavailableError(RuntimeError):
    pass


@dataclass
class PipelineOutput:
    user_transcript: str
    ai_question: str
    ai_feedback: str
    ai_audio_relpath: str
    processing_ms: int
    timings: Dict[str, int]


class InterviewPipeline:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._models_lock = threading.Lock()
        self._groq = None

    @classmethod
    def instance(cls) -> "InterviewPipeline":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _ensure_models(self) -> None:
        with self._models_lock:
            if self._groq is None:
                self._groq = self._load_groq()

    def _load_groq(self):
        try:
            groq_module = importlib.import_module('groq')
            Groq = getattr(groq_module, 'Groq')
        except Exception as exc:
            raise PipelineUnavailableError(f"groq import failed: {exc}") from exc

        api_key = getattr(settings, 'GROQ_API_KEY', '')
        if not api_key:
            raise PipelineUnavailableError('Missing GROQ_API_KEY in environment/settings')
        return Groq(api_key=api_key)

    @staticmethod
    def _speech_worker_url() -> str:
        return (getattr(settings, 'SPEECH_WORKER_URL', '') or '').rstrip('/')

    @staticmethod
    def _speech_worker_timeout() -> int:
        return int(getattr(settings, 'SPEECH_WORKER_TIMEOUT_SECONDS', 120))

    def transcribe(self, audio_path: str) -> str:
        worker_url = self._speech_worker_url()
        if not worker_url:
            raise PipelineUnavailableError('SPEECH_WORKER_URL is not configured')

        last_exc = None
        for attempt in range(3):
            try:
                with open(audio_path, 'rb') as audio_file:
                    response = requests.post(
                        f"{worker_url}/stt",
                        files={'audio': (Path(audio_path).name, audio_file, 'audio/webm')},
                        timeout=self._speech_worker_timeout(),
                    )
                response.raise_for_status()
                payload = response.json()
                return (payload.get('transcript') or '').strip()
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.0)

        raise PipelineUnavailableError(
            f'STT worker request failed after retries: {last_exc}'
        ) from last_exc

    def generate_interviewer_response(
        self,
        *,
        target_role: str,
        target_company: str,
        difficulty: str,
        interview_type: str,
        history: List[Dict[str, str]],
        user_transcript: str,
        is_first_turn: bool,
    ) -> Dict[str, str]:
        self._ensure_models()
        model_name = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-8b-instant')

        system_prompt = (
            'You are an expert technical interviewer. Keep the interview natural, realistic, and concise. '
            'Use context from prior turns and ask one strong next question. '
            'Return strict JSON with keys: ai_question, ai_feedback. '
            'ai_feedback should be one short coaching note for the candidate answer, or empty on first turn.'
        )

        history_text = []
        for item in history[-10:]:
            history_text.append(f"Candidate: {item.get('user', '').strip()}")
            history_text.append(f"Interviewer: {item.get('ai', '').strip()}")

        user_block = user_transcript.strip() or '[NO USER TRANSCRIPT]'
        flow_mode = 'first_question' if is_first_turn else 'follow_up'

        user_prompt = (
            f"Interview Context:\n"
            f"- company: {target_company}\n"
            f"- role: {target_role}\n"
            f"- difficulty: {difficulty}\n"
            f"- interview_type: {interview_type}\n"
            f"- mode: {flow_mode}\n\n"
            f"Conversation History:\n{os.linesep.join(history_text) if history_text else '[NO HISTORY]'}\n\n"
            f"Latest candidate answer:\n{user_block}\n\n"
            "Rules:\n"
            "1) Ask one interviewer question only (no multi-question lists).\n"
            "2) If mode is follow_up, the question must connect to the candidate answer.\n"
            "3) Keep question under 35 words.\n"
            "4) ai_feedback must be under 25 words and actionable.\n"
            "5) Output JSON only."
        )

        result = self._groq.chat.completions.create(
            model=model_name,
            temperature=0.5,
            max_tokens=220,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        )

        text = (result.choices[0].message.content or '').strip()
        parsed = self._parse_llm_json(text)

        ai_question = parsed.get('ai_question', '').strip()
        ai_feedback = parsed.get('ai_feedback', '').strip()
        if not ai_question:
            ai_question = 'Can you walk me through your reasoning and the measurable outcome?'
        return {'ai_question': ai_question, 'ai_feedback': ai_feedback}

    @staticmethod
    def _parse_llm_json(raw_text: str) -> Dict[str, str]:
        if not raw_text:
            return {}

        candidate = raw_text
        if '```' in raw_text:
            parts = raw_text.split('```')
            candidate = parts[1] if len(parts) > 1 else raw_text
            candidate = candidate.replace('json', '', 1).strip()

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return {str(k): str(v) if v is not None else '' for k, v in parsed.items()}
        except json.JSONDecodeError:
            pass

        return {'ai_question': raw_text.strip(), 'ai_feedback': ''}

    def synthesize(self, text: str, output_path: Path) -> None:
        worker_url = self._speech_worker_url()
        if not worker_url:
            raise PipelineUnavailableError('SPEECH_WORKER_URL is not configured')

        last_exc = None
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{worker_url}/tts",
                    json={'text': text, 'output_path': str(output_path)},
                    timeout=self._speech_worker_timeout(),
                )
                response.raise_for_status()
                return
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.0)

        raise PipelineUnavailableError(
            f'TTS worker request failed after retries: {last_exc}'
        ) from last_exc

    def run_turn(
        self,
        *,
        target_role: str,
        target_company: str,
        difficulty: str,
        interview_type: str,
        history: List[Dict[str, str]],
        user_audio_path: str,
        ai_audio_relpath: str,
        is_first_turn: bool,
    ) -> PipelineOutput:
        start = time.perf_counter()

        whisper_start = time.perf_counter()
        user_transcript = '' if is_first_turn else self.transcribe(user_audio_path)
        whisper_ms = int((time.perf_counter() - whisper_start) * 1000)

        llm_start = time.perf_counter()
        if not is_first_turn and not user_transcript.strip():
            llm = {
                'ai_question': 'Why did you not answer? I could not catch your response. Please hold the speak button and answer again.',
                'ai_feedback': 'Speak a bit louder and keep holding the button until you finish.',
            }
        else:
            llm = self.generate_interviewer_response(
                target_role=target_role,
                target_company=target_company,
                difficulty=difficulty,
                interview_type=interview_type,
                history=history,
                user_transcript=user_transcript,
                is_first_turn=is_first_turn,
            )
        llm_ms = int((time.perf_counter() - llm_start) * 1000)

        tts_start = time.perf_counter()
        ai_audio_abs = Path(settings.MEDIA_ROOT) / ai_audio_relpath
        self.synthesize(llm['ai_question'], ai_audio_abs)
        tts_ms = int((time.perf_counter() - tts_start) * 1000)

        total_ms = int((time.perf_counter() - start) * 1000)
        return PipelineOutput(
            user_transcript=user_transcript,
            ai_question=llm['ai_question'],
            ai_feedback=llm['ai_feedback'],
            ai_audio_relpath=ai_audio_relpath,
            processing_ms=total_ms,
            timings={
                'whisper_ms': whisper_ms,
                'llm_ms': llm_ms,
                'tts_ms': tts_ms,
                'total_ms': total_ms,
            },
        )
