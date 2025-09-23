"""Utilities for generating PDFs via WeasyPrint with optional fallbacks."""
from __future__ import annotations

import ctypes.util
import os
import platform
from pathlib import Path
from typing import Iterable


class PdfGenerationError(RuntimeError):
    """Raised when WeasyPrint cannot generate a PDF due to missing libraries."""


_REQUIRED_NATIVE_DEPS_MESSAGE = (
    "Unable to generate PDF exports because WeasyPrint's native dependencies "
    "are missing. Install the Pango, GObject, and Cairo libraries (see the "
    "README for platform-specific instructions) to enable PDF generation."
)

_FALLBACK_DEPENDENCY_MESSAGE = (
    "Unable to generate PDF exports using the wkhtmltopdf fallback because the "
    "binary is not installed or configured. Set the WKHTMLTOPDF_CMD environment "
    "variable or configure the application with the wkhtmltopdf command (see the "
    "README for instructions)."
)

_CHROMIUM_DEPENDENCY_MESSAGE = (
    "Unable to generate PDF exports using the Chromium fallback because the "
    "Playwright dependencies are not installed. Install the Playwright package "
    "and download the Chromium browser to enable this fallback."
)

_MAC_UNSUPPORTED_MESSAGE = (
    "Unable to generate PDF exports on macOS. PDF generation is supported only on "
    "Linux or Windows hosts."
)


_MAC_LIBRARY_ALIASES: dict[str, tuple[str, ...]] = {
    "libgobject-2.0-0": ("libgobject-2.0.dylib", "libgobject-2.0.0.dylib", "gobject-2.0"),
    "libpango-1.0-0": ("libpango-1.0.dylib", "pango-1.0"),
    "libpangocairo-1.0-0": ("libpangocairo-1.0.dylib", "pangocairo-1.0"),
    "libcairo-2": ("libcairo.2.dylib", "libcairo.dylib", "cairo"),
}

_MAC_LIBRARY_DIR_HINTS: tuple[Path, ...] = (
    Path("/opt/homebrew/lib"),
    Path("/usr/local/lib"),
    Path("/usr/local/opt/pango/lib"),
    Path("/usr/local/opt/cairo/lib"),
    Path("/usr/local/opt/glib/lib"),
)

_PATCHED_FIND_LIBRARY = False
_ORIGINAL_FIND_LIBRARY = ctypes.util.find_library


def _iter_env_library_paths() -> Iterable[Path]:
    """Yield additional library locations from the environment."""

    env_value = os.environ.get("WEASYPRINT_NATIVE_LIB_PATHS", "")
    if not env_value:
        return []

    paths: list[Path] = []
    for raw_path in env_value.split(os.pathsep):
        if not raw_path:
            continue
        candidate = Path(raw_path).expanduser()
        paths.append(candidate)
    return paths


def _mac_library_candidates(name: str) -> list[str]:
    """Return candidate library names for macOS to satisfy Windows aliases."""

    candidates: list[str] = [name]
    if name.startswith("lib"):
        trimmed = name[3:]
        if trimmed:
            candidates.append(trimmed)
    candidates.extend(_MAC_LIBRARY_ALIASES.get(name, ()))

    # Deduplicate while preserving order.
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _resolve_candidate_path(directory: Path, candidate: str) -> str | None:
    """Resolve a library candidate inside the provided directory."""

    if directory.is_file():
        if directory.name == candidate:
            return str(directory)
        # Allow specifying a file without the lib prefix or suffix.
        stem_match = directory.stem == candidate or directory.stem == candidate.lstrip("lib")
        if stem_match:
            return str(directory)
        return None

    if not directory.is_dir():
        return None

    direct_path = directory / candidate
    if direct_path.exists():
        return str(direct_path)

    # Try common dynamic library suffixes on macOS.
    for suffix in (".dylib", ".so", ".bundle"):
        with_suffix = direct_path.with_suffix(suffix)
        if with_suffix.exists():
            return str(with_suffix)
    return None


def _patched_find_library(name: str) -> str | None:
    """macOS-aware replacement for :func:`ctypes.util.find_library`."""

    if platform.system() != "Darwin":
        return _ORIGINAL_FIND_LIBRARY(name)

    candidates = _mac_library_candidates(name)
    for candidate in candidates:
        located = _ORIGINAL_FIND_LIBRARY(candidate)
        if located:
            return located

    search_paths: list[Path] = list(_iter_env_library_paths())
    search_paths.extend(path for path in _MAC_LIBRARY_DIR_HINTS if path.exists())

    for candidate in candidates:
        for directory in search_paths:
            resolved = _resolve_candidate_path(directory, candidate)
            if resolved:
                return resolved

    return _ORIGINAL_FIND_LIBRARY(name)


