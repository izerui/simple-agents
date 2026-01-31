---
name: http-client
description: Universal Python-based HTTP client for making web requests. Supports all HTTP methods (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS) with advanced features including multipart file uploads, JSON/form data handling, Bearer/Basic authentication, custom headers, query parameters, cookies, proxy support, timeout configuration, and SSL verification control. Use when making HTTP requests to APIs, uploading files, testing webhooks, debugging endpoints, or any network request operations. Includes two scripts: http_request.py (general-purpose client) and upload_file.py (specialized file upload utility).
---

# HTTP Client

Universal HTTP client for making web requests with Python scripts.

## Quick Start

### Basic Request

Make a GET request:
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/users
```

Make a POST request with JSON:
```bash
python /skills/http-client/scripts/http_request.py POST https://api.example.com/users \
  -j '{"name": "John", "email": "john@example.com"}'
```

Upload a file:
```bash
python /skills/http-client/scripts/upload_file.py https://api.example.com/upload /path/to/file.pdf
```

## Scripts

### http_request.py

General-purpose HTTP client supporting all methods and features.

**Usage:**
```bash
python /skills/http-client/scripts/http_request.py METHOD URL [OPTIONS]
```

**Methods:** GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS

**Common Options:**
- `-j, --json` - JSON body (string or @filename)
- `-d, --data` - Form data (key=value)
- `-f, --file` - Upload file (fieldname=filename)
- `-H, --header` - Custom header (Name: Value)
- `-q, --query` - Query parameter (key=value)
- `-b, --bearer` - Bearer token authentication
- `--basic` - Basic auth (username password)
- `-c, --cookie` - Cookie (key=value)
- `-t, --timeout` - Timeout in seconds (default: 30)
- `--proxy` - Proxy URL
- `--no-ssl-verify` - Disable SSL verification
- `-v, --verbose` - Verbose output
- `-o, --output` - Save response to file

### upload_file.py

Convenience script for multipart file uploads via POST.

**Usage:**
```bash
python /skills/http-client/scripts/upload_file.py URL FILE [OPTIONS]
```

**Options:**
- `-n, --field-name` - Form field name (default: file)
- `-d, --data` - Additional form data
- `-H, --header` - Custom headers
- `-b, --bearer` - Bearer token
- `--basic` - Basic auth
- `-t, --timeout` - Timeout
- `--proxy` - Proxy URL

## Common Patterns

### Authentication

**Bearer token:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/protected -b "token"
```

**Basic auth:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/protected --basic user pass
```

**API key in header:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/data -H "X-API-Key: key123"
```

### Data Submission

**JSON body:**
```bash
python /skills/http-client/scripts/http_request.py POST https://api.example.com/data \
  -j '{"key": "value", "number": 123}'
```

**JSON from file:**
```bash
python /skills/http-client/scripts/http_request.py POST https://api.example.com/data -j @data.json
```

**Form data:**
```bash
python /skills/http-client/scripts/http_request.py POST https://api.example.com/form \
  -d "name=John" -d "email=john@example.com"
```

### File Uploads

**Single file:**
```bash
python /skills/http-client/scripts/http_request.py POST https://api.example.com/upload \
  -f "file=/path/to/document.pdf"
```

**Multiple files:**
```bash
python /skills/http-client/scripts/http_request.py POST https://api.example.com/upload \
  -f "file1=/path/to/doc1.pdf" \
  -f "file2=/path/to/doc2.pdf"
```

**File with metadata:**
```bash
python /skills/http-client/scripts/http_request.py POST https://api.example.com/upload \
  -f "file=/path/to/file.pdf" \
  -d "title=My Document" \
  -d "category=reports"
```

**Using upload_file.py:**
```bash
python /skills/http-client/scripts/upload_file.py https://api.example.com/upload /path/to/file.pdf \
  -d "title=My Document"
```

### REST API Operations

```bash
# Create
python /skills/http-client/scripts/http_request.py POST https://api.example.com/users \
  -j '{"name": "John", "email": "john@example.com"}'

# Read
python /skills/http-client/scripts/http_request.py GET https://api.example.com/users/123

# Update
python /skills/http-client/scripts/http_request.py PUT https://api.example.com/users/123 \
  -j '{"name": "Jane"}'

# Delete
python /skills/http-client/scripts/http_request.py DELETE https://api.example.com/users/123
```

### Advanced Features

**Query parameters:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/items \
  -q "page=1" -q "limit=10" -q "sort=name"
```

**Cookies:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/profile \
  -c "session_id=abc123" -c "user_pref=dark"
```

**Proxy:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/data \
  --proxy http://proxy.example.com:8080
```

**Custom timeout:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/slow -t 120
```

**Disable SSL (testing only):**
```bash
python /skills/http-client/scripts/http_request.py GET https://self-signed.badssl.com/ --no-ssl-verify
```

**Save response:**
```bash
python /skills/http-client/scripts/http_request.py GET https://api.example.com/data -o response.json
```

## Response Handling

Scripts automatically:
- Parse and pretty-print JSON responses
- Display status code in verbose mode (`-v`)
- Extract response cookies
- Exit with status code 0 (success) or 1 (failure)

For more examples and patterns, see [references/examples.md](references/examples.md).
