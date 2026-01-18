docling 默认下载的模型：

| 模型 | 默认值 | 对应仓库 |
|------|--------|----------|
| **layout** (布局模型) | True | docling-project/docling-layout-heron ✅ |
| **tableformer** (表格模型) | True | docling-project/docling-models ✅ |
| **code_formula** (代码公式模型) | True | docling-project/CodeFormulaV2 ✅ |
| **picture_classifier** (图片分类) | True | docling-project/docling-models ✅ |
| **rapidocr** (OCR 模型) | True | 从 ModelScope 自动下载 ✨ |

## 可选模型（默认不下载）：

- with_smolvlm
- with_granitedocling
- with_granite_vision
- with_easyocr

## 结论

✅ **你只需要下载这三个仓库就够了！**

```bash
./scripts/download_core_models.sh
```

RapidOCR 模型会在首次运行 docling 时自动从 ModelScope 下载，不需要手动干预。