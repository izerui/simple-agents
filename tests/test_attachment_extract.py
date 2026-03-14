import base64
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from src.middleware.attachment_extract import AttachmentExtractMiddleware


class DummyBackend:
    def __init__(self):
        self.cwd = Path("/tmp")
        self.uploaded_files = None

    async def aupload_files(self, files):
        self.uploaded_files = files
        return []


@pytest.mark.asyncio
async def test_upload_files_supports_file_and_file_url(monkeypatch):
    middleware = AttachmentExtractMiddleware(backend_factory=DummyBackend())
    backend = middleware.backend_factory

    async def fake_download(_attachment):
        return "remote.pdf", b"remote-bytes"

    monkeypatch.setattr(middleware, "_download_attachment_from_url", fake_download)

    extracted_attachments = [
        {
            "type": "file",
            "filename": "local.txt",
            "data": base64.b64encode(b"local-bytes").decode("utf-8"),
        },
        {
            "type": "file_url",
            "filename": "remote.pdf",
            "url": "https://example.com/remote.pdf",
        },
    ]

    await middleware.upload_files(backend, extracted_attachments)

    assert backend.uploaded_files == [
        ("local.txt", b"local-bytes"),
        ("remote.pdf", b"remote-bytes"),
    ]


@pytest.mark.asyncio
async def test_upload_files_skips_failed_file_url(monkeypatch):
    middleware = AttachmentExtractMiddleware(backend_factory=DummyBackend())
    backend = middleware.backend_factory

    async def fake_download(_attachment):
        return None

    monkeypatch.setattr(middleware, "_download_attachment_from_url", fake_download)

    extracted_attachments = [
        {
            "type": "file_url",
            "filename": "remote.pdf",
            "url": "https://example.com/remote.pdf",
        }
    ]

    await middleware.upload_files(backend, extracted_attachments)

    assert backend.uploaded_files is None


@pytest.mark.asyncio
async def test_abefore_model_extracts_file_url_and_removes_block(monkeypatch):
    backend = DummyBackend()
    middleware = AttachmentExtractMiddleware(backend_factory=backend)

    async def fake_upload_files(_backend, extracted_attachments):
        assert extracted_attachments == [
            {
                "type": "file_url",
                "filename": "sample.pdf",
                "url": "https://example.com/sample.pdf",
                "mime_type": "application/pdf",
            }
        ]

    monkeypatch.setattr("src.middleware.attachment_extract.get_config", lambda: {})
    monkeypatch.setattr(middleware, "upload_files", fake_upload_files)
    monkeypatch.setattr(middleware, "_ensure_skills_in_sandbox", lambda _backend: None)

    message = HumanMessage(content=[
        {"type": "text", "text": "请分析附件"},
        {
            "type": "file_url",
            "url": "https://example.com/sample.pdf",
            "metadata": {"filename": "sample.pdf"},
            "mimeType": "application/pdf",
        },
    ])

    result = await middleware.abefore_model({"messages": [message]}, runtime=None)

    assert result is not None
    assert len(result["messages"]) == 1
    content = result["messages"][0].content
    assert content[0] == {"type": "text", "text": "请分析附件"}
    assert content[1]["type"] == "text"
    assert "sample.pdf" in content[1]["text"]
    assert all(block.get("type") != "file_url" for block in content if isinstance(block, dict))


def test_resolve_download_filename_prefers_metadata_filename():
    middleware = AttachmentExtractMiddleware(backend_factory=DummyBackend())

    filename = middleware._resolve_download_filename(
        {"filename": "../unsafe/report.pdf"},
        "/fallback.txt",
    )

    assert filename == "report.pdf"


def test_resolve_download_filename_falls_back_to_url_path():
    middleware = AttachmentExtractMiddleware(backend_factory=DummyBackend())

    filename = middleware._resolve_download_filename({}, "/files/report%20final.pdf")

    assert filename == "report final.pdf"
