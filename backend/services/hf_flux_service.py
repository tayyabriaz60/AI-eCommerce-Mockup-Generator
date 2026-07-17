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
from PIL import Image

from config import HF_API_TOKEN, HF_BILL_TO, HF_MODEL, HF_PROVIDER

logger = logging.getLogger("hf_flux_service")

# Kontext cold starts can take 15–30s; default client timeout is too short.
INFERENCE_TIMEOUT_SECONDS = 120.0


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
        client_kwargs = {
            "token": HF_API_TOKEN,
            "provider": HF_PROVIDER,
            "timeout": INFERENCE_TIMEOUT_SECONDS,
        }
        if HF_BILL_TO:
            client_kwargs["bill_to"] = HF_BILL_TO
        _client = InferenceClient(**client_kwargs)
    return _client


def generate_mockup_image(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    """Send the uploaded design + editing prompt to FLUX Kontext and return image bytes.

    Raises HfFluxGenerationError with a user-friendly message on any failure
    (rate limit, model loading, invalid input, etc.).
    """
    del mime_type  # normalized to PNG below regardless of upload type.

    png_bytes = _normalize_to_png(image_bytes)
    client = _get_client()

    try:
        result_image = _call_image_to_image(client, image_bytes=png_bytes, prompt=prompt)
    except HfFluxGenerationError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        logger.exception("Unexpected HF response shape from Inference Providers")
        raise HfFluxGenerationError(
            "The AI service returned an unexpected response. If you're on a free Hugging Face "
            "account, you may need Inference Provider credits — see huggingface.co/settings/billing."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - last resort catch for SDK/network issues
        logger.exception("Unexpected error calling Hugging Face Inference API")
        raise HfFluxGenerationError(
            "Something went wrong while generating your mockup. Please try again."
        ) from exc

    return _pil_image_to_bytes(result_image)


def _normalize_to_png(image_bytes: bytes) -> bytes:
    """Convert uploaded image bytes to PNG — fal/HF providers expect a standard raster format."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:
        raise HfFluxGenerationError(
            "The uploaded image could not be processed. Please try a different PNG or JPG."
        ) from exc


def _call_image_to_image(client: InferenceClient, image_bytes: bytes, prompt: str):
    """Call image_to_image once, with a single retry if the model is cold-starting."""
    try:
        # guidance_scale is NOT supported by the fal-ai Kontext endpoint via HF —
        # passing it causes provider validation errors.
        return client.image_to_image(
            image=image_bytes,
            prompt=prompt,
            model=HF_MODEL,
        )
    except HfHubHTTPError as exc:
        api_detail = _extract_api_error_detail(exc)
        logger.error(
            "HF image_to_image failed (status=%s): %s",
            getattr(getattr(exc, "response", None), "status_code", "?"),
            api_detail,
        )

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
                )
            except HfHubHTTPError as retry_exc:
                retry_detail = _extract_api_error_detail(retry_exc)
                logger.exception(
                    "HF image_to_image failed after model-loading retry: %s", retry_detail
                )
                raise HfFluxGenerationError(_friendly_http_error(retry_exc, retry_detail)) from retry_exc

        raise HfFluxGenerationError(_friendly_http_error(exc, api_detail)) from exc
    except InferenceTimeoutError as exc:
        logger.exception("HF inference timed out")
        raise HfFluxGenerationError(
            "The AI service took too long to respond (the model may still be warming up). "
            "Please try again in a moment."
        ) from exc


def _extract_api_error_detail(exc: HfHubHTTPError) -> str:
    """Pull the most useful error string from an HF/fal HTTP error response."""
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                for key in ("error", "detail", "message"):
                    if key in payload and payload[key]:
                        value = payload[key]
                        if isinstance(value, dict):
                            return str(value.get("message") or value.get("detail") or value)
                        return str(value)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        if response.text:
            return response.text[:300]

    return str(getattr(exc, "message", "") or exc)


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


def _friendly_http_error(exc: HfHubHTTPError, api_detail: str) -> str:
    message = api_detail or str(getattr(exc, "message", "") or exc)
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    upper = message.upper()

    if status_code == 402 or "CREDIT" in upper or "PAYMENT" in upper or "BILLING" in upper:
        return (
            "Hugging Face Inference credits are exhausted or billing is not set up. "
            "Free accounts get ~$0.10/month — FLUX mockups need more. Add a payment method "
            "or upgrade to PRO at huggingface.co/settings/billing, then try again."
        )
    if status_code == 429 or "RATE LIMIT" in upper:
        return "Hugging Face API rate limit exceeded. Please wait a moment and try again."
    if status_code in (401, 403) or "UNAUTHORIZED" in upper or "PERMISSION" in upper:
        return (
            "Server is not authorized to call Hugging Face Inference Providers. "
            "Check HF_API_TOKEN has 'Inference Providers' permission, accept the "
            "FLUX.1-Kontext-dev model license, and ensure billing is configured."
        )
    if status_code == 400 or isinstance(exc, BadRequestError) or "INVALID" in upper:
        return "The uploaded image or options were invalid. Please try a different image."
    if status_code == 503 or "LOADING" in upper:
        return (
            "The AI model is still starting up and wasn't ready in time. "
            "Please try again in about 30 seconds."
        )

    # Surface a short hint from the provider when we have one — helps debug without raw tracebacks.
    if api_detail and len(api_detail) < 200:
        return f"Mockup generation failed: {api_detail}"

    return "Mockup generation failed. Please try again with a different image or options."


def _pil_image_to_bytes(image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
