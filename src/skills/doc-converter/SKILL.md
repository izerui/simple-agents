---
name: doc-converter
description: |
  **⚠️ IMPORTANT: Use the EXISTING scripts directly - DO NOT create new scripts or write custom code.**

  Document conversion service with two main capabilities:
  1. **Word to PDF**: Convert .docx, .doc, .wps files to PDF
  2. **Any Format to Markdown**: Convert PDF, DOCX, XLSX, PPTX, images (PNG/JPG/GIF/BMP), AsciiDoc to Markdown

  **AI-Powered Features**:
  - Image recognition: Describe screenshots, diagrams, charts with AI
  - Formula recognition: Extract math formulas to LaTeX format

  **Use when**: Converting documents between formats, extracting Markdown from office documents, or batch processing document conversions.

  **How to use**: Simply call the existing scripts with appropriate arguments. No code writing needed.
---

# Document Converter

**⚠️ DO NOT create custom scripts or write new code. Use the provided scripts directly.**

This skill provides **ready-to-use Python scripts** for document conversion. Just execute them with your files.

**Scripts Location**:
- `/skills/doc-converter/scripts/convert_to_pdf.py` - Convert Word to PDF
- `/skills/doc-converter/scripts/convert_to_markdown.py` - Convert any format to Markdown

## Quick Start

**⚠️ Remember: Execute these scripts directly. DO NOT write new code or create similar scripts.**

### Convert Word to PDF
```bash
python /skills/doc-converter/scripts/convert_to_pdf.py document.docx
```

### Convert Any Document to Markdown
```bash
# Basic conversion (fast)
python /skills/doc-converter/scripts/convert_to_markdown.py document.pdf

# With AI image recognition (best for screenshots/diagrams)
python /skills/doc-converter/scripts/convert_to_markdown.py document.pdf --guess-image

# With AI formula recognition (best for scientific papers)
python /skills/doc-converter/scripts/convert_to_markdown.py paper.docx --guess-formula

# With both AI features (best for technical docs)
python /skills/doc-converter/scripts/convert_to_markdown.py document.pdf --guess-image --guess-formula
```

**Requirements**: Only need `pip install requests` (already installed in most environments)

**⚠️ Common Mistakes to AVOID**:
- ❌ Creating a new Python script with requests code
- ❌ Writing custom API calls
- ❌ Implementing conversion logic from scratch
- ✅ **Just execute the provided scripts with appropriate arguments**

## Supported Formats

### Word to PDF
| Input | Output |
|-------|--------|
| .docx, .doc, .wps | .pdf |

### Document/Image to Markdown
| Type | Formats |
|------|---------|
| Documents | PDF, DOCX, XLSX, PPTX, AsciiDoc |
| Images | PNG, JPG, JPEG, GIF, BMP |

## Python Scripts Reference

### convert_to_pdf.py
**Purpose**: Convert Word documents (.docx, .doc, .wps) to PDF

**Usage:**
```bash
python /skills/doc-converter/scripts/convert_to_pdf.py FILE [-o OUTPUT] [--api-url URL]
```

