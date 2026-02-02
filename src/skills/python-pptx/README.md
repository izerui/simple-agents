# Python-pptx PowerPoint Automation Skill

> Quick Reference Guide for Presentation Automation

## Overview

Create and manipulate PowerPoint presentations with slides, shapes, charts, tables, and template-based generation.

**Version**: 1.0.0
**Category**: office-docs

## ⚠️ Important: Use Custom Template

**CRITICAL**: This skill provides a custom default template at `/skills/python-pptx/default.pptx` (in sandbox). Always use this template instead of the python-pptx library's built-in default.

### Why Not Use Library Default?

```python
# ❌ WRONG - Uses library's generic template
prs = Presentation()

# ✅ CORRECT - Uses our professional template
prs = Presentation("/skills/python-pptx/default.pptx")
```

**Benefits of custom template**:
- Professional layouts and styling
- Consistent 16:9 widescreen format
- Better slide master options
- Brand-ready customization

See [SKILL.md](SKILL.md) for detailed template usage guidelines.

## Quick Start

```bash
# Install
python -m pip install python-pptx

# With image support
python -m pip install python-pptx Pillow
```

## Basic Usage

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

# Create presentation using custom template
prs = Presentation("/skills/python-pptx/default.pptx")

# Title slide
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Quarterly Report"
slide.placeholders[1].text = "Q1 2026"

# Content slide with bullets
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "Key Points"
body = slide.placeholders[1]
tf = body.text_frame
tf.text = "First point"
p = tf.add_paragraph()
p.text = "Second point"

# Add chart
chart_data = CategoryChartData()
chart_data.categories = ['Q1', 'Q2', 'Q3']
chart_data.add_series('Sales', (100, 150, 200))
slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,
    Inches(1), Inches(2), Inches(8), Inches(4), chart_data)

# Save
prs.save('report.pptx')
```

## Key Features

| Feature | Description |
|---------|-------------|
| Slides | Multiple layouts (title, content, blank) |
| Shapes | Rectangles, ovals, arrows, callouts |
| Charts | Column, line, pie, bar, doughnut |
| Tables | Styled headers, formatted cells |
| Images | PNG, JPG with sizing |

## When to Use

**Use for**:
- Automated report presentations
- Data-driven slide decks
- Template-based generation
- Batch presentation creation

**Avoid for**:
- Complex animations
- Video embedding
- Real-time editing

## Common Patterns

### Add Chart
```python
chart_data = CategoryChartData()
chart_data.categories = ['A', 'B', 'C']
chart_data.add_series('Data', (10, 20, 30))
slide.shapes.add_chart(
    XL_CHART_TYPE.PIE,
    Inches(2), Inches(2), Inches(6), Inches(4),
    chart_data
)
```

### Template Replacement
```python
# Load custom template (sandbox path)
prs = Presentation("/skills/python-pptx/default.pptx")

for slide in prs.slides:
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if '{{name}}' in run.text:
                        run.text = run.text.replace('{{name}}', 'Value')
```

## Template Location

The custom default template is located at:
```
/skills/python-pptx/default.pptx
```

**In the sandbox environment**, this path is mapped to the skill directory automatically.

### Sandbox Path Usage

```python
# In sandbox - use absolute path
prs = Presentation("/skills/python-pptx/default.pptx")

# This maps to the project's skill directory:
# <project>/src/skills/python-pptx/default.pptx
```

**Important**: The sandbox environment automatically mounts skill directories at `/skills/`, so you can always use this consistent path regardless of where your code runs within the sandbox.

## Files

```
python-pptx/
  SKILL.md    # Full documentation
  README.md   # This file
```

## Related Skills

- **python-docx** - Word automation
- **openpyxl** - Excel automation
- **plotly** - Interactive charts

## Resources

- [Documentation](https://python-pptx.readthedocs.io/)
- [GitHub](https://github.com/scanny/python-pptx)

---

See `SKILL.md` for complete examples and advanced patterns.
