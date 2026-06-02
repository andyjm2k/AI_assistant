"""
Tests for the main index page and its extracted assets.
Verifies that the page references external CSS/JS and that asset files exist.
"""
import pytest
from pathlib import Path

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestIndexRefactorAssets:
    """Test that index.html and its extracted assets exist and are valid."""

    def test_index_refactor_html_exists(self):
        """Main HTML file must exist at project root."""
        path = PROJECT_ROOT / "index.html"
        assert path.exists(), "index.html should exist"

    def test_index_refactor_contains_css_link(self):
        """Main HTML must link to external catbot.css."""
        path = PROJECT_ROOT / "index.html"
        content = path.read_text(encoding="utf-8")
        assert '/css/catbot.css' in content, "HTML should reference /css/catbot.css"
        assert 'href="/css/catbot.css"' in content or 'href=\"/css/catbot.css\"' in content, (
            "HTML should contain link to catbot.css"
        )

    def test_index_refactor_contains_app_script(self):
        """Main HTML must load external app.js."""
        path = PROJECT_ROOT / "index.html"
        content = path.read_text(encoding="utf-8")
        assert '/js/app.js' in content, "HTML should reference /js/app.js"
        assert 'src="/js/app.js"' in content or 'src=\"/js/app.js\"' in content, (
            "HTML should contain script src for app.js"
        )

    def test_index_refactor_single_body_and_html_close(self):
        """Main HTML must have exactly one </body> and one </html> (no duplicate)."""
        path = PROJECT_ROOT / "index.html"
        content = path.read_text(encoding="utf-8")
        assert content.count("</body>") == 1, "HTML should have exactly one </body>"
        assert content.count("</html>") == 1, "HTML should have exactly one </html>"

    def test_identity_panel_contains_soul_prompt_preview(self):
        """Identity settings should expose the loaded soul prompt as a read-only preview."""
        path = PROJECT_ROOT / "index.html"
        content = path.read_text(encoding="utf-8")
        assert 'id="soul-prompt-display"' in content
        assert "config/soul.md" in content
        assert "Soul Prompt:" in content

    def test_index_contains_attachment_controls(self):
        """Main HTML should expose the attachment picker and preview container for chat uploads."""
        path = PROJECT_ROOT / "index.html"
        content = path.read_text(encoding="utf-8")
        assert 'id="attachment-input"' in content
        assert 'id="attachment-preview"' in content
        assert 'id="attachment-preview-list"' in content
        assert "/v1/files/attachments" not in content

    def test_css_file_exists_and_non_empty(self):
        """Extracted CSS file must exist and be non-empty."""
        path = PROJECT_ROOT / "css" / "catbot.css"
        assert path.exists(), "css/catbot.css should exist"
        content = path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "catbot.css should not be empty"

    def test_js_file_exists_and_non_empty(self):
        """Extracted app.js must exist and be non-empty."""
        path = PROJECT_ROOT / "js" / "app.js"
        assert path.exists(), "js/app.js should exist"
        content = path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "app.js should not be empty"

    def test_app_js_starts_with_expected_global_setup(self):
        """app.js should start with the same global setup as the original inline script."""
        path = PROJECT_ROOT / "js" / "app.js"
        content = path.read_text(encoding="utf-8")
        assert "window.PIXI" in content, "app.js should set window.PIXI"
        assert "PIXI" in content[:500], "app.js should reference PIXI near the start"

    def test_app_js_contains_attachment_upload_flow(self):
        """app.js should upload pending attachments to the proxy before chat completion requests."""
        path = PROJECT_ROOT / "js" / "app.js"
        content = path.read_text(encoding="utf-8")
        assert "async function uploadPendingAttachmentsForChat()" in content
        assert "buildAttachmentPromptText(promptText, attachments)" in content
        assert "/v1/files/attachments" in content
        assert "clearPendingAttachments()" in content
        assert "Do not call pdfToPowerPoint unless the user explicitly asks" in content
        assert "PDF or Markdown document" in content

    def test_app_js_contains_attachment_vision_flow(self):
        """app.js should forward image attachments as image_url parts for vision-capable models."""
        path = PROJECT_ROOT / "js" / "app.js"
        content = path.read_text(encoding="utf-8")
        assert "async function buildVisionImagePartsFromFiles(files = [])" in content
        assert "type: 'image_url'" in content
        assert "hasPendingImageAttachments" in content

    def test_app_js_filters_auto_memory_context_noise(self):
        """Browser auto-memory injection should exclude task-learning and operational memories."""
        path = PROJECT_ROOT / "js" / "app.js"
        content = path.read_text(encoding="utf-8")
        assert "function isConversationContextMemory(mem)" in content
        assert "task_experience" in content
        assert "task_learning" in content
        assert "task_execution" in content
        assert "operationalPattern" in content
        assert ".filter(isConversationContextMemory)" in content

    def test_app_js_can_resolve_scratch_relative_pdfs_for_pdf_to_powerpoint(self):
        """pdfToPowerPoint should resolve PDF and Markdown sources from multiple source types."""
        path = PROJECT_ROOT / "js" / "app.js"
        content = path.read_text(encoding="utf-8")
        assert '"source": {' in content
        assert "structured source descriptor" in content
        assert "function normalizePresentationSourceInput(sourceInput, explicitType = '')" in content
        assert "async function resolvePdfInputToDocumentSource(pdfUrl)" in content
        assert "async function resolveMarkdownInputToTextSource(sourceUrl)" in content
        assert "decodeBase64SourceToBlob" in content
        assert "relativePath" in content
        assert "contentBase64" in content
        assert "/v1/files/content?path=" in content
        assert "sourceUrl" in content
        assert ".pdf,.md,.markdown,application/pdf,text/markdown,text/plain" in content
