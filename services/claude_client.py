"""Claude API wrapper for generating recruiter content.

Uses Claude Haiku for cheap, fast text generation (~$0.25/M input tokens).
Primarily used for personalised call openers and LinkedIn messages.
"""

import anthropic
import config

# Use Haiku for cost efficiency — short outputs, high volume
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 256


def _get_client() -> anthropic.Anthropic:
    """Return an Anthropic client, raising if no API key."""
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set in .env. "
            "Get your key at https://console.anthropic.com/"
        )
    return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)


def generate_text(system_prompt: str, user_prompt: str, max_tokens: int = MAX_TOKENS) -> str:
    """Generate text via Claude API.

    Args:
        system_prompt: System instructions for Claude.
        user_prompt: The user message / content to process.
        max_tokens: Max output tokens.

    Returns:
        Generated text string, or empty string on failure.
    """
    client = _get_client()

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text.strip()
    except anthropic.APIError as e:
        print(f"  Claude API error: {e}")
        return ""
