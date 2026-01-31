#!/usr/bin/env python3
"""
Convert documents to Markdown using the document conversion API.
Supports PDF, DOCX, XLSX, PPTX, PNG, JPG, JPEG, GIF, BMP, AsciiDoc formats.
"""

import argparse
import sys
import os
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install it with: pip install requests", file=sys.stderr)
    sys.exit(1)


def convert_to_markdown(
    file_path: str,
    output_path: str = None,
    guess_image: bool = False,
    guess_formula: bool = False,
    api_base_url: str = "https://dcca.hhstu.edu.cn/transfer"
) -> bool:
    """
    Convert a document to Markdown.

    Args:
        file_path: Path to the document (PDF, DOCX, XLSX, PPTX, images, etc.)
        output_path: Where to save the Markdown file (default: same as input with .md extension)
        guess_image: Use AI model to recognize image content (slower but more accurate)
        guess_formula: Use AI model to recognize math formulas (slower but more accurate)
        api_base_url: Base URL of the conversion API

    Returns:
        True if conversion succeeded, False otherwise
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return False

    # Determine output path
    if output_path is None:
        output_path = str(Path(file_path).with_suffix('.md'))

    # Calculate timeout (longer for AI features)
    # 基础超时: 5分钟, AI功能: 10分钟
    timeout = 600 if (guess_image or guess_formula) else 300

    ai_features = []
    if guess_image:
        ai_features.append("image recognition")
    if guess_formula:
        ai_features.append("formula recognition")

    ai_note = f" (with AI {', '.join(ai_features)})" if ai_features else ""
    print(f"Converting {file_path} to Markdown{ai_note}...")

    try:
        # Prepare and send request
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            data = {
                'guess_image': 'true' if guess_image else 'false',
                'guess_formula': 'true' if guess_formula else 'false'
            }
            response = requests.post(
                f"{api_base_url}/api/to-markdown",
                files=files,
                data=data,
                timeout=timeout,
                verify=False  # 跳过 SSL 证书验证(沙箱环境证书路径问题)
            )

        # Check response
        response.raise_for_status()

        # Verify content type - reject HTML responses (likely login/error pages)
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' in content_type.lower():
            print(f"✗ Conversion failed: Received HTML instead of Markdown", file=sys.stderr)
            print(f"  This usually means the API redirected to a login page or error page.", file=sys.stderr)
            # Print first 200 chars of response for debugging
            preview = response.text[:200] if response.text else ''
            if '<html' in preview.lower() or '<!doctype' in preview.lower():
                print(f"  Response preview: {preview}", file=sys.stderr)
            return False

        # Save Markdown content
        with open(output_path, 'wb') as f:
            f.write(response.content)

        print(f"✓ Successfully converted to: {output_path}")
        return True

    except requests.exceptions.HTTPError as e:
        print(f"✗ Conversion failed: HTTP {e.response.status_code}", file=sys.stderr)
        try:
            print(f"  Details: {e.response.text}", file=sys.stderr)
        except:
            pass
        return False
    except requests.exceptions.Timeout:
        print(f"✗ Conversion failed: Request timeout", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Conversion failed: {str(e)}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ Conversion failed: {str(e)}", file=sys.stderr)
        return False


def main():
    """CLI interface for Markdown conversion."""
    parser = argparse.ArgumentParser(
        description='Convert documents to Markdown using document conversion API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Convert a document
  python scripts/convert_to_markdown.py document.pdf

  # Convert with custom output path
  python scripts/convert_to_markdown.py document.docx -o output.md

  # Convert with AI image recognition (slower but more accurate)
  python scripts/convert_to_markdown.py document.pdf --guess-image

  # Convert with AI formula recognition
  python scripts/convert_to_markdown.py document.docx --guess-formula

  # Convert with both AI features
  python scripts/convert_to_markdown.py document.pdf --guess-image --guess-formula

  # Convert multiple documents
  python scripts/convert_to_markdown.py *.pdf

Supported formats:
  - Documents: PDF, DOCX, XLSX, PPTX, AsciiDoc
  - Images: PNG, JPG, JPEG, GIF, BMP
        '''
    )

    parser.add_argument('file', help='Document file to convert')
    parser.add_argument('-o', '--output', help='Output Markdown file path')
    parser.add_argument('--guess-image', action='store_true',
                       help='Use AI model for image recognition (slower but more accurate)')
    parser.add_argument('--guess-formula', action='store_true',
                       help='Use AI model for math formula recognition (slower but more accurate)')
    parser.add_argument('--api-url', default='https://dcca.hhstu.edu.cn/transfer',
                       help='API base URL (default: https://dcca.hhstu.edu.cn/transfer)')

    args = parser.parse_args()

    # Handle wildcard expansion (for *.pdf patterns)
    files = [args.file]
    if '*' in args.file or '?' in args.file:
        from glob import glob
        files = glob(args.file)
        if not files:
            print(f"No files found matching pattern: {args.file}", file=sys.stderr)
            sys.exit(1)

    success_count = 0
    for file_path in files:
        if convert_to_markdown(
            file_path,
            args.output,
            args.guess_image,
            args.guess_formula,
            args.api_url
        ):
            success_count += 1

    total = len(files)
    if total > 1:
        print(f"\nConverted {success_count}/{total} files")

    sys.exit(0 if success_count == total else 1)


if __name__ == '__main__':
    main()
