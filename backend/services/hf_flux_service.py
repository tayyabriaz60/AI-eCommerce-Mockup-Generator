"""
Wraps Hugging Face Inference API calls for FLUX.1 Kontext image editing.

Model name and client config live here in one place so they're easy to tweak
without touching the router or prompt logic.
"""
import io
import json
import logging
import time

from huggingface_hub import InferenceClient
from huggingface_hub.errors import BadRequestError, HfHubHTTPError, InferenceTimeoutError

from config import HF_API_TOKEN, HF_MODEL

logger = logging.getLogger("hf_flux_service")

# Kontext cold starts can take 15–30s; default client timeout is too short.
INFERENCE_TIMEOUT_SECONDS = 120.0
# Sensible default for Kontext editing (matches diffusers examples).
DEFAULT_GUIDANCE_SCALE = 2.5


class HfFluxGenerationError(Exception):
    """Raised when FLUX/Kontext fails to produce a usable mockup image."""


_client: InferenceClient | None = None


def _get_client() -> InferenceClient:
    global _client
    if _client is None:
        if not HF_API_TOKEN:
            raise HfFluxGenerationError(
                "Server is missing HF_API_TOKEN configuration. Please set it in your environment."
            )
        _client = InferenceClient(token=HF_API_TOKEN, timeout=INFERENCE_TIMEOUT_SECONDS)
    return _client


def generate_mockup_image(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    """Send the uploaded design + editing prompt to FLUX Kontext and return image bytes.

    Raises HfFluxGenerationError with a user-friendly message on any failure
    (rate limit, model loading, invalid input, etc.).
    """
    del mime_type  # kept for interface compatibility; HF client accepts raw bytes directly.

    client = _get_client()

    try:
        result_image = _call_image_to_image(client, image_bytes=image_bytes, prompt=prompt)
    except HfFluxGenerationError:
        raise
    except Exception as exc:  # noqa: BLE001 - last resort catch for SDK/network issues
        logger.exception("Unexpected error calling Hugging Face Inference API")
        raise HfFluxGenerationError(
            "Something went wrong while generating your mockup. Please try again."
        ) from exc

    return _pil_image_to_bytes(result_image)


def _call_image_to_image(client: InferenceClient, image_bytes: bytes, prompt: str):
    """Call image_to_image once, with a single retry if the model is cold-starting."""
    try:
        return client.image_to_image(
            image=image_bytes,
            prompt=prompt,
            model=HF_MODEL,
            guidance_scale=DEFAULT_GUIDANCE_SCALE,
        )
    except HfHubHTTPError as exc:
        wait_seconds = _extract_estimated_wait(exc)
        if wait_seconds is not None:
            logger.info(
                "HF model loading (estimated %.1fs); waiting once before retry", wait_seconds
            )
            time.sleep(wait_seconds)
            try:
                return client.image_to_image(
                    image=image_bytes,
                    prompt=prompt,
                    model=HF_MODEL,
                    guidance_scale=DEFAULT_GUIDANCE_SCALE,
                )
            except HfHubHTTPError as retry_exc:
                logger.exception("HF image_to_image failed after model-loading retry")
                raise HfFluxGenerationError(_friendly_http_error(retry_exc)) from retry_exc

        logger.exception("HF image_to_image client error")
        raise HfFluxGenerationError(_friendly_http_error(exc)) from exc
    except InferenceTimeoutError as exc:
        logger.exception("HF inference timed out")
        raise HfFluxGenerationError(
            "The AI service took too long to respond (the model may still be warming up). "
            "Please try again in a moment."
        ) from exc


def _extract_estimated_wait(exc: HfHubHTTPError) -> float | None:
    """Return estimated wait seconds if the API says the model is loading."""
    response = getattr(exc, "response", None)
    if response is None:
        return None

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError, TypeError):
        payload = None

    if isinstance(payload, dict):
        estimated = payload.get("estimated_time")
        if estimated is not None:
            try:
                return max(1.0, float(estimated))
            except (TypeError, ValueError):
                pass

        error_text = str(payload.get("error", "")).lower()
        if "loading" in error_text:
            return 20.0

    status_code = getattr(response, "status_code", None)
    if status_code == 503:
        return 20.0

    if "loading" in str(exc).lower():
        return 20.0

    return None


def _friendly_http_error(exc: HfHubHTTPError) -> str:
    message = str(getattr(exc, "message", "") or exc)
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    upper = message.upper()

    if status_code == 429 or "RATE LIMIT" in upper:
        return "Hugging Face API rate limit exceeded. Please wait a moment and try again."
    if status_code in (401, 403) or "UNAUTHORIZED" in upper:
        return "Server is not authorized to call Hugging Face (check HF_API_TOKEN)."
    if status_code == 400 or isinstance(exc, BadRequestError) or "INVALID" in upper:
        return "The uploaded image or options were invalid. Please try a different image."
    if status_code == 503 or "LOADING" in upper:
        return (
            "The AI model is still starting up and wasn't ready in time. "
            "Please try again in about 30 seconds."
        )

    return "Mockup generation failed. Please try again with a different image or options."


def _pil_image_to_bytes(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
