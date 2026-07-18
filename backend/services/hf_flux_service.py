"""
Wraps the public Hugging Face ZeroGPU Space for FLUX.1 Kontext image editing.

Uses gradio_client to call the community Space (HF_MODEL / default
"black-forest-labs/FLUX.1-Kontext-dev") — free shared compute, no Inference
Providers billing. Slower and less reliable than a paid API.

Space API (verified via client.view_api() — re-logged on first client init):
  api_name="/infer"
  predict(input_image, prompt, seed, randomize_seed, guidance_scale, steps)
    -> (result_image, seed)

If the Space interface changes, adjust SPACE_API_NAME and _INFER_PARAM_* below,
or inspect startup logs for the view_api() dump.
"""
from __future__ import annotations

import io
import logging
import tempfile
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path

import httpx
from gradio_client import Client
from gradio_client.exceptions import AppError
from gradio_client.utils import QueueError, TooManyRequestsError, handle_file
from huggingface_hub.utils import RepositoryNotFoundError
from PIL import Image

from config import HF_API_TOKEN, HF_MODEL, HF_SPACE_TIMEOUT_SECONDS

logger = logging.getLogger("hf_flux_service")

# --- Space endpoint tuning (change here if the Space UI/API is updated) ---
SPACE_API_NAME = "/infer"
_INFER_PARAM_GUIDANCE_SCALE = 2.5
_INFER_PARAM_STEPS = 28
_INFER_PARAM_SEED = 0
_INFER_PARAM_RANDOMIZE_SEED = True

MSG_SPACE_BUSY = "The free AI model is busy right now, please try again in a minute."
MSG_SPACE_UNAVAILABLE = (
    "The mockup generator is temporarily unavailable, please try again shortly."
)
MSG_UNEXPECTED_RESPONSE = "Something went wrong generating your mockup."
MSG_BAD_UPLOAD = (
    "The uploaded image could not be processed. Please try a different PNG or JPG."
)


class HfFluxGenerationError(Exception):
    """Raised when FLUX/Kontext fails to produce a usable mockup image."""


_client: Client | None = None
_api_logged = False


def _log_space_api(client: Client) -> None:
    """Log the Space's Gradio API shape once so mismatches are easy to debug."""
    global _api_logged
    if _api_logged:
        return
    try:
        client.view_api(all_endpoints=True, print_info=False)
        api_info = client.view_api(return_format="dict", print_info=False)
        logger.info(
            "HF ZeroGPU Space %s API endpoints: %s",
            HF_MODEL,
            list(api_info.get("named_endpoints", {}).keys()),
        )
        infer = api_info.get("named_endpoints", {}).get(SPACE_API_NAME)
        if infer:
            param_names = [p.get("parameter_name") for p in infer.get("parameters", [])]
            logger.info(
                "Expected %s params: %s (adjust hf_flux_service.py if these differ)",
                SPACE_API_NAME,
                param_names,
            )
        else:
            logger.warning(
                "Space API endpoint %s not found — check view_api() output above and "
                "update SPACE_API_NAME in hf_flux_service.py",
                SPACE_API_NAME,
            )
    except Exception:
        logger.exception("Could not introspect HF Space API via view_api()")
    _api_logged = True


def _get_client() -> Client:
    global _client
    if _client is None:
        client_kwargs: dict = {
            "verbose": False,
            "httpx_kwargs": {
                "timeout": httpx.Timeout(
                    connect=30.0,
                    read=60.0,
                    write=60.0,
                    pool=30.0,
                )
            },
        }
        if HF_API_TOKEN:
            # gradio_client parameter is `token` (HF user access token).
            client_kwargs["token"] = HF_API_TOKEN

        try:
            _client = Client(HF_MODEL, **client_kwargs)
        except RepositoryNotFoundError as exc:
            logger.exception("HF Space not found: %s", HF_MODEL)
            raise HfFluxGenerationError(MSG_SPACE_UNAVAILABLE) from exc
        except (httpx.ConnectError, httpx.NetworkError, OSError) as exc:
            logger.exception("Could not connect to HF Space: %s", HF_MODEL)
            raise HfFluxGenerationError(MSG_SPACE_UNAVAILABLE) from exc
        except Exception as exc:
            logger.exception("Failed to initialize gradio_client for %s", HF_MODEL)
            raise HfFluxGenerationError(MSG_SPACE_UNAVAILABLE) from exc

        _log_space_api(_client)
    return _client