def _ensure_native_dependencies_configured() -> None:
    """Ensure platform-specific configuration is applied before imports."""

    global _PATCHED_FIND_LIBRARY
    if _PATCHED_FIND_LIBRARY:
        return

    if platform.system() == "Darwin":
        ctypes.util.find_library = _patched_find_library  # type: ignore[assignment]

    _PATCHED_FIND_LIBRARY = True


def _render_html_to_pdf_with_weasyprint(html: str, base_url: str | None = None) -> bytes:
    """Render HTML to PDF bytes using WeasyPrint."""

    try:
        _ensure_native_dependencies_configured()

        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
    except (ImportError, OSError) as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_REQUIRED_NATIVE_DEPS_MESSAGE) from exc

    try:
        font_config = FontConfiguration()
        return HTML(string=html, base_url=base_url).write_pdf(
            font_config=font_config
        )
    except OSError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_REQUIRED_NATIVE_DEPS_MESSAGE) from exc


def _render_html_to_pdf_with_chromium(
    html: str, base_url: str | None = None
) -> bytes:
    """Render HTML to PDF bytes using Playwright with Chromium."""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_CHROMIUM_DEPENDENCY_MESSAGE) from exc

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="networkidle", base_url=base_url)
                return page.pdf(
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={
                        "top": "0",
                        "right": "0",
                        "bottom": "0",
                        "left": "0",
                    },
                )
            finally:
                browser.close()
    except Exception as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_CHROMIUM_DEPENDENCY_MESSAGE) from exc


def _get_configured_wkhtmltopdf_command() -> str | None:
    """Return the configured wkhtmltopdf command, if available."""

    env_value = os.environ.get("WKHTMLTOPDF_CMD")
    if env_value:
        return env_value

    try:
        from flask import current_app

        try:
            return current_app.config.get("WKHTMLTOPDF_CMD")
        except RuntimeError:
            # Accessing current_app outside of an application context.
            return None
    except Exception:
        return None


def _render_html_to_pdf_with_wkhtmltopdf(
    html: str, base_url: str | None = None
) -> bytes:
    """Render HTML to PDF bytes using pdfkit/wkhtmltopdf."""

    try:
        import pdfkit
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_FALLBACK_DEPENDENCY_MESSAGE) from exc

    wkhtmltopdf_cmd = _get_configured_wkhtmltopdf_command()
    try:
        configuration = (
            pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_cmd)
            if wkhtmltopdf_cmd
            else pdfkit.configuration()
        )
    except (OSError, IOError) as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_FALLBACK_DEPENDENCY_MESSAGE) from exc

    options: dict[str, str | None] = {
        "encoding": "UTF-8",
        "quiet": "",
    }
    if base_url:
        options["--base-url"] = base_url
        options["enable-local-file-access"] = ""

    try:
        return pdfkit.from_string(
            html,
            False,
            options=options,
            configuration=configuration,
        )
    except Exception as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_FALLBACK_DEPENDENCY_MESSAGE) from exc


def render_html_to_pdf(html: str, base_url: str | None = None) -> bytes:
    """Render HTML content to PDF bytes using WeasyPrint."""

    if platform.system() == "Darwin":
        raise PdfGenerationError(_MAC_UNSUPPORTED_MESSAGE)

    weasyprint_error: PdfGenerationError | None = None
    try:
        return _render_html_to_pdf_with_weasyprint(html, base_url=base_url)
    except PdfGenerationError as exc:
        weasyprint_error = exc

    chromium_error: PdfGenerationError | None = None
    try:
        return _render_html_to_pdf_with_chromium(html, base_url=base_url)
    except PdfGenerationError as exc:
        chromium_error = exc

    wkhtmltopdf_error: PdfGenerationError | None = None
    try:
        return _render_html_to_pdf_with_wkhtmltopdf(html, base_url=base_url)
    except PdfGenerationError as exc:
        wkhtmltopdf_error = exc

    messages: list[str] = []
    if weasyprint_error is not None:
        messages.append(str(weasyprint_error))
    if chromium_error is not None:
        messages.append(str(chromium_error))
    if wkhtmltopdf_error is not None:
        messages.append(str(wkhtmltopdf_error))

    errors_to_chain = wkhtmltopdf_error or weasyprint_error
    raise PdfGenerationError(" ".join(messages)) from errors_to_chain
