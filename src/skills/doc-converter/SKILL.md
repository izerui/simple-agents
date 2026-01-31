---
name: doc-converter
description: Document format conversion service for converting Word documents to PDF and various file formats to Markdown. Supports converting .docx, .doc, .wps files to PDF, and converting PDF, DOCX, XLSX, PPTX, PNG, JPG, JPEG, GIF, BMP, and AsciiDoc files to Markdown with optional AI-enhanced image and formula recognition. Use when converting documents between formats, extracting Markdown from office documents, or batch processing document conversions. Self-contained with built-in HTTP functionality.
---

# Document Converter

Convert documents between formats using the document conversion API service.

**API Base URL:** `https://dcca.hhstu.edu.cn/transfer`

## Conversion Types

### Word to PDF

Convert Word documents (.docx, .doc, .wps) to PDF format.

```bash
python scripts/convert_to_pdf.py document.docx
```

### Any Format to Markdown

Convert documents and images to Markdown format.

**Supported formats:**
- **Documents:** PDF, DOCX, XLSX, PPTX, AsciiDoc
- **Images:** PNG, JPG, JPEG, GIF, BMP

```bash
# Basic conversion
python scripts/convert_to_markdown.py document.pdf

# With AI image recognition (slower but more accurate)
python scripts/convert_to_markdown.py document.pdf --guess-image

# With AI formula recognition
python scripts/convert_to_markdown.py document.docx --guess-formula

# With both AI features enabled
python scripts/convert_to_markdown.py document.pdf --guess-image --guess-formula
```

## Scripts

### convert_to_pdf.py

Convert Word documents to PDF.

**Usage:**
```bash
python scripts/convert_to_pdf.py FILE [-o OUTPUT] [--api-url URL]
```

**Arguments:**
- `FILE` - Word document to convert (.docx, .doc, .wps)

**Options:**
- `-o, --output` - Output PDF path (default: same as input with .pdf extension)
- `--api-url` - API base URL (default: https://dcca.hhstu.edu.cn/transfer)

**Examples:**
```bash
# Convert single file
python scripts/convert_to_pdf.py report.docx

# Convert with custom output
python scripts/convert_to_pdf.py report.docx -o documents/report.pdf

# Convert multiple files
python scripts/convert_to_pdf.py *.docx
```

### convert_to_markdown.py

Convert documents and images to Markdown.

**Usage:**
```bash
python scripts/convert_to_markdown.py FILE [-o OUTPUT] [OPTIONS]
```

**Arguments:**
- `FILE` - Document or image file to convert

**Options:**
- `-o, --output` - Output Markdown path (default: same as input with .md extension)
- `--guess-image` - Use AI for image recognition (slower but more accurate)
- `--guess-formula` - Use AI for math formula recognition (slower but more accurate)
- `--api-url` - API base URL

**Examples:**
```bash
# Convert PDF to Markdown
python scripts/convert_to_markdown.py document.pdf

# Convert DOCX to Markdown
python scripts/convert_to_markdown.py document.docx -o output.md

# Convert with AI image recognition (for documents with screenshots/diagrams)
python scripts/convert_to_markdown.py document.pdf --guess-image

# Convert scientific document with formulas
python scripts/convert_to_markdown.py paper.docx --guess-formula

# Convert image to Markdown
python scripts/convert_to_markdown.py screenshot.png --guess-image

# Batch convert multiple PDFs
python scripts/convert_to_markdown.py *.pdf
```

## Use Cases

### Convert Word Report to PDF
```bash
python scripts/convert_to_pdf.py monthly_report.docx
```

### Extract Markdown from PDF
```bash
python scripts/convert_to_markdown.py research_paper.pdf
```

### Convert Presentation to Markdown
```bash
python scripts/convert_to_markdown.py slides.pptx --guess-image
```

### Process Document with Images
For documents containing screenshots, diagrams, or charts:
```bash
python scripts/convert_to_markdown.py user_guide.pdf --guess-image
```

### Convert Scientific Document
For documents with mathematical formulas:
```bash
python scripts/convert_to_markdown.py math_paper.docx --guess-formula
```

### Batch Document Conversion
```bash
# Convert all Word docs to PDF
python scripts/convert_to_pdf.py reports/*.docx

# Convert all PDFs to Markdown
python scripts/convert_to_markdown.py documents/*.pdf
```

## AI Features

### Image Recognition (`--guess-image`)
Uses AI model to recognize and describe image content.
- **When to use:** Documents with screenshots, diagrams, charts, or illustrations
- **Trade-off:** Slower processing but more accurate image descriptions
- **Example:** User manuals, technical documentation, presentations

### Formula Recognition (`--guess-formula`)
Uses AI model to recognize mathematical formulas.
- **When to use:** Scientific papers, mathematical documents, technical reports
- **Trade-off:** Slower processing but accurate LaTeX formula extraction
- **Example:** Research papers, math textbooks, engineering documents

## Requirements

- Python 3.6+
- **requests** library (install with: `pip install requests`)
- Internet connection to access the conversion API

## Error Handling

Scripts will:
- Check if input file exists
- Display conversion progress
- Report success/failure status
- Show detailed error messages on failure
- Return appropriate exit codes (0 = success, 1 = failure)

For more API details, see [references/api.md](references/api.md).
