from __future__ import annotations

import io
import os
import wave
from pathlib import Path

DEFAULT_SAMPLE_RATE = 24000
DEFAULT_SAMPLE_WIDTH = 2
DEFAULT_CHANNELS = 1


def ensure_cloud_tts_client(project_id: str):
    try:
        import google.auth
        from google.cloud import texttospeech
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "google-cloud-texttospeech is not installed in this environment. "
            "Run: source .venv/bin/activate && pip install google-cloud-texttospeech"
        ) from exc

    quota_project_id = project_id.strip() or (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    if not quota_project_id:
        raise RuntimeError("GOOGLE_TTS_PROJECT_ID / --project-id must not be empty.")
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", quota_project_id)

    credentials, default_project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=quota_project_id,
    )
    client = texttospeech.TextToSpeechClient(credentials=credentials)
    return client, texttospeech, quota_project_id, default_project


def synthesize_cloud_tts_audio(
    client,
    texttospeech,
    *,
    model: str,
    voice_name: str,
    language_code: str,
    prompt: str,
    text: str,
) -> bytes:
    synthesis_input = texttospeech.SynthesisInput(
        text=text,
        prompt=prompt,
    )
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
        model_name=model,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=DEFAULT_SAMPLE_RATE,
    )
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    audio_content = getattr(response, "audio_content", b"")
    if not isinstance(audio_content, (bytes, bytearray)) or not audio_content:
        raise RuntimeError("Cloud TTS response did not contain audio bytes.")
    return bytes(audio_content)


def measure_wave_or_pcm_duration(audio_bytes: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> float:
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_in:
            frames = wav_in.getnframes()
            rate = wav_in.getframerate() or sample_rate
            return round(frames / float(rate), 3)
    except Exception:
        frame_count = len(audio_bytes) / (DEFAULT_CHANNELS * DEFAULT_SAMPLE_WIDTH)
        return round(frame_count / float(sample_rate), 3)


def write_wave_bytes(path: Path, audio_bytes: bytes, sample_rate: int = DEFAULT_SAMPLE_RATE) -> float:
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_in:
            path.write_bytes(audio_bytes)
            frames = wav_in.getnframes()
            rate = wav_in.getframerate() or sample_rate
            return round(frames / float(rate), 3)
    except Exception:
        with wave.open(str(path), "wb") as wav_out:
            wav_out.setnchannels(DEFAULT_CHANNELS)
            wav_out.setsampwidth(DEFAULT_SAMPLE_WIDTH)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(audio_bytes)
        return measure_wave_or_pcm_duration(audio_bytes, sample_rate=sample_rate)
