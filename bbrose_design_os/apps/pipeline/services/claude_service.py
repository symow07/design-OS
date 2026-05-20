import anthropic
from django.conf import settings

from apps.pipeline.services.pipeline_errors import retry_on_exception

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=30.0)

MODEL = "claude-opus-4-7"


@retry_on_exception(max_retries=2, delay=5)
def call_claude(system_prompt, user_message, tools=None, max_tokens=4096):
    """
    Base Claude API call used by all agents.
    Returns the full response object.

    The system prompt is sent as a cached block — it is the stable prefix
    shared across repeated agent calls, so caching it cuts cost/latency on
    every call after the first within the 5-minute window.
    """
    kwargs = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_message}],
    }
    if tools:
        kwargs["tools"] = tools

    response = client.messages.create(**kwargs)
    return response


def extract_text(response):
    """Extract plain text from Claude response."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def extract_tool_use(response):
    """Extract tool use calls from Claude response."""
    calls = []
    for block in response.content:
        if block.type == "tool_use":
            calls.append({"name": block.name, "input": block.input})
    return calls


if __name__ == "__main__":
    response = call_claude(
        system_prompt="You are a helpful assistant.",
        user_message="Say hello in one sentence.",
    )
    print(extract_text(response))
