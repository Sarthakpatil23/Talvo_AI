import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel


app = FastAPI(title='Talvo Speech Worker', version='1.0.0')

_whisper_model = None
_tts_model = None


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

        segments, _ = _whisper_model.transcribe(tmp_path, beam_size=1, vad_filter=True)
        transcript = ' '.join((segment.text or '').strip() for segment in segments).strip()

        # Retry once without VAD when the first pass misses soft/short speech.
        if not transcript:
            retry_segments, _ = _whisper_model.transcribe(tmp_path, beam_size=5, vad_filter=False)
            transcript = ' '.join((segment.text or '').strip() for segment in retry_segments).strip()

        return {'transcript': transcript}
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
        return {'ok': True, 'output_path': str(output_path)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'TTS failed: {exc}') from exc
