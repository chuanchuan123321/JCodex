"""Bounded HTTP(S) URL fetching for the model-facing read_url / web_fetch tools.

Fetches anonymously with no ambient credentials, follows only same-hostname
redirects (a redirect to another host is refused so each new host requires
its own tool call), enforces byte and character caps, classifies and decodes
text bodies, and returns a structured outcome for callers to format.

No API key or external service is required: this is a plain HTTP(S) client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from agent.tools.shell import decode_stream

#: Largest accepted request URL length (characters).
DEFAULT_MAX_URL_LENGTH = 2048
#: Largest response body accepted in bytes; the streamed read stops past this.
DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024
#: Largest decoded body returned in characters (truncated past this).
DEFAULT_MAX_BODY_CHARS = 100_000
#: Request timeout in seconds.
DEFAULT_TIMEOUT_S = 15.0
#: Maximum same-hostname redirect hops to follow.
DEFAULT_MAX_REDIRECTS = 5
#: Browser-like User-Agent; some sites refuse default client identifiers.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

_REDIRECT_STATUS = {301, 302, 303, 307, 308}
#: Charset labels requests defaults to when the server declares none; these
#: carry no real encoding information, so the body needs real detection.
_AMBIGUOUS_CHARSETS = {"iso-8859-1", "ascii"}


@dataclass
class FetchOutcome:
    """Structured outcome of one bounded fetch."""

    ok: bool
    text: str = ""
    status_code: Optional[int] = None
    final_url: str = ""
    kind: str = "text"  # 'html' when the body should be rendered from markup
    truncated: bool = False
    error: str = ""


def validate_fetch_url(
    raw: str, max_length: int = DEFAULT_MAX_URL_LENGTH
) -> Tuple[bool, str]:
    """Validate transport hygiene before any network access.

    Returns ``(True, normalized_url)`` or ``(False, error_message)``. Rejects
    non-http(s) schemes, embedded credentials, and over-long URLs.
    """
    if not raw:
        return False, "url 不能为空"
    if len(raw) > max_length:
        return False, f"URL 长度超过上限（{max_length} 字符）"
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False, "无效的 URL"
    if parsed.scheme not in {"http", "https"}:
        return False, f"不支持的协议 \"{parsed.scheme}\"（仅允许 http 和 https）"
    if parsed.username or parsed.password:
        return False, "URL 中不允许包含用户名密码"
    if not parsed.netloc:
        return False, "无效的 URL（缺少主机名）"
    return True, raw


def classify_content_type(content_type: Optional[str]) -> Optional[str]:
    """Classify a Content-Type into a decodable body kind, or None for binary.

    ``text/html`` and ``application/xhtml+xml`` are ``html``; other ``text/*``
    plus a few structured text types are ``text``; everything else (images,
    archives, downloads) is unsupported.
    """
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime in {"text/html", "application/xhtml+xml"}:
        return "html"
    if mime.startswith("text/"):
        return "text"
    if mime in {"application/json", "application/xml"} or mime.endswith("+json") or mime.endswith("+xml"):
        return "text"
    return None


def decode_body(raw: bytes, declared: Optional[str], max_chars: int) -> Tuple[str, bool]:
    """Decode a body with its declared charset, falling back to real detection.

    A declared charset that is absent or ambiguous (requests defaults
    ISO-8859-1 when the server declares none) is ignored in favor of a
    UTF-8 -> GBK -> Latin-1 detection chain, so GBK pages without a charset
    header still decode correctly. Unknown declared charsets also fall back.
    Returns ``(text, truncated)`` with the text capped at ``max_chars``.
    """
    if declared is not None and declared.lower() not in _AMBIGUOUS_CHARSETS:
        try:
            text = raw.decode(declared, errors="replace")
        except (LookupError, TypeError):
            text = decode_stream(raw)
    else:
        text = decode_stream(raw)
    truncated = len(text) > max_chars
    return text[:max_chars], truncated


def fetch_url(
    raw_url: str,
    timeout: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_chars: int = DEFAULT_MAX_BODY_CHARS,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    user_agent: str = DEFAULT_USER_AGENT,
) -> FetchOutcome:
    """Fetch one URL with bounded size, redirects, and decoding.

    Follows only same-hostname redirects up to ``max_redirects`` hops; a
    redirect to a different host is refused so the caller decides explicitly
    about each new origin. Response bodies are streamed and cut at
    ``max_bytes`` (a declared larger Content-Length is rejected outright) and
    decoded text is capped at ``max_chars``.
    """
    valid, error = validate_fetch_url(raw_url)
    if not valid:
        return FetchOutcome(ok=False, error=error)

    headers = {"User-Agent": user_agent}
    current = raw_url
    truncated = False
    for _hop in range(max_redirects + 1):
        try:
            response = requests.get(
                current,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
        except requests.exceptions.Timeout:
            return FetchOutcome(ok=False, error="请求超时")
        except requests.exceptions.RequestException as e:
            return FetchOutcome(ok=False, error=f"网络请求失败 - {e}")

        try:
            if response.status_code in _REDIRECT_STATUS:
                location = response.headers.get("Location")
                if not location:
                    return FetchOutcome(ok=False, error=f"重定向响应（HTTP {response.status_code}）缺少 Location 头")
                target = urljoin(current, location)
                valid_target, target_error = validate_fetch_url(target)
                if not valid_target:
                    return FetchOutcome(ok=False, error=target_error)
                if urlparse(target).hostname.lower() != urlparse(current).hostname.lower():
                    return FetchOutcome(
                        ok=False,
                        error=(
                            f"跨主机重定向被拒绝（{urlparse(current).hostname} → "
                            f"{urlparse(target).hostname}）；请直接访问目标 URL"
                        ),
                    )
                current = target
                continue

            if not response.ok:
                return FetchOutcome(
                    ok=False,
                    error=f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    final_url=current,
                )

            content_type = response.headers.get("Content-Type")
            kind = classify_content_type(content_type)
            if kind is None:
                return FetchOutcome(
                    ok=False,
                    error=f"不支持的内容类型 \"{content_type or '未知'}\"",
                    status_code=response.status_code,
                    final_url=current,
                )

            declared_length = response.headers.get("Content-Length")
            if declared_length is not None and declared_length.isdigit() and int(declared_length) > max_bytes:
                return FetchOutcome(
                    ok=False,
                    error=f"响应超过最大限制（{max_bytes} 字节）",
                    status_code=response.status_code,
                    final_url=current,
                )

            raw = b""
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                remaining = max_bytes - len(raw)
                if len(chunk) > remaining:
                    raw += chunk[:remaining]
                    truncated = True
                    break
                raw += chunk

            text, truncated_by_chars = decode_body(raw, response.encoding, max_chars)
            return FetchOutcome(
                ok=True,
                text=text,
                status_code=response.status_code,
                final_url=current,
                kind=kind,
                truncated=truncated or truncated_by_chars,
            )
        finally:
            response.close()
    return FetchOutcome(ok=False, error=f"重定向次数超过上限（{max_redirects} 次）")
