#!/usr/bin/env python3
"""
Convert Word documents to PDF using the document conversion API.
Supports .docx, .doc, .wps file formats.
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


def convert_to_pdf(
    file_path: str,
    output_path: str = None,
    api_base_url: str = "https://dcca.hhstu.edu.cn/transfer"
) -> bool:
    """
    Convert a Word document to PDF.

    Args:
        file_path: Path to the Word document (.docx, .doc, .wps)
        output_path: Where to save the PDF (default: same as input with .pdf extension)
        api_base_url: Base URL of the conversion API

    Returns:
        True if conversion succeeded, False otherwise
    """
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return False

    # Determine output path
    if output_path is None:
        output_path = str(Path(file_path).with_suffix('.pdf'))

    print(f"Converting {file_path} to PDF...")

    try:
        # Prepare and send request
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
            response = requests.post(
                f"{api_base_url}/api/convert-download",
                files=files,
                timeout=60
            )

        # Check response
        response.raise_for_status()

        # Save PDF content
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
    """CLI interface for PDF conversion."""
    parser = argparse.ArgumentParser(
        description='Convert Word documents to PDF using document conversion API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Convert a document
  python scripts/convert_to_pdf.py document.docx

  # Convert with custom output path
  python scripts/convert_to_pdf.py document.docx -o output.pdf

  # Convert multiple documents
  python scripts/convert_to_pdf.py *.docx

Supported formats: .docx, .doc, .wps
        '''
    )

    parser.add_argument('file', help='Word document file to convert')
    parser.add_argument('-o', '--output', help='Output PDF file path')
    parser.add_argument('--api-url', default='https://dcca.hhstu.edu.cn/transfer',
                       help='API base URL (default: https://dcca.hhstu.edu.cn/transfer)')

    args = parser.parse_args()

    # Handle wildcard expansion (for *.docx patterns)
    files = [args.file]
    if '*' in args.file or '?' in args.file:
        from glob import glob
        files = glob(args.file)
        if not files:
            print(f"No files found matching pattern: {args.file}", file=sys.stderr)
            sys.exit(1)

    success_count = 0
    for file_path in files:
        if convert_to_pdf(file_path, args.output, args.api_url):
            success_count += 1

    total = len(files)
    if total > 1:
        print(f"\nConverted {success_count}/{total} files")

    sys.exit(0 if success_count == total else 1)


if __name__ == '__main__':
    main()
