"""Thin wrapper around the Anthropic SDK for Claude API calls."""

import json
import anthropic
from config.settings import settings


_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def chat(
    system: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.0,
) -> str:
    """Send a single-turn message to Claude and return the text response."""
    client = get_client()
    response = client.messages.create(
        model=model or settings.claude_model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def chat_json(
    system: str,
    user_message: str,
    model: str | None = None,
    max_tokens: int = 4096,
) -> dict:
    """Send a message and parse the JSON response."""
    text = chat(system, user_message, model=model, max_tokens=max_tokens)
    # Extract JSON from the response (handle markdown code blocks)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())
