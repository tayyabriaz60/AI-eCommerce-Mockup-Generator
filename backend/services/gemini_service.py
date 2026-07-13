"""
Wraps calls to Google's Gemini image-generation API (`google-genai` SDK).

Model name and generation config live here in one place so they're easy to
tweak/swap later without touching the router or prompt logic.
"""
import logging

from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("gemini_service")

# Response modalities requested from the model. We only need the image back,
# but keeping 'Text' allowed lets Gemini attach a short caption/refusal reason
# in `part.text` if it declines to generate an image, which is useful for
# building clearer error messages.
RESPONSE_MODALITIES = ["Text", "Image"]


class GeminiGenerationError(Exception):
    """Raised when Gemini fails to produce a usable mockup image."""


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise GeminiGenerationError(
                "Server is missing GEMINI_API_KEY configuration. Please set it in your environment."
            )
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate_mockup_image(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    """Send the uploaded design + prompt to Gemini and return the generated image bytes.

    Raises GeminiGenerationError with a user-friendly message on any failure
    (safety block, quota, invalid input, no image in response, etc.).
    """
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_modalities=RESPONSE_MODALITIES,
            ),
        )
    except ClientError as exc:
        logger.exception("Gemini client error during generation")
        raise GeminiGenerationError(_friendly_client_error(exc)) from exc
    except ServerError as exc:
        logger.exception("Gemini server error during generation")
        raise GeminiGenerationError(
            "The AI service is temporarily unavailable. Please try again in a moment."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - last resort catch for SDK/network issues
        logger.exception("Unexpected error calling Gemini")
        raise GeminiGenerationError(
            "Something went wrong while generating your mockup. Please try again."
        ) from exc

    return _extract_image_bytes(response)


def _extract_image_bytes(response) -> bytes:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        raise GeminiGenerationError(
            "Gemini did not return any content. Your image or prompt may have been blocked."
        )

    candidate = candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)

    parts = getattr(candidate.content, "parts", None) or []
    text_notes = []
    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data is not None and inline_data.data:
            return inline_data.data
        if getattr(part, "text", None):
            text_notes.append(part.text)

    # No image part found — build the clearest message we can.
    if finish_reason and "STOP" not in str(finish_reason).upper():
        raise GeminiGenerationError(
            f"Gemini couldn't generate an image (reason: {finish_reason}). "
            "This can happen if the content was flagged by safety filters. Try a different image or wording."
        )

    if text_notes:
        raise GeminiGenerationError(
            "Gemini responded without an image: " + " ".join(text_notes)[:300]
        )

    raise GeminiGenerationError("Gemini did not return an image. Please try again.")


def _friendly_client_error(exc: ClientError) -> str:
    message = str(getattr(exc, "message", "") or exc)
    status_code = getattr(exc, "code", None)

    if status_code == 429 or "RESOURCE_EXHAUSTED" in message.upper():
        return "Gemini API quota/rate limit exceeded. Please wait a moment and try again."
    if "SAFETY" in message.upper() or "BLOCKED" in message.upper():
        return "Your request was blocked by content safety filters. Please try a different image."
    if status_code == 400 or "INVALID_ARGUMENT" in message.upper():
        return "The uploaded image or options were invalid. Please try a different image."
    if status_code in (401, 403):
        return "Server is not authorized to call Gemini (check GEMINI_API_KEY)."

    return "Gemini image generation failed. Please try again with a different image or options."