def generate_mockup_image(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    """Send the uploaded design + editing prompt to FLUX Kontext and return PNG bytes."""
    del mime_type  # normalized to PNG below regardless of upload type.

    png_bytes = _normalize_to_png(image_bytes)

    try:
        result = _call_space_infer(png_bytes=png_bytes, prompt=prompt)
        return _extract_image_bytes(result)
    except HfFluxGenerationError:
        raise
    except Exception as exc:
        friendly = _friendly_error(exc)
        if friendly:
            raise HfFluxGenerationError(friendly) from exc
        logger.exception("Unexpected error calling HF ZeroGPU Space")
        raise HfFluxGenerationError(MSG_UNEXPECTED_RESPONSE) from exc


def _normalize_to_png(image_bytes: bytes) -> bytes:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:
        raise HfFluxGenerationError(MSG_BAD_UPLOAD) from exc


def _call_space_infer(png_bytes: bytes, prompt: str):
    """Call the Space /infer endpoint with a timeout for queue + generation."""
    client = _get_client()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes)
        tmp_path = tmp.name

    try:
        job = client.submit(
            handle_file(tmp_path),
            prompt,
            _INFER_PARAM_SEED,
            _INFER_PARAM_RANDOMIZE_SEED,
            _INFER_PARAM_GUIDANCE_SCALE,
            _INFER_PARAM_STEPS,
            api_name=SPACE_API_NAME,
        )
        return job.result(timeout=HF_SPACE_TIMEOUT_SECONDS)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _extract_image_bytes(result) -> bytes:
    """Parse gradio_client output into raw PNG/JPEG bytes."""
    image_payload = _unwrap_image_payload(result)

    if isinstance(image_payload, (bytes, bytearray)):
        return bytes(image_payload)

    if isinstance(image_payload, str):
        path = Path(image_payload)
        if path.is_file():
            return path.read_bytes()
        if image_payload.startswith(("http://", "https://")):
            return _download_image_url(image_payload)

    if isinstance(image_payload, dict):
        local_path = image_payload.get("path")
        if local_path:
            path = Path(local_path)
            if path.is_file():
                return path.read_bytes()
        remote_url = image_payload.get("url")
        if remote_url:
            return _download_image_url(str(remote_url))

    logger.error("Unexpected HF Space response shape: %r", result)
    raise HfFluxGenerationError(MSG_UNEXPECTED_RESPONSE)


def _unwrap_image_payload(result):
    """The /infer endpoint returns (image, seed); take the image component."""
    if isinstance(result, (list, tuple)) and result:
        return result[0]
    return result


def _download_image_url(url: str) -> bytes:
    try:
        response = httpx.get(url, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
        return response.content
    except Exception:
        logger.exception("Failed to download generated image from %s", url)
        raise HfFluxGenerationError(MSG_UNEXPECTED_RESPONSE)


def _friendly_error(exc: Exception) -> str | None:
    """Map gradio/network exceptions to user-facing messages."""
    if isinstance(exc, (QueueError, TooManyRequestsError)):
        return MSG_SPACE_BUSY

    if isinstance(exc, (TimeoutError, FuturesTimeoutError)):
        return MSG_SPACE_BUSY

    if isinstance(exc, httpx.TimeoutException):
        return MSG_SPACE_BUSY

    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError, ConnectionError, OSError)):
        return MSG_SPACE_UNAVAILABLE

    if isinstance(exc, AppError):
        message = str(exc).lower()
        if any(word in message for word in ("queue", "busy", "rate", "wait", "full")):
            return MSG_SPACE_BUSY
        if any(word in message for word in ("unavailable", "down", "error", "failed")):
            return MSG_SPACE_UNAVAILABLE

    if isinstance(exc, RepositoryNotFoundError):
        return MSG_SPACE_UNAVAILABLE

    return None
