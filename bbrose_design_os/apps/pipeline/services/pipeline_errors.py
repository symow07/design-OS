import json
import logging
import re
import time
from functools import wraps

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Base exception for pipeline failures."""
    pass


class AgentParseError(PipelineError):
    """Claude returned unparseable JSON."""
    pass


class ImageGenerationError(PipelineError):
    """OpenAI image generation failed."""
    pass


def retry_on_exception(max_retries=2, delay=5, exceptions=(Exception,)):
    """
    Decorator: retry a function up to max_retries times on given exceptions.
    Used for external API calls (Claude, OpenAI, Pacdora).
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        logger.warning(
                            f'{fn.__name__} attempt {attempt+1} failed: {e}. '
                            f'Retrying in {delay}s.'
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f'{fn.__name__} failed after {max_retries+1} attempts: {e}'
                        )
            raise last_exc
        return wrapper
    return decorator


def safe_json_parse(text, agent_name, log_fn=None):
    """
    Parse JSON from Claude response. Strips markdown fences if present.
    Raises AgentParseError with the raw text attached for debugging.
    """
    cleaned = re.sub(r'^```(?:json)?\n?', '', text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```$', '', cleaned.strip(), flags=re.MULTILINE)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        msg = f'{agent_name}: JSON parse failed — {e}'
        if log_fn:
            log_fn(msg, {'raw_response': text[:500]})
        raise AgentParseError(msg) from e
