import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel


app = FastAPI(title='Talvo Speech Worker', version='1.0.0')

_whisper_model = None
_tts_model = None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score_transcript(transcript: str, avg_logprob: float, no_speech_prob: float) -> float:
    words = len((transcript or '').split())
    logprob_score = _clamp((avg_logprob + 2.0) / 2.0, 0.0, 1.0)
    length_score = _clamp(words / 12.0, 0.0, 1.0)
    speech_score = _clamp(1.0 - no_speech_prob, 0.0, 1.0)

    confidence = (0.55 * logprob_score) + (0.30 * length_score) + (0.15 * speech_score)
    if words < 3:
        confidence *= 0.7
    return round(_clamp(confidence, 0.0, 1.0), 3)


def _transcribe_candidate(tmp_path: str, *, beam_size: int, vad_filter: bool) -> Dict[str, object]:
    language = (os.getenv('STT_LANGUAGE', 'en') or 'en').strip()
    vad_parameters = {'min_silence_duration_ms': 450, 'speech_pad_ms': 320} if vad_filter else None
    no_speech_threshold = float(os.getenv('STT_NO_SPEECH_THRESHOLD', '0.85'))
    log_prob_threshold = float(os.getenv('STT_LOG_PROB_THRESHOLD', '-2.0'))
    compression_ratio_threshold = float(os.getenv('STT_COMPRESSION_RATIO_THRESHOLD', '2.8'))
    initial_prompt = (
        os.getenv(
            'STT_INITIAL_PROMPT',
            'This is a software engineering interview. Common words include API, microservices, latency, throughput, '
            'cache invalidation, Kubernetes, CI/CD, and PostgreSQL.'
        )
        or ''
    ).strip()

    segments, info = _whisper_model.transcribe(
        tmp_path,
        language=language,
        task='transcribe',
        beam_size=beam_size,
        best_of=max(beam_size, 5),
        vad_filter=vad_filter,
        vad_parameters=vad_parameters,
        condition_on_previous_text=False,
        temperature=[0.0, 0.1, 0.2],
        no_speech_threshold=no_speech_threshold,
        log_prob_threshold=log_prob_threshold,
        compression_ratio_threshold=compression_ratio_threshold,
        initial_prompt=initial_prompt,
    )

    texts: List[str] = []
    logprobs: List[float] = []
    no_speech_values: List[float] = []
    for segment in segments:
        part = (getattr(segment, 'text', '') or '').strip()
        if part:
            texts.append(part)
        logprobs.append(float(getattr(segment, 'avg_logprob', -2.0) or -2.0))
        no_speech_values.append(float(getattr(segment, 'no_speech_prob', 0.5) or 0.5))

    transcript = ' '.join(texts).strip()
    avg_logprob = (sum(logprobs) / len(logprobs)) if logprobs else -2.0
    no_speech_prob = (sum(no_speech_values) / len(no_speech_values)) if no_speech_values else 0.5
    confidence = _score_transcript(transcript, avg_logprob, no_speech_prob)

    return {
        'transcript': transcript,
        'confidence': confidence,
        'avg_logprob': round(avg_logprob, 3),
        'no_speech_prob': round(no_speech_prob, 3),
        'language': str(getattr(info, 'language', language) or language),
        'language_probability': round(float(getattr(info, 'language_probability', 0.0) or 0.0), 3),
        'beam_size': beam_size,
        'vad_filter': vad_filter,
    }


class TTSRequest(BaseModel):
    text: str
    output_path: str


def _configure_espeak() -> None:
    default_dir = Path('C:/Program Files/eSpeak NG')
    default_dll = default_dir / 'libespeak-ng.dll'
    default_data = default_dir / 'espeak-ng-data'

    if 'PHONEMIZER_ESPEAK_LIBRARY' not in os.environ and default_dll.exists():
        os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = str(default_dll)
    if 'ESPEAK_DATA_PATH' not in os.environ and default_data.exists():
        os.environ['ESPEAK_DATA_PATH'] = str(default_data)

    path_value = os.environ.get('PATH', '')
    if default_dir.exists() and str(default_dir) not in path_value:
        os.environ['PATH'] = f"{default_dir};{path_value}"


