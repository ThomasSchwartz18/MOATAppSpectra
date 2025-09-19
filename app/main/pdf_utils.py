"""Utilities for generating PDFs via WeasyPrint."""
from __future__ import annotations


class PdfGenerationError(RuntimeError):
    """Raised when WeasyPrint cannot generate a PDF due to missing libraries."""


_REQUIRED_NATIVE_DEPS_MESSAGE = (
    "Unable to generate PDF exports because WeasyPrint's native dependencies "
    "are missing. Install the Pango, GObject, and Cairo libraries to enable PDF "
    "generation."
)


def render_html_to_pdf(html: str, base_url: str | None = None) -> bytes:
    """Render HTML content to PDF bytes using WeasyPrint.

    Args:
        html: The HTML string to convert into a PDF document.
        base_url: The base URL used by WeasyPrint to resolve relative assets.

    Raises:
        PdfGenerationError: If WeasyPrint or its native dependencies are not
            available on the system.
    """

    try:
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_REQUIRED_NATIVE_DEPS_MESSAGE) from exc

    try:
        font_config = FontConfiguration()
        return HTML(string=html, base_url=base_url).write_pdf(
            font_config=font_config
        )
    except OSError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_REQUIRED_NATIVE_DEPS_MESSAGE) from exc
