import json
import importlib
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import requests
from django.conf import settings

from .prompt_engineering import InterviewPromptBuilder
from .rag_retriever import InterviewRAGRetriever


class PipelineUnavailableError(RuntimeError):
    pass


@dataclass
class PipelineOutput:
    user_transcript: str
    ai_question: str
    ai_feedback: str
    ai_audio_relpath: str
    ai_lipsync_relpath: str
    processing_ms: int
    timings: Dict[str, int]
    rag_context: List[Dict[str, str]]


class InterviewPipeline:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._models_lock = threading.Lock()
        self._groq = None
        self._prompt_builder = InterviewPromptBuilder()
        self._retriever = InterviewRAGRetriever()

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

        api_key = str(getattr(settings, 'GROQ_API_KEY', '') or '').strip()
        if not api_key or api_key == 'your-groq-api-key':
            raise PipelineUnavailableError('Missing or placeholder GROQ_API_KEY in .env. Set a real key and restart server.')
        return Groq(api_key=api_key)

    @staticmethod
    def _software_only_enabled() -> bool:
        return str(getattr(settings, 'INTERVIEW_SOFTWARE_ONLY', '1')).strip().lower() in {'1', 'true', 'yes', 'on'}

    @staticmethod
    def _normalize_software_type(interview_type: str) -> str:
        allowed_raw = str(getattr(settings, 'INTERVIEW_SOFTWARE_ALLOWED_TYPES', 'technical,coding,system design,debugging,behavioral'))
        allowed = [x.strip().lower() for x in allowed_raw.split(',') if x.strip()]
        normalized = (interview_type or '').strip().lower()
        if normalized in {'final round', 'final'}:
            return 'Final Round'
        if normalized in allowed:
            return normalized.title()
        for value in allowed:
            if normalized and (normalized in value or value in normalized):
                return value.title()
        return 'Technical'

    @staticmethod
    def _speech_worker_url() -> str:
        return (getattr(settings, 'SPEECH_WORKER_URL', '') or '').rstrip('/')

    @staticmethod
    def _speech_worker_timeout() -> int:
        return int(getattr(settings, 'SPEECH_WORKER_TIMEOUT_SECONDS', 120))

    @staticmethod
    def _stt_min_confidence() -> float:
        try:
            return float(getattr(settings, 'STT_MIN_CONFIDENCE', 0.45))
        except Exception:
            return 0.45

    @staticmethod
    def _is_final_round(interview_type: str) -> bool:
        normalized = (interview_type or '').strip().lower()
        return normalized in {'final round', 'final'}

    @staticmethod
    def _build_final_round_opening_question(candidate_name: str) -> str:
        cleaned_name = ' '.join(str(candidate_name or '').strip().split())
        if cleaned_name:
            return f"Hi {cleaned_name}, welcome to the final round. Could you briefly introduce yourself and highlight your most relevant experience?"
        return 'Hi, welcome to the final round. Could you briefly introduce yourself and highlight your most relevant experience?'

    @staticmethod
    def _extract_intro_skill_keywords(user_transcript: str) -> List[str]:
        text = str(user_transcript or '').strip().lower()
        if not text:
            return []

        known = [
            'python', 'java', 'javascript', 'typescript', 'django', 'flask', 'fastapi',
            'react', 'node', 'aws', 'azure', 'gcp', 'docker', 'kubernetes',
            'sql', 'postgresql', 'mysql', 'mongodb', 'redis', 'machine learning',
            'deep learning', 'nlp', 'system design', 'api', 'microservices',
        ]

        found: List[str] = []
        for skill in known:
            if skill in text:
                label = 'API' if skill == 'api' else skill.title()
                found.append(label)
            if len(found) >= 2:
                break
        return found

    @staticmethod
    def _count_candidate_responses(history: List[Dict[str, str]], current_user_transcript: str) -> int:
        total = 0
        for item in history:
            if str(item.get('user', '') or '').strip():
                total += 1
        if str(current_user_transcript or '').strip():
            total += 1
        return total

    def _build_final_round_intro_followup_question(
        self,
        *,
        candidate_name: str,
        user_transcript: str,
        candidate_response_count: int,
    ) -> str:
        cleaned_name = ' '.join(str(candidate_name or '').strip().split())
        prefix = f"Thanks {cleaned_name}," if cleaned_name else 'Thanks,'

        if candidate_response_count <= 1:
            keywords = self._extract_intro_skill_keywords(user_transcript)
            if keywords:
                skill_text = ' and '.join(keywords[:2])
                return (
                    f"{prefix} you mentioned {skill_text}. Could you describe one project where you used it, your role, "
                    'and measurable impact?'
                )
            return f"{prefix} could you describe one recent project, your core responsibilities, and the measurable outcome?"

        return (
            'Great context. Before company-specific questions, what was the hardest tradeoff in that work, '
            'why did you choose that approach, and what metric improved?'
        )

    def transcribe(self, audio_path: str) -> Dict[str, object]:
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
                transcript = (payload.get('transcript') or '').strip() if isinstance(payload, dict) else ''
                confidence = 0.0
                if isinstance(payload, dict):
                    try:
                        confidence = float(payload.get('confidence', 0.0) or 0.0)
                    except Exception:
                        confidence = 0.0

                return {
                    'transcript': transcript,
                    'confidence': confidence,
                    'decode_mode': (payload.get('decode_mode') or '') if isinstance(payload, dict) else '',
                    'language': (payload.get('language') or '') if isinstance(payload, dict) else '',
                }
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
        include_resume: bool = False,
        resume_context: str = '',
        candidate_name: str = '',
    ) -> Dict[str, str]:
        self._ensure_models()
        model_name = getattr(settings, 'GROQ_MODEL_NAME', 'llama-3.1-8b-instant')
        rag_top_k_setting = int(getattr(settings, 'INTERVIEW_RAG_TOP_K', 4))
        if self._is_final_round(interview_type) and (is_first_turn or len(history) <= 1):
            rag_top_k = max(1, min(rag_top_k_setting, 2))
        else:
            rag_top_k = max(2, min(rag_top_k_setting, 3))

        retrieved = self._retriever.retrieve(
            company=target_company,
            role=target_role,
            difficulty=difficulty,
            interview_type=interview_type,
            user_transcript=user_transcript,
            history=history,
            top_k=rag_top_k,
        )

        prompt_bundle = self._prompt_builder.build(
            target_company=target_company,
            target_role=target_role,
            difficulty=difficulty,
            interview_type=interview_type,
            history=history,
            user_transcript=user_transcript,
            is_first_turn=is_first_turn,
            retrieved_items=retrieved,
            include_resume=include_resume,
            resume_context=resume_context,
            candidate_name=candidate_name,
        )

        try:
            result = self._groq.chat.completions.create(
                model=model_name,
                temperature=0.35,
                max_tokens=170,
                messages=[
                    {'role': 'system', 'content': prompt_bundle.system_prompt},
                    {'role': 'user', 'content': prompt_bundle.user_prompt},
                ],
            )
        except Exception as exc:
            message = str(exc)
            lower_message = message.lower()
            if 'invalid_api_key' in lower_message or 'invalid api key' in lower_message:
                raise PipelineUnavailableError(
                    'Invalid GROQ_API_KEY in .env. Replace it with a valid key and restart server.'
                ) from exc
            raise PipelineUnavailableError(f'Groq API request failed: {message}') from exc

        text = (result.choices[0].message.content or '').strip()
        parsed = self._parse_llm_json(text)

        ai_question = parsed.get('ai_question', '').strip()
        ai_feedback = parsed.get('ai_feedback', '').strip()
        if not ai_question:
            ai_question = 'Can you walk me through your reasoning and the measurable outcome?'

        debug_items: List[Dict[str, str]] = []
        for item in retrieved[:4]:
            debug_items.append(
                {
                    'question': str(item.get('question', '')),
                    'rationale': str(item.get('rationale', '')),
                    'company': str(item.get('company', '')),
                    'role': str(item.get('role', '')),
                    'difficulty': str(item.get('difficulty', '')),
                    'interview_type': str(item.get('interview_type', '')),
                    'score': str(item.get('score', '')),
                }
            )

        return {
            'ai_question': ai_question,
            'ai_feedback': ai_feedback,
            'retrieved_examples': debug_items,
        }

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

    def synthesize(self, text: str, output_path: Path) -> Dict[str, str]:
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
                payload = response.json() if response.content else {}
                lipsync_abs = ''
                if isinstance(payload, dict):
                    lipsync_abs = str(payload.get('lipsync_path', '') or '').strip()

                lipsync_rel = ''
                if lipsync_abs:
                    try:
                        lipsync_rel = str(Path(lipsync_abs).resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())).replace('\\', '/')
                    except Exception:
                        lipsync_rel = ''

                return {
                    'ai_audio_relpath': str(output_path.relative_to(Path(settings.MEDIA_ROOT))).replace('\\', '/'),
                    'ai_lipsync_relpath': lipsync_rel,
                }
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
        user_transcript_override: str = '',
        include_resume: bool = False,
        resume_context: str = '',
        candidate_name: str = '',
    ) -> PipelineOutput:
        if self._software_only_enabled():
            target_role = 'Software Engineer'
            interview_type = self._normalize_software_type(interview_type)

        start = time.perf_counter()

        whisper_start = time.perf_counter()
        stt_result = {'transcript': '', 'confidence': 1.0, 'decode_mode': '', 'language': ''}
        user_transcript = ''
        if not is_first_turn:
            override = str(user_transcript_override or '').strip()
            if override:
                user_transcript = override
            else:
                stt_result = self.transcribe(user_audio_path)
                user_transcript = str(stt_result.get('transcript', '') or '').strip()
        stt_confidence = float(stt_result.get('confidence', 0.0) or 0.0)
        whisper_ms = int((time.perf_counter() - whisper_start) * 1000)
        candidate_response_count = self._count_candidate_responses(history, user_transcript)

        llm_start = time.perf_counter()
        if is_first_turn and self._is_final_round(interview_type):
            llm = {
                'ai_question': self._build_final_round_opening_question(candidate_name),
                'ai_feedback': 'Begin warm and professional; evaluate intro clarity, relevance, and communication structure.',
                'retrieved_examples': [],
            }
        elif not is_first_turn and not user_transcript.strip():
            llm = {
                'ai_question': 'Why did you not answer? I could not catch your response. Please hold the speak button and answer again.',
                'ai_feedback': 'Speak a bit louder and keep holding the button until you finish.',
                'retrieved_examples': [],
            }
        elif not is_first_turn and user_transcript and stt_confidence < self._stt_min_confidence():
            llm = {
                'ai_question': (
                    'I may have misheard part of your answer. Please repeat that response clearly in one or two short sentences.'
                ),
                'ai_feedback': (
                    f"Low transcript confidence ({stt_confidence:.2f}). Keep mic close, reduce background noise, and hold the speak button until finished."
                ),
                'retrieved_examples': [],
            }
        elif self._is_final_round(interview_type) and candidate_response_count <= 2:
            llm = {
                'ai_question': self._build_final_round_intro_followup_question(
                    candidate_name=candidate_name,
                    user_transcript=user_transcript,
                    candidate_response_count=candidate_response_count,
                ),
                'ai_feedback': 'Probe intro claims with concrete role, decisions, and measurable outcomes before transitioning deeper.',
                'retrieved_examples': [],
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
                include_resume=include_resume,
                resume_context=resume_context,
                candidate_name=candidate_name,
            )
        llm_ms = int((time.perf_counter() - llm_start) * 1000)

        tts_start = time.perf_counter()
        ai_audio_abs = Path(settings.MEDIA_ROOT) / ai_audio_relpath
        tts_artifacts = self.synthesize(llm['ai_question'], ai_audio_abs)
        tts_ms = int((time.perf_counter() - tts_start) * 1000)

        total_ms = int((time.perf_counter() - start) * 1000)
        return PipelineOutput(
            user_transcript=user_transcript,
            ai_question=llm['ai_question'],
            ai_feedback=llm['ai_feedback'],
            ai_audio_relpath=ai_audio_relpath,
            ai_lipsync_relpath=str(tts_artifacts.get('ai_lipsync_relpath', '') or ''),
            processing_ms=total_ms,
            timings={
                'whisper_ms': whisper_ms,
                'llm_ms': llm_ms,
                'tts_ms': tts_ms,
                'total_ms': total_ms,
                'stt_confidence': round(stt_confidence, 3),
            },
            rag_context=llm.get('retrieved_examples', []),
        )
