"""Recognise temporary failures (network drops, timeouts, provider overload) that deserve an automatic retry."""
import ssl

import httpx
from botocore.exceptions import ConnectionError as BotoConnectionError
from google.genai import errors as genai_errors

from app.services.llm import LLMUnavailable

TRANSIENT_TYPES = (ssl.SSLError, ConnectionError, TimeoutError, httpx.TransportError, BotoConnectionError,
                   genai_errors.ServerError, LLMUnavailable)


def is_transient(exc: BaseException) -> bool:
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, TRANSIENT_TYPES):
            return True
        if isinstance(exc, genai_errors.ClientError) and exc.code == 429:
            return True
        exc = exc.__cause__ or exc.__context__
    return False
