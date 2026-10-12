"""Convert model-generated A2UI JSON to ADK Web's native renderer format."""

import json
import re
from typing import Any

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.inference_formats.direct_json import DirectJsonFormat


_A2UI_KEYS = {"beginRendering", "surfaceUpdate", "dataModelUpdate", "deleteSurface"}
_OPEN_TAG = "<a2a_datapart_json>"
_CLOSE_TAG = "</a2a_datapart_json>"
_CATALOG = DirectJsonFormat(
    version="0.8", catalogs=[BasicCatalog.get_config("0.8")]
).get_selected_catalog()


def _messages_from_text(text: str) -> list[dict[str, Any]]:
    """Extract one JSON array or a sequence of JSON objects from model text."""
    text = text.strip()
    if text.startswith("<a2ui-json>") and text.endswith("</a2ui-json>"):
        text = text[len("<a2ui-json>") : -len("</a2ui-json>")].strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()

    start = next((i for i, char in enumerate(text) if char in "[{"), None)
    if start is None:
        return []

    decoder = json.JSONDecoder()
    try:
        first, end = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return []

    if isinstance(first, list):
        values = first
    elif isinstance(first, dict):
        values = [first]
        remainder = text[start + end :].strip()
        while remainder:
            try:
                value, consumed = decoder.raw_decode(remainder)
            except json.JSONDecodeError:
                break
            if not isinstance(value, dict):
                break
            values.append(value)
            remainder = remainder[consumed:].strip()
    else:
        return []

    return [
        item
        for item in values
        if isinstance(item, dict) and _A2UI_KEYS.intersection(item)
    ]


def _wrap_for_adk_web(message: dict[str, Any]) -> types.Part:
    """Encode one A2UI message in the format consumed by ADK Web."""
    envelope = {
        "kind": "data",
        "metadata": {"mimeType": "application/json+a2ui"},
        "data": message,
    }
    data = _OPEN_TAG.encode() + json.dumps(envelope, separators=(",", ":")).encode() + _CLOSE_TAG.encode()
    return types.Part(inline_data=types.Blob(data=data, mime_type="text/plain"))


def a2ui_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse | None:
    """Replace A2UI JSON text with renderer-compatible inline data parts."""
    del callback_context
    if not llm_response.content or not llm_response.content.parts:
        return None

    for part in llm_response.content.parts:
        if not part.text:
            continue
        messages = _messages_from_text(part.text)
        if not messages:
            continue

        # A2UI v0.8's schema validator expects the complete ordered message list.
        # Invalid output falls back to the original model response for diagnosis.
        try:
            _CATALOG.validator.validate(messages)
        except Exception:
            return None

        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[_wrap_for_adk_web(message) for message in messages],
            ),
            custom_metadata={"a2a:response": "true"},
        )
    return None


def unwrap_adk_web_part(part: types.Part) -> list[dict[str, Any]]:
    """Recover A2UI messages from an ADK Web inline data part."""
    if not part.inline_data or not part.inline_data.data:
        return []
    raw = part.inline_data.data
    if isinstance(raw, str):
        raw = raw.encode()
    try:
        text = raw.decode("utf-8")
        start = text.index(_OPEN_TAG) + len(_OPEN_TAG)
        end = text.index(_CLOSE_TAG, start)
        envelope = json.loads(text[start:end])
        message = envelope.get("data")
        return [message] if isinstance(message, dict) and _A2UI_KEYS.intersection(message) else []
    except (UnicodeDecodeError, ValueError, KeyError, json.JSONDecodeError):
        return []
