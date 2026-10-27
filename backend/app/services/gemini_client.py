"""Shared Gemini client.

FORCE_IPV4: on some networks the IPv6 route to Google drops most TLS connections (measured here: 7/10 failed
over IPv6, 10/10 succeeded over IPv4). Binding the HTTP client to an IPv4 local address avoids that.
"""
import httpx
from google import genai
from google.genai import types

from app.core.config import get_settings


def make_client(timeout_ms: int) -> genai.Client:
    s = get_settings()
    options = {"timeout": timeout_ms}
    if s.gemini_force_ipv4:
        options["httpx_client"] = httpx.Client(
            transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=2),
            timeout=timeout_ms / 1000,
        )
    return genai.Client(api_key=s.gemini_api_key, http_options=types.HttpOptions(**options))
