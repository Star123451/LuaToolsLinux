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
        # Handle both regular responses and HTTPError objects
        if hasattr(urllib_response, 'code'):
            self.status_code = urllib_response.code
        elif hasattr(urllib_response, 'getcode'):
            self.status_code = urllib_response.getcode()
        else:
            self.status_code = 200
        self.text = data.decode('utf-8', errors='replace')
    
    def json(self) -> Any:
        """Parse response body as JSON."""
        return _json.loads(self.text)
    
    def raise_for_status(self) -> None:
        """Raise an exception if status code indicates an error."""
        if self.status_code >= 400:
            # Get URL from response
            url = getattr(self._urllib_response, 'url', 
                         getattr(self._urllib_response, 'geturl', lambda: '')())
            # Already an error, just re-raise if it's an HTTPError
            if isinstance(self._urllib_response, urllib.error.HTTPError):
                raise self._urllib_response
            # Otherwise create a new HTTPError
            raise urllib.error.HTTPError(
                url if url else 'unknown',
                self.status_code,
                f"HTTP {self.status_code}",
                {},
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
        content: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> HTTPResponse:
        """Perform HTTP POST request."""
        # Support both data= and content= parameters (httpx uses content=)
        post_data = content if content is not None else data
        # Encode string to bytes if needed
        if isinstance(post_data, str):
            post_data = post_data.encode('utf-8')
        req = urllib.request.Request(
            url,
            data=post_data,
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
    
    def stream(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True
    ) -> 'HTTPStreamResponse':
        """Perform streaming HTTP request (returns context manager)."""
        return HTTPStreamResponse(
            method=method.upper(),
            url=url,
            headers=headers,
            timeout=timeout if timeout is not None else self.timeout
        )
    
    def close(self) -> None:
        """Close client (no-op for urllib, kept for API compatibility)."""
        pass


class HTTPStreamResponse:
    """Streaming HTTP response for large downloads."""
    
    def __init__(self, method: str, url: str, headers: Optional[Dict[str, str]], timeout: float):
        self.method = method
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self._response = None
        self.status_code = None
    
    def __enter__(self) -> 'HTTPStreamResponse':
        """Open the streaming connection."""
        req = urllib.request.Request(self.url, headers=self.headers, method=self.method)
        try:
            self._response = urllib.request.urlopen(req, timeout=self.timeout)
            self.status_code = self._response.getcode()
        except urllib.error.HTTPError as e:
            self._response = e
            self.status_code = e.code
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close the streaming connection."""
        if self._response:
            try:
                self._response.close()
            except Exception:
                pass
        return False
    
    def raise_for_status(self) -> None:
        """Raise an exception if status code indicates an error."""
        if self.status_code and self.status_code >= 400:
            if isinstance(self._response, urllib.error.HTTPError):
                raise self._response
            raise urllib.error.HTTPError(
                self.url,
                self.status_code,
                f"HTTP {self.status_code}",
                {},
                None
            )
    
    def iter_bytes(self, chunk_size: int = 8192):
        """Iterate over response body in chunks."""
        if not self._response:
            return
        while True:
            chunk = self._response.read(chunk_size)
            if not chunk:
                break
            yield chunk


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

