"""TTS (Text-to-Speech) manager for generating audio from narration text."""

import base64
import logging
import os

import httpx

logger = logging.getLogger(__name__)


class TTSManagerError(Exception):
    """Raised when TTS API call fails."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"TTS API error ({status_code}): {message}")


class TTSManager:
    """Wraps the Dashscope TTS HTTP API for speech synthesis."""

    def __init__(self):
        self.api_base = os.getenv("TTS_API_BASE", "")
        self.api_key = os.getenv("TTS_API_KEY", "")
        self.model = os.getenv("TTS_MODEL", "qwen3-tts-flash")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_base and self.api_key)

    async def synthesize(self, text: str, voice: str = "Cherry") -> bytes:
        """Call TTS API to generate audio from text.

        Args:
            text: The text to synthesize into speech.
            voice: The voice name to use (e.g. "Cherry", "Serena").

        Returns:
            Raw audio bytes (mp3/wav).

        Raises:
            TTSManagerError: If the API call fails.
            RuntimeError: If TTS is not configured.
        """
        if not self.is_configured:
            raise RuntimeError("TTS manager not configured: missing TTS_API_BASE or TTS_API_KEY")

        payload = {
            "model": self.model,
            "input": {
                "text": text,
                "voice": voice,
            },
        }

        logger.info("[TTS] synthesizing: voice=%s, text_len=%d", voice, len(text))

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.api_base,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code != 200:
                error_msg = response.text[:500]
                logger.error("[TTS] API error: status=%d, body=%s", response.status_code, error_msg)
                raise TTSManagerError(response.status_code, error_msg)

            # The API returns audio data directly or wrapped in JSON
            content_type = response.headers.get("content-type", "")
            if "audio" in content_type:
                audio_bytes = response.content
            else:
                data = response.json()
                audio_info = (
                    data.get("output", {}).get("audio")
                    or data.get("audio")
                    or data.get("data", {}).get("audio")
                )

                if isinstance(audio_info, dict):
                    # DashScope non-streaming: audio is {"url": "...", "data": "", ...}
                    audio_url = audio_info.get("url", "")
                    if audio_url:
                        logger.info("[TTS] downloading audio from URL: %s", audio_url[:120])
                        dl_resp = await client.get(audio_url)
                        if dl_resp.status_code != 200:
                            raise TTSManagerError(
                                dl_resp.status_code,
                                f"Audio download failed: {dl_resp.text[:200]}",
                            )
                        audio_bytes = dl_resp.content
                        if not audio_bytes:
                            raise TTSManagerError(200, "Audio download returned empty content")
                    else:
                        audio_b64 = audio_info.get("data", "")
                        if not audio_b64:
                            raise TTSManagerError(200, "No audio data in response")
                        audio_bytes = base64.b64decode(audio_b64)
                else:
                    # Streaming or other format: treat as base64 string
                    if not audio_info:
                        raise TTSManagerError(200, "No audio data in response")
                    audio_bytes = base64.b64decode(audio_info)

        logger.info("[TTS] synthesized: %d bytes", len(audio_bytes))
        return audio_bytes
