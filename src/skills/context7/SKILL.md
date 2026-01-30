---
name: context7
description: Retrieve up-to-date documentation for software libraries, frameworks, and components via the Context7 API. This skill should be used when looking up documentation for any programming library or framework, finding code examples for specific APIs or features, verifying correct usage of library functions, or obtaining current information about library APIs that may have changed since training.
---

# Context7

## Overview

This skill enables retrieval of current documentation for software libraries and components by querying the Context7 API via Python. Use it instead of relying on potentially outdated training data.

## Workflow

### Step 1: Search for the Library

To find the Context7 library ID, query the search endpoint:

```bash
python -c "import urllib.request, json; data = json.loads(urllib.request.urlopen('https://context7.com/api/v2/libs/search?libraryName=LIBRARY_NAME&query=TOPIC').read().decode('utf-8')); print(data['results'][0])"
```

**Parameters:**
- `libraryName` (required): The library name to search for (e.g., "react", "nextjs", "fastapi", "axios")
- `query` (required): A description of the topic for relevance ranking

**Response fields:**
- `id`: Library identifier for the context endpoint (e.g., `/websites/react_dev_reference`)
- `title`: Human-readable library name
- `description`: Brief description of the library
- `totalSnippets`: Number of documentation snippets available

### Step 2: Fetch Documentation

To retrieve documentation, use the library ID from step 1:

```bash
python -c "import urllib.request; print(urllib.request.urlopen('https://context7.com/api/v2/context?libraryId=LIBRARY_ID&query=TOPIC&type=txt').read().decode('utf-8'))"
```

**Parameters:**
- `libraryId` (required): The library ID from search results
- `query` (required): The specific topic to retrieve documentation for
- `type` (optional): Response format - `json` (default) or `txt` (plain text, more readable)

## Examples

### React hooks documentation

```bash
# Find React library ID
python -c "import urllib.request, json; data = json.loads(urllib.request.urlopen('https://context7.com/api/v2/libs/search?libraryName=react&query=hooks').read().decode('utf-8')); print(data['results'][0]['id'])"
# Returns: "/websites/react_dev_reference"

# Fetch useState documentation
python -c "import urllib.request; print(urllib.request.urlopen('https://context7.com/api/v2/context?libraryId=/websites/react_dev_reference&query=useState&type=txt').read().decode('utf-8'))"
```

### Next.js routing documentation

```bash
# Find Next.js library ID
python -c "import urllib.request, json; data = json.loads(urllib.request.urlopen('https://context7.com/api/v2/libs/search?libraryName=nextjs&query=routing').read().decode('utf-8')); print(data['results'][0]['id'])"

# Fetch app router documentation
python -c "import urllib.request; print(urllib.request.urlopen('https://context7.com/api/v2/context?libraryId=/vercel/next.js&query=app+router&type=txt').read().decode('utf-8'))"
```

### FastAPI dependency injection

```bash
# Find FastAPI library ID
python -c "import urllib.request, json; data = json.loads(urllib.request.urlopen('https://context7.com/api/v2/libs/search?libraryName=fastapi&query=dependencies').read().decode('utf-8')); print(data['results'][0]['id'])"

# Fetch dependency injection documentation
python -c "import urllib.request; print(urllib.request.urlopen('https://context7.com/api/v2/context?libraryId=/fastapi/fastapi&query=dependency+injection&type=txt').read().decode('utf-8'))"
```

## Tips

- Use `type=txt` for more readable output
- Use Python's json module to parse and filter JSON responses
- Be specific with the `query` parameter to improve relevance ranking
- If the first search result is not correct, check additional results in the array by modifying the index
- URL-encode query parameters containing spaces (use `+` or `%20`)
- No API key is required for basic usage (rate-limited)