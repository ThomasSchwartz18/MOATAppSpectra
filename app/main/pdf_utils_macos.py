"""macOS-specific PDF rendering utilities."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used only for type checking
    from .pdf_utils import PdfGenerationError

_MAC_FALLBACK_DEPENDENCY_MESSAGE = (
    "Unable to generate PDF exports using the macOS Chromium fallback because the "
    "pyppeteer package or a compatible headless Chromium binary is unavailable. "
    "Install pyppeteer and ensure Chromium is downloaded (see the README for "
    "instructions)."
)


def _run_asyncio_task(coro: "asyncio.Future[bytes]") -> bytes:
    """Execute an asyncio coroutine from synchronous code."""

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    if loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()

    return loop.run_until_complete(coro)


async def _async_render_html_to_pdf(
    html: str, base_url: str | None = None
) -> bytes:
    """Render HTML to PDF using pyppeteer and headless Chromium."""

    from .pdf_utils import PdfGenerationError

    try:
        from pyppeteer import launch
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_MAC_FALLBACK_DEPENDENCY_MESSAGE) from exc

    browser = await launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    try:
        page = await browser.newPage()
        try:
            content = html
            if base_url:
                content = f'<base href="{base_url}">{html}'
            await page.setContent(content, waitUntil="networkidle0")
            pdf_bytes = await page.pdf(printBackground=True)
        finally:
            await page.close()
    except Exception as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_MAC_FALLBACK_DEPENDENCY_MESSAGE) from exc
    finally:
        await browser.close()

    return pdf_bytes


def render_html_to_pdf_with_macos_fallback(
    html: str, base_url: str | None = None
) -> bytes:
    """Render HTML to PDF on macOS using a Chromium-based fallback."""

    from .pdf_utils import PdfGenerationError

    try:
        return _run_asyncio_task(_async_render_html_to_pdf(html, base_url=base_url))
    except PdfGenerationError:
        raise
    except Exception as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_MAC_FALLBACK_DEPENDENCY_MESSAGE) from exc
