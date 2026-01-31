# HTTP Client Examples

Common usage patterns for the HTTP client scripts.

## Using http_request.py

### GET Request

```bash
python scripts/http_request.py GET https://api.example.com/users
```

### GET with Query Parameters

```bash
python scripts/http_request.py GET https://api.example.com/users \
  -q "page=1" \
  -q "limit=10"
```

### GET with Headers

```bash
python scripts/http_request.py GET https://api.example.com/users \
  -H "Accept: application/json" \
  -H "X-Custom-Header: value"
```

### GET with Bearer Token Authentication

```bash
python scripts/http_request.py GET https://api.example.com/users \
  -b "your-token-here"
```

### GET with Basic Authentication

```bash
python scripts/http_request.py GET https://api.example.com/users \
  --basic username password
```

### POST with JSON Body

```bash
python scripts/http_request.py POST https://api.example.com/users \
  -j '{"name": "John Doe", "email": "john@example.com"}'
```

### POST with JSON from File

```bash
# Create JSON file
cat > data.json << EOF
{
  "name": "John Doe",
  "email": "john@example.com"
}
EOF

# Send request
python scripts/http_request.py POST https://api.example.com/users \
  -j @data.json
```

### POST with Form Data

```bash
python scripts/http_request.py POST https://api.example.com/form \
  -d "name=John Doe" \
  -d "email=john@example.com"
```

### POST with File Upload

```bash
python scripts/http_request.py POST https://api.example.com/upload \
  -f "file=/path/to/file.txt" \
  -f "thumbnail=/path/to/image.jpg"
```

### POST with File Upload and Additional Data

```bash
python scripts/http_request.py POST https://api.example.com/upload \
  -f "file=/path/to/document.pdf" \
  -d "title=My Document" \
  -d "category=reports"
```

### PUT Request

```bash
python scripts/http_request.py PUT https://api.example.com/users/123 \
  -j '{"name": "Jane Doe"}'
```

### PATCH Request

```bash
python scripts/http_request.py PATCH https://api.example.com/users/123 \
  -j '{"email": "jane@example.com"}'
```

### DELETE Request

```bash
python scripts/http_request.py DELETE https://api.example.com/users/123
```

### Request with Cookies

```bash
python scripts/http_request.py GET https://api.example.com/profile \
  -c "session_id=abc123" \
  -c "user_pref=dark"
```

### Request with Proxy

```bash
python scripts/http_request.py GET https://api.example.com/data \
  --proxy http://proxy.example.com:8080
```

### Request with Custom Timeout

```bash
python scripts/http_request.py GET https://api.example.com/slow-endpoint \
  -t 60
```

### Disable SSL Verification (for testing)

```bash
python scripts/http_request.py GET https://self-signed-cert.example.com/data \
  --no-ssl-verify
```

### Save Response to File

```bash
python scripts/http_request.py GET https://api.example.com/data \
  -o response.json
```

### Verbose Output (include status and headers)

```bash
python scripts/http_request.py GET https://api.example.com/users -v
```

## Using upload_file.py

### Simple File Upload

```bash
python scripts/upload_file.py https://api.example.com/upload /path/to/file.txt
```

### Upload with Custom Field Name

```bash
python scripts/upload_file.py https://api.example.com/upload /path/to/file.pdf \
  -n document
```

### Upload with Additional Form Data

```bash
python scripts/upload_file.py https://api.example.com/upload /path/to/file.jpg \
  -d "title=My Photo" \
  -d "category=images" \
  -d "private=true"
```

### Upload with Authentication

```bash
# Bearer token
python scripts/upload_file.py https://api.example.com/upload /path/to/file.pdf \
  -b "your-token-here"

# Basic auth
python scripts/upload_file.py https://api.example.com/upload /path/to/file.pdf \
  --basic username password
```

### Upload with Custom Headers

```bash
python scripts/upload_file.py https://api.example.com/upload /path/to/file.pdf \
  -H "X-API-Key: your-api-key" \
  -H "X-Custom-Header: value"
```

### Upload with Proxy

```bash
python scripts/upload_file.py https://api.example.com/upload /path/to/file.pdf \
  --proxy http://proxy.example.com:8080
```

## Common Scenarios

### REST API CRUD Operations

```bash
# Create (POST)
python scripts/http_request.py POST https://api.example.com/users \
  -j '{"name": "John", "email": "john@example.com"}'

# Read (GET)
python scripts/http_request.py GET https://api.example.com/users/123

# Update (PUT)
python scripts/http_request.py PUT https://api.example.com/users/123 \
  -j '{"name": "Jane", "email": "jane@example.com"}'

# Delete (DELETE)
python scripts/http_request.py DELETE https://api.example.com/users/123
```

### Testing Webhooks

```bash
python scripts/http_request.py POST https://your-server.com/webhook \
  -j '{"event": "user.created", "data": {"id": 123}}' \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: secret123"
```

### Uploading Multiple Files

```bash
python scripts/http_request.py POST https://api.example.com/upload \
  -f "file1=/path/to/document.pdf" \
  -f "file2=/path/to/image.jpg" \
  -f "file3=/path/to/data.csv"
```

### API Authentication Patterns

```bash
# Bearer token (OAuth2/JWT)
python scripts/http_request.py GET https://api.example.com/protected \
  -b "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# API Key in header
python scripts/http_request.py GET https://api.example.com/data \
  -H "X-API-Key: your-api-key"

# Basic auth
python scripts/http_request.py GET https://api.example.com/protected \
  --basic api_user api_password
```

### Pagination

```bash
# Get first page
python scripts/http_request.py GET https://api.example.com/items \
  -q "page=1" -q "per_page=100"

# Get next page
python scripts/http_request.py GET https://api.example.com/items \
  -q "page=2" -q "per_page=100"
```

### Debugging API Issues

```bash
# Verbose mode to see status and headers
python scripts/http_request.py GET https://api.example.com/endpoint -v

# Save response for inspection
python scripts/http_request.py GET https://api.example.com/endpoint \
  -o debug_response.json
```

## Response Handling

All scripts return structured response with:
- `status_code`: HTTP status code
- `headers`: Response headers
- `body`: Response body (bytes)
- `cookies`: Response cookies (extracted from Set-Cookie headers)
- `success`: Boolean indicating if request succeeded
- `error`: Error message (if failed)

Scripts automatically:
- Parse and pretty-print JSON responses
- Handle UTF-8 decoding with fallback for binary data
- Exit with status code 0 on success, 1 on failure
