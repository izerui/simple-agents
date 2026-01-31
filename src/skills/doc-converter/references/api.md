# Document Converter API Reference

API documentation for the document conversion service.

**Base URL:** `https://dcca.hhstu.edu.cn/transfer`

## API Endpoints

### 1. Convert Word to PDF

**Endpoint:** `POST /api/convert-download`

Upload a Word document and convert it to PDF, returning the PDF file for download.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body Parameters:
  - `file` (binary, required): Word document file
    - Supported formats: `.docx`, `.doc`, `.wps`

**Response:**
- Status: 200 (success)
- Content-Type: `application/pdf`
- Body: PDF file binary content

**Example using curl:**
```bash
curl -X POST https://dcca.hhstu.edu.cn/transfer/api/convert-download \
  -F "file=@document.docx" \
  -o output.pdf
```

**Example using Python:**
```python
import requests

with open('document.docx', 'rb') as f:
    response = requests.post(
        'https://dcca.hhstu.edu.cn/transfer/api/convert-download',
        files={'file': f}
    )

with open('output.pdf', 'wb') as f:
    f.write(response.content)
```

---

### 2. Convert to Markdown

**Endpoint:** `POST /api/to-markdown`

Upload a document or image and convert it to Markdown format, returning the `.md` file for download.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body Parameters:
  - `file` (binary, required): Document or image file
    - Supported formats:
      - Documents: `PDF`, `DOCX`, `XLSX`, `PPTX`, `AsciiDoc`
      - Images: `PNG`, `JPG`, `JPEG`, `GIF`, `BMP`
  - `guess_image` (boolean, optional): Use AI model to recognize image content
    - Default: `false`
    - Enables better OCR and image description
  - `guess_formula` (boolean, optional): Use AI model to recognize math formulas
    - Default: `false`
    - Enables LaTeX formula extraction

**Response:**
- Status: 200 (success)
- Content-Type: `text/markdown` or `application/octet-stream`
- Body: Markdown file content

**Example using curl:**
```bash
# Basic conversion
curl -X POST https://dcca.hhstu.edu.cn/transfer/api/to-markdown \
  -F "file=@document.pdf" \
  -o output.md

# With AI features enabled
curl -X POST https://dcca.hhstu.edu.cn/transfer/api/to-markdown \
  -F "file=@document.pdf" \
  -F "guess_image=true" \
  -F "guess_formula=true" \
  -o output.md
```

**Example using Python:**
```python
import requests

with open('document.pdf', 'rb') as f:
    response = requests.post(
        'https://dcca.hhstu.edu.cn/transfer/api/to-markdown',
        files={'file': f},
        data={
            'guess_image': 'true',
            'guess_formula': 'false'
        }
    )

with open('output.md', 'wb') as f:
    f.write(response.content)
```

## Supported File Formats

### Word to PDF Conversion
| Input Format | Output Format |
|-------------|---------------|
| .docx       | .pdf          |
| .doc        | .pdf          |
| .wps        | .pdf          |

### Markdown Conversion
| Type        | Formats                                    |
|-------------|--------------------------------------------|
| Documents   | PDF, DOCX, XLSX, PPTX, AsciiDoc           |
| Images      | PNG, JPG, JPEG, GIF, BMP                   |

## AI Features

### Image Recognition (`guess_image=true`)
- **Purpose:** Recognize and describe image content using AI
- **Use Cases:**
  - Documents with screenshots, diagrams, or charts
  - Scanned documents with embedded images
  - Technical documentation with illustrations
- **Trade-off:** 2-3x slower processing time
- **Benefit:** Significantly more accurate image descriptions and OCR

### Formula Recognition (`guess_formula=true`)
- **Purpose:** Recognize mathematical formulas using AI
- **Use Cases:**
  - Scientific papers and research documents
  - Math textbooks and engineering documents
  - Technical reports with equations
- **Trade-off:** 1.5-2x slower processing time
- **Benefit:** Extracts formulas in proper LaTeX format

## Performance Notes

- **Basic conversion:** 1-5 seconds per document
- **With AI features:** 5-30 seconds depending on document complexity
- **Recommended timeouts:**
  - Word to PDF: 30 seconds
  - Basic Markdown: 30 seconds
  - Markdown with AI: 120 seconds

## Error Handling

### Common Error Scenarios

1. **Unsupported file format**
   - Symptom: API returns error or fails to convert
   - Solution: Verify file format matches supported formats

2. **File too large**
   - Symptom: Timeout or memory error
   - Solution: Check API file size limits

3. **Corrupted file**
   - Symptom: Conversion fails immediately
   - Solution: Verify file can be opened normally

4. **Network timeout**
   - Symptom: Request times out
   - Solution:
     - Increase timeout value for large files
     - Use longer timeout when AI features are enabled

5. **AI processing timeout**
   - Symptom: Timeout during Markdown conversion with AI features
   - Solution: Increase timeout to 120+ seconds

### HTTP Status Codes

| Status | Meaning                     |
|--------|-----------------------------|
| 200    | Success                     |
| 422    | Validation error (missing/invalid parameters) |
| 500    | Server error (contact API provider) |

## Tips for Best Results

### Word to PDF
- Ensure Word document is not password-protected
- Check that embedded images are accessible
- Verify document can be opened in Word/WPS

### Document to Markdown
- Use `--guess-image` for documents with visual content
- Use `--guess-formula` for scientific/technical documents
- Enable both AI features for complex technical documentation
- Consider file size vs. processing time trade-off

### Image to Markdown
- Always use `--guess-image` for best OCR results
- High-resolution images produce better results
- Ensure text in images is clear and readable
