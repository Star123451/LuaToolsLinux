"""Shared HTTP client management for the LuaTools backend."""

import json as _json
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

from config import HTTP_TIMEOUT_SECONDS
from logger import logger


class HTTPResponse:
    """Simple HTTP response wrapper that mimics httpx.Response interface."""
    
    def __init__(self, urllib_response: Any, data: bytes):
        self._urllib_response = urllib_response
        self._data = data
        self.status_code = urllib_response.getcode()
        self.text = data.decode('utf-8', errors='replace')
    
    def json(self) -> Any:
        """Parse response body as JSON."""
        return _json.loads(self.text)
    
    def raise_for_status(self) -> None:
        """Raise an exception if status code indicates an error."""
        if self.status_code >= 400:
            raise urllib.error.HTTPError(
                self._urllib_response.url,
                self.status_code,
                f"HTTP {self.status_code}",
                self._urllib_response.headers,
                None
            )


class HTTPClient:
    """Simple HTTP client using urllib that mimics httpx.Client interface."""
    
    def __init__(self, timeout: float = HTTP_TIMEOUT_SECONDS):
        self.timeout = timeout
    
    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True
    ) -> HTTPResponse:
        """Perform HTTP GET request."""
        req = urllib.request.Request(url, headers=headers or {})
        timeout_val = timeout if timeout is not None else self.timeout
        
        try:
            response = urllib.request.urlopen(req, timeout=timeout_val)
            data = response.read()
            return HTTPResponse(response, data)
        except urllib.error.HTTPError as e:
            # Read error response body if available
            data = e.read() if hasattr(e, 'read') else b''
            return HTTPResponse(e, data)
    
    def post(
        self,
        url: str,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> HTTPResponse:
        """Perform HTTP POST request."""
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers or {},
            method='POST'
        )
        timeout_val = timeout if timeout is not None else self.timeout
        
        try:
            response = urllib.request.urlopen(req, timeout=timeout_val)
            resp_data = response.read()
            return HTTPResponse(response, resp_data)
        except urllib.error.HTTPError as e:
            # Read error response body if available
            resp_data = e.read() if hasattr(e, 'read') else b''
            return HTTPResponse(e, resp_data)
    
    def close(self) -> None:
        """Close client (no-op for urllib, kept for API compatibility)."""
        pass


_HTTP_CLIENT: Optional[HTTPClient] = None


def ensure_http_client(context: str = "") -> HTTPClient:
    """Create the shared HTTP client if needed and return it."""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        prefix = f"{context}: " if context else ""
        logger.log(f"{prefix}Initializing shared HTTP client...")
        try:
            _HTTP_CLIENT = HTTPClient(timeout=HTTP_TIMEOUT_SECONDS)
            logger.log(f"{prefix}HTTP client initialized")
        except Exception as exc:
            logger.error(f"{prefix}Failed to initialize HTTP client: {exc}")
            raise
    return _HTTP_CLIENT


def get_http_client() -> HTTPClient:
    """Return the shared HTTP client, creating it if necessary."""
    return ensure_http_client()


def close_http_client(context: str = "") -> None:
    """Close and dispose of the shared HTTP client."""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        return

    try:
        _HTTP_CLIENT.close()
    except Exception:
        pass
    finally:
        _HTTP_CLIENT = None
        prefix = f"{context}: " if context else ""
        logger.log(f"{prefix}HTTP client closed")