**Arguments & Options:**
- `FILE` - Word document to convert
- `-o, --output` - Custom output path (default: same filename with .pdf extension)
- `--api-url` - API endpoint (default: https://dcca.hhstu.edu.cn/transfer)

**Examples:**
```bash
# Convert single file
python /skills/doc-converter/scripts/convert_to_pdf.py report.docx

# Custom output location
python /skills/doc-converter/scripts/convert_to_pdf.py report.docx -o documents/report.pdf

# Batch convert all Word docs
python /skills/doc-converter/scripts/convert_to_pdf.py reports/*.docx
```

### convert_to_markdown.py
**Purpose**: Convert documents/images to Markdown with optional AI features

**Usage:**
```bash
python /skills/doc-converter/scripts/convert_to_markdown.py FILE [-o OUTPUT] [OPTIONS]
```

**Arguments & Options:**
- `FILE` - Document or image file to convert
- `-o, --output` - Custom output path (default: same filename with .md extension)
- `--guess-image` - Enable AI image recognition (slower but better OCR/descriptions)
- `--guess-formula` - Enable AI math formula recognition (extracts LaTeX)
- `--api-url` - API endpoint

**Examples:**
```bash
# Basic PDF to Markdown
python /skills/doc-converter/scripts/convert_to_markdown.py document.pdf

# Custom output
python /skills/doc-converter/scripts/convert_to_markdown.py document.docx -o output.md

# Document with screenshots/diagrams
python /skills/doc-converter/scripts/convert_to_markdown.py guide.pdf --guess-image

# Scientific paper with formulas
python /skills/doc-converter/scripts/convert_to_markdown.py research.docx --guess-formula

# Image OCR (best quality)
python /skills/doc-converter/scripts/convert_to_markdown.py screenshot.png --guess-image

# Technical document (both features)
python /skills/doc-converter/scripts/convert_to_markdown.py manual.pdf --guess-image --guess-formula

# Batch conversion
python /skills/doc-converter/scripts/convert_to_markdown.py documents/*.pdf
```

## Common Use Cases

### 1. Convert Word Report to PDF
```bash
python /skills/doc-converter/scripts/convert_to_pdf.py monthly_report.docx
```

### 2. Extract Markdown from PDF
```bash
python /skills/doc-converter/scripts/convert_to_markdown.py research_paper.pdf
```

### 3. Convert Presentation Slides
```bash
python /skills/doc-converter/scripts/convert_to_markdown.py slides.pptx --guess-image
```

### 4. Process Technical Documentation
For documents with screenshots, diagrams, or charts:
```bash
python /skills/doc-converter/scripts/convert_to_markdown.py user_guide.pdf --guess-image
```

### 5. Convert Scientific Papers
For documents with mathematical formulas:
```bash
python /skills/doc-converter/scripts/convert_to_markdown.py math_paper.docx --guess-formula
```

### 6. Image to Text (OCR)
```bash
python /skills/doc-converter/scripts/convert_to_markdown.py screenshot.png --guess-image
```

### 7. Batch Processing
```bash
# Convert all Word docs to PDF
python /skills/doc-converter/scripts/convert_to_pdf.py reports/*.docx

# Convert all PDFs to Markdown
python /skills/doc-converter/scripts/convert_to_markdown.py documents/*.pdf
```

## AI Features Explained

### Image Recognition (`--guess-image`)
**What it does**: Uses AI to recognize and describe image content with high accuracy

**When to use**:
- Documents with screenshots or UI mockups
- Technical diagrams and flowcharts
- Charts, graphs, or data visualizations
- Scanned documents with embedded images
- Presentations with visual content

**Trade-off**: 2-3x slower processing time, but significantly better image descriptions

**Real examples**:
```bash
# User manual with screenshots
python /skills/doc-converter/scripts/convert_to_markdown.py user_guide.pdf --guess-image

# Presentation with slides
python /skills/doc-converter/scripts/convert_to_markdown.py presentation.pptx --guess-image

# Document with charts/diagrams
python /skills/doc-converter/scripts/convert_to_markdown.py report.pdf --guess-image
```

### Formula Recognition (`--guess-formula`)
**What it does**: Uses AI to recognize mathematical formulas and convert them to LaTeX

**When to use**:
- Scientific research papers
- Math or physics textbooks
- Engineering documents with equations
- Financial reports with formulas

**Trade-off**: 1.5-2x slower processing time, but extracts proper LaTeX formulas

**Real examples**:
```bash
# Research paper
python /skills/doc-converter/scripts/convert_to_markdown.py research.pdf --guess-formula

# Math textbook
python /skills/doc-converter/scripts/convert_to_markdown.py textbook.docx --guess-formula

# Both features for complex technical docs
python /skills/doc-converter/scripts/convert_to_markdown.py paper.pdf --guess-image --guess-formula
```

## Requirements & Setup

### Prerequisites
- Python 3.6 or higher
- Internet connection (for API access)

### Install Dependencies
```bash
pip install requests
```

**That's it!** The scripts are ready to use.

## Error Handling

The scripts provide comprehensive error handling:
- ✅ Validates input file exists before processing
- ✅ Shows conversion progress in real-time
- ✅ Displays clear success/failure messages
- ✅ Provides detailed error messages on failure
- ✅ Returns proper exit codes (0 = success, 1 = failure)
- ✅ Handles network timeouts gracefully
- ✅ Supports batch processing with individual file status

### Common Issues & Solutions

**Issue**: `requests library not found`
```bash
# Solution
pip install requests
```

**Issue**: Conversion timeout on large files
- Use with AI features requires more time (scripts auto-adjust timeout)
- For very large documents, consider processing without AI first

**Issue**: Unsupported file format
- Verify your file extension matches supported formats
- Check file is not corrupted

## Advanced Usage

### Custom API Endpoint
If you need to use a different API server:
```bash
python /skills/doc-converter/scripts/convert_to_pdf.py file.docx --api-url https://your-api.com/transfer
python /skills/doc-converter/scripts/convert_to_markdown.py file.pdf --api-url https://your-api.com/transfer
```

### Programmatic Usage
You can also import and use these scripts as Python modules:

```python
from scripts.convert_to_pdf import convert_to_pdf
from scripts.convert_to_markdown import convert_to_markdown

# Convert to PDF
convert_to_pdf('document.docx', 'output.pdf')

# Convert to Markdown with AI features
convert_to_markdown(
    'document.pdf',
    'output.md',
    guess_image=True,
    guess_formula=True
)
```

## Performance Notes

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Word to PDF | 1-5 seconds | Depends on file size |
| Basic to Markdown | 1-5 seconds | Fast conversion |
| With image AI | 5-30 seconds | Best for visual content |
| With formula AI | 5-20 seconds | Best for scientific docs |
| Both AI features | 10-40 seconds | For complex technical docs |

---

## ⚠️ Important Usage Guidelines

### DO ✅
- Execute the provided scripts directly with appropriate arguments
- Use `python /skills/doc-converter/scripts/convert_to_pdf.py` for Word to PDF conversion
- Use `python /skills/doc-converter/scripts/convert_to_markdown.py` for any format to Markdown
- Adjust script arguments (input file, output path, AI options) as needed

### DO NOT ❌
- Create new Python scripts with requests/AI code
- Write custom API integration code
- Implement document conversion logic from scratch
- Copy the script code into new files

### Why?
The scripts are already:
- ✅ Fully implemented and tested
- ✅ Handle all error cases
- ✅ Optimized for performance
- ✅ Support all features (AI recognition, batch processing, etc.)

**Just use them directly - no development needed!**

For more API details, see [references/api.md](references/api.md).
