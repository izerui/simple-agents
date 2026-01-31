#!/usr/bin/env python3
"""
Universal HTTP Request Client
Supports all HTTP methods with advanced features: auth, files, proxies, cookies, etc.
"""

import argparse
import json
import sys
from typing import Optional, Dict, Any, List
import urllib.request
import urllib.parse
import urllib.error
import os
import mimetypes
import ssl


class HTTPClient:
    """Universal HTTP client supporting all standard methods and advanced features."""

    def __init__(
        self,
        timeout: int = 300,  # 默认 5 分钟超时
        verify_ssl: bool = True,
        proxy: Optional[str] = None,
        user_agent: str = "Mozilla/5.0 (compatible; HTTPClient/1.0)"
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.proxy = proxy
        self.user_agent = user_agent

    def _create_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None
    ) -> urllib.request.Request:
        """Create a urllib Request object with custom method support."""
        req = urllib.request.Request(url, data=body, headers=headers or {}, method=method.upper())
        req.add_header('User-Agent', self.user_agent)
        return req

    def _add_auth_bearer(self, headers: Dict[str, str], token: str):
        """Add Bearer token authentication."""
        headers['Authorization'] = f'Bearer {token}'

    def _add_auth_basic(self, headers: Dict[str, str], username: str, password: str):
        """Add Basic authentication."""
        import base64
        credentials = f"{username}:{password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers['Authorization'] = f'Basic {encoded}'

    def _add_cookies(self, headers: Dict[str, str], cookies: Dict[str, str]):
        """Add cookies to request."""
        cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
        headers['Cookie'] = cookie_str

    def _build_multipart_body(
        self,
        data: Dict[str, Any],
        files: Dict[str, tuple]
    ) -> tuple[bytes, str]:
        """Build multipart/form-data body with boundary."""
        boundary = f'----WebKitFormBoundary{os.urandom(16).hex()}'

        body_parts = []

        # Add regular data fields
        for key, value in data.items():
            body_parts.append(
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'
                f'{value}\r\n'
            )

        # Add file fields
        for field_name, (filename, content, content_type) in files.items():
            body_parts.append(
                f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n'
            )
            body_parts.append(content)
            body_parts.append(b'\r\n')

        body_parts.append(f'--{boundary}--\r\n'.encode())

        body = b''.join([part.encode() if isinstance(part, str) else part for part in body_parts])
        content_type = f'multipart/form-data; boundary={boundary}'

        return body, content_type

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, tuple]] = None,
        auth_bearer: Optional[str] = None,
        auth_basic: Optional[tuple[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute HTTP request with full feature support.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
            url: Request URL
            headers: Custom headers dictionary
            params: Query parameters
            json_data: JSON body (automatically sets Content-Type: application/json)
            data: Form data or multipart data
            files: Files for upload: {field_name: (filename, content, content_type)}
            auth_bearer: Bearer token string
            auth_basic: (username, password) tuple for basic auth
            cookies: Cookie dictionary

        Returns:
            Dictionary with status, headers, body, cookies
        """
        # Build URL with query parameters
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}" if '?' not in url else f"{url}&{query_string}"

        # Prepare headers
        headers = headers.copy() if headers else {}

        # Add authentication
        if auth_bearer:
            self._add_auth_bearer(headers, auth_bearer)
        elif auth_basic:
            self._add_auth_basic(headers, auth_basic[0], auth_basic[1])

        # Add cookies
        if cookies:
            self._add_cookies(headers, cookies)

        # Prepare body
        body = None
        if json_data:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(json_data).encode('utf-8')
        elif files:
            body, content_type = self._build_multipart_body(data or {}, files)
            headers['Content-Type'] = content_type
        elif data:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body = urllib.parse.urlencode(data).encode('utf-8')

        # Create request
        req = self._create_request(method, url, headers, body)

        # Setup SSL context
        ssl_context = ssl.create_default_context()
        if not self.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        # Setup opener with SSL context and optional proxy
        if self.proxy:
            proxy_handler = urllib.request.ProxyHandler({'http': self.proxy, 'https': self.proxy})
            opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ssl_context))
        else:
            opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))

        # Execute request
        try:
            response = opener.open(req, timeout=self.timeout)
            status_code = response.status
            response_headers = dict(response.headers)
            response_body = response.read()
            response_cookies = self._extract_cookies(response_headers.get('Set-Cookie', ''))

            return {
                'status_code': status_code,
                'headers': response_headers,
                'body': response_body,
                'cookies': response_cookies,
                'success': True
            }

        except urllib.error.HTTPError as e:
            return {
                'status_code': e.code,
                'headers': dict(e.headers) if e.headers else {},
                'body': e.read() if hasattr(e, 'read') else str(e).encode(),
                'cookies': {},
                'success': False,
                'error': str(e)
            }
        except urllib.error.URLError as e:
            return {
                'status_code': None,
                'headers': {},
                'body': str(e).encode(),
                'cookies': {},
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            return {
                'status_code': None,
                'headers': {},
                'body': str(e).encode(),
                'cookies': {},
                'success': False,
                'error': str(e)
            }

    def _extract_cookies(self, set_cookie_header: str) -> Dict[str, str]:
        """Extract cookies from Set-Cookie header."""
        cookies = {}
        if not set_cookie_header:
            return cookies

        for part in set_cookie_header.split(','):
            if '=' in part.split(';')[0]:
                name, value = part.split(';')[0].strip().split('=', 1)
                cookies[name] = value

        return cookies


def format_response(response: Dict[str, Any], verbose: bool = False) -> str:
    """Format response for display."""
    output = []

    if verbose:
        output.append(f"Status: {response['status_code']}")

    # Try to parse JSON body
    try:
        body_json = json.loads(response['body'])
        body_str = json.dumps(body_json, indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
        try:
            body_str = response['body'].decode('utf-8', errors='replace')
        except (AttributeError, UnicodeDecodeError):
            body_str = str(response['body'])

    if response.get('success'):
        output.append(body_str)
    else:
        output.append(f"Error: {response.get('error', 'Unknown error')}")
        output.append(body_str)

    return '\n'.join(output)


def main():
    """CLI interface for HTTP client."""
    parser = argparse.ArgumentParser(
        description='Universal HTTP client with advanced features',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('method', help='HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)')
    parser.add_argument('url', help='Request URL')

    # Headers
    parser.add_argument('-H', '--header', action='append', dest='headers',
                       help='Add header (format: "Name: Value")')

    # Query parameters
    parser.add_argument('-q', '--query', action='append', dest='params',
                       help='Add query parameter (format: "key=value")')

    # Authentication
    parser.add_argument('-b', '--bearer', help='Bearer token for authentication')
    parser.add_argument('--basic', nargs=2, metavar=('USERNAME', 'PASSWORD'),
                       help='Basic authentication')

    # Body data
    parser.add_argument('-j', '--json', help='JSON body (string or @filename)')
    parser.add_argument('-d', '--data', action='append', dest='form_data',
                       help='Form data (format: "key=value")')

    # File upload
    parser.add_argument('-f', '--file', action='append', dest='files',
                       metavar='FIELDNAME=FILENAME',
                       help='Upload file (format: "fieldname=filename")')

    # Cookies
    parser.add_argument('-c', '--cookie', action='append', dest='cookies',
                       help='Add cookie (format: "key=value")')

    # Options
    parser.add_argument('-t', '--timeout', type=int, default=300, help='Request timeout (seconds, default: 5 minutes)')
    parser.add_argument('--no-ssl-verify', action='store_true', help='Disable SSL verification')
    parser.add_argument('--proxy', help='Proxy URL (e.g., http://proxy.example.com:8080)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-o', '--output', help='Save response body to file')

    args = parser.parse_args()

    # Parse headers
    headers = {}
    if args.headers:
        for h in args.headers:
            if ':' in h:
                name, value = h.split(':', 1)
                headers[name.strip()] = value.strip()

    # Parse query parameters
    params = {}
    if args.params:
        for p in args.params:
            if '=' in p:
                key, value = p.split('=', 1)
                params[key] = value

    # Parse form data
    form_data = {}
    if args.form_data:
        for d in args.form_data:
            if '=' in d:
                key, value = d.split('=', 1)
                form_data[key] = value

    # Parse cookies
    cookies = {}
    if args.cookies:
        for c in args.cookies:
            if '=' in c:
                key, value = c.split('=', 1)
                cookies[key] = value

    # Parse JSON body
    json_data = None
    if args.json:
        if args.json.startswith('@'):
            # Read from file
            filename = args.json[1:]
            with open(filename, 'r') as f:
                json_data = json.load(f)
        else:
            # Parse string
            json_data = json.loads(args.json)

    # Parse file uploads
    files = None
    if args.files:
        files = {}
        for f in args.files:
            if '=' in f:
                field_name, filename = f.split('=', 1)
                content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                with open(filename, 'rb') as file:
                    content = file.read()
                files[field_name] = (filename, content, content_type)

    # Create client and execute request
    client = HTTPClient(
        timeout=args.timeout,
        verify_ssl=not args.no_ssl_verify,
        proxy=args.proxy
    )

    response = client.request(
        method=args.method,
        url=args.url,
        headers=headers,
        params=params,
        json_data=json_data,
        data=form_data if form_data else None,
        files=files,
        auth_bearer=args.bearer,
        auth_basic=tuple(args.basic) if args.basic else None,
        cookies=cookies
    )

    # Output response
    output = format_response(response, args.verbose)

    if args.output:
        with open(args.output, 'wb') as f:
            if isinstance(response['body'], bytes):
                f.write(response['body'])
            else:
                f.write(str(response['body']).encode())
        print(f"Response saved to {args.output}")
    else:
        print(output)

    # Exit with appropriate code
    sys.exit(0 if response['success'] else 1)


if __name__ == '__main__':
    main()
