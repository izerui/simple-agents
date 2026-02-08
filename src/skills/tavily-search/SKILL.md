---
name: tavily-search
description: "Search the web using Tavily's LLM-optimized search API. Usage: python /skills/tavily-search/scripts/search.py '{\"query\": \"your search query\"}'. Returns relevant results with content snippets, scores, and metadata."
---

# Tavily Search Skill

Search the web and get relevant results optimized for LLM consumption.

## Quick Start

### Using the Script

Run the script directly with a JSON argument:

```bash
python /skills/tavily-search/scripts/search.py '<json>'
```

**Examples:**
```bash
# Basic search
python /skills/tavily-search/scripts/search.py '{"query": "python async patterns"}'

# With options
python /skills/tavily-search/scripts/search.py '{"query": "React hooks tutorial", "max_results": 10}'

# Advanced search with filters
python /skills/tavily-search/scripts/search.py '{"query": "AI news", "topic": "news", "time_range": "week", "max_results": 10}'

# Domain-filtered search
python /skills/tavily-search/scripts/search.py '{"query": "machine learning", "include_domains": ["arxiv.org", "github.com"], "search_depth": "advanced"}'
```

### Basic Search

```bash
python /skills/tavily-search/scripts/search.py '{
  "query": "latest developments in quantum computing",
  "max_results": 5
}'
```

### Advanced Search

```bash
python /skills/tavily-search/scripts/search.py '{
  "query": "machine learning best practices",
  "max_results": 10,
  "search_depth": "advanced",
  "include_domains": ["arxiv.org", "github.com"],
  "chunks_per_source": 3
}'
```

## API Reference

### Endpoint

```
POST https://api.tavily.com/search
```

### Headers

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <TAVILY_API_KEY>` |
| `Content-Type` | `application/json` |

### Request Body

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | Required | Search query (keep under 400 chars) |
| `max_results` | integer | 5 | Maximum results (0-20) |
| `search_depth` | string | `"basic"` | `ultra-fast`, `fast`, `basic`, `advanced` |
| `topic` | string | `"general"` | `general`, `news`, `finance` |
| `chunks_per_source` | integer | 3 | Chunks per source (advanced/fast only) |
| `time_range` | string | null | `day`, `week`, `month`, `year` |
| `include_domains` | array | [] | Domains to include (max 300) |
| `exclude_domains` | array | [] | Domains to exclude (max 150) |
| `include_answer` | boolean | false | Include AI-generated answer |
| `include_raw_content` | boolean | false | Include full page content |
| `include_images` | boolean | false | Include image results |

### Response Format

```json
{
  "query": "latest developments in quantum computing",
  "results": [
    {
      "title": "Page Title",
      "url": "https://example.com/page",
      "content": "Extracted text snippet...",
      "score": 0.85
    }
  ],
  "response_time": 1.2
}
```

## Search Depth

| Depth | Latency | Relevance | Content Type |
|-------|---------|-----------|--------------|
| `ultra-fast` | Lowest | Lower | NLP summary |
| `fast` | Low | Good | Chunks |
| `basic` | Medium | High | NLP summary |
| `advanced` | Higher | Highest | Chunks |

**When to use each:**
- `ultra-fast`: Real-time chat, autocomplete
- `fast`: Need chunks but latency matters
- `basic`: General-purpose, balanced
- `advanced`: Precision matters (default recommendation)

## Examples

### News Search

```bash
python /skills/tavily-search/scripts/search.py '{
  "query": "AI news today",
  "topic": "news",
  "time_range": "day",
  "max_results": 10
}'
```

### Domain-Filtered Search

```bash
python /skills/tavily-search/scripts/search.py '{
  "query": "Python async best practices",
  "include_domains": ["docs.python.org", "realpython.com", "github.com"],
  "search_depth": "advanced"
}'
```

### Search with Full Content

```bash
python /skills/tavily-search/scripts/search.py '{
  "query": "React hooks tutorial",
  "max_results": 3,
  "include_raw_content": true
}'
```

### Finance Search

```bash
python /skills/tavily-search/scripts/search.py '{
  "query": "AAPL earnings Q4 2024",
  "topic": "finance",
  "max_results": 10
}'
```

## Tips

- **Keep queries under 400 characters** - Think search query, not prompt
- **Break complex queries into sub-queries** - Better results than one massive query
- **Use `include_domains`** to focus on trusted sources
- **Use `time_range`** for recent information
- **Filter by `score`** (0-1) to get highest relevance results