def _cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _load_whisper():
    from faster_whisper import WhisperModel

    model_size = os.getenv('WHISPER_MODEL_SIZE', 'base')
    device = 'cuda' if _cuda_available() else 'cpu'
    compute_type = 'float16' if device == 'cuda' else 'int8'
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _load_tts():
    from TTS.api import TTS

    model_name = os.getenv('COQUI_TTS_MODEL', 'tts_models/en/ljspeech/vits')
    use_gpu = os.getenv('TTS_USE_GPU', '0') in {'1', 'true', 'True'} and _cuda_available()
    return TTS(model_name=model_name, progress_bar=False, gpu=use_gpu)


def _find_rhubarb_binary() -> str:
    configured = (os.getenv('RHUBARB_BINARY', '') or '').strip()
    candidates = [configured] if configured else []
    candidates.extend(['rhubarb', 'rhubarb.exe'])

    for candidate in candidates:
        if not candidate:
            continue
        if Path(candidate).exists():
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return ''


def _generate_lipsync_json(audio_path: Path) -> Path | None:
    rhubarb_bin = _find_rhubarb_binary()
    if not rhubarb_bin:
        return None

    output_json = audio_path.with_suffix('.lipsync.json')
    timeout_seconds = int(os.getenv('RHUBARB_TIMEOUT_SECONDS', '20') or '20')

    cmd = [
        rhubarb_bin,
        '-f',
        'json',
        '-o',
        str(output_json),
        str(audio_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout_seconds)
        if output_json.exists():
            return output_json
    except Exception:
        return None

    return None


@app.on_event('startup')
def startup() -> None:
    global _whisper_model, _tts_model
    _configure_espeak()
    if _whisper_model is None:
        _whisper_model = _load_whisper()
    if _tts_model is None:
        _tts_model = _load_tts()


@app.get('/health')
def health():
    return {'ok': True, 'service': 'speech-worker'}


@app.post('/stt')
async def stt(audio: UploadFile = File(...)):
    global _whisper_model

    suffix = Path(audio.filename or 'audio.webm').suffix or '.webm'
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name

        primary_beam = int(os.getenv('STT_BEAM_PRIMARY', '8'))
        backup_beam = int(os.getenv('STT_BEAM_BACKUP', '12'))

        primary = _transcribe_candidate(tmp_path, beam_size=primary_beam, vad_filter=True)
        backup = _transcribe_candidate(tmp_path, beam_size=backup_beam, vad_filter=False)

        chosen = primary if float(primary['confidence']) >= float(backup['confidence']) else backup
        return {
            'transcript': str(chosen['transcript']),
            'confidence': float(chosen['confidence']),
            'language': str(chosen['language']),
            'language_probability': float(chosen['language_probability']),
            'avg_logprob': float(chosen['avg_logprob']),
            'no_speech_prob': float(chosen['no_speech_prob']),
            'decode_mode': f"beam={chosen['beam_size']},vad={chosen['vad_filter']}",
            'alternatives': [
                {
                    'decode_mode': f"beam={primary['beam_size']},vad={primary['vad_filter']}",
                    'confidence': float(primary['confidence']),
                    'transcript': str(primary['transcript']),
                },
                {
                    'decode_mode': f"beam={backup['beam_size']},vad={backup['vad_filter']}",
                    'confidence': float(backup['confidence']),
                    'transcript': str(backup['transcript']),
                },
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'STT failed: {exc}') from exc
    finally:
        if tmp_path and Path(tmp_path).exists():
            Path(tmp_path).unlink(missing_ok=True)


@app.post('/tts')
def tts(payload: TTSRequest):
    global _tts_model

    text = (payload.text or '').strip()
    output_path = Path(payload.output_path)
    if not text:
        raise HTTPException(status_code=400, detail='text is required')

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _tts_model.tts_to_file(text=text, file_path=str(output_path))
        lipsync_path = _generate_lipsync_json(output_path)
        return {
            'ok': True,
            'output_path': str(output_path),
            'lipsync_path': str(lipsync_path) if lipsync_path else '',
            'lipsync_enabled': bool(lipsync_path),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'TTS failed: {exc}') from exc
