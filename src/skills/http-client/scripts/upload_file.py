#!/usr/bin/env python3
"""
Convenience script for file uploads via multipart/form-data POST requests.
"""

import argparse
import sys
import mimetypes
import os
from pathlib import Path

# Import the HTTPClient from http_request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http_request import HTTPClient


def upload_file(
    url: str,
    file_path: str,
    field_name: str = 'file',
    additional_data: dict = None,
    headers: dict = None,
    auth_bearer: str = None,
    auth_basic: tuple = None,
    timeout: int = 300,  # 默认 5 分钟超时
    verify_ssl: bool = True,
    proxy: str = None
) -> dict:
    """
    Upload a file via multipart/form-data POST.

    Args:
        url: Upload endpoint URL
        file_path: Path to file to upload
        field_name: Form field name for the file (default: 'file')
        additional_data: Additional form fields to include
        headers: Custom headers
        auth_bearer: Bearer token
        auth_basic: (username, password) tuple
        timeout: Request timeout in seconds
        verify_ssl: Verify SSL certificate
        proxy: Proxy URL

    Returns:
        Response dictionary
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read file content
    with open(file_path, 'rb') as f:
        content = f.read()

    # Detect content type
    content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

    # Prepare file upload
    files = {
        field_name: (os.path.basename(file_path), content, content_type)
    }

    # Create client and upload
    client = HTTPClient(timeout=timeout, verify_ssl=verify_ssl, proxy=proxy)

    return client.request(
        method='POST',
        url=url,
        headers=headers,
        data=additional_data or {},
        files=files,
        auth_bearer=auth_bearer,
        auth_basic=auth_basic
    )


def main():
    """CLI for file upload."""
    parser = argparse.ArgumentParser(
        description='Upload files via HTTP multipart/form-data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('url', help='Upload endpoint URL')
    parser.add_argument('file', help='File to upload')

    parser.add_argument('-n', '--field-name', default='file',
                       help='Form field name for file (default: file)')
    parser.add_argument('-d', '--data', action='append', dest='form_data',
                       help='Additional form data (format: "key=value")')
    parser.add_argument('-H', '--header', action='append', dest='headers',
                       help='Add header (format: "Name: Value")')
    parser.add_argument('-b', '--bearer', help='Bearer token')
    parser.add_argument('--basic', nargs=2, metavar=('USERNAME', 'PASSWORD'),
                       help='Basic authentication')
    parser.add_argument('-t', '--timeout', type=int, default=300, help='Request timeout (seconds, default: 5 minutes)')
    parser.add_argument('--no-ssl-verify', action='store_true')
    parser.add_argument('--proxy', help='Proxy URL')
    parser.add_argument('-v', '--verbose', action='store_true')

    args = parser.parse_args()

    # Parse additional data
    additional_data = {}
    if args.form_data:
        for d in args.form_data:
            if '=' in d:
                key, value = d.split('=', 1)
                additional_data[key] = value

    # Parse headers
    headers = {}
    if args.headers:
        for h in args.headers:
            if ':' in h:
                name, value = h.split(':', 1)
                headers[name.strip()] = value.strip()

    try:
        response = upload_file(
            url=args.url,
            file_path=args.file,
            field_name=args.field_name,
            additional_data=additional_data,
            headers=headers,
            auth_bearer=args.bearer,
            auth_basic=tuple(args.basic) if args.basic else None,
            timeout=args.timeout,
            verify_ssl=not args.no_ssl_verify,
            proxy=args.proxy
        )

        if args.verbose:
            print(f"Status: {response['status_code']}")
            print(f"Headers: {response['headers']}")

        print(response['body'].decode('utf-8', errors='replace'))

        sys.exit(0 if response['success'] else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
