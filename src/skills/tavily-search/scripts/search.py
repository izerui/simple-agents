#!/usr/bin/env python3
"""
Tavily Search API script
Usage: /skills/tavily-search/scripts/search.py '{"query": "your search query", ...}'
Example: /skills/tavily-search/scripts/search.py '{"query": "AI news", "topic": "news", "time_range": "week", "max_results": 10}'
"""

import sys
import os
import json
from typing import Any

import requests


def print_usage() -> None:
    """Print usage information."""
    print("Usage: ./search.py '<json>'")
    print("")
    print("Required:")
    print("  query: string - Search query (keep under 400 chars)")
    print("")
    print("Optional:")
    print("  search_depth: \"ultra-fast\", \"fast\", \"basic\" (default), \"advanced\"")
    print("  topic: \"general\" (default), \"news\", \"finance\"")
    print("  max_results: 1-20 (default: 5)")
    print("  chunks_per_source: 1-5 (default: 3, advanced/fast depth only)")
    print("  time_range: \"day\", \"week\", \"month\", \"year\"")
    print("  start_date: \"YYYY-MM-DD\"")
    print("  end_date: \"YYYY-MM-DD\"")
    print("  include_domains: [\"domain1.com\", \"domain2.com\"]")
    print("  exclude_domains: [\"domain1.com\", \"domain2.com\"]")
    print("  country: country name (general topic only)")
    print("  include_answer: true/false or \"basic\"/\"advanced\"")
    print("  include_raw_content: true/false or \"markdown\"/\"text\"")
    print("  include_images: true/false")
    print("  include_image_descriptions: true/false")
    print("  include_favicon: true/false")
    print("")
    print("Example:")
    print('  ./search.py \'{"query": "latest AI trends", "topic": "news", "time_range": "week"}\'')


def validate_json_input(json_input: str) -> dict[str, Any]:
    """
    Validate and parse JSON input.

    Args:
        json_input: JSON string to validate

    Returns:
        Parsed JSON dictionary

    Raises:
        SystemExit: If JSON is invalid or missing required fields
    """
    try:
        data = json.loads(json_input)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input - {e}", file=sys.stderr)
        sys.exit(1)

    # Check for required query field
    if "query" not in data:
        print("Error: 'query' field is required", file=sys.stderr)
        sys.exit(1)

    return data


def search_tavily(search_params: dict[str, Any]) -> dict[str, Any]:
    """
    Call Tavily Search API.

    Args:
        search_params: Search parameters dictionary

    Returns:
        API response as dictionary

    Raises:
        SystemExit: If API call fails
    """
    url = "https://api.tavily.com/search"
    headers = {
        "Authorization": f"Bearer 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",
        "Content-Type": "application/json",
        "x-client-source": "claude-code-skill",
    }

    try:
        # 跳过 SSL 验证（沙箱环境中可能无法访问 CA 证书）
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.post(url, json=search_params, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: API request failed - {e}", file=sys.stderr)
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    json_input = sys.argv[1]

    # Validate and parse JSON input
    search_params = validate_json_input(json_input)

    # Call Tavily API
    result = search_tavily(search_params)

    # Print formatted JSON result
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
