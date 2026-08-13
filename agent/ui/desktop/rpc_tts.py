"""JCodex desktop UI - text-to-speech RPC."""

import base64
import contextlib
import os
import subprocess
import tempfile
import time
from pathlib import Path

import eel

from agent.ui.desktop import constants


def _trim_tts_silence(mp3_bytes: bytes, max_pause: float = 0.3) -> bytes:
    """Cap interior silences in edge-tts audio so sentence pauses stay short."""
    if not mp3_bytes:
        return mp3_bytes
    source_path = ""
    output_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as source:
            source.write(mp3_bytes)
            source_path = source.name
        output_path = f"{source_path}.trim.mp3"
        result = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                source_path,
                "-af",
                (
                    "silenceremove=start_periods=0:stop_periods=-1:"
                    f"stop_duration={max_pause:.2f}:stop_threshold=-40dB"
                ),
                "-c:a",
                "libmp3lame",
                "-q:a",
                "5",
                output_path,
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0 or not Path(output_path).is_file():
            return mp3_bytes
        trimmed = Path(output_path).read_bytes()
        return trimmed or mp3_bytes
    except Exception:
        return mp3_bytes
    finally:
        try:
            if source_path:
                os.unlink(source_path)
        except OSError:
            pass
        try:
            if output_path:
                os.unlink(output_path)
        except OSError:
            pass


def _edge_tts_speech_sync(text: str, voice: str) -> bytes:
    """Synthesize speech with Microsoft Edge neural voices on a fresh loop."""
    import asyncio

    import edge_tts

    async def _speak() -> bytes:
        communicate = edge_tts.Communicate(text, voice)
        audio = bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                audio.extend(chunk.get("data") or b"")
        return bytes(audio)

    last_error = None
    for attempt in range(2):
        loop = asyncio.new_event_loop()
        try:
            audio = loop.run_until_complete(_speak())
            if audio:
                return _trim_tts_silence(audio)
            last_error = RuntimeError("edge-tts 未返回音频")
        except Exception as exc:
            last_error = exc
        finally:
            with contextlib.suppress(Exception):
                loop.close()
        if attempt == 0:
            time.sleep(1.2)
    if last_error is not None:
        raise last_error
    return b""


@eel.expose
def voice_tts_speak(text: str, voice: str = "zh-CN-XiaoxiaoNeural"):
    """Synthesize speech for voice mode and return base64 MP3 audio.

    The frontend plays the returned audio directly; on any failure it falls
    back to the system speech synthesizer, so a missing package or network
    outage never blocks voice mode.
    """
    try:
        audio = _edge_tts_speech_sync(
            str(text or "").strip()[: constants._EDGE_TTS_TEXT_LIMIT],
            str(voice or "zh-CN-XiaoxiaoNeural").strip(),
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}
    if not audio:
        return {"success": False, "error": "edge-tts 未返回音频"}
    return {
        "success": True,
        "audio_base64": base64.b64encode(audio).decode("ascii"),
    }


__all__ = ["_edge_tts_speech_sync", "_trim_tts_silence", "voice_tts_speak"]
